"""Applying with a tailored resume: a resume made for a job must be accepted for
that job (even when the scraped posting contains HTML the pipeline strips) and
refused for any other job."""
from backend.app.models.application import Application
from backend.app.models.job import Job
from backend.app.models.resume import Resume
from backend.test.test_platform_quality import db, client, headers  # noqa: F401

SCRAPED = '<p>We need a <b>Staff System Architect</b>.</p>\n<ul><li>AWS   and networking</li><li>Security</li></ul>'
CLEANED = 'We need a Staff System Architect .\nAWS and networking\nSecurity'   # what the pipeline stores


def add_job(db, **fields):
    data = dict(title='Staff System Architect', company='IonQ', description=SCRAPED,
                url='https://example.com/apply', is_active=True)
    job = Job(**{**data, **fields}); db.add(job); db.commit()
    return job


def add_resume(db, name, **analysis):
    db.add(Resume(owner_id=2, filename=f'optimized_{name}.pdf', content=b'%PDF', analysis_data={'overall_score': 82, **analysis}))
    db.commit()


def test_resume_tailored_from_the_job_is_accepted_even_when_the_posting_has_html(client, db):
    job = add_job(db)
    add_resume(db, 'fromjob', job_id=job.id, job_description=CLEANED)
    res = client.post(f'/api/v1/jobs/{job.id}/apply', json={'resume_id': 'fromjob'}, headers=headers())
    assert res.status_code == 200 and res.json()['job_url'] == job.url
    assert db.query(Application).one().ats_score == 82


def test_pasted_description_matches_after_the_same_clean_up(client, db):
    job = add_job(db)
    add_resume(db, 'pasted', job_description=CLEANED)       # no job id: tailored from a pasted description
    assert client.post(f'/api/v1/jobs/{job.id}/apply', json={'resume_id': 'pasted'}, headers=headers()).status_code == 200


def test_resume_for_another_job_is_refused(client, db):
    job, other = add_job(db), add_job(db, title='Data Engineer', company='Other', description='Spark and SQL pipelines.')
    add_resume(db, 'other', job_id=other.id, job_description='Spark and SQL pipelines.')
    add_resume(db, 'pasted-other', job_description='Spark and SQL pipelines.')
    for name in ('other', 'pasted-other'):
        res = client.post(f'/api/v1/jobs/{job.id}/apply', json={'resume_id': name}, headers=headers())
        assert res.status_code == 409 and 'Tailor the selected resume' in res.json()['detail']


def test_unfinished_resume_is_refused(client, db):
    job = add_job(db)
    db.add(Resume(owner_id=2, filename='optimized_busy.pdf', status='processing', analysis_data={'job_id': job.id}))
    db.commit()
    assert client.post(f'/api/v1/jobs/{job.id}/apply', json={'resume_id': 'busy'}, headers=headers()).status_code == 409


def test_my_resumes_lists_only_resumes_for_this_job(client, db):
    job, other = add_job(db), add_job(db, title='Data Engineer', company='Other', description='Spark and SQL pipelines.')
    add_resume(db, 'mine', job_id=job.id, job_description=CLEANED, job_title='Staff System Architect')
    add_resume(db, 'notmine', job_id=other.id)
    db.add(Resume(owner_id=1, filename='optimized_someone.pdf', content=b'%PDF', analysis_data={'job_id': job.id}))
    db.commit()
    body = client.get(f'/api/v1/jobs/{job.id}/my-resumes', headers=headers()).json()
    assert [i['task_id'] for i in body['items']] == ['mine'] and body['items'][0]['score'] == 82
    assert body['internal'] is False
