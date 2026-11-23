"""Enterprise team access: invites, seats, joining, leaving and the shared plan."""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db, get_read_db
from backend.app.main import app
from backend.app.models.registry import import_all_models
from backend.app.models.subscription import Subscription
from backend.app.models.team import TeamMember
from backend.app.models.user import User
from backend.app.routes import team as team_routes
from backend.app.services import audit, security_events
from backend.app.services.auth_service import create_access_token


@pytest.fixture
def db(monkeypatch):
    import_all_models()
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_read_db] = lambda: session
    monkeypatch.setattr(security_events, '_session', Session)
    monkeypatch.setattr('backend.app.database.SessionLocal', Session)
    session.add_all([User(id=1, email='owner@contoso.com', full_name='Olu Owner', hashed_password='x', is_verified=True),
                     User(id=2, email='ada@contoso.com', hashed_password='x', is_verified=True),
                     User(id=3, email='bo@contoso.com', hashed_password='x', is_verified=True),
                     User(id=4, email='pro@contoso.com', hashed_password='x', is_verified=True),
                     Subscription(user_id=1, plan='enterprise', status='active'),
                     Subscription(user_id=4, plan='pro', status='active')])
    session.commit()
    yield session
    audit.flush()
    app.dependency_overrides.clear()
    session.close()
    engine.dispose()


@pytest.fixture
def sent(monkeypatch):
    """Capture invite emails instead of sending them; returns [(to, raw_token)]."""
    out = []

    def fake(owner, row, raw):
        out.append((row.email, raw))
    monkeypatch.setattr(team_routes, '_send_invite', fake)
    return out


def auth(email):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': email})}


OWNER, ADA, BO, PRO = (auth(e) for e in ('owner@contoso.com', 'ada@contoso.com', 'bo@contoso.com', 'pro@contoso.com'))


def plan(client, headers):
    return client.get('/api/v1/billing/status', headers=headers).json()


def test_only_enterprise_can_invite(db, sent):
    client = TestClient(app)
    denied = client.post('/api/v1/team/invites', json={'email': 'x@contoso.com'}, headers=PRO)
    assert denied.status_code == 403 and denied.json()['detail']['error'] == 'enterprise_required'
    assert client.get('/api/v1/team', headers=PRO).json()['role'] == 'none'
    assert not sent


def test_invite_accept_and_members_get_enterprise(db, sent):
    client = TestClient(app)
    created = client.post('/api/v1/team/invites', json={'email': 'Ada@Contoso.com'}, headers=OWNER)
    assert created.status_code == 201 and created.json()['status'] == 'invited'
    (to, token), = sent
    assert to == 'ada@contoso.com'
    assert db.query(TeamMember).one().token_hash != token                    # only the hash is stored

    assert plan(client, ADA)['plan'] == 'free'
    preview = client.get('/api/v1/team/invite', params={'token': token}, headers=ADA).json()
    assert preview['owner']['name'] == 'Olu Owner' and preview['email_matches'] is True
    assert client.post('/api/v1/team/accept', json={'token': token}, headers=ADA).json()['joined'] is True

    status = plan(client, ADA)
    assert status['plan'] == 'enterprise' and status['scans_limit'] == -1
    assert status['via_team'] == {'owner_name': 'Olu Owner', 'owner_email': 'owner@contoso.com'}
    assert client.get('/api/v1/team', headers=ADA).json()['role'] == 'member'
    team = client.get('/api/v1/team', headers=OWNER).json()
    assert team['seats_used'] == 2 and team['members'][0]['status'] == 'active'
    # Single use: the same link cannot be used again.
    assert client.post('/api/v1/team/accept', json={'token': token}, headers=ADA).status_code == 404


def test_invite_only_works_for_the_invited_email(db, sent):
    client = TestClient(app)
    client.post('/api/v1/team/invites', json={'email': 'ada@contoso.com'}, headers=OWNER)
    token = sent[0][1]
    wrong = client.post('/api/v1/team/accept', json={'token': token}, headers=BO)
    assert wrong.status_code == 403 and 'ada@contoso.com' in wrong.json()['detail']
    assert plan(client, BO)['plan'] == 'free'


def test_invites_expire_after_seven_days_and_can_be_resent(db, sent):
    client = TestClient(app)
    member_id = client.post('/api/v1/team/invites', json={'email': 'ada@contoso.com'}, headers=OWNER).json()['id']
    row = db.get(TeamMember, member_id)
    assert row.expires_at - row.invited_at == timedelta(days=7)
    row.expires_at = datetime.utcnow() - timedelta(minutes=1); db.commit()
    assert client.post('/api/v1/team/accept', json={'token': sent[0][1]}, headers=ADA).status_code == 410
    assert client.get('/api/v1/team', headers=OWNER).json()['members'][0]['status'] == 'expired'

    client.post(f'/api/v1/team/invites/{member_id}/resend', headers=OWNER)
    assert client.post('/api/v1/team/accept', json={'token': sent[0][1]}, headers=ADA).status_code == 404  # old link dead
    assert client.post('/api/v1/team/accept', json={'token': sent[1][1]}, headers=ADA).status_code == 200


