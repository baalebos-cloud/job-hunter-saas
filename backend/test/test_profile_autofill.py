"""Resume kept on the profile, filling the profile from it (review first, nothing
invented, nothing overwritten unless ticked), and multi-select sign-up choices."""
from types import SimpleNamespace

import pytest

from backend.app.models.user import Experience, OtherSkill, User
from backend.app.services import profile_autofill
from backend.app.utils.pdf_generator import export_resume
from backend.test.test_platform_quality import db, client, headers  # noqa: F401

SOURCE = """Jordan Lee
DevOps Engineer
jordan.lee@example.org | +234 801 555 0101 | linkedin.com/in/jordanlee | Lagos, Nigeria
Summary
DevOps engineer running Kubernetes on AWS.
Experience
DevOps Engineer, Litware, Jan 2022 - Present
- Migrated 40 services to Kubernetes on AWS EKS.
Cloud Engineer, Adatum, 2019 - 2021
- Set up Prometheus alerting for 120 hosts.
Education
B.Sc. Computer Science, University of Lagos, 2018
Skills
AWS, Kubernetes, Terraform, Prometheus
"""
EXTRACTED = {
    'name': 'Jordan Lee', 'title': 'DevOps Engineer',
    'contact': 'jordan.lee@example.org | +234 801 555 0101 | linkedin.com/in/jordanlee | Lagos, Nigeria',
    'summary': 'DevOps engineer running Kubernetes on AWS.',
    'experience': [
        {'role': 'DevOps Engineer', 'company': 'Litware', 'location': '', 'dates': 'Jan 2022 - Present', 'environment': '',
         'bullets': ['Migrated 40 services to Kubernetes on AWS EKS.']},
        {'role': 'Cloud Engineer', 'company': 'Adatum', 'location': '', 'dates': '2019 - 2021', 'environment': '',
         'bullets': ['Set up Prometheus alerting for 120 hosts.']},
        {'role': 'Staff SRE', 'company': 'Google', 'location': '', 'dates': '2023 - 2024', 'environment': '',   # invented
         'bullets': ['Kept Search online.']}],
    'projects': [], 'skills': {'Skills': ['AWS', 'Kubernetes', 'Terraform', 'Prometheus', 'Azure']},          # Azure invented
    'education': [{'degree': 'B.Sc. Computer Science', 'institution': 'University of Lagos', 'year': '2018'}],
    'certifications': [], 'additional_information': '',
}


@pytest.fixture
def reader(monkeypatch):
    import backend.app.utils.ats_engine as engine
    monkeypatch.setattr(engine, 'extract_text_with_ocr', lambda content, filename: SOURCE)
    monkeypatch.setattr(engine, 'prepare_resume_text', lambda text, filename: text)
    monkeypatch.setattr(engine, 'extract_resume_data', lambda text: {**EXTRACTED})


def pdf():
    return export_resume({'name': 'Jordan Lee', 'title': 'DevOps Engineer', 'summary': 'DevOps engineer.',
                          'experience': [], 'skills': {}, 'education': []}).pdf


def upload(client):
    return client.post('/api/v1/profile/resume', headers=headers(), files={'file': ('Jordan_Lee.pdf', pdf(), 'application/pdf')})


def test_resume_is_kept_on_the_profile_replaced_and_removed(client, db):
    assert client.get('/api/v1/profile/resume', headers=headers()).json()['resume'] is None
    bad = client.post('/api/v1/profile/resume', headers=headers(), files={'file': ('notes.pdf', b'not a pdf', 'application/pdf')})
    assert bad.status_code == 400
    meta = upload(client).json()['resume']
    assert meta['filename'] == 'Jordan_Lee.pdf' and meta['size_bytes'] > 500 and meta['read_at'] is None
    download = client.get('/api/v1/profile/resume/file', headers=headers())
    assert download.status_code == 200 and download.content.startswith(b'%PDF') and download.headers['cache-control'] == 'private, no-store'
    assert client.delete('/api/v1/profile/resume', headers=headers()).json()['resume'] is None
    assert client.get('/api/v1/profile/resume/file', headers=headers()).status_code == 404


def test_reading_lists_only_what_the_file_says_and_what_to_fill_in(client, db, reader):
    upload(client)
    user = db.get(User, 2)
    user.full_name = 'Jordan A. Lee'; db.commit()                       # profile already has a (different) name
    body = client.post('/api/v1/profile/resume/read', headers=headers()).json()
    rows = {r['key']: r for r in body['rows']}
    assert rows['full_name']['status'] == 'keep' and rows['full_name']['current'] == 'Jordan A. Lee'
    assert rows['phone'] == {'key': 'phone', 'label': 'Phone', 'status': 'new', 'value': '+234 801 555 0101'}
    assert rows['city']['value'] == 'Lagos' and rows['country']['value'] == 'Nigeria'
    assert rows['linkedin_url']['value'] == 'https://linkedin.com/in/jordanlee'
    assert rows['experience']['count'] == 2 and not any('Google' in v for v in rows['experience']['value'])   # invented role dropped
    assert 'Azure' not in rows['skills']['value']                                                            # invented skill dropped
    assert rows['languages']['status'] == 'missing'


