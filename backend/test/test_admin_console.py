"""Owner console: duplicate accounts, account controls, blocked IPs, 2FA, alerts, exports."""
import secrets
import time
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core import geoip
from backend.app.database import Base, get_db, get_read_db
from backend.app.main import app
from backend.app.models.registry import import_all_models
from backend.app.models.security import BlockedIP
from backend.app.models.security_event import SecurityEvent
from backend.app.models.user import User
from backend.app.services import account_integrity, mfa, security_controls, security_events
from backend.app.services.auth_service import create_access_token, hash_password

OWNER = 'owner@baalebos.example'
PASSWORD = secrets.token_urlsafe(16)        # generated per run: no credential literals in the repo
NEW_PASSWORD = secrets.token_urlsafe(16)


@pytest.fixture
def env(monkeypatch):
    import_all_models()
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add(User(email=OWNER, full_name='Owner', hashed_password=hash_password(PASSWORD), is_admin=True,
                role='super_admin', is_verified=True, email_canonical=OWNER))
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_read_db] = lambda: db
    monkeypatch.setattr(security_events, '_session', Session)
    monkeypatch.setattr('backend.app.database.SessionLocal', Session)   # audit writes stay in this test's DB
    store = {}

    def kv(method, *args, default=None, **kwargs):
        if method == 'window_count':
            return (0, time.time())
        if method == 'window_add':
            store[args[0]] = store.get(args[0], 0) + 1
            return store[args[0]]
        if method == 'setex':
            store[args[0]] = args[2] if len(args) > 2 else '1'
            return True
        if method == 'exists':
            return args[0] in store
        if method == 'delete':
            for key in args:
                store.pop(key, None)
            return 0
        return default
    monkeypatch.setattr('backend.app.core.kv_store.safe_call', kv)
    monkeypatch.setattr('backend.app.core.rate_limit.safe_call', kv)
    # TestClient's peer is not an IP: read the simulated client address from X-Forwarded-For.
    monkeypatch.setattr('backend.app.core.client_ip.resolve_client_ip', lambda peer, xff, spec=None: xff or '198.51.100.250')
    sent = []
    monkeypatch.setattr(security_controls, '_send_async', lambda to, subject, html: sent.append((tuple(to), subject)))
    monkeypatch.setattr('backend.app.routes.auth.send_verification_email', lambda **k: True)
    monkeypatch.setattr('backend.app.routes.hr_auth._send_hr_verification_email', lambda **k: True)
    monkeypatch.setattr('backend.app.routes.hr_auth._send_admin_hr_notification', lambda **k: True)
    monkeypatch.setenv('ADMIN_2FA_REQUIRED', 'false')
    yield type('Env', (), {'db': db, 'sent': sent, 'client': TestClient(app), 'store': store})
    from backend.app.services import audit
    audit.flush()                     # drain queued request records before the next test's database
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def owner(env):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': OWNER})}


def user(env, email, **fields):
    u = User(email=email, full_name=fields.pop('full_name', 'Test User'), hashed_password=hash_password(PASSWORD),
             is_verified=True, email_canonical=account_integrity.canonical_email(email), **fields)
    env.db.add(u)
    env.db.commit()
    return u


def login(env, email, ip='203.0.113.10', password=PASSWORD):
    return env.client.post('/api/v1/auth/login', json={'email': email, 'password': password},
                           headers={'X-Forwarded-For': ip})


def events(env, name):
    env.db.expire_all()
    return env.db.query(SecurityEvent).filter(SecurityEvent.event == name).all()


# ── Duplicate accounts ───────────────────────────────────────────────────────

def test_canonical_email_folds_case_tags_and_gmail_dots():
    c = account_integrity.canonical_email
    assert c(' J.Doe+jobs@GoogleMail.com ') == c('jdoe@gmail.com') == 'jdoe@gmail.com'
    assert c('ann+x@company.com') == 'ann@company.com'
    assert c('a.b@company.com') == 'a.b@company.com'        # dots only matter outside Gmail


