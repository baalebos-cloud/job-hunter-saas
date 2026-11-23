"""Acceptance tests for the global-standard, ATS-friendly resume export."""
import io
import json
import shutil
import subprocess

import pdfplumber
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4, LETTER
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models.resume import Resume
from backend.app.models.subscription import Subscription
from backend.app.models.user import User
from backend.app.services.auth_service import create_access_token
from backend.app.utils.pdf_generator import (
    MIN_BODY_FONT, ResumeExportError, download_filename, export_resume, generate_optimized_resume,
    merge_confirmed_keywords, normalize_dates, normalize_resume_data, resolve_region)

YORUBA_NAME = 'Ọlájídé Ẹ̀bùn Adéwálé'
YORUBA_BULLET = 'Ṣe àkóso iṣẹ́ ìmọ̀ ẹ̀rọ fún àwọn oníbàárà ní Èkó'


def resume(**overrides):
    data = {
        'name': 'Renée Müller', 'title': 'Platform Engineer',
        'contact': 'renee@example.com | +1 555 0100 | Austin, TX, USA | linkedin.com/in/renee',
        'summary': 'Platform engineer focused on reliable Python services.',
        'experience': [{'role': 'Platform Engineer', 'company': 'Example Corp', 'dates': 'January 2021 – Present',
                        'bullets': ['Built Python deployment tooling.', 'Led R&D on caching with <5s cold starts.'],
                        'environment': ''}],
        'projects': [{'title': 'Internal CLI', 'tech': 'Python', 'bullets': ['Automated release notes.']}],
        'skills': {'Languages': ['Python', 'Bash'], 'Cloud': ['AWS']},
        'education': [{'degree': 'BSc Computer Science', 'institution': 'State University', 'year': '2019'}],
        'certifications': ['AWS Certified Cloud Practitioner'],
        'additional_information': '',
    }
    data.update(overrides)
    return data


