"""Enterprise integrations API: keys (create once, hashed, revoke) and the API itself."""
import pytest

from backend.app.models.api_key import ApiKey
from backend.app.models.job import Job
from backend.app.models.subscription import Subscription
from backend.app.utils.pdf_generator import export_resume
from backend.test.test_scaling import AUTH, BASE, client, db, pipeline  # noqa: F401

JD = 'We need Python and Terraform skills for this platform engineering role, building internal tools.'
API = '/api/public/v1'


def enterprise(db):
    db.add(Subscription(user_id=1, plan='enterprise', status='active'))
    db.commit()


def new_key(client, name='CI pipeline'):
    response = client.post('/api/v1/api-keys', json={'name': name}, headers=AUTH)
    assert response.status_code == 201, response.text
    return response.json()


def bearer(key):
    return {'Authorization': f"Bearer {key['key']}"}


def resume_file():
    return {'file': ('cv.pdf', export_resume(BASE).pdf, 'application/pdf')}


def test_keys_are_enterprise_only(client, db):
    denied = client.post('/api/v1/api-keys', json={'name': 'x'}, headers=AUTH)
    assert denied.status_code == 403 and denied.json()['detail']['error'] == 'enterprise_required'
    assert client.get('/api/v1/api-keys', headers=AUTH).json()['enabled'] is False


def test_key_is_shown_once_and_stored_hashed(client, db):
    enterprise(db)
    created = new_key(client)
    assert created['key'].startswith('bb_live_') and created['prefix'] == created['key'][:12]
    stored = db.query(ApiKey).one()
    assert stored.key_hash != created['key'] and created['key'] not in (stored.prefix, stored.name)
    listed = client.get('/api/v1/api-keys', headers=AUTH).json()
    assert listed['enabled'] is True and 'key' not in listed['keys'][0]
    me = client.get(f'{API}/me', headers=bearer(created)).json()
    assert me['plan'] == 'enterprise' and me['rate_limit_per_minute'] == 60
    assert client.get(f'{API}/me', headers={'X-API-Key': created['key']}).status_code == 200


def test_up_to_five_keys_and_revoked_keys_stop_working(client, db):
    enterprise(db)
    keys = [new_key(client, f'k{i}') for i in range(5)]
    assert client.post('/api/v1/api-keys', json={'name': 'sixth'}, headers=AUTH).status_code == 400
    assert client.delete(f"/api/v1/api-keys/{keys[0]['id']}", headers=AUTH).json() == {'revoked': True}
    assert client.get(f'{API}/me', headers=bearer(keys[0])).status_code == 401
    assert client.get(f'{API}/me', headers=bearer(keys[1])).status_code == 200
    new_key(client, 'replacement')                                    # the revoked one freed a slot


@pytest.mark.parametrize('headers', [{}, {'Authorization': 'Bearer nope'}, {'X-API-Key': 'bb_live_wrong'},
                                     {'Authorization': 'Bearer ' + 'a.b.c'}])
def test_requests_without_a_valid_key_are_refused(client, db, headers):
    response = client.get(f'{API}/me', headers=headers)
    assert response.status_code == 401 and response.json()['detail']['error'] == 'invalid_api_key'


def test_session_tokens_do_not_work_on_the_api(client, db):
    enterprise(db)
    assert client.get(f'{API}/me', headers=AUTH).status_code == 401


def test_keys_stop_working_when_enterprise_ends(client, db):
    enterprise(db)
    key = new_key(client)
    db.query(Subscription).filter_by(user_id=1).one().status = 'cancelled'; db.commit()
    blocked = client.get(f'{API}/me', headers=bearer(key))
    assert blocked.status_code == 403 and blocked.json()['detail']['error'] == 'enterprise_required'


def test_sixty_requests_per_minute_per_key(client, db):
    enterprise(db)
    key = new_key(client)
    for _ in range(60):
        assert client.get(f'{API}/me', headers=bearer(key)).status_code == 200
    limited = client.get(f'{API}/me', headers=bearer(key))
    assert limited.status_code == 429 and int(limited.headers['Retry-After']) >= 1
    assert client.get(f'{API}/me', headers=bearer(new_key(client, 'other'))).status_code == 200   # per key


def test_tailor_poll_and_download(client, db, pipeline):
    enterprise(db)
    key = new_key(client)
    job = Job(title='Platform Engineer', company='Contoso', description=JD, is_active=True)
    db.add(job); db.commit()
    started = client.post(f'{API}/resumes', headers=bearer(key), data={'job_id': job.id}, files=resume_file())
    assert started.status_code == 202, started.text
    task_id = started.json()['task_id']
    assert started.headers['Location'] == f'{API}/resumes/{task_id}'
    status = client.get(f'{API}/resumes/{task_id}', headers=bearer(key)).json()
    assert status['status'] == 'completed' and status['company'] == 'Contoso' and status['job_id'] == job.id
    assert isinstance(status['match_after'], (int, float)) and status['links']['pdf'].endswith('/pdf')
    pdf = client.get(f'{API}/resumes/{task_id}/pdf', headers=bearer(key))
    assert pdf.status_code == 200 and pdf.content.startswith(b'%PDF')
    docx = client.get(f'{API}/resumes/{task_id}/docx', headers=bearer(key))
    assert docx.status_code == 200 and docx.content[:2] == b'PK'
    # The result is also in My resumes on the website.
    assert client.get('/api/v1/resume/history', headers=AUTH).json()['total'] == 1


def test_tailor_with_your_own_job_description(client, db, pipeline):
    enterprise(db)
    key = new_key(client)
    ok = client.post(f'{API}/resumes', headers=bearer(key), files=resume_file(),
                     data={'job_title': 'Data Engineer', 'job_description': JD})
    assert ok.status_code == 202
    assert client.post(f'{API}/resumes', headers=bearer(key), files=resume_file(),
                       data={'job_title': 'Data Engineer', 'job_description': 'too short'}).status_code == 400
    assert client.post(f'{API}/resumes', headers=bearer(key), files=resume_file()).status_code == 400
    assert client.post(f'{API}/resumes', headers=bearer(key), files=resume_file(), data={'job_id': 99999}).status_code == 404


def test_other_peoples_resumes_are_not_reachable(client, db, pipeline):
    from backend.app.models.resume import Resume
    enterprise(db)
    key = new_key(client)
    db.add(Resume(owner_id=2, filename='optimized_someone-else.pdf', status='completed', content=b'%PDF')); db.commit()
    assert client.get(f'{API}/resumes/someone-else', headers=bearer(key)).status_code == 404
    assert client.get(f'{API}/resumes/someone-else/pdf', headers=bearer(key)).status_code == 404


def test_search_the_job_board(client, db):
    enterprise(db)
    key = new_key(client)
    db.add_all([Job(title='Platform Engineer', company='Contoso', description=JD, is_active=True),
                Job(title='Platform Engineer', company='Contoso', description=JD, is_active=True),   # duplicate
                Job(title='Chef', company='Fabrikam', description='Cooking', is_active=True),
                Job(title='Old role', company='Litware', description=JD, is_active=False)])
    db.commit()
    found = client.get(f'{API}/jobs', params={'q': 'platform'}, headers=bearer(key)).json()
    assert found['total'] == 1 and found['items'][0]['company'] == 'Contoso'
    every = client.get(f'{API}/jobs', headers=bearer(key)).json()
    assert every['total'] == 2
    detail = client.get(f"{API}/jobs/{found['items'][0]['id']}", headers=bearer(key)).json()
    assert detail['description'] == JD
