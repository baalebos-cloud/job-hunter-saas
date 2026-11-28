"""Paid-tier editing before download, layout presets, and bulk tailoring from the profile resume."""
import io
import json

import pdfplumber
import pytest
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

from backend.app.models.resume import Resume
from backend.app.models.subscription import Subscription
from backend.app.utils.docx_export import build_docx
from backend.app.utils.pdf_generator import ResumeExportError, export_resume
from backend.test.test_resume_global_standard import long_resume, resume
from backend.test.test_scaling import AUTH, BASE, client, db, pipeline, upload  # noqa: F401


def pro(db, plan='pro', user_id=1):
    sub = db.query(Subscription).filter_by(user_id=user_id).first()
    if sub is None:
        db.add(Subscription(user_id=user_id, plan=plan, status='active'))
    else:
        sub.plan, sub.status = plan, 'active'
    db.commit()


def tailored(client):
    response = upload(client)
    assert response.status_code == 200, response.text
    return response.json()['task_id']


def text_of(pdf):
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        return '\n'.join(p.extract_text() or '' for p in doc.pages)


def test_editing_is_for_paid_plans(client, db, pipeline):
    task = tailored(client)
    denied = client.patch(f'/api/v1/resume/{task}/edit', headers=AUTH, json={'summary': 'Changed.'})
    assert denied.status_code == 403 and denied.json()['detail']['error'] == 'pro_required'


def test_edit_summary_bullets_length_and_layout(client, db, pipeline):
    task = tailored(client)
    pro(db)
    before = client.get(f'/api/v1/resume/{task}/edit', headers=AUTH).json()
    assert before['resume']['experience'][0] == {'role': 'Engineer', 'company': 'Acme', 'dates': '2021',
                                                 'bullets': ['Built Python tools.']}
    edited = client.patch(f'/api/v1/resume/{task}/edit', headers=AUTH, json={
        'summary': 'Python engineer who builds internal tools.',
        'experience': [{'bullets': ['Built Python tools for five teams.', '  ', 'Wrote the runbooks.']}],
        'max_pages': '2', 'template': 'modern'})
    assert edited.status_code == 200, edited.text
    document = edited.json()['result']['document']
    assert document['template'] == 'modern' and document['max_pages'] == 2
    assert edited.json()['resume']['experience'][0]['bullets'] == ['Built Python tools for five teams.', 'Wrote the runbooks.']
    pdf = client.get(f'/api/v1/resume/download/{task}', headers=AUTH).content
    text = text_of(pdf)
    assert 'Python engineer who builds internal tools.' in text and 'Wrote the runbooks.' in text
    assert 'Professional Summary' in text                 # modern: title-case headings
    # The Word copy follows the same edits and layout.
    word = Document(io.BytesIO(client.get(f'/api/v1/resume/download/{task}/docx', headers=AUTH).content))
    assert word.paragraphs[0].alignment == WD_ALIGN_PARAGRAPH.LEFT
    assert any(p.text == 'Wrote the runbooks.' for p in word.paragraphs)


def test_employers_titles_and_dates_cannot_be_edited(client, db, pipeline):
    task = tailored(client)
    pro(db)
    r = client.patch(f'/api/v1/resume/{task}/edit', headers=AUTH,
                     json={'experience': [{'bullets': ['x'], 'company': 'Google', 'role': 'CTO', 'dates': '2010'}]})
    assert r.status_code == 200
    record = db.query(Resume).filter(Resume.filename == f'optimized_{task}.pdf').one()
    role = json.loads(record.parsed_data)['experience'][0]
    assert (role['company'], role['role'], role['dates']) == ('Acme', 'Engineer', '2021')


@pytest.mark.parametrize('payload, status', [
    ({'experience': []}, 422),                                         # every role must be sent
    ({'experience': [{'bullets': ['x' * 601]}]}, 422),
    ({'summary': 'x' * 1501}, 422),
    ({'max_pages': '3'}, 400),
    ({'template': 'fancy'}, 400),
])
def test_bad_edits_are_refused(client, db, pipeline, payload, status):
    task = tailored(client)
    pro(db)
    assert client.patch(f'/api/v1/resume/{task}/edit', headers=AUTH, json=payload).status_code == status


