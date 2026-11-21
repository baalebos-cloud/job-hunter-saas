"""Security events: full-IP sign-in/sign-up/admin trail for owner oversight."""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core import geoip
from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models.registry import import_all_models
from backend.app.models.security_event import SecurityEvent
from backend.app.models.user import User
from backend.app.services import security_events
from backend.app.services.auth_service import create_access_token, hash_password

OWNER = 'owner@baalebos.example'
CANDIDATE = 'candidate@baalebos.example'


@pytest.fixture
def db(monkeypatch):
    import_all_models()
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add_all([
        User(email=OWNER, full_name='Owner', hashed_password=hash_password('owner-password'),
             is_admin=True, role='super_admin', is_verified=True),
        User(email=CANDIDATE, full_name='Candidate', hashed_password=hash_password('candidate-password'), is_verified=True),
    ])
    session.commit()
    app.dependency_overrides[get_db] = lambda: session
    monkeypatch.setattr(security_events, '_session', Session)   # events go to the test database
    monkeypatch.setattr('backend.app.core.rate_limit.safe_call',
                        lambda method, *a, **k: (0, 0) if method == 'window_count' else 0)
    yield session
    app.dependency_overrides.clear()
    session.close()
    engine.dispose()


def owner_headers():
    return {'Authorization': 'Bearer ' + create_access_token({'sub': OWNER})}


def events(db, event=None):
    db.expire_all()
    q = db.query(SecurityEvent)
    return q.filter(SecurityEvent.event == event).all() if event else q.all()


def test_sign_in_success_and_failure_are_recorded_with_ip_and_portal(db):
    client = TestClient(app)
    assert client.post('/api/v1/auth/login', json={'email': CANDIDATE, 'password': 'wrong'}).status_code == 401
    assert client.post('/api/v1/auth/login', json={'email': 'ghost@baalebos.example', 'password': 'x'}).status_code == 401
    assert client.post('/api/v1/auth/login', json={'email': CANDIDATE, 'password': 'candidate-password'}).status_code == 200
    failed = events(db, 'login.failed')
    assert {(e.email, e.details['reason']) for e in failed} == {(CANDIDATE, 'wrong_password'),
                                                                 ('ghost@baalebos.example', 'unknown_account')}
    success = events(db, 'login.success')[0]
    assert success.email == CANDIDATE and success.portal == 'login' and success.ip and success.user_id


def test_locked_out_sign_in_is_recorded(db, monkeypatch):
    monkeypatch.setattr('backend.app.core.rate_limit.safe_call',
                        lambda method, *a, **k: (99, 0) if method == 'window_count' else 0)
    response = TestClient(app).post('/api/v1/auth/login', json={'email': CANDIDATE, 'password': 'x'})
    assert response.status_code == 429
    assert events(db, 'login.blocked')[0].email == CANDIDATE


def test_admin_summary_flags_suspicious_ips_and_requires_admin(db):
    now = datetime.utcnow()
    db.add_all([SecurityEvent(ts=now - timedelta(minutes=i), event='login.failed', ip='203.0.113.9',
                              email=f'victim{i % 3}@x.example', country='Testland') for i in range(6)]
               + [SecurityEvent(ts=now, event='login.failed', ip='198.51.100.1', email='a@x.example'),
                  SecurityEvent(ts=now, event='login.success', ip='198.51.100.1', email='a@x.example', country='Nigeria'),
                  SecurityEvent(ts=now - timedelta(days=3), event='login.failed', ip='203.0.113.9')])
    db.commit()
    client = TestClient(app)
    candidate = {'Authorization': 'Bearer ' + create_access_token({'sub': CANDIDATE})}
    assert client.get('/api/v1/admin/security/summary', headers=candidate).status_code == 403
    summary = client.get('/api/v1/admin/security/summary', headers=owner_headers()).json()
    assert summary['failed_sign_ins'] == 7 and summary['sign_ins'] == 1
    assert summary['suspicious_ips'] == [{'ip': '203.0.113.9', 'failures': 6, 'last_seen': summary['suspicious_ips'][0]['last_seen'],
                                         'country': 'Testland', 'accounts': 3}]
    assert summary['top_countries'] == [{'country': 'Nigeria', 'sign_ins': 1}]
    assert summary['retention_days'] == 90


