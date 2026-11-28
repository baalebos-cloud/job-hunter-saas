"""Employer workspaces: company team, roles, invitations and hiring-team job access."""
from datetime import datetime, timedelta

import pytest

from backend.app.models.application import Application
from backend.app.models.company import Company, CompanyMember, JobTeamMember
from backend.app.models.job import Job
from backend.app.models.user import User
from backend.app.routes import hr_team
from backend.test.test_platform_quality import db, client, headers  # noqa: F401

HR = 'hr@example.com'          # approved employer from the shared fixture (no workspace yet)


@pytest.fixture
def sent(monkeypatch):
    """Capture invitation emails (and their raw tokens) instead of sending them."""
    from backend.app.main import reset_rate_limits
    reset_rate_limits()
    from backend.app.services import audit
    mails = []
    monkeypatch.setattr(hr_team, '_send_invite', lambda inviter, company, row, raw: mails.append(
        {'to': row.email, 'token': raw, 'company': company, 'inviter': inviter}))
    yield mails
    audit.flush()          # drain queued request records before the next test's database


@pytest.fixture(autouse=True)
def _drain_audit():
    yield
    from backend.app.services import audit
    audit.flush()


def invite(client, email, role, as_=HR):
    return client.post('/api/v1/hr/team/invites', json={'email': email, 'role': role}, headers=headers(as_))


def join(client, sent, email, role, name='New Person', password='a-strong-password'):
    assert invite(client, email, role).status_code == 201
    token = [m for m in sent if m['to'] == email][-1]['token']
    res = client.post('/api/v1/hr/team/accept', json={'token': token, 'full_name': name, 'password': password})
    assert res.status_code == 200, res.text
    return token


def post_job(client, title, as_=HR):
    res = client.post('/api/v1/hr/jobs', json={'title': title, 'company': 'Northwind', 'location': 'Lagos',
                                              'description': 'Kubernetes'}, headers=headers(as_))
    assert res.status_code == 200, res.text
    return res.json()['job_id']


def test_existing_employer_becomes_admin_of_a_company_with_their_jobs(client, db):
    hr = db.query(User).filter_by(email=HR).first()
    hr.company_name = 'Northwind'
    old = Job(title='Legacy role', company='Northwind', hr_user_id=hr.id, posted_by_hr=True, is_active=True)
    db.add(old)
    db.commit()
    body = client.get('/api/v1/hr/workspace', headers=headers(HR)).json()
    assert body['company']['name'] == 'Northwind' and body['role'] == 'admin'
    assert all(body['permissions'].values())
    assert [j['title'] for j in client.get('/api/v1/hr/jobs', headers=headers(HR)).json()] == ['Legacy role']
    db.refresh(old)
    assert old.company_id == body['company']['id']
    # A second visit reuses the same company.
    client.get('/api/v1/hr/workspace', headers=headers(HR))
    assert db.query(Company).count() == 1


def test_invited_recruiter_joins_and_works_on_every_company_job(client, db, sent):
    job_id = post_job(client, 'Platform Engineer')
    join(client, sent, 'rec@northwind.example', 'recruiter', name='Rita Recruiter')
    assert sent[0]['company'] and 'HR' in sent[0]['inviter']
    rita = db.query(User).filter_by(email='rec@northwind.example').first()
    assert rita.is_hr and rita.is_verified and rita.hr_approved
    me = client.get('/api/v1/hr/workspace', headers=headers(rita.email)).json()
    assert me['role'] == 'recruiter' and not me['permissions']['manage_team'] and me['permissions']['post_jobs']
    assert [j['id'] for j in client.get('/api/v1/hr/jobs', headers=headers(rita.email)).json()] == [job_id]
    assert post_job(client, 'SRE', as_=rita.email)
    assert invite(client, 'x@northwind.example', 'interviewer', as_=rita.email).status_code == 403
    # The invitation is single-use.
    again = client.post('/api/v1/hr/team/accept', json={'token': sent[0]['token'], 'password': 'whatever-123'})
    assert again.status_code == 404


def test_hiring_manager_sees_only_hiring_team_jobs_and_interviewer_cannot_move(client, db, sent):
    mine, other = post_job(client, 'Backend Engineer'), post_job(client, 'Data Engineer')
    join(client, sent, 'hm@northwind.example', 'hiring_manager')
    join(client, sent, 'int@northwind.example', 'interviewer')
    hm = db.query(User).filter_by(email='hm@northwind.example').first()
    iv = db.query(User).filter_by(email='int@northwind.example').first()
    assert client.get('/api/v1/hr/jobs', headers=headers(hm.email)).json() == []
    res = client.put(f'/api/v1/hr/jobs/{mine}/team', headers=headers(HR), json={'members': [
        {'user_id': hm.id, 'role': 'hiring_manager'}, {'user_id': iv.id, 'role': 'interviewer'}]})
    assert res.status_code == 200 and len(res.json()['members']) == 2
    assert [j['id'] for j in client.get('/api/v1/hr/jobs', headers=headers(hm.email)).json()] == [mine]
    assert client.get(f'/api/v1/hr/jobs/{other}/applications', headers=headers(hm.email)).status_code == 404
    app = Application(user_id=2, job_id=mine, status='pending')
    db.add(app)
    db.commit()
    move = f'/api/v1/hr/applications/{app.id}/status?new_status=reviewed'
    assert client.patch(move, headers=headers(iv.email)).status_code == 403
    assert client.patch(move, headers=headers(hm.email)).status_code == 200
    assert client.get(f'/api/v1/hr/jobs/{mine}/applications', headers=headers(iv.email)).status_code == 200
    # Hiring managers cannot post or delete jobs.
    assert client.delete(f'/api/v1/hr/jobs/{mine}', headers=headers(hm.email)).status_code == 403


