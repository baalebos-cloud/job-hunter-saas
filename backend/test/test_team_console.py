"""Team console: product manager and social media manager roles, and the
figures behind the Growth, Campaigns and Content tabs."""
import secrets
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db, get_read_db
from backend.app.main import app
from backend.app.models.application import Application
from backend.app.models.growth import GrowthCounter
from backend.app.models.job import Job
from backend.app.models.referral import Referral
from backend.app.models.registry import import_all_models
from backend.app.models.resume import Resume
from backend.app.models.subscription import Subscription
from backend.app.models.user import User
from backend.app.services import audit, security_events
from backend.app.services.auth_service import create_access_token
from backend.app.services.growth import salary_top

OWNER, PM, SMM, NOBODY = 'owner@example.com', 'pm@example.com', 'smm@example.com', 'seeker@example.com'


@pytest.fixture
def ctx(monkeypatch):
    import_all_models()
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_read_db] = lambda: session
    monkeypatch.setattr(security_events, '_session', Session)
    monkeypatch.setattr('backend.app.database.SessionLocal', Session)
    monkeypatch.setattr('backend.app.core.rate_limit.hit', lambda key, limit, window: (True, 0))
    monkeypatch.setenv('ADMIN_2FA_REQUIRED', 'true')
    two_step = datetime.utcnow()
    session.add_all([
        User(email=OWNER, hashed_password=secrets.token_urlsafe(), is_verified=True, is_admin=True, role='super_admin',
             totp_enabled_at=two_step),
        User(email=PM, full_name='Pat Manager', hashed_password=secrets.token_urlsafe(), is_verified=True,
             role='product_manager', totp_enabled_at=two_step),
        User(email=SMM, hashed_password=secrets.token_urlsafe(), is_verified=True, role='social_media_manager',
             totp_enabled_at=two_step),
        User(email=NOBODY, hashed_password=secrets.token_urlsafe(), is_verified=True, career_track='DevOps'),
    ])
    session.commit()
    yield TestClient(app), session
    audit.flush()
    app.dependency_overrides.clear()
    session.close()
    engine.dispose()


def auth(email):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': email})}


# ── Who can open what ────────────────────────────────────────────────────────

CONSOLE = ['/api/v1/console/analytics', '/api/v1/console/growth', '/api/v1/console/campaigns',
           '/api/v1/console/content', '/api/v1/support/admin/tickets', '/api/v1/support/admin/slack']
ADMIN_ONLY = ['/api/v1/admin/overview', '/api/v1/admin/security/summary', '/api/v1/admin/accounts',
              '/api/v1/admin/employers', '/api/v1/rbac/users', '/api/v1/governance/audit']


@pytest.mark.parametrize('email, allowed', [
    (OWNER, set(CONSOLE)),
    (PM, set(CONSOLE)),
    (SMM, {'/api/v1/console/analytics', '/api/v1/console/campaigns', '/api/v1/console/content'}),
    (NOBODY, set()),
])
def test_each_role_reaches_only_its_tabs(ctx, email, allowed):
    client, _ = ctx
    for path in CONSOLE:
        status = client.get(path, headers=auth(email)).status_code
        assert (status == 200) == (path in allowed), (email, path, status)


@pytest.mark.parametrize('email', [PM, SMM])
def test_staff_never_reach_admin_security_users_or_audit(ctx, email):
    client, _ = ctx
    for path in ADMIN_ONLY:
        assert client.get(path, headers=auth(email)).status_code in (403, 404), path
    assert client.put('/api/v1/rbac/users/4/role', json={'role': 'super_admin'}, headers=auth(email)).status_code == 403


def test_staff_must_turn_on_two_step_verification(ctx):
    client, db = ctx
    db.query(User).filter_by(email=PM).one().totp_enabled_at = None; db.commit()
    blocked = client.get('/api/v1/console/growth', headers=auth(PM))
    assert blocked.status_code == 403 and blocked.json()['detail']['code'] == 'mfa_enrollment_required'


