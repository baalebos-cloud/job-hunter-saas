"""Custom branding on PDF and Word exports (Enterprise)."""
import io

from PIL import Image
from pypdf import PdfReader

from backend.app.models.branding import Branding
from backend.app.models.subscription import Subscription
from backend.app.models.team import TeamMember
from backend.app.models.user import User
from backend.app.services.auth_service import create_access_token
from backend.app.utils.pdf_generator import export_resume
from backend.test.test_scaling import AUTH, BASE, client, db, pipeline  # noqa: F401

JD = 'We need Python and Terraform skills for this platform engineering role, building internal tools.'


def enterprise(db, user_id=1):
    db.add(Subscription(user_id=user_id, plan='enterprise', status='active'))
    db.commit()


def png(size=(400, 120), color=(5, 150, 105, 255)):
    out = io.BytesIO()
    Image.new('RGBA', size, color).save(out, format='PNG')
    return out.getvalue()


def tailored(client):
    response = client.post('/api/v1/resume/upload', headers=AUTH,
                           data={'job_description': JD, 'job_title': 'Platform Engineer'},
                           files={'file': ('cv.pdf', export_resume(BASE).pdf, 'application/pdf')})
    assert response.status_code == 200, response.text
    return response.json()['task_id']


def text_of(pdf: bytes) -> str:
    return '\n'.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(pdf)).pages)


def test_branding_is_an_enterprise_feature(client, db):
    assert client.get('/api/v1/branding', headers=AUTH).json()['enabled'] is False
    denied = client.put('/api/v1/branding', json={'brand_name': 'Acme Talent'}, headers=AUTH)
    assert denied.status_code == 403 and denied.json()['detail']['error'] == 'enterprise_required'


def test_save_validate_and_logo(client, db):
    enterprise(db)
    saved = client.put('/api/v1/branding', json={'brand_name': '  Acme   Talent ', 'accent_color': '#1D4ED8'}, headers=AUTH).json()
    assert saved['brand_name'] == 'Acme Talent' and saved['accent_color'] == '#1d4ed8' and saved['configured']
    assert client.put('/api/v1/branding', json={'brand_name': 'x', 'accent_color': 'blue'}, headers=AUTH).status_code == 400
    assert client.put('/api/v1/branding', json={'brand_name': 'A' * 61}, headers=AUTH).status_code == 400

    big = Image.new('RGB', (3000, 900), (10, 20, 30)); raw = io.BytesIO(); big.save(raw, format='JPEG')
    up = client.post('/api/v1/branding/logo', headers=AUTH, files={'file': ('logo.jpg', raw.getvalue(), 'image/jpeg')})
    assert up.status_code == 200 and up.json()['has_logo'] is True
    stored = Image.open(io.BytesIO(db.get(Branding, 1).logo))
    assert stored.format == 'PNG' and stored.size[0] <= 600 and stored.size[1] <= 180
    assert client.get('/api/v1/branding/logo', headers=AUTH).headers['content-type'] == 'image/png'
    bad = client.post('/api/v1/branding/logo', headers=AUTH, files={'file': ('x.png', b'not an image', 'image/png')})
    assert bad.status_code == 400
    assert client.delete('/api/v1/branding/logo', headers=AUTH).json()['has_logo'] is False


def test_branded_pdf_adds_header_and_footer_without_touching_the_resume(client, db, pipeline):
    enterprise(db)
    task = tailored(client)
    plain = client.get(f'/api/v1/resume/download/{task}', headers=AUTH)
    assert client.get(f'/api/v1/resume/download/{task}?branded=true', headers=AUTH).status_code == 409   # not set up yet

    client.put('/api/v1/branding', json={'brand_name': 'Acme Talent', 'accent_color': '#1d4ed8'}, headers=AUTH)
    client.post('/api/v1/branding/logo', headers=AUTH, files={'file': ('logo.png', png(), 'image/png')})
    branded = client.get(f'/api/v1/resume/download/{task}?branded=true', headers=AUTH)
    assert branded.status_code == 200 and branded.content.startswith(b'%PDF')
    assert 'Prepared by Acme Talent' in text_of(branded.content)
    assert 'Prepared by' not in text_of(plain.content)
    assert len(PdfReader(io.BytesIO(branded.content)).pages) == len(PdfReader(io.BytesIO(plain.content)).pages)
    # Every word of the original resume is still there.
    assert set(text_of(plain.content).split()) <= set(text_of(branded.content).split())
    assert b'pypdf' not in branded.content