def test_event_log_filters_and_every_view_is_recorded(db):
    db.add_all([SecurityEvent(event='login.failed', ip='203.0.113.9', email='x@x.example'),
                SecurityEvent(event='signup', ip='198.51.100.7', email='new@x.example', city='Lagos', country='Nigeria')])
    db.commit()
    client = TestClient(app)
    body = client.get('/api/v1/admin/security/events?ip=203.0.113.9', headers=owner_headers()).json()
    assert [e['event'] for e in body['events']] == ['login.failed']
    body = client.get('/api/v1/admin/security/events?q=lagos', headers=owner_headers()).json()
    assert body['events'][0]['location'] == 'Lagos, Nigeria' and body['events'][0]['label'] == 'Candidate sign-up'
    viewed = events(db, 'admin.security_viewed')
    assert len(viewed) == 2 and viewed[0].email == OWNER and viewed[0].details == {'filters': {'ip': '203.0.113.9'}}


def test_admin_actions_are_recorded(db):
    db.add(User(email='hr@acme.example', hashed_password='x', is_hr=True, is_verified=True, company_name='Acme'))
    db.commit()
    hr = db.query(User).filter_by(email='hr@acme.example').one()
    assert TestClient(app).post(f'/api/v1/hr-auth/approve/{hr.id}', headers=owner_headers()).status_code == 200
    approved = events(db, 'admin.hr_approved')[0]
    assert approved.email == OWNER and approved.details['target_email'] == 'hr@acme.example'


def test_privacy_export_erasure_and_retention_cover_security_events(db):
    from backend.app.services.privacy import erase_user, export_user_data, run_retention
    candidate = db.query(User).filter_by(email=CANDIDATE).one()
    db.add_all([SecurityEvent(event='login.success', user_id=candidate.id, email=CANDIDATE, ip='198.51.100.2'),
                SecurityEvent(event='login.failed', email=CANDIDATE, ip='198.51.100.3'),
                SecurityEvent(event='login.failed', email='someone@else.example', ts=datetime.utcnow() - timedelta(days=91))])
    db.commit()
    assert len(export_user_data(db, candidate)['security_events']) == 2
    erase_user(db, candidate)
    assert {e.email for e in events(db)} == {'someone@else.example'}
    assert run_retention(db)['security_events'] == 1 and events(db) == []


def test_geolocation_labels_private_ranges_and_uses_the_local_database(monkeypatch):
    assert geoip.locate('10.0.0.5')['country'] == 'Private network'
    assert geoip.locate('not-an-ip')['country'] is None
    record = SimpleNamespace(country=SimpleNamespace(iso_code='NG', name='Nigeria'), city=SimpleNamespace(name='Lagos'),
                             subdivisions=SimpleNamespace(most_specific=SimpleNamespace(name='Lagos State')))
    monkeypatch.setattr(geoip, '_reader', lambda: SimpleNamespace(city=lambda ip: record))
    assert geoip.locate('102.89.1.1') == {'country_code': 'NG', 'country': 'Nigeria', 'region': 'Lagos State', 'city': 'Lagos'}


def test_geoip_download_never_prints_the_licence_key(monkeypatch, tmp_path, capsys):
    from backend.scripts import download_geoip
    monkeypatch.setenv('GEOIP_DB_PATH', str(tmp_path / 'GeoLite2-City.mmdb'))
    monkeypatch.delenv('MAXMIND_LICENSE_KEY', raising=False)
    assert download_geoip.main() == 0
    monkeypatch.setenv('MAXMIND_LICENSE_KEY', 'synthetic-secret-key')

    def fail(url, timeout):
        raise OSError(f'connection refused for {url}')
    monkeypatch.setattr(download_geoip.urllib.request, 'urlopen', fail)
    assert download_geoip.main() == 0
    out = capsys.readouterr()
    assert 'synthetic-secret-key' not in out.out + out.err and 'download failed (OSError)' in out.err