def test_me_lists_the_roles_permissions(ctx):
    client, _ = ctx
    pm = set(client.get('/api/v1/auth/me', headers=auth(PM)).json()['permissions'])
    assert {'growth:read', 'support:manage', 'content:read'} <= pm and 'admin:access' not in pm
    smm = set(client.get('/api/v1/auth/me', headers=auth(SMM)).json()['permissions'])
    assert smm == {'analytics:read', 'campaigns:read', 'content:read'}


def test_owner_assigns_roles_after_seeing_the_profile(ctx):
    client, db = ctx
    found = client.get('/api/v1/rbac/users', params={'q': 'seeker'}, headers=auth(OWNER)).json()
    assert found[0]['career_track'] == 'DevOps' and found[0]['two_step'] is False and found[0]['joined']
    user_id = found[0]['id']
    invited = client.put(f'/api/v1/rbac/users/{user_id}/role', json={'role': 'social_media_manager'}, headers=auth(OWNER)).json()
    assert invited['status'] == 'invited' and invited['invited_role'] == 'social_media_manager'
    pending = client.get('/api/v1/rbac/invitations', headers=auth(OWNER)).json()
    assert [(p['email'], p['role'], p['status']) for p in pending] == [(found[0]['email'], 'social_media_manager', 'pending')]
    matrix = client.get('/api/v1/rbac/matrix', headers=auth(OWNER)).json()['roles']
    assert set(matrix['product_manager']['permissions']) >= {'growth:read', 'support:manage'}
    assert 'support:manage' not in matrix['social_media_manager']['permissions']


# ── Figures ──────────────────────────────────────────────────────────────────

def seed_people(db):
    now = datetime.utcnow()
    people = []
    for i, (verified, source) in enumerate([(True, 'linkedin'), (True, 'linkedin'), (False, None), (True, 'x')]):
        u = User(email=f'u{i}@example.com', hashed_password='x', is_verified=verified, created_at=now - timedelta(days=2),
                 signup_utm_source=source, signup_utm_medium='social' if source else None,
                 signup_utm_campaign='launch' if source else None, signup_referrer='linkedin.com' if source == 'linkedin' else None,
                 job_alerts_enabled=i == 0)
        db.add(u); db.flush(); people.append(u)
    db.add(Resume(owner_id=people[0].id, filename='optimized_a.pdf', status='completed', created_at=now))
    db.add(Resume(owner_id=people[1].id, filename='optimized_b.pdf', status='completed', created_at=now))
    db.add(Resume(owner_id=people[1].id, filename='optimized_c.pdf', status='failed', created_at=now))
    job = Job(title='SRE', company='Contoso', is_active=True); db.add(job); db.flush()
    db.add(Application(user_id=people[0].id, job_id=job.id, created_at=now))
    db.add(Subscription(user_id=people[0].id, plan='pro', status='active'))
    db.add(Subscription(user_id=people[3].id, plan='enterprise', status='active'))
    db.add(Referral(referrer_id=people[0].id, referred_email='friend@example.com', referred_user_id=people[2].id,
                    created_at=now))
    db.add(GrowthCounter(kind='plan:upgraded', day=date.today(), count=2))
    db.add(GrowthCounter(kind='alerts:unsubscribed', day=date.today(), count=1))
    db.commit()
    return people


def test_growth_funnel_plans_referrals_and_alerts(ctx):
    client, db = ctx
    seed_people(db)
    data = client.get('/api/v1/console/growth', headers=auth(PM)).json()
    funnel = {f['step']: f['count'] for f in data['funnel']}
    # 4 seeded people + the fixture's job seeker; the owner and both staff accounts are not counted.
    assert funnel == {'Signed up': 5, 'Verified email': 4, 'Tailored a resume': 2, 'Applied to a job': 1,
                      'On a paid plan': 2}
    assert data['plans']['pro'] == 1 and data['plans']['enterprise'] == 1 and data['plans']['estimated_mrr'] == 68
    assert 'Estimate' in data['plans']['mrr_note'] and data['plans']['upgrades'] == 2
    assert data['referrals'] == {'invites': 1, 'signed_up': 1, 'converted': 0}
    assert data['alerts']['subscribers'] == 1 and data['alerts']['unsubscribed'] == 1
    csv = client.get('/api/v1/console/growth.csv', headers=auth(PM))
    assert csv.headers['content-type'].startswith('text/csv') and 'Signed up,5' in csv.text


