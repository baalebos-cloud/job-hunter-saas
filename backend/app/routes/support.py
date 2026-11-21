"""Help & support requests.

Candidates, employers and signed-out visitors can open a request; signed-in
users follow and answer theirs under "My requests". Staff answer from the
Owner console. Emails go out in the background so the API stays fast.
"""
from __future__ import annotations

import io
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field, TypeAdapter, ValidationError
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.dependencies.auth import get_current_user
from backend.app.dependencies.roles import require_admin
from backend.app.models.support import CATEGORIES, STATUSES, SupportMessage, SupportTicket
from backend.app.services import support as svc

router = APIRouter(tags=['Support'])

MAX_SCREENSHOT = 5 * 1024 * 1024
MAX_MESSAGE = 5000


def _optional_user(request: Request, db: Session):
    from backend.app.routes.job_board import optional_user
    return optional_user(request, db)


def _limit(key: str, limit: int, window: int):
    from backend.app.core.rate_limit import hit
    allowed, retry = hit(key, limit, window)
    if not allowed:
        raise HTTPException(429, f'You have sent several requests in a short time. Please wait {max(1, retry // 60)} '
                                 'minute(s) or email support directly.', headers={'Retry-After': str(retry)})


def _screenshot(upload: UploadFile | None) -> tuple[bytes | None, str | None]:
    """Re-encode the screenshot: proves it is an image and strips metadata."""
    if upload is None or not upload.filename:
        return None, None
    raw = upload.file.read(MAX_SCREENSHOT + 1)
    if len(raw) > MAX_SCREENSHOT:
        raise HTTPException(400, 'The screenshot is too large. Max 5 MB.')
    from PIL import Image, ImageOps, UnidentifiedImageError
    try:
        image = Image.open(io.BytesIO(raw))
        if image.format not in ('PNG', 'JPEG', 'WEBP'):
            raise HTTPException(400, 'Attach a PNG, JPG or WebP screenshot.')
        image = ImageOps.exif_transpose(image).convert('RGB')
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(400, 'The screenshot could not be read. Attach a PNG, JPG or WebP image.')
    image.thumbnail((1920, 1920))
    out = io.BytesIO()
    image.save(out, format='WEBP', quality=85)
    return out.getvalue(), 'image/webp'


def _clean(text: str | None, limit: int) -> str:
    return (text or '').replace('\x00', '').strip()[:limit]


# ── Requester ────────────────────────────────────────────────────────────────

@router.post('/tickets', status_code=201)
def create_ticket(request: Request, background: BackgroundTasks, db: Session = Depends(get_db),
                  category: str = Form('question'), subject: str = Form(...), message: str = Form(...),
                  email: Optional[str] = Form(None), name: Optional[str] = Form(None),
                  page: Optional[str] = Form(None), website: Optional[str] = Form(None),
                  screenshot: Optional[UploadFile] = File(None)):
    from backend.app.core.client_ip import client_ip
    if website:   # honeypot: real people never fill this hidden field
        return {'id': 0, 'number': 'BB-00000', 'status': 'open'}
    user = _optional_user(request, db)
    subject, message = _clean(subject, 160), _clean(message, MAX_MESSAGE)
    if len(subject) < 3:
        raise HTTPException(422, 'Add a short subject (at least 3 characters).')
    if len(message) < 10:
        raise HTTPException(422, 'Tell us a little more (at least 10 characters).')
    if category not in CATEGORIES:
        category = 'other'
    if user:
        address, display = user.email, user.full_name or name
    else:
        try:
            address = str(TypeAdapter(EmailStr).validate_python((email or '').strip()))
        except ValidationError:
            raise HTTPException(422, 'Enter a valid email address so we can reply.')
        display = name
    _limit(f'support:ip:{client_ip(request)}', 6, 3600)
    from backend.app.core.rate_limit import _email_key
    _limit(f'support:email:{_email_key(address)}', 10, 86400)
    attachment, kind = _screenshot(screenshot)
    now = datetime.utcnow()
    ticket = SupportTicket(user_id=getattr(user, 'id', None), email=address.lower(), name=_clean(display, 120) or None,
                           category=category, subject=subject, status='open', page=_clean(page, 300) or None,
                           user_agent=_clean(request.headers.get('user-agent'), 300) or None,
                           attachment=attachment, attachment_type=kind, created_at=now, updated_at=now)
    ticket.messages.append(SupportMessage(author='user', body=message, created_at=now))
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    background.add_task(svc.notify_created, ticket, message)
    return {'id': ticket.id, 'number': ticket.number, 'status': ticket.status, 'email': ticket.email}


def _mine(db: Session, user):
    query = db.query(SupportTicket)
    if user.is_verified:     # requests sent before signing in, from the same verified address
        return query.filter(or_(SupportTicket.user_id == user.id, SupportTicket.email == user.email.lower()))
    return query.filter(SupportTicket.user_id == user.id)


def _my_ticket(db: Session, user, ticket_id: int) -> SupportTicket:
    ticket = _mine(db, user).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(404, 'Request not found.')
    return ticket


