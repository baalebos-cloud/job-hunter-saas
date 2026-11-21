"""Help & support: requests, emails to the support inbox, staff answers, privacy."""
import io
import secrets

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db, get_read_db
from backend.app.main import app
from backend.app.models.registry import import_all_models
from backend.app.models.support import SupportMessage, SupportTicket
from backend.app.models.user import User
from backend.app.services import audit, security_events
from backend.app.services.auth_service import create_access_token

ME, OTHER, OWNER = 'me@example.com', 'other@example.com', 'owner@example.com'


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
    sent = []
    monkeypatch.setattr('backend.app.utils.email.send_account_message',
                        lambda to, subject, html, reply_to=None: sent.append((to, subject, html, reply_to)) or True)
    session.add_all([User(email=ME, full_name='Ada Obi', hashed_password=secrets.token_urlsafe(), is_verified=True),
                     User(email=OTHER, hashed_password=secrets.token_urlsafe(), is_verified=True),
                     User(email=OWNER, hashed_password=secrets.token_urlsafe(), is_verified=True, is_admin=True,
                          role='super_admin')])
    session.commit()
    yield TestClient(app), session, sent
    audit.flush()
    app.dependency_overrides.clear()
    session.close()
    engine.dispose()


def auth(email=ME):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': email})}


def png(size=(2400, 1200)):
    out = io.BytesIO()
    Image.new('RGB', size, (200, 30, 30)).save(out, format='PNG')
    return out.getvalue()


def test_signed_in_request_emails_requester_and_support_inbox(ctx):
    client, db, sent = ctx
    r = client.post('/api/v1/support/tickets', headers={**auth(), 'User-Agent': 'Mozilla/5.0 Chrome/130'},
                    data={'category': 'bug', 'subject': 'Download button <b>does nothing</b>',
                          'message': 'I click Download PDF and nothing happens.', 'page': '/optimizer'},
                    files={'screenshot': ('s.png', png(), 'image/png')})
    assert r.status_code == 201 and r.json()['number'] == 'BB-00001'
    ticket = db.query(SupportTicket).one()
    assert ticket.email == ME and ticket.page == '/optimizer' and 'Chrome' in ticket.user_agent
    assert ticket.attachment_type == 'image/webp' and max(Image.open(io.BytesIO(ticket.attachment)).size) == 1920

    to_user, to_support = sent
    assert to_user[0] == ME and 'BB-00001' in to_user[1]
    assert to_support[0] == 'support@baalebo.xyz' and to_support[3] == ME          # reply goes to the requester
    assert '<b>does nothing</b>' not in to_support[2] and '&lt;b&gt;' in to_support[2]  # user text is escaped
    assert '/optimizer' in to_support[2]

    mine = client.get('/api/v1/support/tickets', headers=auth()).json()
    assert [t['number'] for t in mine['items']] == ['BB-00001'] and mine['support_email'] == 'support@baalebo.xyz'
    assert client.get('/api/v1/support/tickets', headers=auth(OTHER)).json()['items'] == []
    assert client.get(f'/api/v1/support/tickets/{ticket.id}', headers=auth(OTHER)).status_code == 404
    assert client.get(f'/api/v1/support/tickets/{ticket.id}/attachment', headers=auth()).status_code == 200


def test_signed_out_visitor_needs_a_valid_email_and_bots_are_ignored(ctx):
    client, db, sent = ctx
    body = {'subject': 'Pricing question', 'message': 'Do you offer student discounts?'}
    assert client.post('/api/v1/support/tickets', data={**body, 'email': 'not-an-email'}).status_code == 422
    assert client.post('/api/v1/support/tickets', data={**body, 'email': 'visitor@example.org'}).status_code == 201
    assert client.post('/api/v1/support/tickets', data={**body, 'email': 'x@example.org', 'website': 'spam'}).status_code == 201
    assert db.query(SupportTicket).count() == 1 and db.query(SupportTicket).one().user_id is None
    assert client.post('/api/v1/support/tickets', data={'subject': 'Hi', 'message': 'short', 'email': 'a@example.org'}).status_code == 422
    bad = client.post('/api/v1/support/tickets', data={**body, 'email': 'v@example.org'},
                      files={'screenshot': ('x.png', b'<svg/>', 'image/png')})
    assert bad.status_code == 400


def test_staff_answer_is_emailed_and_visible_and_follow_up_reopens(ctx):
    client, db, sent = ctx
    tid = client.post('/api/v1/support/tickets', headers=auth(),
                      data={'subject': 'Cannot verify email', 'message': 'The link says it expired.'}).json()['id']
    assert client.get('/api/v1/support/admin/tickets', headers=auth()).status_code == 403     # not staff
    inbox = client.get('/api/v1/support/admin/tickets', headers=auth(OWNER), params={'status': 'open'}).json()
    assert inbox['counts'] == {'open': 1, 'answered': 0, 'solved': 0} and inbox['items'][0]['email'] == ME
    assert client.get('/api/v1/support/admin/tickets', headers=auth(OWNER), params={'q': 'BB-00001'}).json()['total'] == 1

    sent.clear()
    r = client.post(f'/api/v1/support/admin/tickets/{tid}/reply', headers=auth(OWNER),
                    json={'body': 'I have sent a fresh link.', 'solve': False})
    assert r.status_code == 200 and r.json()['status'] == 'answered'
    assert sent[0][0] == ME and 'Re: Cannot verify email' in sent[0][1]
    thread = client.get(f'/api/v1/support/tickets/{tid}', headers=auth()).json()
    assert [m['author'] for m in thread['messages']] == ['user', 'support'] and thread['status'] == 'answered'

    sent.clear()
    again = client.post(f'/api/v1/support/tickets/{tid}/messages', headers=auth(), json={'body': 'Still expired.'}).json()
    assert again['status'] == 'open' and sent[0][0] == 'support@baalebo.xyz'
    assert client.post(f'/api/v1/support/tickets/{tid}/solve', headers=auth()).json()['status'] == 'solved'
    assert client.patch(f'/api/v1/support/admin/tickets/{tid}', headers=auth(OWNER), json={'status': 'open'}).json()['status'] == 'open'


def test_rate_limit_and_erasure(ctx, monkeypatch):
    client, db, sent = ctx
    monkeypatch.setattr('backend.app.core.rate_limit.hit',
                        lambda key, limit, window: (not key.startswith('support:'), 600))
    limited = client.post('/api/v1/support/tickets', headers=auth(), data={'subject': 'Hello', 'message': 'Hello there team'})
    assert limited.status_code == 429 and 'support directly' in limited.json()['detail']

    monkeypatch.setattr('backend.app.core.rate_limit.hit', lambda key, limit, window: (True, 0))
    client.post('/api/v1/support/tickets', headers=auth(), data={'subject': 'Delete me', 'message': 'Please erase my data'})
    from backend.app.services.privacy import erase_user
    erase_user(db, db.query(User).filter_by(email=ME).one())
    assert db.query(SupportTicket).count() == 0 and db.query(SupportMessage).count() == 0
