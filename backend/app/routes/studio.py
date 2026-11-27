"""Resume Studio: save the hand-edited resume and load starting points."""
import json
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.dependencies.auth import get_current_user
from backend.app.models.studio import StudioDocument
from backend.app.services import studio

router = APIRouter()


class StudioSave(BaseModel):
    data: dict[str, Any]
    paper: Literal['A4', 'Letter'] = 'A4'
    preset: Literal['as-is', 'cloud', 'software', 'ai'] = 'as-is'


def _view(doc: StudioDocument | None) -> dict:
    if doc is None:
        return {'document': None, 'paper': 'A4', 'preset': 'as-is', 'updated_at': None}
    return {'document': doc.data, 'paper': doc.paper, 'preset': doc.preset,
            'updated_at': doc.updated_at.isoformat() + 'Z' if doc.updated_at else None}


@router.get('')
def get_document(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return _view(db.get(StudioDocument, current_user.id))


@router.put('')
def save_document(payload: StudioSave, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    try:
        data = studio.validate(payload.data)
    except studio.StudioError as exc:
        raise HTTPException(422, str(exc)) from exc
    doc = db.get(StudioDocument, current_user.id)
    if doc is None:
        doc = StudioDocument(user_id=current_user.id)
        db.add(doc)
    doc.data, doc.paper, doc.preset, doc.updated_at = data, payload.paper, payload.preset, datetime.utcnow()
    db.commit()
    return _view(doc)


@router.delete('')
def delete_document(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    doc = db.get(StudioDocument, current_user.id)
    if doc is not None:
        db.delete(doc)
        db.commit()
    return {'deleted': doc is not None}


@router.get('/sources')
def list_sources(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Where a Studio resume can start from: the profile and tailored resumes the plan keeps."""
    from backend.app.models.resume import Resume
    from backend.app.routes.resume import HISTORY_LIMIT_FREE, HISTORY_LIMIT_PAID
    from backend.app.services.processing_gate import has_priority
    limit = HISTORY_LIMIT_PAID if has_priority(db, current_user) else HISTORY_LIMIT_FREE
    rows = (db.query(Resume).filter(Resume.owner_id == current_user.id, Resume.status == 'completed',
                                    Resume.filename.like('optimized_%'), Resume.parsed_data.isnot(None))
            .order_by(Resume.created_at.desc(), Resume.id.desc()).limit(limit).all())
    tailored = [{'task_id': r.filename[len('optimized_'):-len('.pdf')],
                 'job_title': (r.analysis_data or {}).get('job_title') or 'Tailored resume',
                 'company': (r.analysis_data or {}).get('company'),
                 'created_at': r.created_at.isoformat() + 'Z' if r.created_at else None} for r in rows]
    return {'profile': True, 'tailored': tailored}


@router.get('/sources/profile')
def source_profile(current_user=Depends(get_current_user)):
    return {'data': studio.from_profile(current_user)}


@router.get('/sources/resume/{task_id}')
def source_resume(task_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    from backend.app.routes.resume import owned_resume
    record = owned_resume(task_id, db, current_user)
    try:
        tailored = json.loads(record.parsed_data or '{}')
    except (TypeError, ValueError):
        tailored = {}
    if record.status != 'completed' or not isinstance(tailored, dict) or not tailored:
        raise HTTPException(409, 'This resume has no editable content.')
    analysis = record.analysis_data or {}
    return {'data': studio.from_tailored(tailored), 'job_description': (analysis.get('job_description') or '')[:20000],
            'job_title': analysis.get('job_title')}
