"""Application forms on jobs posted on Baalebos: employers choose what to ask per
job, candidates' answers are checked and stored as a snapshot, and employers see
exactly what was sent."""
import pytest

from backend.app.models.application import Application
from backend.app.models.job import Job
from backend.app.models.resume import Resume
from backend.app.models.user import User
from backend.app.services.application_form import FormError, normalize_form, validate_answers
from backend.test.test_platform_quality import db, client, headers  # noqa: F401

HR = 'hr@example.com'
DETAILS = {'full_name': 'Ada Candidate', 'phone': '+234 801 555 0101', 'country': 'Nigeria'}
FORM = {'standard': {'cover_letter': 'optional', 'work_authorization': 'required', 'experience_years': 'required',
                     'portfolio': 'off'},
        'authorization_country': 'United Kingdom',
        'questions': [
            {'label': 'Have you run Kubernetes in production?', 'type': 'yes_no', 'required': True},
            {'label': 'Which cloud do you know best?', 'type': 'single_choice', 'options': ['AWS', 'GCP', 'Azure', 'AWS'],
             'required': True},
            {'label': 'Which on-call tools have you used?', 'type': 'multi_choice', 'options': ['PagerDuty', 'Opsgenie']},
            {'label': 'Earliest start date', 'type': 'date'},
            {'label': 'Link to a talk or write-up', 'type': 'url'}]}


def post_job(client, form=FORM, **extra):
    body = {'title': 'Senior DevOps Engineer', 'company': 'Northwind', 'location': 'London',
            'description': 'Kubernetes and Terraform on AWS.', 'application_form': form, **extra}
    return client.post('/api/v1/hr/jobs', json=body, headers=headers(HR))


def tailored(db, job_id, name='mine'):
    db.add(Resume(owner_id=2, filename=f'optimized_{name}.pdf', content=b'%PDF', analysis_data={'job_id': job_id, 'overall_score': 80}))
    db.commit()


def ids(client, job_id):
    return {f['label']: f['id'] for f in client.get(f'/api/v1/jobs/{job_id}/application-form', headers=headers()).json()['fields']}


def good_answers(q):
    return {'std_work_authorization': 'yes', 'std_experience_years': '6', q['Have you run Kubernetes in production?']: 'no',
            q['Which cloud do you know best?']: 'GCP', q['Which on-call tools have you used?']: ['Opsgenie'],
            q['Earliest start date']: '2027-01-15'}


def test_employer_builds_a_form_per_job_and_the_candidate_sees_it(client, db):
    res = post_job(client)
    assert res.status_code == 200
    job_id = res.json()['job_id']
    form = client.get('/api/v1/hr/jobs', headers=headers(HR)).json()[0]['application_form']
    assert form['questions'][1]['options'] == ['AWS', 'GCP', 'Azure']          # duplicate choice dropped
    body = client.get(f'/api/v1/jobs/{job_id}/application-form', headers=headers()).json()
    labels = [f['label'] for f in body['fields']]
    assert labels[:3] == ['Cover letter', 'Years of relevant experience', 'Are you authorised to work in United Kingdom?']
    assert 'Portfolio or GitHub link' not in labels and len(labels) == 8
    assert body['internal'] is True and body['profile']['email'] == 'candidate@example.com'


def test_a_complete_application_is_stored_as_a_snapshot_and_shown_to_the_employer(client, db, monkeypatch):
    sent = []
    monkeypatch.setattr('backend.app.services.support._deliver', lambda *a, **k: sent.append(a) or True)
    job_id = post_job(client).json()['job_id']
    tailored(db, job_id)
    q = ids(client, job_id)
    res = client.post(f'/api/v1/jobs/{job_id}/apply', headers=headers(), json={
        'resume_id': 'mine', 'details': DETAILS, 'answers': good_answers(q), 'consent': True, 'save_to_profile': True})
    assert res.status_code == 200 and res.json()['status'] == 'submitted_internal'
    app = db.query(Application).one()
    assert app.applicant_details == {**DETAILS, 'email': 'candidate@example.com'}
    by_label = {a['label']: a['value'] for a in app.answers}
    assert by_label['Years of relevant experience'] == 6 and by_label['Which on-call tools have you used?'] == ['Opsgenie']
    assert db.get(User, 2).phone == DETAILS['phone']                            # saved to profile on request
    assert sent and sent[0][0] == 'candidate@example.com' and 'GCP' in sent[0][2]

    # The employer edits the form afterwards: the application keeps what was sent.
    assert client.put(f'/api/v1/hr/jobs/{job_id}/application-form', headers=headers(HR),
                      json={'questions': [{'label': 'A brand new question', 'type': 'short_text'}]}).status_code == 200
    seen = client.get(f'/api/v1/hr/jobs/{job_id}/applications', headers=headers(HR)).json()[0]
    assert seen['applicant_name'] == 'Ada Candidate' and seen['details']['phone'] == DETAILS['phone']
    assert [a['label'] for a in seen['answers']][2] == 'Are you authorised to work in United Kingdom?'
    assert 'A brand new question' in [f['label'] for f in client.get(f'/api/v1/jobs/{job_id}/application-form', headers=headers()).json()['fields']]


