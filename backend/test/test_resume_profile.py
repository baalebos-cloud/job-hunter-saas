"""Profile photos stored in the database, Word export of the tailored resume, experience editing."""
import io
import json

import pytest
from docx import Document
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db, get_read_db
from backend.app.main import app
from backend.app.models.registry import import_all_models
from backend.app.models.resume import Resume
from backend.app.models.user import Experience, ProfilePhoto, User
from backend.app.services import security_events
from backend.app.services.auth_service import create_access_token

TAILORED = {
    'name': 'Jordan Lee', 'title': 'Senior DevOps Engineer',
    'contact': {'email': 'jordan@example.org', 'location': 'Lagos, Nigeria'},
    'additional_information': 'Date of birth: 1990-01-01\nOpen to relocation',
    'summary': 'DevOps engineer running Kubernetes on AWS.',
    'skills': {'Cloud': ['AWS', 'Kubernetes'], 'IaC': ['Terraform']},
    'experience': [{'role': 'DevOps Engineer', 'company': 'Litware', 'dates': '2022 - Present',
                    'bullets': ['Migrated 40 services to Kubernetes on AWS EKS.', 'Built Terraform modules.']}],
    'education': [{'degree': 'B.Sc. Computer Science', 'institution': 'University of Lagos', 'year': '2018'}],
}


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
    session.add_all([User(email='me@example.com', hashed_password='x', is_verified=True),
                     User(email='other@example.com', hashed_password='x', is_verified=True)])
    session.commit()
    yield session
    from backend.app.services import audit
    audit.flush()          # drain queued request records before the shared connection closes
    app.dependency_overrides.clear()
    session.close()
    engine.dispose()


def auth(email='me@example.com'):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': email})}


def image_bytes(fmt='PNG', size=(900, 600)):
    out = io.BytesIO()
    Image.new('RGB', size, (16, 185, 129)).save(out, format=fmt)
    return out.getvalue()


def test_photo_is_reencoded_stored_in_db_and_served_publicly(db):
    client = TestClient(app)
    r = client.post('/api/v1/profile/photo', headers=auth(), files={'file': ('me.png', image_bytes(), 'image/png')})
    assert r.status_code == 200
    url = r.json()['photo_url']
    assert url.startswith('/api/v1/profile/photo/') and url.endswith('.webp')
    served = client.get(url)
    assert served.status_code == 200 and served.headers['content-type'] == 'image/webp'
    assert 'immutable' in served.headers['cache-control']
    assert Image.open(io.BytesIO(served.content)).size == (512, 512)        # square, 512 px
    assert client.get('/api/v1/profile/me', headers=auth()).json()['photo_url'] == url

    # A new upload replaces the old URL; the old one stops working.
    second = client.post('/api/v1/profile/photo', headers=auth(),
                         files={'file': ('me.jpg', image_bytes('JPEG', (400, 800)), 'image/jpeg')}).json()['photo_url']
    assert second != url and client.get(url).status_code == 404 and client.get(second).status_code == 200
    assert db.query(ProfilePhoto).count() == 1

    assert client.delete('/api/v1/profile/photo', headers=auth()).json() == {'photo_url': None}
    assert client.get(second).status_code == 404


def test_photo_rejects_non_images_and_oversized_files(db):
    client = TestClient(app)
    bad = client.post('/api/v1/profile/photo', headers=auth(), files={'file': ('x.png', b'<svg></svg>', 'image/png')})
    assert bad.status_code == 400
    gif = io.BytesIO(); Image.new('RGB', (10, 10)).save(gif, format='GIF')
    assert client.post('/api/v1/profile/photo', headers=auth(),
                       files={'file': ('x.gif', gif.getvalue(), 'image/gif')}).status_code == 400
    huge = client.post('/api/v1/profile/photo', headers=auth(),
                       files={'file': ('x.png', b'0' * (5 * 1024 * 1024 + 10), 'image/png')})
    assert huge.status_code == 400 and 'Max 5 MB' in huge.json()['detail']
    assert client.get('/api/v1/profile/photo/not-a-token.webp').status_code == 404


def test_word_copy_of_the_tailored_resume(db):
    me = db.query(User).filter_by(email='me@example.com').one()
    db.add(Resume(owner_id=me.id, filename='optimized_task123.pdf', status='completed',
                  parsed_data=json.dumps(TAILORED), analysis_data={'document': {'region': 'US'}}))
    db.commit()
    client = TestClient(app)
    r = client.get('/api/v1/resume/download/task123/docx', headers=auth())
    assert r.status_code == 200 and r.headers['content-disposition'].split('filename="')[1].split('"')[0].endswith('.docx')
    text = '\n'.join(p.text for p in Document(io.BytesIO(r.content)).paragraphs)
    assert 'JORDAN LEE' in text and 'Migrated 40 services to Kubernetes on AWS EKS.' in text
    assert 'Terraform' in text and 'University of Lagos' in text
    assert '1990' not in text and 'Open to relocation' in text   # US convention: no date of birth
    assert client.get('/api/v1/resume/download/task123/docx', headers=auth('other@example.com')).status_code == 404


def test_experience_can_be_edited_by_its_owner_only(db):
    me = db.query(User).filter_by(email='me@example.com').one()
    db.add(Experience(user_id=me.id, title='Engineer', company='Litware'))
    db.commit()
    entry = db.query(Experience).one()
    client = TestClient(app)
    body = {'title': 'DevOps Engineer', 'company': 'Litware', 'start_date': 'Jan 2022', 'end_date': None,
            'description': 'Kubernetes on AWS'}
    assert client.patch(f'/api/v1/profile/experience/{entry.id}', json=body, headers=auth('other@example.com')).status_code == 404
    r = client.patch(f'/api/v1/profile/experience/{entry.id}', json=body, headers=auth())
    assert r.status_code == 200 and r.json()['title'] == 'DevOps Engineer' and r.json()['start_date'] == 'Jan 2022'
