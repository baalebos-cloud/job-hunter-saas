"""Resume Studio: saving the hand-edited resume, starting points copied without
adding anything, and the document's place in data export and erasure."""
import json

from backend.app.models import audit, security_event, support, team  # noqa: F401  (tables used by export and erasure)
from backend.app.models.resume import Resume
from backend.app.models.studio import StudioDocument
from backend.app.models.user import Education, Experience, OtherSkill, User
from backend.app.services import studio
from backend.test.test_platform_quality import db, client, headers  # noqa: F401

DOC = {
    'fullName': 'Oluwadare Jayeola', 'headline': 'Cloud DevOps Engineer', 'location': 'Lagos, Nigeria',
    'email': 'candidate@example.com', 'summary': 'Cloud DevOps engineer.', 'coreCompetencies': ['CI/CD', 'Kubernetes'],
    'technicalSkills': [{'label': 'Cloud', 'items': ['AWS', 'GCP']}],
    'experience': [{'role': 'DevOps Engineer', 'company': 'Acme', 'location': 'Lagos', 'dates': '2022 – Present',
                    'bullets': ['Cut deployment failures by 30%.']}],
    'education': [], 'certifications': [{'name': 'AWS Cloud Practitioner', 'issuer': 'AWS', 'date': '2024'}],
    'unknown_key': 'dropped',
}
TAILORED = {
    'name': 'Jordan Lee', 'title': 'Site Reliability Engineer',
    'contact': 'jordan@example.org | +234 801 555 0101 | linkedin.com/in/jordanlee | github.com/jordan | Lagos, Nigeria',
    'summary': 'SRE running Kubernetes on AWS.',
    'skills': {'Cloud': ['AWS', 'EKS'], 'Observability': ['Prometheus']},
    'experience': [{'role': 'DevOps Engineer', 'company': 'Litware', 'location': '', 'dates': '2022 - Present',
                    'bullets': ['Migrated 40 services to EKS.'], 'environment': ''}],
    'projects': [{'title': 'Homelab', 'subtitle': 'k3s cluster', 'tech': 'k3s, Ansible', 'bullets': ['Runs 6 nodes.']}],
    'education': [{'degree': 'B.Sc. Computer Science', 'institution': 'University of Lagos', 'year': '2018'}],
    'certifications': ['CKA'], 'additional_information': '',
}


def test_save_and_load_round_trip(client, db):
    assert client.get('/api/v1/studio', headers=headers()).json()['document'] is None
    saved = client.put('/api/v1/studio', headers=headers(), json={'data': DOC, 'paper': 'Letter', 'preset': 'cloud'})
    assert saved.status_code == 200
    loaded = client.get('/api/v1/studio', headers=headers()).json()
    assert loaded['paper'] == 'Letter' and loaded['preset'] == 'cloud'
    assert loaded['document']['fullName'] == 'Oluwadare Jayeola' and 'unknown_key' not in loaded['document']
    assert loaded['document']['experience'][0]['bullets'] == ['Cut deployment failures by 30%.']
    assert loaded['document']['projects'] == [] and loaded['document']['phone'] == ''


def test_each_person_sees_only_their_own_document(client, db):
    client.put('/api/v1/studio', headers=headers(), json={'data': DOC})
    assert client.get('/api/v1/studio', headers=headers('hr@example.com')).json()['document'] is None
    assert client.delete('/api/v1/studio', headers=headers('hr@example.com')).json() == {'deleted': False}
    assert client.delete('/api/v1/studio', headers=headers()).json() == {'deleted': True}
    assert client.get('/api/v1/studio', headers=headers()).json()['document'] is None


def test_requires_sign_in(client):
    assert client.get('/api/v1/studio').status_code == 401
    assert client.put('/api/v1/studio', json={'data': DOC}).status_code == 401


def test_bad_shapes_and_sizes_are_refused(client, db):
    for bad in ({**DOC, 'summary': 'x' * 3001}, {**DOC, 'experience': 'not a list'},
                {**DOC, 'coreCompetencies': [1, 2]}, {**DOC, 'experience': [{'bullets': ['x'] * 16}]},
                {**DOC, 'projects': [{'title': 't'}] * 13}):
        assert client.put('/api/v1/studio', headers=headers(), json={'data': bad}).status_code == 422
    assert client.put('/api/v1/studio', headers=headers(), json={'data': DOC, 'paper': 'A3'}).status_code == 422
    assert db.get(StudioDocument, db.query(User).filter_by(email='candidate@example.com').one().id) is None