def pdf_text(pdf: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        return '\n'.join(page.extract_text() or '' for page in doc.pages)


# ── Generator acceptance tests ───────────────────────────────────────────────

def test_route_style_improvements_never_enter_the_resume():
    improvements = [{'skill': 'Terraform', 'bullet_point': 'Added to resume: Terraform'},
                    {'skill': 'Kubernetes', 'bullet_point': 'Add Terraform and Kubernetes to your skills section'}]
    pdf = generate_optimized_resume('cv.pdf', score=87.5, improvements=improvements, resume_data=resume()).getvalue()
    text = pdf_text(pdf)
    assert 'Added to resume' not in text
    assert 'to your skills section' not in text
    assert 'Baalebos' not in text and '87.5' not in text
    metadata = PdfReader(io.BytesIO(pdf)).metadata
    assert all('baalebos' not in str(v).lower() and 'reportlab' not in str(v).lower() for v in metadata.values())
    assert metadata['/Title'] == 'Renée Müller - Resume' and metadata['/Author'] == 'Renée Müller'


def test_missing_keyword_is_not_added_unless_confirmed():
    assert 'Terraform' not in pdf_text(export_resume(resume()).pdf)
    confirmed = merge_confirmed_keywords(resume(), ['Terraform'])
    assert 'Terraform' in pdf_text(export_resume(confirmed).pdf)
    assert merge_confirmed_keywords(resume(), [])['skills'] == resume()['skills']


@pytest.mark.parametrize('name', [YORUBA_NAME, 'Renée Müller'])
def test_unicode_names_and_bullets_extract_exactly(name):
    data = resume(name=name, experience=[{'role': 'Engineer', 'company': 'Ìbàdàn Tech', 'dates': '2020 - 2022',
                                          'bullets': [YORUBA_BULLET]}])
    result = export_resume(data, region='NG')
    text = pdf_text(result.pdf)
    assert name in text
    assert YORUBA_BULLET in text and 'Ìbàdàn Tech' in text
    assert '(cid:' not in text and not result.warnings


def test_markup_characters_are_escaped_exactly():
    text = pdf_text(export_resume(resume()).pdf)
    assert 'Led R&D on caching with <5s cold starts.' in text
    assert 'R&D;' not in text and '&amp;' not in text and '&lt;' not in text


def test_skills_as_list_and_empty_data():
    pdf = export_resume(resume(skills=['Python', 'AWS', 'python'])).pdf
    assert 'Python, AWS' in pdf_text(pdf)
    with pytest.raises(ResumeExportError, match='no resume was generated'):
        generate_optimized_resume('cv.pdf', resume_data={})
    with pytest.raises(ResumeExportError):
        export_resume({'name': 'Only A Name'})


def long_resume():
    jobs = [{'role': f'Engineer {i}', 'company': f'Company {i}', 'location': 'Lagos, Nigeria',
             'dates': f'Jan {2010 + i} - Dec {2011 + i}',
             'bullets': [f'Delivered Python service improvement number {j} for team {i} with careful reviews.' for j in range(6)]}
            for i in range(7)]
    return resume(experience=jobs, summary='Engineer. ' * 40,
                  certifications=[f'Certification {i}' for i in range(5)],
                  education=[{'degree': 'BSc Physics', 'institution': 'University of Lagos', 'year': '2009'},
                             {'degree': 'MSc Computing', 'institution': 'University of Ibadan', 'year': '2012'}])


@pytest.mark.parametrize('data', [resume(), long_resume()])
def test_ats_structure_fonts_and_page_count(data):
    result = export_resume(data, region='NG')
    with pdfplumber.open(io.BytesIO(result.pdf)) as doc:
        assert len(doc.pages) == 1 == result.pages
        for page in doc.pages:
            assert page.find_tables() == []
            # pdfplumber derives sizes from text matrices; 9pt can read as 8.999999.
            assert round(min(c['size'] for c in page.chars), 3) >= MIN_BODY_FONT == 9
            assert not page.images
        text = '\n'.join(p.extract_text() for p in doc.pages)
    assert '(cid:' not in text
    for font in _fonts(result.pdf):
        assert font.get('/FontFile2') or font.get('/FontFile') or font.get('/FontFile3'), font
    # Section order: skills ahead of experience, education last.
    order = [text.index(h) for h in ('PROFESSIONAL SUMMARY', 'CORE SKILLS', 'PROFESSIONAL EXPERIENCE',
                                     'SELECTED PROJECTS', 'CERTIFICATIONS', 'EDUCATION')]
    assert order == sorted(order)


def _fonts(pdf):
    descriptors = []
    for page in PdfReader(io.BytesIO(pdf)).pages:
        for font in page['/Resources']['/Font'].values():
            font = font.get_object()
            for item in [font] + [d.get_object() for d in font.get('/DescendantFonts', [])]:
                if '/FontDescriptor' in item:
                    descriptors.append(item['/FontDescriptor'].get_object())
                else:
                    assert item.get('/Subtype') == '/Type0', f'non-embedded font {item.get("/BaseFont")}'
    assert descriptors
    return descriptors


def test_strict_one_page_keeps_every_employer_degree_and_certification():
    data = long_resume()
    result = export_resume(data, priority_keywords=['Python'])
    assert result.pages == 1 and result.condensed
    text = pdf_text(result.pdf)
    for job in data['experience']:
        assert job['company'] in text
    assert 'University of Ibadan' in text and 'Certification 4' in text


def test_pdftotext_extracts_cleanly():
    if not shutil.which('pdftotext'):
        pytest.skip('pdftotext not installed')
    pdf = export_resume(resume(name=YORUBA_NAME)).pdf
    text = subprocess.run(['pdftotext', '-enc', 'UTF-8', '-', '-'], input=pdf, capture_output=True, check=True).stdout.decode()
    assert YORUBA_NAME in text and '(cid:' not in text and 'R&D' in text


@pytest.mark.parametrize('region,size', [('NG', A4), ('UK', A4), ('EU', A4), ('OTHER', A4), ('US', LETTER), ('CA', LETTER)])
def test_page_size_follows_region(region, size):
    box = PdfReader(io.BytesIO(export_resume(resume(), region=region).pdf)).pages[0].mediabox
    assert (round(float(box.width)), round(float(box.height))) == (round(size[0]), round(size[1]))


def test_region_rules_and_resolution():
    info = 'Date of Birth: 01 Jan 1990\nMarital Status: Single\nLanguages: English, Yoruba'
    us = pdf_text(export_resume(resume(additional_information=info), region='US').pdf)
    ng = pdf_text(export_resume(resume(additional_information=info), region='NG').pdf)
    assert 'Date of Birth' not in us and 'Marital Status' not in us and 'Yoruba' in us
    assert 'Date of Birth' in ng  # present in the source and permitted by convention
    assert resolve_region(None, 'United States') == 'US' and resolve_region(None, 'Nigeria') == 'NG'
    assert resolve_region(None, 'Germany') == 'EU' and resolve_region('gb') == 'UK' and resolve_region(None, None) == 'OTHER'


def test_long_unbroken_tokens_do_not_break_layout():
    url = 'https://example.com/' + 'a' * 300
    assert export_resume(resume(contact='renee@example.com | ' + url)).pages == 1


@pytest.mark.parametrize('name', ['田中太郎', 'محمد علي', 'Renée 김민준'])
def test_non_latin_names_use_fallback_fonts(name):
    pytest.importorskip('arabic_reshaper')
    from backend.app.utils.pdf_generator import _fallback
    if _fallback('ResumeCJK') is None or _fallback('ResumeArabic') is None:
        pytest.skip('fallback fonts not installed (Dockerfile installs fonts-noto-core, fonts-wqy-zenhei)')
    result = export_resume(resume(name=name))
    assert not result.warnings
    import unicodedata
    assert unicodedata.normalize('NFKC', name) in unicodedata.normalize('NFKC', pdf_text(result.pdf))


def test_glyphs_without_any_font_are_reported_not_silently_dropped():
    result = export_resume(resume(name='Ada \U00012000'))
    assert any('not supported' in w for w in result.warnings)


def _font_names(pdf: bytes) -> set[str]:
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        return {c['fontname'].split('+')[-1] for page in doc.pages for c in page.chars}


@pytest.mark.parametrize('name,family', [('Renée Müller', 'Carlito'), ('Анна Иванова', 'Carlito'),
                                         (YORUBA_NAME, 'DejaVuSans')])
def test_carlito_by_default_whole_document_falls_back_to_dejavu(name, family):
    result = export_resume(resume(name=name))
    assert result.info()['font'] == family and not result.warnings
    assert {f.split('-')[0] for f in _font_names(result.pdf)} == {family}
    assert name in pdf_text(result.pdf)


def test_entry_line_carries_location_dates_and_project_subtitle():
    data = resume(experience=[{'role': 'Senior AI Trainer', 'company': 'micro1', 'location': 'Remote (Contract)',
                               'dates': 'Sep 2026 – Present', 'environment': 'Python, pytest',
                               'bullets': ['Quality evaluation: Assess AI outputs against written guidelines.']}],
                  projects=[{'title': 'Gateway', 'subtitle': 'Multi-provider LLM gateway',
                             'tech': 'Python, Groq, PyPI', 'bullets': ['Packaged and released: Published on PyPI.']}],
                  certifications=['AWS Educate: Introduction to Generative AI'])
    lines = pdf_text(export_resume(data).pdf).splitlines()
    assert 'Senior AI Trainer | micro1 · Remote (Contract) Sep 2026 - Present' in lines
    assert 'Gateway | Multi-provider LLM gateway' in lines
    assert 'Python · Groq · PyPI' in lines and 'Tools: Python · pytest' in lines


def test_bullet_labels_are_bold_only_in_experience_and_projects():
    data = resume(experience=[{'role': 'Engineer', 'company': 'Example', 'dates': '2025', 'environment': '',
                               'bullets': ['Docker-based CI/CD: Built pipelines.', 'Cut latency vs. baseline: by caching.']}],
                  certifications=['AWS Educate: Introduction to Generative AI'])
    with pdfplumber.open(io.BytesIO(export_resume(data).pdf)) as doc:
        words = doc.pages[0].extract_words(extra_attrs=['fontname'])
    font = {w['text']: w['fontname'] for w in words}
    assert font['Docker-based'].endswith('Carlito-Bold') and font['pipelines.'].endswith('Carlito-Regular')
    assert font['Educate:'].endswith('Carlito-Regular')     # a certification name, not a label
    assert font['Cut'].endswith('Carlito-Regular')          # a lead-in containing "." is a sentence
    # Role is bold; employer and dates on the same line are regular weight.
    assert font['Engineer'].endswith('Carlito-Bold') and font['Example'].endswith('Carlito-Regular')
    assert font['2025'].endswith('Carlito-Italic')


# ── normalize_resume_data ────────────────────────────────────────────────────

def test_normalize_tolerates_missing_and_wrong_types():
    empty = normalize_resume_data(None)
    assert empty['experience'] == [] and empty['skills'] == {} and empty['name'] == ''
    data = normalize_resume_data({
        'name': '  Ada  Obi ', 'contact': {'email': 'ada@example.com', 'phone': '+234 1'},
        'skills': 'Python, AWS; Docker', 'experience': [{'title': 'Engineer', 'employer': 'Acme', 'start_date': 'March 2020',
                                                         'bullets': '• Built APIs\n- Wrote tests'}, 'Intern at Lab', 42],
        'education': 'BSc Physics', 'certifications': [{'name': 'CKA', 'issuer': 'CNCF'}], 'projects': None,
        'summary': ['line one', 'line two']})
    assert data['name'] == 'Ada Obi'
    assert data['contact'] == 'ada@example.com | +234 1'
    assert data['skills'] == {'Skills': ['Python', 'AWS', 'Docker']}
    assert data['experience'][0] == {'role': 'Engineer', 'company': 'Acme', 'location': '', 'dates': 'Mar 2020 - Present',
                                     'bullets': ['Built APIs', 'Wrote tests'], 'environment': ''}
    assert data['experience'][1]['role'] == 'Intern at Lab' and len(data['experience']) == 2
    assert data['education'][0]['degree'] == 'BSc Physics'
    assert data['certifications'] == ['CKA | CNCF'] and data['projects'] == []
    assert data['summary'] == 'line one, line two'
    assert normalize_resume_data({'skills': {'Cloud': 'AWS, GCP', 'Empty': []}})['skills'] == {'Cloud': ['AWS', 'GCP']}


@pytest.mark.parametrize('raw,expected', [('January 2020 – Present', 'Jan 2020 - Present'), ('2019-2021', '2019 - 2021'),
                                          ('2020-01', '2020-01'), ('Sept 2018 to date', 'Sep 2018 - Present'), ('', '')])
def test_normalize_dates(raw, expected):
    assert normalize_dates(raw) == expected


def test_download_filename_is_candidate_name():
    assert download_filename(YORUBA_NAME) == ('Olajide_Ebun_Adewale_Resume.pdf', 'Ọlájídé_Ẹ̀bùn_Adéwálé_Resume.pdf')
    assert download_filename(None)[0] == 'Candidate_Resume.pdf'


# ── Endpoint tests ───────────────────────────────────────────────────────────

@pytest.fixture
def db():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all([User(email='a@example.com', full_name='A', hashed_password='x', is_verified=True, country='Nigeria'),
                     User(email='b@example.com', full_name='B', hashed_password='x', is_verified=True, country='United States')])
    session.commit()
    app.dependency_overrides[get_db] = lambda: session
    yield session
    app.dependency_overrides.clear(); session.close(); engine.dispose()


@pytest.fixture
def client(db):
    from backend.app import main
    main.reset_rate_limits()
    return TestClient(app)


def auth(email='a@example.com'):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': email})}


@pytest.fixture
def pipeline(monkeypatch):
    import backend.app.utils.ats_engine as engine
    base = resume(name=YORUBA_NAME, contact='olajide@example.com | Lagos, Nigeria')
    monkeypatch.setattr(engine, 'extract_resume_data', lambda text: json.loads(json.dumps(base)))
    monkeypatch.setattr(engine, 'extract_requirements', lambda jd: [{'phrase': 'Python', 'priority': 'required'},
                                                                    {'phrase': 'Terraform', 'priority': 'required'}])
    monkeypatch.setattr(engine, 'rewrite_resume_for_job', lambda **kw: {
        'optimized_summary': base['summary'], 'optimized_experience': base['experience'],
        'optimized_skills': {'Skills': ['Python', 'Terraform']}, 'confirmation_questions': [], 'suggestions_applied': []})
    return base


def upload(client, email='a@example.com', **data):
    # The uploaded file must contain what the (faked) extraction returns:
    # extraction output is now verified against the file.
    source = export_resume(resume(name=YORUBA_NAME, contact='olajide@example.com | Lagos, Nigeria')).pdf
    return client.post('/api/v1/resume/upload', headers=auth(email), files={'file': ('cv.pdf', source, 'application/pdf')},
                       data={'job_title': 'Engineer', 'job_description': 'Python and Terraform skills required for this engineering role.', **data})


def test_upload_confirm_regenerate_and_download_flow(client, db, pipeline):
    res = upload(client)
    assert res.status_code == 200, res.text
    result = res.json()['result']
    task_id = res.json()['task_id']
    assert result['task_id'] == task_id and result['suggested_skills'] == ['Terraform']
    assert result['document']['page_size'] == 'A4' and result['document']['region'] == 'NG'
    assert result['rewrite_guard'] == {'summary_reverted': False, 'roles_reverted': 0}
    assert result['document']['font'] in ('Carlito', 'DejaVuSans')
    record = db.query(Resume).one()
    assert 'Terraform' not in pdf_text(record.content)
    assert db.query(Subscription).one().scans_this_month == 1

    assert client.post(f'/api/v1/resume/regenerate/{task_id}', headers=auth(),
                       json={'confirmed_keywords': ['Kubernetes']}).status_code == 422
    res = client.post(f'/api/v1/resume/regenerate/{task_id}', headers=auth(), json={'confirmed_keywords': ['terraform']})
    assert res.status_code == 200, res.text
    assert res.json()['result']['overall_score'] == 100 and res.json()['result']['confirmed_keywords'] == ['Terraform']
    db.refresh(record)
    assert 'Terraform' in pdf_text(record.content)
    assert db.query(Subscription).one().scans_this_month == 1  # regenerating does not burn quota

    download = client.get(f'/api/v1/resume/download/{task_id}', headers=auth())
    assert download.status_code == 200 and download.content == record.content
    disposition = download.headers['content-disposition']
    assert disposition.startswith('attachment; filename="Olajide_Ebun_Adewale_Resume.pdf"') and 'Baalebos' not in disposition
    status = client.get(f'/api/v1/resume/status/{task_id}', headers=auth()).json()
    assert status['result']['task_id'] == task_id


def test_region_from_profile_and_request(client, db, pipeline):
    res = upload(client, email='b@example.com')
    assert res.json()['result']['document']['page_size'] == 'LETTER'
    res = upload(client, email='b@example.com', region='UK')
    assert res.json()['result']['document']['page_size'] == 'A4'


def test_download_requires_auth_and_ownership(client, db, pipeline):
    task_id = upload(client).json()['task_id']
    for endpoint in ('download', 'preview', 'status'):
        assert client.get(f'/api/v1/resume/{endpoint}/{task_id}').status_code == 401
        assert client.get(f'/api/v1/resume/{endpoint}/{task_id}', headers=auth('b@example.com')).status_code == 404
    assert client.post(f'/api/v1/resume/regenerate/{task_id}', headers=auth('b@example.com'),
                       json={'confirmed_keywords': ['Terraform']}).status_code == 404


def test_db_save_failure_returns_500_and_charges_nothing(client, db, pipeline, monkeypatch):
    real_commit = db.commit
    def failing_commit():
        if any(isinstance(obj, Resume) for obj in db.new):
            raise RuntimeError('database unavailable')
        real_commit()
    monkeypatch.setattr(db, 'commit', failing_commit)
    res = upload(client)
    assert res.status_code == 500 and 'completed' not in res.text
    monkeypatch.setattr(db, 'commit', real_commit)
    assert db.query(Resume).count() == 0
    assert (db.query(Subscription).first().scans_this_month if db.query(Subscription).first() else 0) == 0


def test_empty_extraction_returns_error_and_saves_nothing(client, db, pipeline, monkeypatch):
    monkeypatch.setattr('backend.app.utils.resume_quality.merge_rewrite', lambda *a, **k: {})
    res = upload(client)
    assert res.status_code == 422 and 'no resume was generated' in res.json()['detail']
    assert db.query(Resume).count() == 0
    sub = db.query(Subscription).first()
    assert sub is None or sub.scans_this_month == 0


def test_status_polling_is_not_rate_limited_below_30_per_minute(client, db, pipeline):
    task_id = upload(client).json()['task_id']
    assert all(client.get(f'/api/v1/resume/status/{task_id}', headers=auth()).status_code == 200 for _ in range(35))
