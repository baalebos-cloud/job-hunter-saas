"""Job board API: filters, employer jobs first, resume match, and the owner's clear action."""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db, get_read_db
from backend.app.main import app
from backend.app.models.job import Job
from backend.app.models.registry import import_all_models
from backend.app.models.resume import Resume
from backend.app.models.user import User
from backend.app.services import security_events
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
    now = datetime.utcnow()
    session.add_all([
        User(email='owner@example.com', hashed_password='x', is_verified=True, role='super_admin', is_admin=True),
        User(email='cand@example.com', hashed_password='x', is_verified=True),
        Job(title='Senior DevOps Engineer', company='Contoso', location='Remote · Europe', category='DevOps Engineer',
            work_type='remote', url='https://a/1', source='Greenhouse', is_active=True, published_at=now - timedelta(days=1),
            skills=['Kubernetes', 'Terraform', 'AWS', 'Helm'], salary_range='$90k–$120k / year'),
        Job(title='Data Engineer', company='Fabrikam', location='London, UK', category='Data Engineer', work_type='hybrid',
            url='https://a/2', source='Lever', is_active=True, published_at=now - timedelta(days=10),
            skills=['Python', 'SQL', 'Airflow']),
        Job(title='Platform Engineer', company='Northwind', location='Lagos', category='DevOps Engineer',
            description='We use Kubernetes, Terraform and AWS daily.', is_active=True, posted_by_hr=True),
        Job(title='Closed role', company='Old', url='https://a/3', is_active=False),
    ])
    session.commit()
    yield session
    app.dependency_overrides.clear()
    session.close()
    engine.dispose()


def bearer(email):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': email})}


def test_board_lists_active_jobs_with_employer_jobs_first_and_filters(db):
    client = TestClient(app)
    body = client.get('/api/v1/jobs/board').json()
    assert body['total'] == 3 and body['personalised'] is False
    assert [j['title'] for j in body['items']] == ['Platform Engineer', 'Senior DevOps Engineer', 'Data Engineer']
    first = body['items'][0]
    assert first['is_employer'] and first['source'] == 'Baalebos' and 'Kubernetes' in first['skills']   # skills computed
    assert [j['title'] for j in client.get('/api/v1/jobs/board?work_type=hybrid').json()['items']] == ['Data Engineer']
    assert [j['title'] for j in client.get('/api/v1/jobs/board?region=uk').json()['items']] == ['Data Engineer']
    assert client.get('/api/v1/jobs/board?category=devops&has_salary=true').json()['total'] == 1
    assert client.get('/api/v1/jobs/board?posted_within=3').json()['total'] == 2   # employer jobs always included
    assert client.get('/api/v1/jobs/board?q=fabrikam').json()['items'][0]['company'] == 'Fabrikam'


def test_board_scores_jobs_against_the_users_resume(db):
    cand = db.query(User).filter_by(email='cand@example.com').one()
    db.add(Resume(owner_id=cand.id, filename='cv.pdf', parsed_data='Kubernetes, Terraform and AWS on EKS. Python.'))
    db.commit()
    body = TestClient(app).get('/api/v1/jobs/board', headers=bearer('cand@example.com')).json()
    assert body['personalised'] is True
    devops = next(j for j in body['items'] if j['title'] == 'Senior DevOps Engineer')
    assert devops['match'] == {'score': 75, 'matched': ['Kubernetes', 'Terraform', 'AWS'], 'missing': ['Helm']}
    detail = TestClient(app).get(f"/api/v1/jobs/board/{devops['id']}", headers=bearer('cand@example.com')).json()
    assert detail['match']['score'] == 75 and 'description' in detail
    assert TestClient(app).get('/api/v1/jobs/board/999').status_code == 404


def test_owner_can_clear_scraped_jobs(db, monkeypatch):
    monkeypatch.setenv('ADMIN_2FA_REQUIRED', 'false')
    monkeypatch.setattr('backend.app.routes.admin._refresh_jobs_in_background', lambda: None)
    client = TestClient(app)
    assert client.post('/api/v1/admin/jobs/clear-scraped', json={'confirm': 'yes'},
                       headers=bearer('owner@example.com')).status_code == 400
    assert client.post('/api/v1/admin/jobs/clear-scraped', json={'confirm': 'CLEAR JOBS'},
                       headers=bearer('cand@example.com')).status_code == 403
    r = client.post('/api/v1/admin/jobs/clear-scraped', json={'confirm': 'CLEAR JOBS', 'refresh': True},
                    headers=bearer('owner@example.com'))
    assert r.status_code == 200 and r.json() == {'deleted': 3, 'closed': 0, 'kept_employer_jobs': 1, 'refreshing': True}
    assert [j.title for j in db.query(Job)] == ['Platform Engineer']
