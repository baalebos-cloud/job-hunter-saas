"""Settings -> Branding (Enterprise): the brand name, logo and accent colour
used on branded PDF and Word downloads. Team members use the team owner's
branding and cannot change it."""
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.dependencies.auth import get_current_user
from backend.app.dependencies.plan_guard import own_plan, plan_for, team_owner
from backend.app.models.branding import DEFAULT_ACCENT, Branding
from backend.app.models.user import User
from backend.app.services import branding as svc
from backend.app.services.audit import record_event

router = APIRouter(tags=['Branding'])


class BrandingBody(BaseModel):
    brand_name: str | None = Field(None, max_length=200)
    accent_color: str | None = Field(None, max_length=20)


def _editable_row(db: Session, user: User) -> Branding:
    if own_plan(db, user) != 'enterprise':
        if team_owner(db, user) is not None:
            raise HTTPException(403, 'Your team owner manages the branding for your team.')
        raise HTTPException(403, {'error': 'enterprise_required',
                                  'message': 'Custom branding is part of the Enterprise plan.', 'upgrade_url': '/pricing'})
    row = db.get(Branding, user.id)
    if row is None:
        row = Branding(owner_id=user.id, accent_color=DEFAULT_ACCENT)
        db.add(row)
    return row


def _json(db: Session, user: User) -> dict:
    owner = team_owner(db, user) if own_plan(db, user) != 'enterprise' else None
    row = db.get(Branding, owner.id if owner else user.id)
    return {'enabled': plan_for(db, user) == 'enterprise', 'can_edit': own_plan(db, user) == 'enterprise',
            'managed_by': (owner.full_name or owner.email.split('@')[0]) if owner else None,
            'brand_name': row.brand_name if row else None,
            'accent_color': row.accent_color if row else DEFAULT_ACCENT,
            'has_logo': bool(row and row.logo), 'configured': bool(row and row.configured)}


@router.get('')
def get_branding(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _json(db, current_user)


@router.put('')
def save_branding(body: BrandingBody, request: Request, db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    row = _editable_row(db, current_user)
    try:
        row.brand_name = svc.clean_name(body.brand_name)
        row.accent_color = svc.clean_color(body.accent_color)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    db.commit()
    record_event('branding.update', actor=current_user, trace_id=getattr(request.state, 'trace_id', None))
    return _json(db, current_user)


@router.post('/logo')
async def upload_logo(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db),
                      current_user: User = Depends(get_current_user)):
    row = _editable_row(db, current_user)
    raw = await file.read(svc.MAX_LOGO_BYTES + 1)
    try:
        row.logo = svc.clean_logo(raw)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(400, str(exc)) from exc
    db.commit()
    record_event('branding.logo', actor=current_user, trace_id=getattr(request.state, 'trace_id', None))
    return _json(db, current_user)


@router.delete('/logo')
def remove_logo(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    row = _editable_row(db, current_user)
    row.logo = None
    db.commit()
    return _json(db, current_user)


@router.get('/logo')
def get_logo(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    row = db.get(Branding, svc.branding_owner_id(db, current_user))
    if row is None or not row.logo:
        raise HTTPException(404, 'No logo uploaded.')
    return Response(row.logo, media_type='image/png', headers={'Cache-Control': 'private, no-store'})