def test_missing_or_invalid_answers_are_reported_per_field_and_nothing_is_saved(client, db):
    job_id = post_job(client).json()['job_id']
    tailored(db, job_id)
    q = ids(client, job_id)
    bad = {**good_answers(q), 'std_experience_years': '99', q['Which cloud do you know best?']: 'Oracle',
           q['Link to a talk or write-up']: 'javascript:alert(1)', q['Earliest start date']: '2027-02-31'}
    del bad[q['Have you run Kubernetes in production?']]
    res = client.post(f'/api/v1/jobs/{job_id}/apply', headers=headers(),
                      json={'resume_id': 'mine', 'details': {**DETAILS, 'phone': 'call me'}, 'answers': bad})
    assert res.status_code == 422
    fields = res.json()['detail']['fields']
    assert set(fields) == {'std_experience_years', q['Which cloud do you know best?'], q['Link to a talk or write-up'],
                           q['Earliest start date'], q['Have you run Kubernetes in production?'], 'phone', 'consent'}
    assert db.query(Application).count() == 0


def test_only_the_posting_employer_can_change_the_form(client, db):
    job_id = post_job(client).json()['job_id']
    other = User(email='other-hr@example.com', hashed_password='x', is_hr=True, is_verified=True, hr_approved=True)
    db.add(other); db.commit()
    assert client.put(f'/api/v1/hr/jobs/{job_id}/application-form', headers=headers('other-hr@example.com'), json={}).status_code == 404
    assert client.put(f'/api/v1/hr/jobs/{job_id}/application-form', headers=headers(), json={}).status_code == 403


def test_jobs_posted_before_forms_existed_use_the_default_form(client, db):
    job = Job(title='Python', company='Employer', description='Python required.', hr_user_id=3, posted_by_hr=True, is_active=True)
    db.add(job); db.commit()
    fields = client.get(f'/api/v1/jobs/{job.id}/application-form', headers=headers()).json()['fields']
    assert [(f['label'], f['required']) for f in fields] == [('Cover letter', False), ('LinkedIn profile', False)]


def test_external_jobs_have_no_form(client, db):
    job = Job(title='Ops', company='Elsewhere', url='https://example.com/apply', is_active=True)
    db.add(job); db.commit()
    body = client.get(f'/api/v1/jobs/{job.id}/application-form', headers=headers()).json()
    assert body['internal'] is False and body['fields'] == []


@pytest.mark.parametrize('form, message', [
    ({'questions': [{'label': 'Pick one', 'type': 'single_choice', 'options': ['Only']}]}, 'two choices'),
    ({'questions': [{'label': 'x', 'type': 'short_text'}]}, 'at least 3'),
    ({'questions': [{'label': 'Same question', 'type': 'short_text'}] * 2}, 'repeats'),
    ({'questions': [{'label': f'Question {i}', 'type': 'short_text'} for i in range(21)]}, 'up to 20'),
    ({'questions': [{'label': 'Upload file', 'type': 'file'}]}, 'unknown answer type'),
    ({'standard': {'work_authorization': 'required'}}, 'which country'),
    ({'standard': {'shoe_size': 'required'}}, 'Unknown standard field'),
])
def test_invalid_forms_are_refused_with_a_clear_reason(client, form, message):
    res = post_job(client, form=form)
    assert res.status_code == 422 and message in res.json()['detail']
    with pytest.raises(ValueError, match=message):
        normalize_form(form)


def test_markup_in_questions_and_answers_is_neutralised():
    form = normalize_form({'questions': [{'label': '<script>x</script>Your <b>GitHub</b> handle?', 'type': 'short_text', 'required': True}]})
    assert form['questions'][0]['label'] == 'Your GitHub handle?'
    snapshot = validate_answers(form, {form['questions'][0]['id']: '<img src=x onerror=alert(1)>octocat'})
    assert snapshot[-1]['value'] == 'octocat'
    with pytest.raises(FormError):
        validate_answers(form, {})
