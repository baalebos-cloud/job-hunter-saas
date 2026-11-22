"""No duplicate listings: one active job per role per company."""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db, get_read_db
from backend.app.main import app
from backend.app.models.application import Application
from backend.app.models.job import Job
from backend.app.models.registry import import_all_models
from backend.app.models.user import User
from backend.app.services import security_events
from backend.app.services.auth_service import create_access_token
from backend.app.utils.global_scraper import collapse_duplicate_jobs, dedupe_key, save_jobs_to_db


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
    yield session
    from backend.app.services import audit
    audit.flush()          # drain queued request records before the shared connection closes
    app.dependency_overrides.clear()
    session.close()
    engine.dispose()


def job(n, title, company, **extra):
    seen = datetime.utcnow() - timedelta(days=extra.pop('age', 0))
    return Job(title=title, company=company, url=f'https://jobs.example/{n}', source='Feed', is_active=True,
               first_seen_at=seen, scraped_at=seen, **extra)


def active(db):
    db.expire_all()
    return sorted((j.title, j.company) for j in db.query(Job).filter(Job.is_active == True))  # noqa: E712


def test_key_matches_the_same_role_written_differently():
    assert dedupe_key('Sr. DevOps Eng - Remote (EU)', 'Acme, Inc.') == dedupe_key('Senior DevOps Engineer', 'Acme')
    assert dedupe_key('Senior Data Scientist (LATAM)', 'Lemon.io') == dedupe_key('Senior Data Scientist', 'Lemon io')
    assert dedupe_key('DevOps Engineer', 'Acme') != dedupe_key('DevOps Engineer', 'Acme Health')   # different company
    assert dedupe_key('Data Engineer', 'Acme') != dedupe_key('Data Scientist', 'Acme')             # different role
    assert dedupe_key('Engineer', 'SA Power Networks').endswith('|sa power networks')               # suffix only at the end


def test_existing_duplicates_are_closed_keeping_the_best_listing(db):
    db.add(User(id=1, email='c@example.org', hashed_password='x', is_verified=True))
    old_copy, applied_copy, newest = (job(1, 'Senior Data Scientist', 'Lemon.io', age=9),
                                      job(2, 'Senior Data Scientist (LATAM)', 'Lemon.io', age=5),
                                      job(3, 'Sr Data Scientist', 'Lemon io', age=1))
    db.add_all([old_copy, applied_copy, newest, job(4, 'Data Engineer', 'Lemon.io'), job(5, 'Senior Data Scientist', 'Other Co')])
    db.flush()
    db.add(Application(user_id=1, job_id=applied_copy.id, status='applied'))
    db.commit()

    assert collapse_duplicate_jobs(db) == 2
    kept = db.query(Job).filter(Job.is_active == True, Job.company.like('Lemon%'), Job.title.like('%Scientist%')).one()  # noqa: E712
    assert kept.id == applied_copy.id                       # applied-to listing wins over the older one
    assert db.get(Job, old_copy.id).is_active is False      # closed, not deleted
    assert all(j.dedupe_key for j in db.query(Job))          # legacy rows get keys
    assert collapse_duplicate_jobs(db) == 0                  # idempotent


def test_employer_posting_wins_and_is_never_closed(db):
    db.add_all([job(1, 'Platform Engineer', 'Northwind', age=30),
                job(2, 'Platform Engineer', 'Northwind', posted_by_hr=True, age=1)])
    db.commit()
    collapse_duplicate_jobs(db)
    assert [(j.posted_by_hr, j.is_active) for j in db.query(Job).order_by(Job.id)] == [(False, False), (True, True)]


def test_scraper_skips_copies_and_does_not_reopen_a_closed_twin(db):
    stats = {'db_errors': 0}
    first = {'title': 'Cloud Engineer', 'company': 'Contoso', 'url': 'https://a/1', 'source': 'A'}
    assert save_jobs_to_db([first], db, stats) == 1
    assert save_jobs_to_db([{**first, 'title': 'Cloud Engineer - Remote', 'url': 'https://b/9', 'source': 'B'}], db, stats) == 0
    assert stats['duplicates'] == 1 and active(db) == [('Cloud Engineer', 'Contoso')]

    # A closed listing that reappears at its own URL stays closed while an active copy exists.
    closed = job(7, 'Cloud Engineer', 'Contoso', dedupe_key=dedupe_key('Cloud Engineer', 'Contoso'))
    closed.is_active = False
    db.add(closed); db.commit()
    save_jobs_to_db([{**first, 'url': closed.url}], db, stats)
    assert db.get(Job, closed.id).is_active is False and len(active(db)) == 1


def test_board_never_shows_two_listings_for_one_role(db):
    db.add_all([job(1, 'Backend Developer', 'Fabrikam'), job(2, 'Backend Dev', 'Fabrikam Ltd'),
                job(3, 'Backend Developer', 'Contoso')])
    db.commit()
    items = TestClient(app).get('/api/v1/jobs/board').json()
    companies = sorted(i['company'] for i in items['items'])
    assert items['total'] == 2 and companies[0] == 'Contoso' and companies[1].startswith('Fabrikam')


def test_employer_cannot_post_the_same_role_twice_and_replaces_a_scraped_copy(db):
    db.add(User(email='hr@northwind.example', hashed_password='x', is_verified=True, is_hr=True, hr_approved=True,
                company_name='Northwind'))
    db.add(job(1, 'Site Reliability Engineer', 'Northwind'))
    db.commit()
    headers = {'Authorization': 'Bearer ' + create_access_token({'sub': 'hr@northwind.example'})}
    body = {'title': 'Site Reliability Engineer', 'company': 'Northwind', 'location': 'Remote',
            'description': 'Run our Kubernetes platform.'}
    client = TestClient(app)
    assert client.post('/api/v1/hr/jobs', json=body, headers=headers).status_code == 200
    assert [(j.posted_by_hr, j.is_active) for j in db.query(Job).order_by(Job.id)] == [(False, False), (True, True)]
    again = client.post('/api/v1/hr/jobs', json={**body, 'title': 'Site Reliability Engineer - Remote'}, headers=headers)
    assert again.status_code == 409 and 'already posted' in again.json()['detail']


def test_public_stats_count_matches_the_board_and_is_cached(db, monkeypatch):
    from backend.app.routes import job_board
    monkeypatch.setattr(job_board, '_STATS_CACHE', {'at': 0.0, 'value': None})
    db.add_all([job(1, 'Backend Developer', 'Fabrikam'), job(2, 'Backend Dev', 'Fabrikam Ltd'),   # one role
                job(3, 'Data Engineer', 'Contoso'), job(4, 'Closed role', 'Old')])
    db.commit()
    db.get(Job, 4).is_active = False
    db.commit()
    client = TestClient(app)
    stats = client.get('/api/v1/jobs/stats').json()
    assert stats['open_jobs'] == client.get('/api/v1/jobs/board').json()['total'] == 2
    assert stats['updated_at'].endswith('Z')
    db.add(job(5, 'QA Engineer', 'Litware')); db.commit()
    assert client.get('/api/v1/jobs/stats').json()['open_jobs'] == 2      # cached for five minutes