def test_campaign_results_group_signups_by_source(ctx):
    client, db = ctx
    seed_people(db)
    data = client.get('/api/v1/console/campaigns', headers=auth(SMM)).json()
    by_source = {s['source']: s for s in data['sources']}
    assert by_source['linkedin']['signups'] == 2 and by_source['linkedin']['paid'] == 1
    assert by_source['(direct or untagged)']['signups'] == 2           # one seeded person + the fixture's seeker
    assert data['referrers'][0] == {'referrer': 'linkedin.com', 'signups': 2, 'verified': 2, 'paid': 1}
    assert 'email' not in str(data)                                          # no personal data


def test_signup_records_first_touch_campaign_tags_cleanly(ctx):
    client, db = ctx
    response = client.post('/api/v1/auth/signup', json={
        'email': 'new@example.com', 'full_name': 'New Person', 'password': secrets.token_urlsafe(12),
        'utm_source': 'LinkedIn', 'utm_medium': 'Social <script>', 'utm_campaign': 'Launch Week',
        'referrer': 'https://www.linkedin.com/feed/?x=1'})
    assert response.status_code == 201, response.text
    user = db.query(User).filter_by(email='new@example.com').one()
    assert (user.signup_utm_source, user.signup_utm_medium, user.signup_utm_campaign, user.signup_referrer) == \
        ('linkedin', 'social script', 'launch week', 'linkedin.com')


def test_partner_clicks_are_counted_without_personal_data(ctx):
    client, db = ctx
    for _ in range(3):
        assert client.post('/api/v1/track/partner-click', json={'partner': 'mercor'}).status_code == 204
    assert client.post('/api/v1/track/partner-click', json={'partner': 'unknown'}).status_code == 404
    row = db.query(GrowthCounter).filter_by(kind='partner_click:mercor').one()
    assert row.count == 3 and row.day == date.today()
    partners = {p['partner']: p for p in client.get('/api/v1/console/campaigns', headers=auth(SMM)).json()['partners']}
    assert partners['mercor']['clicks_7d'] == 3 and partners['micro1']['clicks_30d'] == 0


def test_alert_unsubscribes_are_counted(ctx):
    from backend.app.services.job_alerts import unsubscribe_token
    client, db = ctx
    user = db.query(User).filter_by(email=NOBODY).one()
    user.job_alerts_enabled = True; db.commit()
    assert client.post('/api/v1/alerts/unsubscribe', params={'t': unsubscribe_token(user)}).json() == {'unsubscribed': True}
    assert db.query(GrowthCounter).filter_by(kind='alerts:unsubscribed').one().count == 1


def test_content_posts_use_only_live_jobs_and_carry_campaign_tags(ctx):
    client, db = ctx
    now = datetime.utcnow()
    db.add_all([
        Job(title='Senior SRE', company='Contoso', location='Remote', work_type='remote', is_active=True,
            salary_range='$150K – $190K', first_seen_at=now),
        Job(title='Platform Engineer', company='Contoso', location='Berlin', work_type='onsite', is_active=True,
            salary_range='€70,000', first_seen_at=now),
        Job(title='Data Engineer', company='Fabrikam', location='Remote', work_type='remote', is_active=True,
            salary_range='$60/hr', first_seen_at=now - timedelta(days=30)),
        Job(title='Closed Role', company='Northwind', is_active=False, first_seen_at=now),
    ])
    db.commit()
    data = client.get('/api/v1/console/content', headers=auth(SMM)).json()
    assert data['live_jobs'] == 3 and data['new_this_week'] == 2 and data['remote_new_this_week'] == 1
    assert data['top_companies'][0] == {'company': 'Contoso', 'open_roles': 2}
    assert [j['title'] for j in data['top_paid']] == ['Senior SRE', 'Platform Engineer']   # hourly pay not ranked
    texts = '\n'.join(p['text'] for p in data['posts'])
    assert 'Closed Role' not in texts and 'Northwind' not in texts
    assert '2 new tech jobs on Baalebos this week, 1 of them remote' in texts
    assert all('utm_source=social' in j['link'] for j in data['newest_remote'])


