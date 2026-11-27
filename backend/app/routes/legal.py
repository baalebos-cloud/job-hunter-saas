"""Public legal pages, and the Legal console (legal:manage) to edit and publish them."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.dependencies.roles import require_console
from backend.app.services import legal_docs

router = APIRouter(tags=["Legal"])
console_router = APIRouter(tags=["Legal console"])


def _slug(slug: str) -> str:
    if slug not in legal_docs.DOCS:
        raise HTTPException(404, 'Unknown document.')
    return slug


@router.get('')
def list_documents(db: Session = Depends(get_db)):
    return [{k: v for k, v in legal_docs.public_view(db, slug).items() if k != 'body'} for slug in legal_docs.DOCS]


@router.get('/{slug}')
def read_document(slug: str, db: Session = Depends(get_db)):
    return legal_docs.public_view(db, _slug(slug))


class DraftIn(BaseModel):
    title: str
    body: str


class PublishIn(BaseModel):
    note: str = ''


@console_router.get('')
def console_list(db: Session = Depends(get_db), _=Depends(require_console('legal:manage'))):
    return [legal_docs.console_view(db, slug) for slug in legal_docs.DOCS]


@console_router.put('/{slug}')
def console_save(slug: str, body: DraftIn, request: Request, db: Session = Depends(get_db),
                 user=Depends(require_console('legal:manage'))):
    try:
        legal_docs.save_draft(db, _slug(slug), body.title, body.body, user.id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    db.commit()
    return legal_docs.console_view(db, slug)


@console_router.post('/{slug}/publish')
def console_publish(slug: str, body: PublishIn, request: Request, db: Session = Depends(get_db),
                    user=Depends(require_console('legal:manage'))):
    from backend.app.services import security_events
    try:
        row = legal_docs.publish(db, _slug(slug), body.note, user.id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    db.commit()
    security_events.record('legal.published', request, user=user, details={'document': slug, 'version': row.version})
    try:
        from backend.app.services.audit import record_event
        record_event(action='legal.published', actor=None, details={'document': slug, 'version': row.version, 'by': user.id})
    except Exception:
        pass
    return legal_docs.console_view(db, slug)
