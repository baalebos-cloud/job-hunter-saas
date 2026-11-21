"""HR verification email: delivered through Resend when configured, and re-sendable."""
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.config import Settings
from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models.registry import import_all_models
from backend.app.models.user import User
from backend.app.routes import hr_auth
from backend.app.services.auth_service import hash_token
from backend.app.utils import email

SIGNUP = {'email': 'talent@acme-hiring.example', 'password': 'a-long-password', 'full_name': 'Ada Recruiter',
          'company_name': 'Acme Hiring', 'country': 'Nigeria'}


@pytest.fixture
def db():
    import_all_models()
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    app.dependency_overrides[get_db] = lambda: session
    yield session
    app.dependency_overrides.clear()
    session.close()
    engine.dispose()


@pytest.fixture
def resend(monkeypatch):
    """Resend configured; SMTP (blocked on Railway Hobby) must never be used for verification."""
    monkeypatch.setattr(email, 'settings', Settings(_env_file=None, RESEND_API_KEY='synthetic-key',
                        EMAILS_FROM_EMAIL='noreply@baalebo.xyz', EMAILS_FROM_NAME='Baalebos Cloud'))
    monkeypatch.setattr(email.smtplib, 'SMTP_SSL', lambda *a, **k: (_ for _ in ()).throw(AssertionError('SMTP used')))
    monkeypatch.delenv('ADMIN_EMAIL', raising=False)
    monkeypatch.delenv('EMAILS_FROM_EMAIL', raising=False)
    monkeypatch.setattr(hr_auth, 'hit', lambda key, limit, window: (True, 0))
    sent = []

    def post(url, **kwargs):
        sent.append(kwargs['json'])
        return httpx.Response(200, json={'id': f'email-{len(sent)}'})
    monkeypatch.setattr(email.httpx, 'post', post)
    return sent


def verify_token_from(message):
    return message['html'].split('/hr/verify?token=')[1].split('"')[0]


def test_hr_signup_verification_email_goes_through_resend(db, resend):
    client = TestClient(app)
    assert client.post('/api/v1/hr-auth/signup', json=SIGNUP).status_code == 200
    assert len(resend) == 1
    message = resend[0]
    assert message['to'] == [SIGNUP['email']] and message['subject'] == 'Verify your Baalebos HR account'
    token = verify_token_from(message)
    user = db.query(User).filter_by(email=SIGNUP['email']).one()
    assert user.verification_token == hash_token(token) and not user.is_verified


def test_unverified_hr_can_request_a_new_link_and_old_link_stops_working(db, resend):
    client = TestClient(app)
    client.post('/api/v1/hr-auth/signup', json=SIGNUP)
    first = verify_token_from(resend[0])
    response = client.post('/api/v1/hr-auth/resend-verification', json={'email': SIGNUP['email'].upper()})
    assert response.status_code == 200 and response.json()['message'] == hr_auth.RESEND_VERIFICATION_MESSAGE
    assert len(resend) == 2
    second = verify_token_from(resend[1])
    user = db.query(User).filter_by(email=SIGNUP['email']).one()
    assert second != first and user.verification_token == hash_token(second)


@pytest.mark.parametrize('case', ['unknown', 'verified', 'candidate'])
def test_resend_reveals_nothing_and_sends_nothing_for_other_accounts(db, resend, case):
    db.add_all([User(email='verified-hr@acme-hiring.example', hashed_password='x', is_hr=True, is_verified=True),
                User(email='candidate@acme-hiring.example', hashed_password='x', is_verified=False)])
    db.commit()
    address = {'unknown': 'nobody@acme-hiring.example', 'verified': 'verified-hr@acme-hiring.example',
               'candidate': 'candidate@acme-hiring.example'}[case]
    response = TestClient(app).post('/api/v1/hr-auth/resend-verification', json={'email': address})
    assert response.status_code == 200 and response.json()['message'] == hr_auth.RESEND_VERIFICATION_MESSAGE
    assert resend == []


def test_resend_is_rate_limited(db, resend, monkeypatch):
    calls = []
    monkeypatch.setattr(hr_auth, 'hit', lambda key, limit, window: calls.append((key, limit)) or (len(calls) == 1, 1800))
    response = TestClient(app).post('/api/v1/hr-auth/resend-verification', json={'email': SIGNUP['email']})
    assert response.status_code == 429 and response.headers['Retry-After'] == '1800'
    assert calls[0][1] == hr_auth.RESEND_LIMIT_PER_EMAIL and calls[1][1] == hr_auth.RESEND_LIMIT_PER_IP
    assert 'acme-hiring' not in calls[0][0]   # the email itself is hashed in the key


def test_pending_list_shows_whether_each_employer_verified_their_email(db, resend):
    from backend.app.services.auth_service import create_access_token
    db.add_all([User(email='owner@baalebo.example', hashed_password='x', is_admin=True, role='super_admin', is_verified=True),
                User(email='ready@acme-hiring.example', hashed_password='x', is_hr=True, is_verified=True, company_name='Acme'),
                User(email='waiting@acme-hiring.example', hashed_password='x', is_hr=True, is_verified=False, company_name='Acme')])
    db.commit()
    headers = {'Authorization': 'Bearer ' + create_access_token({'sub': 'owner@baalebo.example'})}
    client = TestClient(app)
    pending = {p['email']: p['is_verified'] for p in client.get('/api/v1/hr-auth/pending', headers=headers).json()}
    assert pending == {'ready@acme-hiring.example': True, 'waiting@acme-hiring.example': False}
    waiting = db.query(User).filter_by(email='waiting@acme-hiring.example').one()
    refused = client.post(f'/api/v1/hr-auth/approve/{waiting.id}', headers=headers)
    assert refused.status_code == 400 and 'verify' in refused.json()['detail']
    ready = db.query(User).filter_by(email='ready@acme-hiring.example').one()
    assert client.post(f'/api/v1/hr-auth/approve/{ready.id}', headers=headers).status_code == 200
    db.refresh(ready)
    assert ready.hr_approved
