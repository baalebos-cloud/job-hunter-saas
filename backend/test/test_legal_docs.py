"""Legal pages: starter drafts until published, versioned publishing, and only
legal:manage (with two-step verification) may edit."""
import secrets
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models.registry import import_all_models
from backend.app.models.user import User
from backend.app.services import legal_docs, security_events
from backend.app.services.auth_service import create_access_token

LEGAL, SEEKER = 'counsel@example.com', 'seeker@example.com'


@pytest.fixture
def client(monkeypatch):
    import_all_models()
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add_all([User(email=LEGAL, hashed_password=secrets.token_urlsafe(), is_verified=True, role='legal_counsel',
                     totp_enabled_at=datetime.utcnow()),
                User(email=SEEKER, hashed_password=secrets.token_urlsafe(), is_verified=True)])
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    monkeypatch.setattr(security_events, '_session', Session)
    monkeypatch.setattr('backend.app.database.SessionLocal', Session)
    yield TestClient(app)
    app.dependency_overrides.clear(); db.close(); engine.dispose()


def auth(email):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': email})}


def test_every_document_has_a_starter_draft_shown_as_draft(client):
    docs = client.get('/api/v1/legal').json()
    assert [d['slug'] for d in docs] == list(legal_docs.DOCS) and all(d['draft'] for d in docs)
    privacy = client.get('/api/v1/legal/privacy').json()
    assert privacy['title'] == 'Privacy Policy' and 'Nigeria Data Protection Act 2023' in privacy['body']
    assert client.get('/api/v1/legal/secret').status_code == 404


def test_counsel_edits_a_draft_then_publishes_numbered_versions(client):
    doc = client.get('/api/v1/console/legal', headers=auth(LEGAL)).json()[0]
    body = doc['body'].replace('[Company legal name]', 'Baalebos Technologies Ltd')
    saved = client.put('/api/v1/console/legal/terms', json={'title': doc['title'], 'body': body}, headers=auth(LEGAL)).json()
    assert saved['has_draft'] and saved['published_version'] is None
    assert client.get('/api/v1/legal/terms').json()['draft'] is True                 # not public until published
    published = client.post('/api/v1/console/legal/terms/publish', json={'note': 'Company name added'}, headers=auth(LEGAL)).json()
    assert published['published_version'] == 1 and not published['has_draft']
    public = client.get('/api/v1/legal/terms').json()
    assert public['draft'] is False and 'Baalebos Technologies Ltd' in public['body'] and public['version'] == 1
    assert client.post('/api/v1/console/legal/terms/publish', json={}, headers=auth(LEGAL)).status_code == 409   # nothing to publish
    client.put('/api/v1/console/legal/terms', json={'title': 'Terms & Conditions', 'body': body + '\n\nNew clause.'}, headers=auth(LEGAL))
    history = client.post('/api/v1/console/legal/terms/publish', json={}, headers=auth(LEGAL)).json()['history']
    assert [h['version'] for h in history] == [2, 1] and history[1]['note'] == 'Company name added'


def test_only_legal_staff_can_edit(client):
    assert client.get('/api/v1/console/legal', headers=auth(SEEKER)).status_code == 403
    assert client.put('/api/v1/console/legal/terms', json={'title': 'x', 'body': 'y'}, headers=auth(SEEKER)).status_code == 403
    assert client.put('/api/v1/console/legal/terms', json={'title': 'Terms', 'body': 'too short'},
                      headers=auth(LEGAL)).status_code == 422