def test_signup_rejects_duplicate_and_disposable_addresses(env):
    user(env, 'jdoe@gmail.com')
    body = {'email': 'J.Doe+second@gmail.com', 'password': PASSWORD, 'full_name': 'Jane'}
    r = env.client.post('/api/v1/auth/signup', json=body)
    assert r.status_code == 409 and 'already exists' in r.json()['detail']
    r = env.client.post('/api/v1/auth/signup', json={**body, 'email': 'someone@mailinator.com'})
    assert r.status_code == 400 and 'disposable' in r.json()['detail'].lower()
    reasons = sorted(e.details['reason'] for e in events(env, 'signup.rejected'))
    assert reasons == ['disposable_email', 'duplicate_account']
    r = env.client.post('/api/v1/auth/signup', json={**body, 'email': 'new.person@example.org'},
                        headers={'X-Forwarded-For': '192.0.2.44'})
    assert r.status_code == 201
    created = env.db.query(User).filter_by(email='new.person@example.org').one()
    assert created.email_canonical == 'new.person@example.org' and created.signup_ip == '192.0.2.44'


def test_signups_per_ip_are_capped(env):
    for i in range(account_integrity.SIGNUPS_PER_IP_PER_DAY):
        assert env.client.post('/api/v1/auth/signup', json={'email': f'p{i}@example.org', 'password': PASSWORD,
                                                            'full_name': 'P'},
                               headers={'X-Forwarded-For': '192.0.2.9'}).status_code == 201
    r = env.client.post('/api/v1/auth/signup', json={'email': 'p9@example.org', 'password': PASSWORD, 'full_name': 'P'},
                        headers={'X-Forwarded-For': '192.0.2.9'})
    assert r.status_code == 429


def test_employer_signup_rejects_duplicate(env):
    user(env, 'talent@acme.example', is_hr=True)
    r = env.client.post('/api/v1/hr-auth/signup', json={'full_name': 'T', 'email': 'Talent+2@acme.example',
                                                        'password': PASSWORD, 'company_name': 'Acme'})
    assert r.status_code == 409


def test_duplicate_groups_can_be_rejected_or_dismissed(env):
    first = user(env, 'ann@example.org', phone='+234 801 234 5678')
    second = User(email='Ann+alt@example.org', hashed_password='x', is_verified=True, email_canonical='ann@example.org')
    third = user(env, 'other@example.org', phone='08012345678')
    env.db.add(second)
    env.db.commit()
    groups = env.client.get('/api/v1/admin/duplicates', headers=owner(env)).json()
    by_reason = {g['reason']: g for g in groups}
    assert [a['id'] for a in by_reason['same_email']['accounts']] == [first.id, second.id]
    assert by_reason['same_email']['accounts'][0]['original'] is True
    assert {a['id'] for a in by_reason['same_phone']['accounts']} == {first.id, third.id}

    r = env.client.post('/api/v1/admin/duplicates/reject', json={'user_ids': [second.id], 'action': 'suspend'},
                        headers=owner(env))
    assert r.status_code == 200
    env.db.refresh(second)
    assert second.suspended_reason == 'Duplicate account'
    assert env.client.post('/api/v1/admin/duplicates/dismiss', json={'key': by_reason['same_phone']['key']},
                           headers=owner(env)).status_code == 200
    remaining = env.client.get('/api/v1/admin/duplicates', headers=owner(env)).json()
    assert [g['reason'] for g in remaining] == ['same_email'] and remaining[0]['active_duplicates'] == 0
    r = env.client.post('/api/v1/admin/duplicates/reject', json={'user_ids': [env.db.query(User).filter_by(email=OWNER).one().id]},
                        headers=owner(env))
    assert r.status_code == 400


# ── Account controls ─────────────────────────────────────────────────────────