def test_branded_word_file(client, db, pipeline):
    from docx import Document
    enterprise(db)
    task = tailored(client)
    client.put('/api/v1/branding', json={'brand_name': 'Acme Talent'}, headers=AUTH)
    client.post('/api/v1/branding/logo', headers=AUTH, files={'file': ('logo.png', png(), 'image/png')})
    body = client.get(f'/api/v1/resume/download/{task}/docx?branded=true', headers=AUTH)
    assert body.status_code == 200
    doc = Document(io.BytesIO(body.content))
    assert doc.sections[0].footer.paragraphs[0].text == 'Prepared by Acme Talent'
    assert doc.sections[0].header.part.related_parts                                  # the logo image
    plain = Document(io.BytesIO(client.get(f'/api/v1/resume/download/{task}/docx', headers=AUTH).content))
    assert plain.sections[0].footer.paragraphs[0].text == ''


def test_branding_needs_enterprise_at_download_time(client, db, pipeline):
    enterprise(db)
    task = tailored(client)
    client.put('/api/v1/branding', json={'brand_name': 'Acme Talent'}, headers=AUTH)
    db.query(Subscription).filter_by(user_id=1).one().status = 'cancelled'; db.commit()
    assert client.get(f'/api/v1/resume/download/{task}?branded=true', headers=AUTH).status_code == 403
    assert client.get(f'/api/v1/resume/download/{task}', headers=AUTH).status_code == 200           # plain still works


def test_team_members_use_the_owners_branding_and_cannot_change_it(client, db, pipeline):
    from datetime import datetime
    enterprise(db, user_id=2)                                        # user 2 owns the team
    owner = db.get(User, 2) or User(id=2, email='owner@example.com', hashed_password='x', is_verified=True)
    db.merge(owner); db.commit()
    db.add(Branding(owner_id=2, brand_name='Owner Co', accent_color='#059669'))
    db.add(TeamMember(owner_id=2, email='member', email_canonical='member', user_id=1, status='active',
                      accepted_at=datetime.utcnow()))
    db.commit()
    info = client.get('/api/v1/branding', headers=AUTH).json()
    assert info['enabled'] and not info['can_edit'] and info['brand_name'] == 'Owner Co' and info['managed_by']
    assert client.put('/api/v1/branding', json={'brand_name': 'Mine'}, headers=AUTH).status_code == 403
    task = tailored(client)
    branded = client.get(f'/api/v1/resume/download/{task}?branded=true', headers=AUTH)
    assert 'Prepared by Owner Co' in text_of(branded.content)


def test_branded_downloads_through_the_api(client, db, pipeline):
    enterprise(db)
    client.put('/api/v1/branding', json={'brand_name': 'Acme Talent'}, headers=AUTH)
    key = client.post('/api/v1/api-keys', json={'name': 'ci'}, headers=AUTH).json()['key']
    task = tailored(client)
    pdf = client.get(f'/api/public/v1/resumes/{task}/pdf?branded=true', headers={'Authorization': f'Bearer {key}'})
    assert pdf.status_code == 200 and 'Prepared by Acme Talent' in text_of(pdf.content)
    docx = client.get(f'/api/public/v1/resumes/{task}/docx?branded=true', headers={'Authorization': f'Bearer {key}'})
    assert docx.status_code == 200


def test_branding_fits_every_layout_margin():
    """The header and footer stay inside the smallest page margin (24 pt) on A4 and Letter."""
    from backend.app.models.branding import Branding as Row
    from backend.app.services.branding import SAFE_MARGIN, brand_pdf
    for region in ('UK', 'US'):
        original = export_resume(BASE, region=region).pdf
        branded = brand_pdf(original, Row(brand_name='Acme Talent', accent_color='#059669', logo=png()))
        page = PdfReader(io.BytesIO(branded)).pages[0]
        positions = []
        page.extract_text(visitor_text=lambda text, cm, tm, *_: positions.append((text, tm[5])) if 'Prepared' in text else None)
        assert positions and all(y < SAFE_MARGIN for _, y in positions)
