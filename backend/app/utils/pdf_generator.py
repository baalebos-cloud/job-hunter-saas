"""Single-column, text-based resume export. Improvement notes never enter the CV."""
from io import BytesIO
from pathlib import Path
from html import escape
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT_DIRECTORY = Path(__file__).resolve().parents[1] / 'assets' / 'fonts'
pdfmetrics.registerFont(TTFont('ResumeSans', str(FONT_DIRECTORY / 'DejaVuSans.ttf')))
pdfmetrics.registerFont(TTFont('ResumeSansBold', str(FONT_DIRECTORY / 'DejaVuSans-Bold.ttf')))


def generate_optimized_resume(filename, score=0, improvements=None, resume_data=None):
    data = resume_data or {}
    if not data.get('name') or not data.get('contact'):
        raise ValueError('Cannot export an incomplete resume.')
    buffer = BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle('ResumeBody', fontName='ResumeSans', fontSize=10, leading=15, spaceAfter=5))
    styles.add(ParagraphStyle('ResumeHeading', fontName='ResumeSansBold', fontSize=11, leading=15, spaceBefore=12, spaceAfter=6, keepWithNext=True, textColor=colors.HexColor('#172033')))
    styles.add(ParagraphStyle('ResumeName', fontName='ResumeSansBold', fontSize=19, leading=24, spaceAfter=8))
    # Escape all candidate content before passing it to ReportLab's markup parser.
    def clean(value):
        return escape(str(value or '').replace('–','-').replace('—','-').replace('·',','))
    story = []
    def body(text):
        if text: story.append(Paragraph(clean(text), styles['ResumeBody']))
    def heading(title): story.append(Paragraph(title, styles['ResumeHeading']))
    story.append(Paragraph(clean(data['name']), styles['ResumeName']))
    body(data.get('title')); body(data['contact'])
    if data.get('summary'):
        heading('PROFESSIONAL SUMMARY'); body(data['summary'])
    if data.get('skills'):
        heading('SKILLS')
        for category, values in data['skills'].items(): body(f'{category}: '+', '.join(values))
    if data.get('experience'):
        heading('PROFESSIONAL EXPERIENCE')
        for entry in data['experience']:
            body(entry.get('role')); body(' | '.join(str(entry.get(k,'')) for k in ('company','dates')))
            for bullet in entry.get('bullets',[]): body('- '+bullet)
            if entry.get('environment'): body('Tools: '+str(entry['environment']))
            story.append(Spacer(1,5))
    if data.get('projects'):
        heading('PROJECTS')
        for entry in data['projects']:
            body(entry.get('title')); body(entry.get('tech'))
            for bullet in entry.get('bullets',[]): body('- '+bullet)
    if data.get('education'):
        heading('EDUCATION')
        for entry in data['education']: body(' | '.join(str(entry.get(k,'')) for k in ('degree','institution','year')))
    if data.get('certifications'):
        heading('CERTIFICATIONS')
        for cert in data['certifications']: body(cert)
    if data.get('additional_information'):
        heading('ADDITIONAL INFORMATION'); body(data['additional_information'])
    SimpleDocTemplate(buffer,pagesize=A4,leftMargin=42,rightMargin=42,topMargin=38,bottomMargin=38).build(story)
    buffer.seek(0)
    return buffer
