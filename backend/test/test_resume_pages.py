"""1- and 2-page exports by region, personal-detail rules, PDF language/RTL, and Word parity."""
import io

import pytest
from docx import Document
from docx.shared import Inches, Mm
from fastapi import HTTPException
from pypdf import PdfReader

from backend.app.utils import pdf_generator
from backend.app.utils.docx_export import HEADINGS, build_docx
from backend.app.utils.language import detect_language
from backend.app.utils.pdf_generator import ResumeExportError, export_resume, resolve_max_pages
from backend.test.test_resume_global_standard import long_resume, pdf_text, resume


@pytest.mark.parametrize('region, expected', [('US', 1), ('CA', 1), ('UK', 'auto'), ('EU', 'auto'), ('NG', 'auto'),
                                              ('OTHER', 'auto')])
def test_default_page_length_by_region(region, expected):
    assert resolve_max_pages(region) == expected


def test_explicit_page_length_wins_and_bad_values_are_refused():
    assert resolve_max_pages('US', '2') == 2 and resolve_max_pages('NG', 1) == 1 and resolve_max_pages('US', 'AUTO') == 'auto'
    with pytest.raises(ResumeExportError):
        resolve_max_pages('US', '3')
    from backend.app.routes.resume import _pages_for
    with pytest.raises(HTTPException) as exc:
        _pages_for('US', 'ten')
    assert exc.value.status_code == 400


def bullets_in(data):
    return [b for job in data['experience'] for b in job['bullets']]


def test_auto_uses_two_pages_instead_of_cutting_older_roles():
    data = long_resume()
    result = export_resume(data, region='NG')
    assert result.pages == 2 == len(PdfReader(io.BytesIO(result.pdf)).pages)
    assert not result.condensed and result.max_pages == 'auto'
    text = pdf_text(result.pdf)
    for bullet in bullets_in(data):            # every bullet of every role, the oldest included
        assert bullet in text.replace('\n', ' ')


def test_auto_stays_on_one_page_when_it_fits():
    result = export_resume(resume(), region='UK')
    assert result.pages == 1 and not result.condensed


def test_us_default_is_one_page_and_lists_every_cut():
    result = export_resume(long_resume(), region='US')
    assert result.pages == 1 and result.condensed and result.max_pages == 1
    assert any(w.startswith('To fit one page, some lower-priority content was shortened') for w in result.warnings)
    assert result.info()['condensed_items'] == result.condensed_items


def test_us_resume_can_choose_two_pages():
    result = export_resume(long_resume(), region='US', max_pages=2)
    assert result.pages == 2 and not result.condensed and result.page_size == 'LETTER'


def test_more_than_two_pages_of_content_is_condensed_to_two():
    from backend.test.test_resume_refiner import huge_resume
    result = export_resume(huge_resume(roles=12, bullets=8), region='NG')
    assert result.pages == 2 and result.condensed
    assert any(w.startswith('To fit two pages') for w in result.warnings)


PERSONAL = {**resume(), 'contact': 'jordan@example.org | Date of Birth: 1 May 1990 | Lagos',
            'additional_information': 'Marital status: Single\nPhoto attached\nOpen to relocation'}


@pytest.mark.parametrize('region', ['US', 'CA', 'UK'])
def test_personal_details_removed_for_us_ca_uk(region):
    result = export_resume(PERSONAL, region=region)
    text = pdf_text(result.pdf)
    assert '1990' not in text and 'Single' not in text and 'Photo attached' not in text and 'Open to relocation' in text
    assert any(w.startswith('Removed personal details') and 'date of birth' in w for w in result.warnings)


@pytest.mark.parametrize('region', ['NG', 'EU', 'OTHER'])
def test_personal_details_kept_elsewhere_with_a_note(region):
    result = export_resume(PERSONAL, region=region)
    assert '1990' in pdf_text(result.pdf)
    assert any(w.startswith('Kept personal details') for w in result.warnings)


def test_no_personal_detail_note_when_there_are_none():
    assert not any('personal details' in w for w in export_resume(resume(), region='UK').warnings)


