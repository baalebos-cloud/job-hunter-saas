"""Legal documents: bundled starter text, drafts and published versions."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

DOCS = {   # slug -> default title (order = footer order)
    'terms': 'Terms & Conditions',
    'privacy': 'Privacy Policy',
    'cookies': 'Cookie Policy',
    'refunds': 'Refund Policy',
    'acceptable-use': 'Acceptable Use Policy',
}
DATA = Path(__file__).resolve().parents[1] / 'data' / 'legal'
MAX_BODY = 60_000


def starter(slug: str) -> tuple[str, str]:
    text = (DATA / f'{slug}.md').read_text(encoding='utf-8')
    first, _, rest = text.partition('\n')
    return (first.lstrip('# ').strip() or DOCS[slug]), rest.strip()


def _latest(db, slug: str, status: str):
    from backend.app.models.legal import LegalDocumentVersion as V
    return (db.query(V).filter(V.slug == slug, V.status == status)
            .order_by(V.version.desc() if status == 'published' else V.id.desc(), V.id.desc()).first())


def public_view(db, slug: str) -> dict:
    """What visitors see: the latest published version, else the starter draft (flagged)."""
    row = _latest(db, slug, 'published')
    if row:
        return {'slug': slug, 'title': row.title, 'body': row.body, 'version': row.version,
                'published_at': row.published_at.isoformat() + 'Z', 'draft': False}
    title, body = starter(slug)
    return {'slug': slug, 'title': title, 'body': body, 'version': None, 'published_at': None, 'draft': True}


def console_view(db, slug: str) -> dict:
    from backend.app.models.legal import LegalDocumentVersion as V
    published, draft = _latest(db, slug, 'published'), _latest(db, slug, 'draft')
    working = draft or published
    title, body = (working.title, working.body) if working else starter(slug)
    history = (db.query(V).filter(V.slug == slug, V.status == 'published').order_by(V.version.desc()).limit(20).all())
    return {'slug': slug, 'title': title, 'body': body, 'has_draft': draft is not None,
            'published_version': published.version if published else None,
            'published_at': published.published_at.isoformat() + 'Z' if published else None,
            'draft_updated_at': draft.updated_at.isoformat() + 'Z' if draft else None,
            'history': [{'version': h.version, 'published_at': h.published_at.isoformat() + 'Z', 'note': h.note}
                        for h in history]}


def clean(title: str, body: str) -> tuple[str, str]:
    title = re.sub(r'\s+', ' ', (title or '')).strip()[:120]
    body = (body or '').replace('\x00', '').replace('\r\n', '\n').strip()
    if len(title) < 3:
        raise ValueError('Give the document a title.')
    if len(body) < 50:
        raise ValueError('The document is too short to publish.')
    if len(body) > MAX_BODY:
        raise ValueError(f'Keep the document under {MAX_BODY:,} characters.')
    return title, body


def save_draft(db, slug: str, title: str, body: str, user_id: int):
    from backend.app.models.legal import LegalDocumentVersion as V
    title, body = clean(title, body)
    row = _latest(db, slug, 'draft') or V(slug=slug, status='draft', title=title, body=body)
    row.title, row.body, row.edited_by, row.updated_at = title, body, user_id, datetime.utcnow()
    db.add(row)
    return row


def publish(db, slug: str, note: str, user_id: int):
    from sqlalchemy import func
    from backend.app.models.legal import LegalDocumentVersion as V
    row = _latest(db, slug, 'draft')
    if row is None:
        raise ValueError('There is no draft to publish. Edit the document first.')
    latest = db.query(func.max(V.version)).filter(V.slug == slug, V.status == 'published').scalar() or 0
    row.status, row.version, row.published_at = 'published', latest + 1, datetime.utcnow()
    row.note, row.edited_by = (note or '').strip()[:255] or None, user_id
    return row
