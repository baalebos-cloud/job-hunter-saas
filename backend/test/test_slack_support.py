"""Dedicated Slack support (Enterprise) and priority support requests."""
from datetime import datetime

from backend.app.models.subscription import Subscription
from backend.app.models.support import SlackRequest, SupportTicket
from backend.app.models.team import TeamMember
from backend.app.models.user import User
from backend.test.test_support import ME, OTHER, OWNER, auth, ctx  # noqa: F401


def enterprise(db, email=ME):
    user = db.query(User).filter_by(email=email).one()
    db.add(Subscription(user_id=user.id, plan='enterprise', status='active'))
    db.commit()
    return user


def ask(client, headers=None, **extra):
    body = {'company': 'Acme Talent', 'slack_plan': 'paid', 'emails': ['ops@acme.example'], **extra}
    return client.post('/api/v1/support/slack', json=body, headers=headers or auth())


def test_slack_support_is_an_enterprise_feature(ctx):
    client, db, sent = ctx
    assert client.get('/api/v1/support/slack', headers=auth()).json() == {'eligible': False, 'can_request': False,
                                                                          'request': None}
    denied = ask(client)
    assert denied.status_code == 403 and denied.json()['detail']['error'] == 'enterprise_required'
    assert not sent


def test_request_emails_support_and_the_customer(ctx):
    client, db, sent = ctx
    enterprise(db)
    made = ask(client, emails=['ops@acme.example', 'OPS@acme.example', 'cto@acme.example'], message='We use #support-baalebos')
    assert made.status_code == 201, made.text
    body = made.json()
    assert body['status'] == 'requested' and body['emails'] == [ME, 'ops@acme.example', 'cto@acme.example']
    to_customer, to_support = sent
    assert to_customer[0] == ME and 'Slack support request' in to_customer[1]
    assert to_support[0] == 'support@baalebo.xyz' and to_support[1].startswith('[Priority] Slack channel request')
    assert to_support[3] == ME and 'cto@acme.example' in to_support[2] and '/admin?tab=slack' in to_support[2]
    # One open request per account.
    assert ask(client).status_code == 409
    assert client.get('/api/v1/support/slack', headers=auth()).json()['request']['company'] == 'Acme Talent'


def test_validation(ctx):
    client, db, _ = ctx
    enterprise(db)
    assert ask(client, emails=['not-an-email']).status_code == 422
    assert ask(client, emails=[f'p{i}@acme.example' for i in range(10)]).status_code == 422   # 11 with the requester
    assert ask(client, company='A').status_code == 422
    assert ask(client, slack_plan='enterprise-grid').status_code == 422


def test_owner_marks_invited_and_the_customer_is_emailed(ctx):
    client, db, sent = ctx
    enterprise(db)
    rid = ask(client).json()['id']
    sent.clear()
    assert client.get('/api/v1/support/admin/slack', headers=auth()).status_code == 403             # not staff
    queue = client.get('/api/v1/support/admin/slack', headers=auth(OWNER)).json()
    assert queue['counts']['requested'] == 1 and queue['items'][0]['slack_plan_label'] == 'Paid Slack plan'
    missing = client.patch(f'/api/v1/support/admin/slack/{rid}', headers=auth(OWNER), json={'status': 'invited'})
    assert missing.status_code == 422                                                              # channel name first
    done = client.patch(f'/api/v1/support/admin/slack/{rid}', headers=auth(OWNER),
                        json={'status': 'invited', 'channel_name': '#acme-baalebos', 'staff_note': 'Hi <team>!'}).json()
    assert done['status'] == 'invited' and done['channel_name'] == 'acme-baalebos'
    (to, subject, html, _), = sent
    assert to == ME and 'ready' in subject and '#acme-baalebos' in html and '&lt;team&gt;' in html
    client.patch(f'/api/v1/support/admin/slack/{rid}', headers=auth(OWNER), json={'status': 'connected'})
    assert len(sent) == 1                                                                           # no second email
    mine = client.get('/api/v1/support/slack', headers=auth()).json()['request']
    assert mine['status'] == 'connected' and mine['staff_note'] == 'Hi <team>!' and 'message' not in mine
    # A closed request lets the customer ask again.
    client.patch(f'/api/v1/support/admin/slack/{rid}', headers=auth(OWNER), json={'status': 'closed'})
    assert ask(client).status_code == 201


def test_team_members_see_the_teams_channel_but_only_the_owner_requests(ctx):
    client, db, _ = ctx
    owner = enterprise(db)
    member = db.query(User).filter_by(email=OTHER).one()
    db.add(TeamMember(owner_id=owner.id, email=OTHER, email_canonical=OTHER, user_id=member.id, status='active',
                      accepted_at=datetime.utcnow()))
    db.commit()
    state = client.get('/api/v1/support/slack', headers=auth(OTHER)).json()
    assert state['eligible'] is True and state['can_request'] is False
    assert ask(client, headers=auth(OTHER)).status_code == 403
    ask(client)
    assert client.get('/api/v1/support/slack', headers=auth(OTHER)).json()['request']['company'] == 'Acme Talent'


def test_enterprise_support_requests_are_tagged_priority_and_answered_first(ctx):
    client, db, sent = ctx
    client.post('/api/v1/support/tickets', headers=auth(OTHER), data={'subject': 'Free question', 'message': 'How do I start?'})
    enterprise(db)
    client.post('/api/v1/support/tickets', headers=auth(), data={'subject': 'Enterprise question', 'message': 'Bulk upload help'})
    tickets = {t.subject: t for t in db.query(SupportTicket)}
    assert tickets['Enterprise question'].priority and not tickets['Free question'].priority
    inbox = client.get('/api/v1/support/admin/tickets', headers=auth(OWNER), params={'status': 'open'}).json()['items']
    assert [t['subject'] for t in inbox] == ['Enterprise question', 'Free question'] and inbox[0]['priority'] is True
    support_alerts = [s for s in sent if s[0] == 'support@baalebo.xyz']
    assert support_alerts[-1][1].startswith('[Priority] [BB-')


def test_privacy_export_and_erasure_cover_slack_requests(ctx):
    from backend.app.services.privacy import erase_user, export_user_data
    client, db, _ = ctx
    user = enterprise(db)
    ask(client)
    assert export_user_data(db, user)['slack_support_requests'][0]['company'] == 'Acme Talent'
    erase_user(db, user)
    assert db.query(SlackRequest).count() == 0