def test_blocked_ip_cannot_sign_in_or_sign_up(env):
    user(env, 'cand@example.org')
    r = env.client.post('/api/v1/admin/security/blocked-ips', json={'ip': '203.0.113.66', 'reason': 'spray'},
                        headers=owner(env))
    assert r.status_code == 200
    assert login(env, 'cand@example.org', ip='203.0.113.66').status_code == 403
    assert env.client.post('/api/v1/auth/signup', json={'email': 'x@example.org', 'password': PASSWORD, 'full_name': 'X'},
                           headers={'X-Forwarded-For': '203.0.113.66'}).status_code == 403
    assert login(env, 'cand@example.org', ip='203.0.113.67').status_code == 200
    assert [e.details['reason'] for e in events(env, 'login.blocked')] == ['ip_blocked', 'ip_blocked']
    # an admin cannot block the address they are using
    r = env.client.post('/api/v1/admin/security/blocked-ips', json={'ip': '198.51.100.9'},
                        headers={**owner(env), 'X-Forwarded-For': '198.51.100.9'})
    assert r.status_code == 400
    assert env.client.delete('/api/v1/admin/security/blocked-ips/203.0.113.66', headers=owner(env)).status_code == 200
    assert login(env, 'cand@example.org', ip='203.0.113.66').status_code == 200
    # expired blocks do not apply
    env.db.add(BlockedIP(ip='203.0.113.70', expires_at=datetime.utcnow() - timedelta(minutes=1)))
    env.db.commit()
    assert login(env, 'cand@example.org', ip='203.0.113.70').status_code == 200


def test_suspend_signs_out_and_blocks_until_restored(env):
    target = user(env, 'cand@example.org')
    token = login(env, 'cand@example.org').json()['access_token']
    me = {'Authorization': f'Bearer {token}'}
    assert env.client.get('/api/v1/auth/me', headers=me).status_code == 200
    assert env.client.post(f'/api/v1/admin/users/{target.id}/suspend', json={'reason': 'abuse'},
                           headers=owner(env)).status_code == 200
    assert env.client.get('/api/v1/auth/me', headers=me).status_code == 401      # token revoked
    r = login(env, 'cand@example.org')
    assert r.status_code == 403 and 'suspended' in r.json()['detail']
    assert env.client.post(f'/api/v1/admin/users/{target.id}/unsuspend', headers=owner(env)).status_code == 200
    assert login(env, 'cand@example.org').status_code == 200


def test_sign_out_everywhere_and_forced_password_reset(env, monkeypatch):
    target = user(env, 'cand@example.org')
    me = {'Authorization': 'Bearer ' + login(env, 'cand@example.org').json()['access_token']}
    assert env.client.post(f'/api/v1/admin/users/{target.id}/sign-out', headers=owner(env)).status_code == 200
    assert env.client.get('/api/v1/auth/me', headers=me).status_code == 401
    links = []
    monkeypatch.setattr('backend.app.utils.email.send_password_reset_email',
                        lambda **k: links.append(k['token']) or True)
    assert env.client.post(f'/api/v1/admin/users/{target.id}/force-password-reset', headers=owner(env)).status_code == 200
    r = login(env, 'cand@example.org')
    assert r.status_code == 403 and 'new password' in r.json()['detail']
    assert env.client.post('/api/v1/auth/reset-password', json={'token': links[0], 'new_password': NEW_PASSWORD}
                           ).status_code == 200
    assert login(env, 'cand@example.org', password=NEW_PASSWORD).status_code == 200
    me_id = env.db.query(User).filter_by(email=OWNER).one().id
    assert env.client.post(f'/api/v1/admin/users/{me_id}/suspend', json={}, headers=owner(env)).status_code == 400


# ── Two-step verification ────────────────────────────────────────────────────