def test_other_companies_never_see_each_others_jobs(client, db, sent):
    job_id = post_job(client, 'Security Engineer')
    db.add(User(email='boss@other.example', full_name='Other', hashed_password='x', is_hr=True, is_verified=True,
                hr_approved=True, company_name='Other Co'))
    db.commit()
    assert client.get('/api/v1/hr/jobs', headers=headers('boss@other.example')).json() == []
    assert client.get(f'/api/v1/hr/jobs/{job_id}/applications', headers=headers('boss@other.example')).status_code == 404
    assert client.get(f'/api/v1/hr/jobs/{job_id}/team', headers=headers('boss@other.example')).status_code == 404
    # Nor can they put another company's people on their hiring team.
    other_job = post_job(client, 'Other role', as_='boss@other.example')
    hr = db.query(User).filter_by(email=HR).first()
    res = client.put(f'/api/v1/hr/jobs/{other_job}/team', headers=headers('boss@other.example'),
                     json={'members': [{'user_id': hr.id, 'role': 'recruiter'}]})
    assert res.status_code == 400


def test_invitation_rules(client, db, sent):
    assert invite(client, 'candidate@example.com', 'recruiter').status_code == 409     # candidate account
    assert invite(client, 'not-an-email', 'recruiter').status_code == 400
    assert invite(client, 'someone@gmail.com', 'recruiter').status_code == 400        # free email provider
    assert invite(client, 'a@northwind.example', 'owner').status_code == 400           # unknown role
    assert invite(client, 'a@northwind.example', 'recruiter').status_code == 201
    assert invite(client, 'a@northwind.example', 'recruiter').status_code == 409       # already pending
    db.add(User(email='boss@other.example', hashed_password='x', is_hr=True, is_verified=True, hr_approved=True))
    db.commit()
    assert invite(client, 'boss@other.example', 'recruiter').status_code == 409        # another company's account
    # Expired links are refused.
    row = db.query(CompanyMember).filter_by(email='a@northwind.example').first()
    row.expires_at = datetime.utcnow() - timedelta(minutes=1)
    db.commit()
    token = sent[-1]['token']
    assert client.get(f'/api/v1/hr/team/invite?token={token}').status_code == 410
    # ...and can be sent again.
    assert client.post(f'/api/v1/hr/team/invites/{row.id}/resend', headers=headers(HR)).status_code == 200
    preview = client.get(f"/api/v1/hr/team/invite?token={sent[-1]['token']}").json()
    assert preview['role_label'] == 'Recruiter' and preview['has_account'] is False


def test_the_last_admin_cannot_be_demoted_or_removed(client, db, sent):
    client.get('/api/v1/hr/workspace', headers=headers(HR))
    me = db.query(CompanyMember).filter_by(email=HR).first()
    assert client.patch(f'/api/v1/hr/team/members/{me.id}', json={'role': 'recruiter'}, headers=headers(HR)).status_code == 400
    assert client.delete(f'/api/v1/hr/team/members/{me.id}', headers=headers(HR)).status_code == 400
    join(client, sent, 'second@northwind.example', 'admin')
    assert client.patch(f'/api/v1/hr/team/members/{me.id}', json={'role': 'recruiter'}, headers=headers(HR)).status_code == 200


def test_removed_teammate_loses_access_and_can_rejoin_with_their_password(client, db, sent):
    job_id = post_job(client, 'QA Engineer')
    join(client, sent, 'gone@northwind.example', 'hiring_manager', password='first-password-1')
    gone = db.query(User).filter_by(email='gone@northwind.example').first()
    client.put(f'/api/v1/hr/jobs/{job_id}/team', headers=headers(HR), json={'members': [{'user_id': gone.id, 'role': 'interviewer'}]})
    row = db.query(CompanyMember).filter_by(email='gone@northwind.example').first()
    version = gone.token_version or 0
    assert client.delete(f'/api/v1/hr/team/members/{row.id}', headers=headers(HR)).status_code == 200
    db.refresh(gone)
    assert gone.hr_approved is False and gone.token_version == version + 1
    assert db.query(JobTeamMember).filter_by(user_id=gone.id).count() == 0
    assert db.query(Company).count() == 1            # no new company is created for them
    # Re-invited: the existing account needs its own password.
    assert invite(client, gone.email, 'recruiter').status_code == 201
    token = sent[-1]['token']
    wrong = client.post('/api/v1/hr/team/accept', json={'token': token, 'password': 'not-it'})
    assert wrong.status_code == 401
    right = client.post('/api/v1/hr/team/accept', json={'token': token, 'password': 'first-password-1'})
    assert right.status_code == 200
    db.refresh(gone)
    assert gone.hr_approved is True


def test_new_account_needs_a_name_and_an_8_character_password(client, sent):
    assert invite(client, 'n@northwind.example', 'recruiter').status_code == 201
    token = sent[-1]['token']
    assert client.post('/api/v1/hr/team/accept', json={'token': token, 'password': 'long-enough'}).status_code == 400
    assert client.post('/api/v1/hr/team/accept', json={'token': token, 'full_name': 'N', 'password': 'short'}).status_code == 400


def test_only_admins_see_pending_invitations(client, db, sent):
    join(client, sent, 'rec2@northwind.example', 'recruiter')
    invite(client, 'pending@northwind.example', 'interviewer')
    admin_view = client.get('/api/v1/hr/team', headers=headers(HR)).json()
    rec_view = client.get('/api/v1/hr/team', headers=headers('rec2@northwind.example')).json()
    assert any(m['status'] == 'invited' for m in admin_view['members']) and admin_view['can_manage']
    assert all(m['status'] == 'active' for m in rec_view['members']) and not rec_view['can_manage']