def test_edits_cannot_add_branding_or_notes(client, db, pipeline):
    task = tailored(client)
    pro(db)
    r = client.patch(f'/api/v1/resume/{task}/edit', headers=AUTH, json={
        'summary': 'Python engineer. Optimized by Baalebos AI. ATS score: 98%'})
    assert r.status_code == 200
    text = text_of(client.get(f'/api/v1/resume/download/{task}', headers=AUTH).content)
    assert 'Baalebos' not in text and 'ATS score' not in text


def test_only_the_owner_can_edit(client, db, pipeline):
    from backend.app.services.auth_service import create_access_token
    from backend.app.models.user import User
    task = tailored(client)
    db.add(User(email='b@example.com', full_name='B', hashed_password='x', is_verified=True))
    db.commit()
    pro(db, user_id=2)
    other = {'Authorization': 'Bearer ' + create_access_token({'sub': 'b@example.com'})}
    assert client.patch(f'/api/v1/resume/{task}/edit', headers=other, json={'summary': 'x'}).status_code == 404
    assert client.get(f'/api/v1/resume/{task}/edit', headers=other).status_code == 404


@pytest.mark.parametrize('template', ['classic', 'modern', 'compact'])
def test_every_layout_is_ats_safe(template):
    result = export_resume(resume(), region='US', template=template)
    with pdfplumber.open(io.BytesIO(result.pdf)) as doc:
        assert all(p.find_tables() == [] and not p.images for p in doc.pages)
    assert result.template == template and result.info()['template'] == template
    text = text_of(result.pdf)
    assert ('PROFESSIONAL EXPERIENCE' in text) is (template != 'modern')


def test_compact_fits_more_on_one_page():
    classic = export_resume(long_resume(), region='US', template='classic')
    compact = export_resume(long_resume(), region='US', template='compact')
    assert compact.layout == 'compact' and len(compact.condensed_items) <= len(classic.condensed_items)


def test_unknown_layout_is_refused():
    with pytest.raises(ResumeExportError):
        export_resume(resume(), template='fancy')


def test_word_layouts():
    modern = Document(io.BytesIO(build_docx(resume(), 'US', template='modern')))
    classic = Document(io.BytesIO(build_docx(resume(), 'US')))
    assert modern.paragraphs[0].alignment == WD_ALIGN_PARAGRAPH.LEFT
    assert classic.paragraphs[0].alignment == WD_ALIGN_PARAGRAPH.CENTER
    assert 'Professional Experience' in [p.text for p in modern.paragraphs]


def test_bulk_can_use_the_profile_resume(client, db, pipeline):
    from backend.app.models.job import Job
    from backend.app.models.user import ProfileResume
    pro(db, 'enterprise')
    job = Job(title='Platform Engineer', company='Contoso', description='We need Python and Terraform skills for this '
              'platform engineering role, building internal tools.', is_active=True)
    db.add(job)
    db.commit()
    missing = client.post('/api/v1/resume/bulk', headers=AUTH, data={'job_ids': str(job.id), 'use_profile_resume': 'true'})
    assert missing.status_code == 400 and 'no resume on your profile' in missing.json()['detail']
    pdf = export_resume(BASE).pdf
    db.add(ProfileResume(user_id=1, filename='cv.pdf', content=pdf, size_bytes=len(pdf)))
    db.commit()
    started = client.post('/api/v1/resume/bulk', headers=AUTH,
                          data={'job_ids': str(job.id), 'use_profile_resume': 'true', 'max_pages': '2', 'region': 'UK'})
    assert started.status_code == 202 and started.json()['count'] == 1
    status = client.get(f"/api/v1/resume/bulk/{started.json()['batch_id']}", headers=AUTH).json()
    assert [i['status'] for i in status['items']] == ['completed']
    record = db.query(Resume).filter(Resume.status == 'completed').order_by(Resume.id.desc()).first()
    assert record.analysis_data['document']['max_pages'] == 2 and record.analysis_data['document']['region'] == 'UK'
