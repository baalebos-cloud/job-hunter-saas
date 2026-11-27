"""Authentication, sessions, IP trust, cron, URL validation and RBAC."""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
import jwt
from passlib.hash import bcrypt as legacy_bcrypt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.client_ip import mask_ip, resolve_client_ip
from backend.app.core.config import settings
from backend.app.core.rate_limit import LoginGuard
from backend.app.database import Base, get_db
from backend.app.main import app, reset_rate_limits
from backend.app.models.security import RefreshToken
from backend.app.models.user import User
from backend.app.services.auth_service import (create_access_token, hash_password, hash_token,
                                               verify_and_update_password, verify_password)
from backend.app.utils.url_safety import UnsafeUrl, validate_public_https_url

PASSWORD = 'correct horse battery staple'


@pytest.fixture
def db():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all([
        User(email='admin@example.com', full_name='Admin', hashed_password=hash_password(PASSWORD), is_verified=True, role='super_admin'),
        User(email='auditor@example.com', full_name='Auditor', hashed_password=hash_password(PASSWORD), is_verified=True, role='security_auditor'),
        User(email='viewer@example.com', full_name='Viewer', hashed_password=hash_password(PASSWORD), is_verified=True, role='viewer'),
        User(email='user@example.com', full_name='User', hashed_password=hash_password(PASSWORD), is_verified=True),
        User(email='unverified@example.com', full_name='U', hashed_password=hash_password(PASSWORD), is_verified=False, role='super_admin'),
    ])
    session.commit()
    app.dependency_overrides[get_db] = lambda: session
    reset_rate_limits()
    yield session
    app.dependency_overrides.clear(); session.close(); engine.dispose()


@pytest.fixture
def client(db):
    return TestClient(app, base_url='https://testserver')


def bearer(email, **claims):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': email, **claims})}


def login(client, email='user@example.com', password=PASSWORD):
    return client.post('/api/v1/auth/login', json={'email': email, 'password': password})


# ── Passwords ────────────────────────────────────────────────────────────────

def test_multibyte_passwords_longer_than_72_bytes_are_fully_significant():
    base = 'é' * 50  # 100 bytes in UTF-8: plain bcrypt would ignore everything after this
    hashed = hash_password(base + 'tail-one')
    assert hashed.startswith('$bcrypt-sha256$')
    assert verify_password(base + 'tail-one', hashed)
    assert not verify_password(base + 'tail-two', hashed)
    assert hash_password('\U0001F512' * 300)  # 1200 bytes, no crash


def test_legacy_bcrypt_hash_verifies_and_is_upgraded_on_login(client, db):
    user = db.query(User).filter_by(email='user@example.com').one()
    user.hashed_password = legacy_bcrypt.hash(PASSWORD)
    db.commit()
    ok, new_hash = verify_and_update_password(PASSWORD, user.hashed_password)
    assert ok and new_hash.startswith('$bcrypt-sha256$')
    assert login(client).status_code == 200
    db.refresh(user)
    assert user.hashed_password.startswith('$bcrypt-sha256$')


# ── Access tokens ────────────────────────────────────────────────────────────

def test_access_tokens_are_short_lived_and_typed(client):
    token = login(client).json()['access_token']
    claims = jwt.decode(token, options={'verify_signature': False})
    assert claims['type'] == 'access' and claims['jti'] and claims['tv'] == 0
    assert claims['exp'] - claims['iat'] == 15 * 60
    legacy = jwt.encode({'sub': 'user@example.com', 'exp': datetime.utcnow() + timedelta(days=30)},
                        settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    assert client.get('/api/v1/auth/me', headers={'Authorization': f'Bearer {legacy}'}).status_code == 401


def test_token_version_mismatch_and_logout_revocation(client, db):
    token = login(client).json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}
    assert client.get('/api/v1/auth/me', headers=headers).status_code == 200
    assert client.post('/api/v1/auth/logout', headers=headers).status_code == 200
    assert client.get('/api/v1/auth/me', headers=headers).status_code == 401  # jti revoked
    assert client.get('/api/v1/auth/me', headers=bearer('user@example.com', tv=7)).status_code == 401