def _code(secret, offset=0):
    return mfa.totp(secret, int(time.time() // mfa.STEP) + offset)


def test_two_step_verification_enrolment_and_sign_in(env):
    user(env, 'cand@example.org')
    me = {'Authorization': 'Bearer ' + login(env, 'cand@example.org').json()['access_token']}
    secret = env.client.post('/api/v1/auth/2fa/setup', headers=me).json()['secret']
    stored = env.db.query(User).filter_by(email='cand@example.org').one()
    assert stored.totp_secret != secret and mfa.decrypt_secret(stored.totp_secret) == secret   # encrypted at rest
    assert env.client.post('/api/v1/auth/2fa/enable', json={'code': '000000'}, headers=me).status_code == 400
    enabled = env.client.post('/api/v1/auth/2fa/enable', json={'code': _code(secret)}, headers=me).json()
    assert len(enabled['recovery_codes']) == 10 and enabled['access_token']
    assert env.client.get('/api/v1/auth/me', headers=me).status_code == 401      # other sessions signed out

    first = login(env, 'cand@example.org').json()
    assert first['mfa_required'] is True and 'access_token' not in first
    r = env.client.post('/api/v1/auth/login/mfa', json={'mfa_token': first['mfa_token'], 'code': '123456'})
    assert r.status_code == 401
    r = env.client.post('/api/v1/auth/login/mfa', json={'mfa_token': first['mfa_token'], 'code': _code(secret, 1)})
    assert r.status_code == 200 and r.json()['access_token']
    # the same sign-in step and the same code cannot be reused
    assert env.client.post('/api/v1/auth/login/mfa', json={'mfa_token': first['mfa_token'],
                                                           'code': _code(secret, 1)}).status_code == 401
    # a recovery code works once
    second = login(env, 'cand@example.org').json()
    r = env.client.post('/api/v1/auth/login/mfa', json={'mfa_token': second['mfa_token'],
                                                        'code': enabled['recovery_codes'][0]})
    assert r.status_code == 200 and r.json()['recovery_codes_left'] == 9
    third = login(env, 'cand@example.org').json()
    assert env.client.post('/api/v1/auth/login/mfa', json={'mfa_token': third['mfa_token'],
                                                           'code': enabled['recovery_codes'][0]}).status_code == 401
    assert [e.details['reason'] for e in events(env, 'login.failed')] == ['wrong_2fa_code', 'wrong_2fa_code']
    assert len(events(env, 'login.success')) == 3   # 1 before 2FA + 2 completed second steps


def test_console_requires_two_step_verification_when_enforced(env, monkeypatch):
    monkeypatch.setenv('ADMIN_2FA_REQUIRED', 'true')
    r = env.client.get('/api/v1/admin/overview', headers=owner(env))
    assert r.status_code == 403 and r.json()['detail']['code'] == 'mfa_enrollment_required'
    secret = env.client.post('/api/v1/auth/2fa/setup', headers=owner(env)).json()['secret']
    session = env.client.post('/api/v1/auth/2fa/enable', json={'code': _code(secret)}, headers=owner(env)).json()
    assert env.client.get('/api/v1/admin/overview',
                          headers={'Authorization': 'Bearer ' + session['access_token']}).status_code == 200
    status = env.client.get('/api/v1/auth/2fa', headers={'Authorization': 'Bearer ' + session['access_token']}).json()
    assert status['enabled'] and status['required'] and status['recovery_codes_left'] == 10


# ── Alerts ───────────────────────────────────────────────────────────────────

def test_new_country_sign_in_notifies_the_user_and_owner(env, monkeypatch):
    user(env, 'cand@example.org')
    places = {'102.89.1.1': ('NG', 'Nigeria', 'Lagos'), '81.2.69.1': ('GB', 'United Kingdom', 'London')}
    monkeypatch.setattr(geoip, 'locate', lambda ip: dict(zip(('country_code', 'country', 'city'), places.get(ip, (None,) * 3)),
                                                         region=None))
    assert login(env, 'cand@example.org', ip='102.89.1.1').status_code == 200
    assert env.sent == []                                   # first sign-in: nothing to compare with
    assert login(env, 'cand@example.org', ip='102.89.1.1').status_code == 200
    assert login(env, 'cand@example.org', ip='81.2.69.1').status_code == 200
    assert [s for _, s in env.sent] == ['New sign-in to your Baalebos account']
    notice = events(env, 'login.new_country')[0]
    assert notice.country == 'United Kingdom' and notice.details == {'previous_countries': ['Nigeria']}
    stored = env.db.query(User).filter_by(email='cand@example.org').one()
    assert stored.last_login_ip == '81.2.69.1' and stored.last_login_location == 'London, United Kingdom'


def test_password_spray_alerts_the_owner_once(env):
    user(env, 'cand@example.org')
    for _ in range(7):
        assert login(env, 'cand@example.org', ip='203.0.113.99', password='wrong').status_code == 401
    alerts = [s for to, s in env.sent if OWNER in to]
    assert alerts == ['🛡️ Baalebos security: Possible password attack: 5 failed sign-ins from 203.0.113.99']
    assert len(events(env, 'alert.sent')) == 1


# ── Console data and exports ─────────────────────────────────────────────────

def test_overview_accounts_and_csv_export(env):
    user(env, 'cand@example.org', full_name='=HYPERLINK("http://evil")')
    user(env, 'hr@acme.example', is_hr=True, company_name='Acme')
    overview = env.client.get('/api/v1/admin/overview', headers=owner(env)).json()
    assert overview['kpis']['users'] == 3 and len(overview['growth']) == 30
    assert overview['mix']['employers_pending'] == 1
    assert {a['kind'] for a in overview['attention']} >= {'pending_employers', 'mfa'}
    assert 0 < overview['posture']['score'] < 100

    page = env.client.get('/api/v1/admin/accounts?role=employer', headers=owner(env)).json()
    assert page['total'] == 1 and page['items'][0]['status'] == 'awaiting_approval'
    page = env.client.get('/api/v1/admin/accounts?q=cand', headers=owner(env)).json()
    assert [i['email'] for i in page['items']] == ['cand@example.org']

    csv_text = env.client.get('/api/v1/admin/accounts.csv', headers=owner(env)).text
    assert '\'=HYPERLINK' in csv_text and 'email,full_name' in csv_text.splitlines()[0]
    assert events(env, 'admin.exported')[0].details == {'export': 'users', 'filters': {}}
    login(env, 'cand@example.org', password='wrong')
    sec_csv = env.client.get('/api/v1/admin/security/events.csv?category=failures', headers=owner(env)).text
    assert 'login.failed' in sec_csv and 'login.success' not in sec_csv


def test_employer_review_flags_risks_and_rejects(env, monkeypatch):
    monkeypatch.setattr('backend.app.routes.hr_auth._send_hr_rejection_email', lambda **k: True)
    good = user(env, 'priya@northwind.example', is_hr=True, company_name='Northwind',
                company_url='https://www.northwind.example', linkedin_url='https://linkedin.com/company/nw')
    risky = user(env, 'quickjobs.hr@gmail.com', is_hr=True, company_name='Quick Jobs')
    body = env.client.get('/api/v1/admin/employers?status=pending', headers=owner(env)).json()
    cards = {c['email']: c for c in body['items']}
    assert cards['priya@northwind.example']['risk'] == 'ok'
    assert {c['label'] for c in cards['quickjobs.hr@gmail.com']['checks'] if c['level'] == 'risk'} == {'Free email domain'}
    r = env.client.post(f'/api/v1/hr-auth/reject/{risky.id}', json={'reason': 'Free email domain'}, headers=owner(env))
    assert r.status_code == 200
    body = env.client.get('/api/v1/admin/employers?status=rejected', headers=owner(env)).json()
    assert body['counts'] == {'pending': 1, 'approved': 0, 'rejected': 1}
    assert body['items'][0]['rejected_reason'] == 'Free email domain'
    assert good.id in [c['id'] for c in env.client.get('/api/v1/admin/employers', headers=owner(env)).json()['items']]