def test_ten_seats_including_the_owner(db, sent):
    client = TestClient(app)
    for i in range(9):
        assert client.post('/api/v1/team/invites', json={'email': f'p{i}@contoso.com'}, headers=OWNER).status_code == 201
    full = client.post('/api/v1/team/invites', json={'email': 'p9@contoso.com'}, headers=OWNER)
    assert full.status_code == 400 and '10 seats' in full.json()['detail']
    assert client.post('/api/v1/team/invites', json={'email': 'p0@contoso.com'}, headers=OWNER).status_code == 409
    assert client.post('/api/v1/team/invites', json={'email': 'owner@contoso.com'}, headers=OWNER).status_code == 400
    assert client.post('/api/v1/team/invites', json={'email': 'not-an-email'}, headers=OWNER).status_code == 400
    # Cancelling an invite frees the seat.
    first = client.get('/api/v1/team', headers=OWNER).json()['members'][0]['id']
    assert client.delete(f'/api/v1/team/members/{first}', headers=OWNER).json() == {'removed': True}
    assert client.post('/api/v1/team/invites', json={'email': 'p9@contoso.com'}, headers=OWNER).status_code == 201


def _join(client, sent, email, headers):
    client.post('/api/v1/team/invites', json={'email': email}, headers=OWNER)
    client.post('/api/v1/team/accept', json={'token': sent[-1][1]}, headers=headers)


def test_members_lose_the_plan_when_removed_or_when_they_leave(db, sent):
    client = TestClient(app)
    _join(client, sent, 'ada@contoso.com', ADA)
    _join(client, sent, 'bo@contoso.com', BO)
    ada_row = db.query(TeamMember).filter_by(user_id=2).one().id
    assert client.delete(f'/api/v1/team/members/{ada_row}', headers=BO).status_code == 404   # only the owner removes
    client.delete(f'/api/v1/team/members/{ada_row}', headers=OWNER)
    assert plan(client, ADA)['plan'] == 'free'
    assert client.post('/api/v1/team/leave', headers=BO).json() == {'left': True}
    assert plan(client, BO)['plan'] == 'free'


def test_members_follow_the_owners_plan(db, sent):
    client = TestClient(app)
    _join(client, sent, 'ada@contoso.com', ADA)
    db.query(Subscription).filter_by(user_id=1).one().status = 'cancelled'; db.commit()
    assert plan(client, ADA)['plan'] == 'free'
    assert client.get('/api/v1/team', headers=ADA).json()['active'] is False
    assert client.post('/api/v1/team/invites', json={'email': 'bo@contoso.com'}, headers=OWNER).status_code == 403
    db.query(Subscription).filter_by(user_id=1).one().status = 'active'; db.commit()
    assert plan(client, ADA)['plan'] == 'enterprise'


def test_team_members_get_enterprise_features(db, sent):
    from backend.app.dependencies.plan_guard import plan_for, remaining_scans
    from backend.app.routes.resume import _has_enterprise
    from backend.app.services.processing_gate import has_priority
    client = TestClient(app)
    _join(client, sent, 'ada@contoso.com', ADA)
    ada = db.get(User, 2)
    assert plan_for(db, ada) == 'enterprise' and _has_enterprise(db, ada) and has_priority(db, ada)
    assert remaining_scans(2, db) is None                                    # unlimited
    # Members cannot buy a plan they already have through the team.
    checkout = client.post('/api/v1/billing/checkout', params={'plan': 'pro'}, headers=ADA)
    assert checkout.status_code == 400 and 'through your team' in checkout.json()['detail']


def test_one_team_at_a_time(db, sent, monkeypatch):
    client = TestClient(app)
    db.add(Subscription(user_id=3, plan='enterprise', status='active')); db.commit()
    _join(client, sent, 'ada@contoso.com', ADA)
    client.post('/api/v1/team/invites', json={'email': 'ada@contoso.com'}, headers=BO)
    clash = client.post('/api/v1/team/accept', json={'token': sent[-1][1]}, headers=ADA)
    assert clash.status_code == 409 and 'already on a team' in clash.json()['detail']
    # Someone who manages a team cannot join another one.
    client.post('/api/v1/team/invites', json={'email': 'bo@contoso.com'}, headers=OWNER)
    assert client.post('/api/v1/team/accept', json={'token': sent[-1][1]}, headers=BO).status_code == 409


def test_resumes_stay_private_within_a_team(db, sent):
    from backend.app.models.resume import Resume
    client = TestClient(app)
    _join(client, sent, 'ada@contoso.com', ADA)
    db.add(Resume(owner_id=2, filename='optimized_ada-1.pdf', status='completed', content=b'%PDF',
                  analysis_data={'job_title': 'SRE'})); db.commit()
    assert client.get('/api/v1/resume/history', headers=OWNER).json()['total'] == 0
    assert client.get('/api/v1/resume/history', headers=ADA).json()['total'] == 1


def test_invite_email_has_a_working_link(db, monkeypatch):
    from backend.app.utils import email
    captured = {}
    monkeypatch.setattr(email, 'send_account_message',
                        lambda to, subject, html, reply_to=None: captured.update(to=to, subject=subject, html=html,
                                                                                   reply_to=reply_to))
    row = TeamMember(owner_id=1, email='ada@contoso.com', email_canonical='ada@contoso.com')
    team_routes._send_invite(db.get(User, 1), row, 'RAWTOKEN123')
    assert captured['to'] == 'ada@contoso.com' and captured['reply_to'] == 'owner@contoso.com'
    assert 'Olu Owner invited you' in captured['subject']
    assert '/team/join?token=RAWTOKEN123' in captured['html'] and 'expires in 7 days' in captured['html']