def test_password_reset_uses_json_body_hashed_tokens_and_revokes_sessions(client, db, monkeypatch):
    sent = {}
    monkeypatch.setattr('backend.app.utils.email.send_password_reset_email', lambda **kw: sent.update(kw) or True)
    old_token = login(client).json()['access_token']
    assert client.post('/api/v1/auth/forgot-password?email=user@example.com').status_code == 422
    assert client.post('/api/v1/auth/forgot-password', json={'email': 'user@example.com'}).status_code == 200
    user = db.query(User).filter_by(email='user@example.com').one()
    assert user.reset_token == hash_token(sent['token']) and sent['token'] != user.reset_token
    assert client.post(f"/api/v1/auth/reset-password?token={sent['token']}&new_password=NewPassword1").status_code == 422
    res = client.post('/api/v1/auth/reset-password', json={'token': sent['token'], 'new_password': 'NewPassword1!'})
    assert res.status_code == 200
    assert client.get('/api/v1/auth/me', headers={'Authorization': f'Bearer {old_token}'}).status_code == 401
    assert db.query(RefreshToken).filter(RefreshToken.revoked_at.is_(None)).count() == 0
    assert login(client, password='NewPassword1!').status_code == 200


# ── Refresh-token rotation ───────────────────────────────────────────────────

def test_refresh_cookie_attributes_rotation_and_reuse_detection(client, db):
    res = login(client)
    cookie = res.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'Secure' in cookie and 'SameSite=strict' in cookie
    assert 'Path=/api/v1/auth' in cookie
    first = client.cookies.get(settings.REFRESH_COOKIE_NAME)
    rotated = client.post('/api/v1/auth/refresh')
    assert rotated.status_code == 200 and rotated.json()['access_token']
    second = client.cookies.get(settings.REFRESH_COOKIE_NAME)
    assert second and second != first
    new_access = rotated.json()['access_token']
    # Replaying the first (already rotated) token = theft signal.
    client.cookies.set(settings.REFRESH_COOKIE_NAME, first, domain='testserver.local', path='/api/v1/auth')
    replay = TestClient(app, base_url='https://testserver', cookies={settings.REFRESH_COOKIE_NAME: first})
    assert replay.post('/api/v1/auth/refresh').status_code == 401
    assert db.query(RefreshToken).filter(RefreshToken.revoked_at.is_(None)).count() == 0
    assert client.get('/api/v1/auth/me', headers={'Authorization': f'Bearer {new_access}'}).status_code == 401


def test_refresh_without_cookie_is_401(client):
    assert client.post('/api/v1/auth/refresh').status_code == 401


# ── Client IP / brute force ──────────────────────────────────────────────────

@pytest.mark.parametrize('peer,xff,expected', [
    ('203.0.113.7', '1.2.3.4', '203.0.113.7'),                 # untrusted peer: header ignored
    ('10.0.1.5', '198.51.100.20', '198.51.100.20'),            # ALB in VPC: header honoured
    ('10.0.1.5', '1.2.3.4, 198.51.100.20', '198.51.100.20'),   # client-prepended spoof ignored
    ('10.0.1.5', '198.51.100.20, 10.0.2.9', '198.51.100.20'),  # skip trusted hops
    ('10.0.1.5', 'garbage', '10.0.1.5'),
])
def test_x_forwarded_for_is_only_trusted_from_proxies(peer, xff, expected):
    assert resolve_client_ip(peer, xff, '10.0.0.0/8') == expected


def test_spoofed_x_forwarded_for_does_not_bypass_rate_limit(client):
    codes = [client.post('/api/v1/auth/login', json={'email': 'nobody@example.com', 'password': 'x'},
                         headers={'X-Forwarded-For': f'198.51.100.{i}'}).status_code for i in range(12)]
    assert 429 in codes


def test_per_account_lockout_survives_ip_rotation():
    guard = LoginGuard('test-rotation')
    for i in range(5):
        guard.failure(f'198.51.100.{i}', 'Victim@Example.com ')
    with pytest.raises(Exception) as exc:
        guard.check('203.0.113.99', 'victim@example.com')
    assert getattr(exc.value, 'status_code', None) == 429


def test_ip_masking():
    assert mask_ip('198.51.100.77') == '198.51.100.0/24'
    assert mask_ip('2001:db8:abcd:12::1') == '2001:db8:abcd::/48'


# ── Cron secret ──────────────────────────────────────────────────────────────

def test_cron_requires_header_secret_compared_in_constant_time(client, monkeypatch):
    monkeypatch.setattr(settings, 'CRON_SECRET', 'cron-test-secret')
    monkeypatch.setattr('backend.app.utils.global_scraper.scrape_global_jobs', lambda: {'ok': True})
    assert client.post('/api/v1/cron/scrape').status_code == 403
    assert client.post('/api/v1/cron/scrape?secret=cron-test-secret').status_code == 403
    assert client.post('/api/v1/cron/scrape', headers={'X-Cron-Secret': 'wrong'}).status_code == 403
    assert client.post('/api/v1/cron/scrape', headers={'X-Cron-Secret': 'cron-test-secret'}).json() == {'ok': True}