def test_language_detection():
    assert detect_language('Ingénieur DevOps avec cinq années d’expérience dans le cloud et les pipelines pour des équipes') == 'fr'
    assert detect_language('Ingeniero con experiencia en la nube y en los equipos de plataforma para el banco') == 'es'
    assert detect_language('Platform engineer running Kubernetes on AWS for the product teams') == 'en'
    assert detect_language('مهندس سحابة لديه خبرة في كوبرنيتس') == 'ar'
    assert detect_language('Built CI/CD de la pipeline') == 'en'      # a few foreign words do not flip English


def test_pdf_lang_follows_the_resume():
    french = {**resume(), 'summary': 'Ingénieure DevOps avec cinq années d’expérience dans le cloud pour les équipes de la banque.'}
    result = export_resume(french, region='EU')
    assert result.lang == 'fr' and result.info()['lang'] == 'fr'
    assert PdfReader(io.BytesIO(result.pdf)).trailer['/Root'].get('/Lang') == 'fr'
    assert PdfReader(io.BytesIO(export_resume(resume(), region='US').pdf)).trailer['/Root'].get('/Lang') == 'en'


def test_rtl_resumes_are_right_aligned():
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT
    layout = pdf_generator.LAYOUTS[0]
    token = pdf_generator._DOCUMENT_LANG.set('ar')
    try:
        styles = pdf_generator._styles(layout, pdf_generator.PRIMARY_FONT)
    finally:
        pdf_generator._DOCUMENT_LANG.reset(token)
    assert styles['body'].alignment == styles['bullet'].alignment == TA_RIGHT
    assert pdf_generator._styles(layout, pdf_generator.PRIMARY_FONT)['body'].alignment == TA_LEFT


@pytest.mark.parametrize('region, width, height', [('US', Inches(8.5), Inches(11)), ('NG', Mm(210), Mm(297)),
                                                   ('UK', Mm(210), Mm(297))])
def test_word_page_size_follows_region(region, width, height):
    section = Document(io.BytesIO(build_docx(resume(), region))).sections[0]
    # Word stores sizes in twips, so A4 rounds by a few hundredths of a millimetre.
    assert abs(section.page_width - width) < Mm(0.05) and abs(section.page_height - height) < Mm(0.05)


def test_word_uses_the_pdf_headings_in_the_pdf_order():
    data = {**resume(), 'certifications': ['AWS Certified Cloud Practitioner'], 'additional_information': 'Open to relocation'}
    paragraphs = [p.text for p in Document(io.BytesIO(build_docx(data, 'NG'))).paragraphs]
    headings = [p for p in paragraphs if p in {h.upper() for h in HEADINGS}]
    pdf = pdf_text(export_resume(data, region='NG').pdf)
    assert headings == [h for h in (h.upper() for h in HEADINGS) if h in pdf]
    assert headings.index('CERTIFICATIONS') < headings.index('EDUCATION')


def test_word_matches_the_condensed_pdf_content():
    result = export_resume(long_resume(), region='US')      # one page, condensed
    word = '\n'.join(p.text for p in Document(io.BytesIO(build_docx(result.content, 'US'))).paragraphs)
    pdf = pdf_text(result.pdf).replace('\n', ' ')
    for bullet in bullets_in(result.content):
        assert bullet in word and bullet in pdf
    removed = [b for b in bullets_in(long_resume()) if b not in bullets_in(result.content)]
    assert removed and not any(b in word for b in removed)


def test_word_bold_lead_ins_and_tools_line():
    data = resume(experience=[{'role': 'DevOps Engineer', 'company': 'Litware', 'dates': '2022 - Present',
                               'environment': 'Terraform, AWS',
                               'bullets': ['Migration: moved 40 services to Kubernetes on AWS EKS.']}])
    doc = Document(io.BytesIO(build_docx(data, 'US')))
    bullet = next(p for p in doc.paragraphs if p.text.startswith('Migration:'))
    assert bullet.runs[0].bold and bullet.runs[0].text == 'Migration:' and not bullet.runs[1].bold
    tools = next(p for p in doc.paragraphs if p.text.startswith('Tools:'))
    assert tools.runs[0].bold and tools.text == 'Tools: Terraform · AWS'