@pytest.mark.parametrize('text, value', [
    ('$120K – $160K', 160000), ('€70,000 - €85,000', 85000), ('$60/hr', None), ('$5,000 per month', None),
    ('Competitive', None), ('', None), ('£45k', 45000),
])
def test_salary_ranking_reads_yearly_pay_only(text, value):
    assert salary_top(text) == value


def test_signup_accepts_a_typed_career_track_and_tidies_it(ctx):
    client, db = ctx
    response = client.post('/api/v1/auth/signup', json={
        'email': 'typed@example.com', 'full_name': 'Typed Track', 'password': secrets.token_urlsafe(12),
        'career_track': '  LLM / Generative AI   Engineer\n', 'country': ' Nigeria '})
    assert response.status_code == 201, response.text
    user = db.query(User).filter_by(email='typed@example.com').one()
    assert user.career_track == 'LLM / Generative AI Engineer' and user.country == 'Nigeria'
    long = client.post('/api/v1/auth/signup', json={
        'email': 'long@example.com', 'full_name': 'Long Track', 'password': secrets.token_urlsafe(12),
        'career_track': 'x' * 300})
    assert long.status_code == 201
    assert len(db.query(User).filter_by(email='long@example.com').one().career_track) == 80


def test_assigning_a_role_sends_an_invitation_and_accepting_sends_the_overview(ctx, monkeypatch):
    client, db = ctx
    sent = []
    monkeypatch.setattr('backend.app.utils.email.send_account_message',
                        lambda to, subject, body, reply_to=None: sent.append((to, subject, body, reply_to)) or True)
    person = db.query(User).filter_by(email=NOBODY).one()
    person.full_name = 'Tolu <b>Ade</b>'; db.commit()
    result = client.put(f'/api/v1/rbac/users/{person.id}/role', json={'role': 'product_manager'}, headers=auth(OWNER)).json()
    assert result['notified'] is True and result['status'] == 'invited'
    (to, subject, body, reply_to), = sent
    assert to == NOBODY and subject == 'You are invited to join Baalebos as Product manager' and reply_to == 'support@baalebo.xyz'
    assert 'Growth: funnel' in body and 'Nothing changes on your account until you accept' in body
    assert '/staff-invite?token=' in body and '<b>Ade</b>' not in body and 'Tolu' in body
    token = body.split('/staff-invite?token=')[1].split('"')[0]

    sent.clear()                                        # assigning again while pending replaces the invitation
    assert client.put(f'/api/v1/rbac/users/{person.id}/role', json={'role': 'product_manager'},
                      headers=auth(OWNER)).json()['status'] == 'invited'
    assert client.get(f'/api/v1/staff-invites/{token}').status_code == 410   # the first link no longer works
    token = sent[0][2].split('/staff-invite?token=')[1].split('"')[0]

    sent.clear()
    assert client.post('/api/v1/staff-invites/accept', json={'token': token, 'confidentiality': True},
                       headers=auth(NOBODY)).json()['two_step_required'] is True
    (_, subject, body, _), = sent
    assert subject == 'You are now a Product manager on Baalebos'
    assert 'Sign in again' in body and 'Turn on two-step verification' in body and 'Open Team console' in body
    assert db.query(User).filter_by(email=NOBODY).one().role == 'product_manager'




# ── Legal counsel and staff invitations ──────────────────────────────────────

def invite(client, db, monkeypatch, role='legal_counsel', email=NOBODY):
    links = []
    monkeypatch.setattr('backend.app.services.staff_invitations.send', lambda *a: links.append(a[-1]) or True)
    person = db.query(User).filter_by(email=email).one()
    res = client.put(f'/api/v1/rbac/users/{person.id}/role', json={'role': role}, headers=auth(OWNER)).json()
    return person, res, links