@router.get('/tickets')
def my_tickets(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = _mine(db, user).order_by(SupportTicket.updated_at.desc()).limit(100).all()
    return {'items': [svc.serialize(t) for t in rows], 'support_email': svc.settings.SUPPORT_EMAIL}


@router.get('/tickets/{ticket_id}')
def my_ticket(ticket_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return svc.serialize(_my_ticket(db, user, ticket_id), messages=True)


class ReplyBody(BaseModel):
    body: str = Field(min_length=1, max_length=MAX_MESSAGE)


@router.post('/tickets/{ticket_id}/messages')
def reply_to_my_ticket(ticket_id: int, payload: ReplyBody, request: Request, background: BackgroundTasks,
                       db: Session = Depends(get_db), user=Depends(get_current_user)):
    ticket = _my_ticket(db, user, ticket_id)
    body = _clean(payload.body, MAX_MESSAGE)
    if not body:
        raise HTTPException(422, 'Write a message first.')
    _limit(f'support:reply:{user.id}', 30, 3600)
    now = datetime.utcnow()
    ticket.messages.append(SupportMessage(author='user', body=body, created_at=now))
    ticket.status, ticket.updated_at = 'open', now      # a new message reopens the request
    db.commit()
    background.add_task(svc.notify_follow_up, ticket, body)
    return svc.serialize(ticket, messages=True)


@router.post('/tickets/{ticket_id}/solve')
def solve_my_ticket(ticket_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ticket = _my_ticket(db, user, ticket_id)
    ticket.status, ticket.updated_at = 'solved', datetime.utcnow()
    db.commit()
    return svc.serialize(ticket, messages=True)


def _attachment(ticket: SupportTicket) -> Response:
    if not ticket.attachment:
        raise HTTPException(404, 'No screenshot on this request.')
    return Response(ticket.attachment, media_type=ticket.attachment_type or 'image/webp',
                    headers={'Cache-Control': 'private, max-age=300', 'Content-Disposition': 'inline'})


@router.get('/tickets/{ticket_id}/attachment')
def my_attachment(ticket_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return _attachment(_my_ticket(db, user, ticket_id))


# ── Staff (Owner console) ────────────────────────────────────────────────────

def _staff_ticket(db: Session, ticket_id: int) -> SupportTicket:
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(404, 'Request not found.')
    return ticket


@router.get('/admin/tickets')
def staff_tickets(status: Optional[str] = None, q: Optional[str] = None, page: int = 1, page_size: int = 25,
                  db: Session = Depends(get_db), admin=Depends(require_admin)):
    page, page_size = max(1, page), min(max(1, page_size), 100)
    query = db.query(SupportTicket)
    if status in STATUSES:
        query = query.filter(SupportTicket.status == status)
    if q and q.strip():
        term = q.strip()
        like = f'%{term.lower()}%'
        number = term.upper().removeprefix('BB-').lstrip('0')
        conditions = [func.lower(SupportTicket.subject).like(like), func.lower(SupportTicket.email).like(like),
                      func.lower(func.coalesce(SupportTicket.name, '')).like(like)]
        if number.isdigit():
            conditions.append(SupportTicket.id == int(number))
        query = query.filter(or_(*conditions))
    total = query.count()
    # Requests waiting for support first, then by latest activity.
    rows = (query.order_by((SupportTicket.status != 'open'), SupportTicket.updated_at.desc())
            .offset((page - 1) * page_size).limit(page_size).all())
    counts = dict(db.query(SupportTicket.status, func.count(SupportTicket.id)).group_by(SupportTicket.status).all())
    return {'items': [svc.serialize(t, staff=True) for t in rows], 'total': total, 'page': page, 'page_size': page_size,
            'counts': {s: counts.get(s, 0) for s in STATUSES}, 'support_email': svc.settings.SUPPORT_EMAIL}


@router.get('/admin/tickets/{ticket_id}')
def staff_ticket(ticket_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    return svc.serialize(_staff_ticket(db, ticket_id), messages=True, staff=True)


class StaffReply(BaseModel):
    body: str = Field(min_length=1, max_length=MAX_MESSAGE)
    solve: bool = False


@router.post('/admin/tickets/{ticket_id}/reply')
def staff_reply(ticket_id: int, payload: StaffReply, request: Request, background: BackgroundTasks,
                db: Session = Depends(get_db), admin=Depends(require_admin)):
    from backend.app.services import security_events
    ticket = _staff_ticket(db, ticket_id)
    body = _clean(payload.body, MAX_MESSAGE)
    if not body:
        raise HTTPException(422, 'Write a reply first.')
    now = datetime.utcnow()
    ticket.messages.append(SupportMessage(author='support', staff_id=admin.id, body=body, created_at=now))
    ticket.status = 'solved' if payload.solve else 'answered'
    ticket.updated_at = ticket.last_reply_at = now
    db.commit()
    background.add_task(svc.notify_answer, ticket, body)
    security_events.record('admin.support_replied', request, user=admin,
                           details={'ticket': ticket.number, 'status': ticket.status})
    return svc.serialize(ticket, messages=True, staff=True)


class StatusBody(BaseModel):
    status: Literal['open', 'answered', 'solved']


@router.patch('/admin/tickets/{ticket_id}')
def staff_status(ticket_id: int, payload: StatusBody, db: Session = Depends(get_db), admin=Depends(require_admin)):
    ticket = _staff_ticket(db, ticket_id)
    ticket.status, ticket.updated_at = payload.status, datetime.utcnow()
    db.commit()
    return svc.serialize(ticket, messages=True, staff=True)


@router.get('/admin/tickets/{ticket_id}/attachment')
def staff_attachment(ticket_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    return _attachment(_staff_ticket(db, ticket_id))