# ── URL validation / opaque errors ───────────────────────────────────────────

@pytest.mark.parametrize('url', ['http://example.com/cv.pdf', 'https://127.0.0.1/cv.pdf', 'https://localhost/x',
                                 'https://user:pw@example.com/x', 'https://169.254.169.254/latest/meta-data',
                                 'https://10.0.0.5/x', 'https://svc.railway.internal/x', 'javascript:alert(1)',
                                 'https://example.com:8443/x', 'ftp://example.com/x'])
def test_unsafe_urls_rejected(url):
    with pytest.raises(UnsafeUrl):
        validate_public_https_url(url, resolve=False)


def test_resume_link_requires_public_https(client, monkeypatch):
    import socket
    monkeypatch.setattr(socket, 'getaddrinfo', lambda host, *a, **k: [(2, 1, 6, '', ('93.184.216.34', 443))])
    headers = bearer('user@example.com')
    bad = client.post('/api/v1/profile/resume-link?resume_url=http://example.com/cv.pdf&filename=cv.pdf', headers=headers)
    assert bad.status_code == 422
    good = client.post('/api/v1/profile/resume-link?resume_url=https://example.com/cv.pdf&filename=cv.pdf', headers=headers)
    assert good.status_code == 200
    monkeypatch.setattr(socket, 'getaddrinfo', lambda host, *a, **k: [(2, 1, 6, '', ('10.1.2.3', 443))])
    rebinding = client.post('/api/v1/profile/resume-link?resume_url=https://evil.example/cv.pdf&filename=cv.pdf', headers=headers)
    assert rebinding.status_code == 422


def test_errors_are_opaque_with_trace_id(client, monkeypatch):
    # Any unexpected failure answers with a trace ID only: no exception text, secrets or candidate data.
    from fastapi.testclient import TestClient
    from backend.app.main import app as main_app
    from backend.app.services import processing_gate

    def boom(*a, **k):
        raise RuntimeError('db password=hunter2 candidate@example.com')
    monkeypatch.setattr(processing_gate, 'has_priority', boom)
    res = TestClient(main_app, raise_server_exceptions=False).get('/api/v1/resume/history', headers=bearer('user@example.com'))
    assert res.status_code == 500 and res.json()['trace_id'] and res.headers['X-Trace-Id'] == res.json()['trace_id']
    assert 'hunter2' not in res.text and 'candidate@example.com' not in res.text


def test_mock_ai_analyze_endpoint_is_gone(client):
    # It returned a fixed score and invented skills when no AI key was set.
    assert client.post('/api/v1/ai/analyze', json={'resume_text': 'x', 'job_description': 'y'},
                       headers=bearer('user@example.com')).status_code in (404, 405)


# ── RBAC ─────────────────────────────────────────────────────────────────────

def user_id(db, email):
    return db.query(User).filter_by(email=email).one().id


def test_rbac_permission_boundaries(client, db):
    assert client.get('/api/v1/rbac/matrix', headers=bearer('auditor@example.com')).status_code == 200
    assert client.get('/api/v1/rbac/matrix', headers=bearer('viewer@example.com')).status_code == 403
    assert client.get('/api/v1/rbac/matrix', headers=bearer('user@example.com')).status_code == 403
    assert client.get('/api/v1/admin/stats', headers=bearer('auditor@example.com')).status_code == 403
    assert client.get('/api/v1/admin/stats', headers=bearer('admin@example.com')).status_code == 200
    # Unverified accounts get no permissions even with a role.
    assert client.get('/api/v1/admin/stats', headers=bearer('unverified@example.com')).status_code == 403
    target = user_id(db, 'user@example.com')
    assert client.put(f'/api/v1/rbac/users/{target}/role', json={'role': 'viewer'}, headers=bearer('auditor@example.com')).status_code == 403