def test_legal_counsel_role_reaches_only_legal_privacy_and_audit(ctx):
    client, _ = ctx
    matrix = client.get('/api/v1/rbac/matrix', headers=auth(OWNER)).json()['roles']
    assert set(matrix['legal_counsel']['permissions']) == {'legal:manage', 'privacy:manage', 'audit:read', 'users:read'}
    assert 'legal:manage' in matrix['super_admin']['permissions']


def test_invitation_link_details_hide_the_address_and_accept_needs_the_invited_account(ctx, monkeypatch):
    client, db = ctx
    person, res, links = invite(client, db, monkeypatch)
    assert res['status'] == 'invited' and person.role is None
    details = client.get(f'/api/v1/staff-invites/{links[0]}').json()
    assert details['label'] == 'Legal counsel' and details['invited_email'].startswith('s') and '***' in details['invited_email']
    assert 'Legal: edit and publish' in details['can'][0]
    wrong = client.post('/api/v1/staff-invites/accept', json={'token': links[0], 'confidentiality': True}, headers=auth(PM))
    assert wrong.status_code == 403 and 'Sign out' in wrong.json()['detail']
    no_promise = client.post('/api/v1/staff-invites/accept', json={'token': links[0]}, headers=auth(NOBODY))
    assert no_promise.status_code == 422
    assert client.post('/api/v1/staff-invites/accept', json={'token': links[0], 'confidentiality': True},
                       headers=auth(NOBODY)).json()['role'] == 'legal_counsel'
    assert client.get(f'/api/v1/staff-invites/{links[0]}').status_code == 410     # single use
    assert client.get('/api/v1/auth/me', headers=auth(NOBODY)).status_code == 401  # signed out: fresh sign-in for new access


def test_declined_cancelled_and_expired_invitations_grant_nothing(ctx, monkeypatch):
    from backend.app.models.security import StaffInvitation
    client, db = ctx
    person, _, links = invite(client, db, monkeypatch)
    assert client.post('/api/v1/staff-invites/decline', json={'token': links[0]}).json()['status'] == 'declined'
    _, _, links = invite(client, db, monkeypatch)
    pending = client.get('/api/v1/rbac/invitations', headers=auth(OWNER)).json()
    assert client.delete(f"/api/v1/rbac/invitations/{pending[0]['id']}", headers=auth(OWNER)).status_code == 200
    assert client.get(f'/api/v1/staff-invites/{links[0]}').json()['detail'].startswith('This invitation was withdrawn')
    _, _, links = invite(client, db, monkeypatch)
    row = db.query(StaffInvitation).filter_by(status='pending').one()
    row.expires_at = datetime.utcnow() - timedelta(minutes=1); db.commit()
    assert client.post('/api/v1/staff-invites/accept', json={'token': links[0], 'confidentiality': True},
                       headers=auth(NOBODY)).status_code == 410
    assert db.query(User).filter_by(email=NOBODY).one().role is None


def test_resend_issues_a_new_link_and_removal_is_immediate(ctx, monkeypatch):
    client, db = ctx
    person, _, links = invite(client, db, monkeypatch, role='product_manager')
    pending = client.get('/api/v1/rbac/invitations', headers=auth(OWNER)).json()
    assert client.post(f"/api/v1/rbac/invitations/{pending[0]['id']}/resend", headers=auth(OWNER)).status_code == 200
    assert len(links) == 2 and client.get(f'/api/v1/staff-invites/{links[0]}').status_code == 404
    client.post('/api/v1/staff-invites/accept', json={'token': links[1], 'confidentiality': True}, headers=auth(NOBODY))
    assert db.query(User).filter_by(email=NOBODY).one().role == 'product_manager'
    res = client.put(f'/api/v1/rbac/users/{person.id}/role', json={'role': None}, headers=auth(OWNER)).json()
    assert res['status'] == 'removed' and db.query(User).filter_by(email=NOBODY).one().role is None