def test_tailored_resume_is_copied_without_additions():
    data = studio.from_tailored(TAILORED)
    assert (data['fullName'], data['headline']) == ('Jordan Lee', 'Site Reliability Engineer')
    assert data['email'] == 'jordan@example.org' and data['phone'] == '+234 801 555 0101'
    assert data['linkedin'] == 'linkedin.com/in/jordanlee' and data['github'] == 'github.com/jordan'
    assert data['location'] == 'Lagos, Nigeria' and data['portfolio'] == ''
    assert data['technicalSkills'] == [{'label': 'Cloud', 'items': ['AWS', 'EKS']}, {'label': 'Observability', 'items': ['Prometheus']}]
    assert data['projects'] == [{'title': 'Homelab — k3s cluster', 'tech': 'k3s, Ansible', 'description': 'Runs 6 nodes.'}]
    assert data['education'][0]['date'] == '2018' and data['certifications'] == [{'name': 'CKA', 'issuer': '', 'date': ''}]
    # Nothing the source does not have: no competencies, soft skills or invented facts.
    assert data['coreCompetencies'] == [] and data['softSkills'] == []
    text = json.dumps(data)
    assert 'Google' not in text and 'Azure' not in text


def test_profile_and_tailored_sources(client, db):
    user = db.query(User).filter_by(email='candidate@example.com').one()
    user.city, user.country, user.phone, user.about = 'Lagos', 'Nigeria', '+234 801 000 0000', 'DevOps engineer.'
    db.add_all([Experience(user_id=user.id, title='DevOps Engineer', company='Acme', start_date='Jan 2022', end_date=None,
                           description='- Built CI/CD pipelines.\n- Ran Kubernetes.'),
                Education(user_id=user.id, degree='B.Sc.', institution='UNILAG', end_date='2018'),
                OtherSkill(user_id=user.id, name='Terraform')])
    db.add(Resume(owner_id=user.id, filename='optimized_abc123.pdf', status='completed', content=b'%PDF',
                  parsed_data=json.dumps(TAILORED), analysis_data={'job_title': 'SRE', 'job_description': 'Run EKS.'}))
    db.add(Resume(owner_id=db.query(User).filter_by(email='hr@example.com').one().id, filename='optimized_other.pdf',
                  status='completed', content=b'%PDF', parsed_data=json.dumps(TAILORED)))
    db.commit()
    profile = client.get('/api/v1/studio/sources/profile', headers=headers()).json()['data']
    assert profile['fullName'] == 'Candidate' and profile['location'] == 'Lagos, Nigeria'
    assert profile['experience'][0]['dates'] == 'Jan 2022 – Present'
    assert profile['experience'][0]['bullets'] == ['Built CI/CD pipelines.', 'Ran Kubernetes.']
    assert {'label': 'Skills', 'items': ['Terraform']} in profile['technicalSkills']
    sources = client.get('/api/v1/studio/sources', headers=headers()).json()
    assert [s['task_id'] for s in sources['tailored']] == ['abc123']
    copied = client.get('/api/v1/studio/sources/resume/abc123', headers=headers()).json()
    assert copied['data']['headline'] == 'Site Reliability Engineer' and copied['job_description'] == 'Run EKS.'
    assert client.get('/api/v1/studio/sources/resume/other', headers=headers()).status_code == 404


def test_studio_document_is_exported_and_erased(client, db):
    from backend.app.services.privacy import erase_user, export_user_data
    client.put('/api/v1/studio', headers=headers(), json={'data': DOC})
    user = db.query(User).filter_by(email='candidate@example.com').one()
    assert export_user_data(db, user)['resume_studio']['resume']['fullName'] == 'Oluwadare Jayeola'
    counts = erase_user(db, user)
    assert counts['deleted']['studio_documents'] == 1 and db.query(StudioDocument).count() == 0