def test_only_ticked_items_are_saved_and_existing_values_are_kept(client, db, reader):
    upload(client)
    user = db.get(User, 2)
    user.full_name = 'Jordan A. Lee'
    db.add(Experience(user_id=2, title='DevOps Engineer', company='Litware'))          # already on the profile
    db.add(OtherSkill(user_id=2, name='aws')); db.commit()
    client.post('/api/v1/profile/resume/read', headers=headers())
    result = client.post('/api/v1/profile/resume/apply', headers=headers(),
                         json={'keys': ['phone', 'experience', 'skills', 'education', 'full_name_injected']}).json()
    assert result['applied'] == ['phone', 'experience', 'skills', 'education']
    profile = result['profile']
    assert profile['full_name'] == 'Jordan A. Lee' and profile['phone'] == '+234 801 555 0101'     # name not ticked: kept
    assert sorted((e['title'], e['company']) for e in profile['experience']) == [('Cloud Engineer', 'Adatum'), ('DevOps Engineer', 'Litware')]
    assert sorted(s['name'] for s in profile['other_skills']) == ['Kubernetes', 'Prometheus', 'Terraform', 'aws']
    assert profile['education'][0]['end_date'] == '2018'
    rows = {r['key']: r['status'] for r in client.post('/api/v1/profile/resume/read', headers=headers()).json()['rows']}
    assert rows['experience'] == 'same' and rows['phone'] == 'same'                     # read again: nothing left to add


def test_apply_needs_a_read_and_reads_are_limited(client, db, reader, monkeypatch):
    upload(client)
    assert client.post('/api/v1/profile/resume/apply', headers=headers(), json={'keys': ['phone']}).status_code == 409
    monkeypatch.setattr(profile_autofill, 'READS_PER_DAY', 0)
    r = client.post('/api/v1/profile/resume/read', headers=headers())
    assert r.status_code == 429 and 'times a day' in r.json()['detail'] and 'by hand' in r.json()['detail']


def test_tailoring_can_use_the_profile_resume(client, db):
    r = client.post('/api/v1/resume/upload', headers=headers(),
                    data={'job_title': 'Engineer', 'job_description': 'Python and Terraform skills required for this role.',
                          'use_profile_resume': 'true'})
    assert r.status_code == 400 and 'no resume on your profile' in r.json()['detail']


@pytest.mark.parametrize('contact, expected', [
    ('a@b.com | +1 (415) 555-0100 | San Francisco, United States', {'phone': '+1 (415) 555-0100', 'city': 'San Francisco', 'country': 'United States'}),
    ({'email': 'a@b.com', 'location': 'Berlin, Germany'}, {'city': 'Berlin', 'country': 'Germany'}),
    ('a@b.com', {}),
])
def test_contact_line_parsing(contact, expected):
    assert profile_autofill._contact_parts(contact) == expected


# ── Several choices at sign-up ───────────────────────────────────────────────

def signup(client, **extra):
    body = {'email': 'multi@example.org', 'password': 'Correct-Horse-9', 'full_name': 'Multi Choice', **extra}
    return client.post('/api/v1/auth/signup', json=body)


def test_signup_keeps_several_tracks_work_types_and_countries(client, db, monkeypatch):
    from backend.app.main import reset_rate_limits
    reset_rate_limits()                     # the per-network daily sign-up cap is shared across the test run
    monkeypatch.setattr('backend.app.routes.auth.send_verification_email', lambda **k: True)
    r = signup(client, career_tracks=['DevOps Engineer', ' Cloud engineer ', 'devops engineer'], work_types=['Remote', 'hybrid'],
               country='Nigeria', work_countries=['United Kingdom', 'Canada'])
    assert r.status_code == 201, r.text
    user = db.query(User).filter_by(email='multi@example.org').one()
    assert user.career_track == 'DevOps Engineer' and user.career_tracks == ['DevOps Engineer', 'Cloud engineer']
    assert user.work_types == ['remote', 'hybrid'] and user.job_alert_work_type == 'all'
    assert user.work_countries == ['United Kingdom', 'Canada']


@pytest.mark.parametrize('extra', [{'career_tracks': ['a1', 'b2', 'c3', 'd4']}, {'work_types': ['office']},
                                   {'work_countries': ['A1', 'B2', 'C3', 'D4', 'E5', 'F6']}])
def test_signup_choice_limits(client, extra):
    assert signup(client, **extra).status_code == 422


def test_job_alerts_use_every_track_and_country():
    from backend.app.services.job_automation import matches_preferences
    user = SimpleNamespace(career_track='DevOps Engineer', career_tracks=['DevOps Engineer', 'Data Engineer'],
                           job_alert_work_type='all', work_types=['remote'], country='Nigeria', work_countries=['United Kingdom'])
    job = lambda **k: SimpleNamespace(**{'is_active': True, 'title': 'Data Engineer', 'category': '', 'work_type': 'remote',
                                         'location': 'London, United Kingdom', **k})
    assert matches_preferences(job(), user)                                   # second track, second country
    assert not matches_preferences(job(work_type='onsite'), user)            # work type not chosen
    assert not matches_preferences(job(location='Berlin, Germany'), user)    # country not chosen
    assert not matches_preferences(job(title='Frontend Developer'), user)    # no chosen track