def test_role_assignment_takes_effect_on_acceptance_and_revokes_tokens(client, db, monkeypatch):
    links = []
    monkeypatch.setattr('backend.app.services.staff_invitations.send', lambda *a: links.append(a[-1]) or True)
    target = user_id(db, 'user@example.com')
    old = bearer('user@example.com')
    res = client.put(f'/api/v1/rbac/users/{target}/role', json={'role': 'compliance_officer'}, headers=bearer('admin@example.com'))
    assert res.status_code == 200 and res.json()['status'] == 'invited' and res.json()['role'] is None
    assert client.get('/api/v1/auth/me', headers=old).json()['role'] is None          # nothing granted yet
    assert client.post('/api/v1/staff-invites/accept', json={'token': links[0], 'confidentiality': True},
                       headers=old).status_code == 200
    assert client.get('/api/v1/auth/me', headers=old).status_code == 401  # token_version bumped
    me = client.get('/api/v1/auth/me', headers=bearer('user@example.com', tv=1)).json()
    assert me['role'] == 'compliance_officer' and 'privacy:manage' in me['permissions']
    assert client.put(f'/api/v1/rbac/users/{target}/role', json={'role': 'root'}, headers=bearer('admin@example.com')).status_code == 422


def test_last_super_admin_and_locked_permissions_are_protected(client, db):
    admin = user_id(db, 'admin@example.com')
    res = client.put(f'/api/v1/rbac/users/{admin}/role', json={'role': None}, headers=bearer('admin@example.com'))
    assert res.status_code == 409
    res = client.put('/api/v1/rbac/roles/super_admin/permissions', json={'permissions': ['metrics:read']}, headers=bearer('admin@example.com'))
    assert res.status_code == 409
    res = client.put('/api/v1/rbac/roles/viewer/permissions', json={'permissions': ['metrics:read', 'audit:read']}, headers=bearer('admin@example.com'))
    assert res.status_code == 200
    assert client.get('/api/v1/auth/me', headers=bearer('viewer@example.com')).json()['permissions'] == ['audit:read', 'metrics:read']


@pytest.fixture
def events_here(db, monkeypatch):
    """Security events are written through their own session: point it at the test database."""
    monkeypatch.setattr('backend.app.services.security_events._session', sessionmaker(bind=db.get_bind()))


def test_reset_finds_the_account_in_any_letter_case_and_records_delivery(client, db, monkeypatch, events_here):
    from backend.app.models.security_event import SecurityEvent
    sent = []
    monkeypatch.setattr('backend.app.utils.email.send_password_reset_email', lambda **kw: sent.append(kw) or True)
    assert client.post('/api/v1/auth/forgot-password', json={'email': '  USER@Example.com '}).status_code == 200
    assert len(sent) == 1 and sent[0]['to_email'] == 'user@example.com'
    events = [e.event for e in db.query(SecurityEvent).order_by(SecurityEvent.id)]
    assert events[-2:] == ['password.reset_requested', 'password.reset_email_sent']


def test_failed_reset_delivery_is_recorded_for_the_owner(client, db, monkeypatch, events_here):
    from backend.app.models.security_event import SecurityEvent
    monkeypatch.setattr('backend.app.utils.email.send_password_reset_email', lambda **kw: False)
    client.post('/api/v1/auth/forgot-password', json={'email': 'user@example.com'})
    assert db.query(SecurityEvent).order_by(SecurityEvent.id.desc()).first().event == 'password.reset_email_failed'


def test_reset_requests_are_rate_limited_without_revealing_accounts(client, monkeypatch):
    sent = []
    monkeypatch.setattr('backend.app.utils.email.send_password_reset_email', lambda **kw: sent.append(kw) or True)
    answers = {client.post('/api/v1/auth/forgot-password', json={'email': 'user@example.com'}).json()['message']
               for _ in range(4)}
    unknown = client.post('/api/v1/auth/forgot-password', json={'email': 'nobody@example.com'}).json()['message']
    assert len(sent) == 3 and answers == {unknown}


def test_reset_quota_is_shared_by_gmail_aliases_of_one_inbox(client, db, monkeypatch):
    db.add(User(email='jane.doe@gmail.com', email_canonical='janedoe@gmail.com', full_name='Jane', hashed_password=hash_password(PASSWORD), is_verified=True))
    db.commit()
    sent = []
    monkeypatch.setattr('backend.app.utils.email.send_password_reset_email', lambda **kw: sent.append(kw) or True)
    for alias in ('jane.doe@gmail.com', 'janedoe@gmail.com', 'Jane.Doe+a@gmail.com', 'j.a.n.e.doe+b@googlemail.com',
                  'janedoe+c@gmail.com'):
        assert client.post('/api/v1/auth/forgot-password', json={'email': alias}).status_code == 200
    assert len(sent) == 3
