"""Enterprise integrations API.

Two routers:

* ``keys_router`` (``/api/v1/api-keys``, signed-in session): create, list and
  revoke API keys from Settings -> API.
* ``router`` (``/api/public/v1``, API key): tailor a resume, check its status,
  download the PDF or Word file, and search the job board.

Keys are sent as ``Authorization: Bearer bb_live_...`` (or ``X-API-Key``). Each
key may make 60 requests per minute. A key works only while its owner has
Enterprise (directly or through a team) and is not suspended.
"""
import base64
import secrets
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.database import get_db
from backend.app.dependencies.auth import get_current_user
from backend.app.dependencies.plan_guard import plan_for
from backend.app.models.api_key import KEY_PREFIX, MAX_ACTIVE_KEYS, RATE_LIMIT_PER_MINUTE, ApiKey
from backend.app.models.resume import Resume
from backend.app.models.user import User
from backend.app.services.audit import record_event
from backend.app.services.auth_service import hash_token

keys_router = APIRouter(tags=['API keys'])
router = APIRouter(tags=['Integrations API'])

MAX_IN_FLIGHT = 10            # resumes being prepared at once through the API


def _enterprise_required(message='API access is part of the Enterprise plan.'):
    return HTTPException(403, {'error': 'enterprise_required', 'message': message, 'upgrade_url': '/pricing'})


def _key_json(key: ApiKey) -> dict:
    return {'id': key.id, 'name': key.name, 'prefix': key.prefix,
            'created_at': key.created_at.isoformat() + 'Z',
            'last_used_at': key.last_used_at.isoformat() + 'Z' if key.last_used_at else None,
            'revoked_at': key.revoked_at.isoformat() + 'Z' if key.revoked_at else None}


# ── Key management (Settings -> API) ──────────────────────────────────────────

class NewKey(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)


@keys_router.get('')
def list_keys(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    keys = db.query(ApiKey).filter(ApiKey.owner_id == current_user.id).order_by(ApiKey.created_at.desc()).all()
    return {'enabled': plan_for(db, current_user) == 'enterprise', 'max_keys': MAX_ACTIVE_KEYS,
            'rate_limit_per_minute': RATE_LIMIT_PER_MINUTE,
            'keys': [_key_json(k) for k in keys if k.revoked_at is None]}


@keys_router.post('', status_code=201)
def create_key(body: NewKey, request: Request, db: Session = Depends(get_db),
               current_user: User = Depends(get_current_user)):
    if plan_for(db, current_user) != 'enterprise':
        raise _enterprise_required()
    active = db.query(ApiKey).filter(ApiKey.owner_id == current_user.id, ApiKey.revoked_at.is_(None)).count()
    if active >= MAX_ACTIVE_KEYS:
        raise HTTPException(400, f'You can have up to {MAX_ACTIVE_KEYS} active keys. Revoke one you no longer use first.')
    raw = KEY_PREFIX + secrets.token_urlsafe(32)
    key = ApiKey(owner_id=current_user.id, name=body.name.strip(), prefix=raw[:len(KEY_PREFIX) + 4],
                 key_hash=hash_token(raw))
    db.add(key)
    db.commit()
    record_event('api_key.create', actor=current_user, trace_id=getattr(request.state, 'trace_id', None),
                 details={'key_id': key.id})
    # The only time the full key is returned. It cannot be shown again.
    return {**_key_json(key), 'key': raw}


@keys_router.delete('/{key_id}')
def revoke_key(key_id: int, request: Request, db: Session = Depends(get_db),
               current_user: User = Depends(get_current_user)):
    key = db.query(ApiKey).filter(ApiKey.id == key_id, ApiKey.owner_id == current_user.id,
                                  ApiKey.revoked_at.is_(None)).first()
    if not key:
        raise HTTPException(404, 'API key not found.')
    key.revoked_at = datetime.utcnow()
    db.commit()
    record_event('api_key.revoke', actor=current_user, trace_id=getattr(request.state, 'trace_id', None),
                 details={'key_id': key.id})
    return {'revoked': True}


# ── API-key authentication ────────────────────────────────────────────────────

def _bad_key():
    return HTTPException(401, {'error': 'invalid_api_key', 'message': 'Missing, invalid or revoked API key.'},
                         headers={'WWW-Authenticate': 'Bearer'})


def api_user(request: Request, response: Response, db: Session = Depends(get_db)) -> User:
    header = request.headers.get('authorization', '')
    raw = header[7:].strip() if header.lower().startswith('bearer ') else request.headers.get('x-api-key', '').strip()
    if not raw.startswith(KEY_PREFIX):
        raise _bad_key()
    key = db.query(ApiKey).filter(ApiKey.key_hash == hash_token(raw), ApiKey.revoked_at.is_(None)).first()
    if key is None:
        raise _bad_key()
    from backend.app.core.rate_limit import hit
    allowed, retry = hit(f'apikey:{key.id}', RATE_LIMIT_PER_MINUTE, 60)
    if not allowed:
        raise HTTPException(429, {'error': 'rate_limited',
                                  'message': f'This key is limited to {RATE_LIMIT_PER_MINUTE} requests per minute.'},
                            headers={'Retry-After': str(retry), 'X-RateLimit-Limit': str(RATE_LIMIT_PER_MINUTE)})
    response.headers['X-RateLimit-Limit'] = str(RATE_LIMIT_PER_MINUTE)
    user = db.get(User, key.owner_id)
    if user is None or user.suspended_at is not None:
        raise _bad_key()
    if plan_for(db, user) != 'enterprise':
        raise _enterprise_required('API access is part of the Enterprise plan. This key works again once '
                                   'the account has Enterprise.')
    now = datetime.utcnow()
    if key.last_used_at is None or now - key.last_used_at > timedelta(minutes=1):
        key.last_used_at = now
        db.commit()
    request.state.user = user
    request.state.actor = SimpleNamespace(id=user.id, email=user.email, role=getattr(user, 'role', None), is_hr=False)
    request.state.api_key_id = key.id
    return user


# ── Integrations API ──────────────────────────────────────────────────────────

def _links(task_id: str) -> dict:
    base = '/api/public/v1/resumes/' + task_id
    return {'self': base, 'pdf': base + '/pdf', 'docx': base + '/docx'}


@router.get('/me')
def me(db: Session = Depends(get_db), user: User = Depends(api_user)):
    return {'email': user.email, 'name': user.full_name, 'plan': plan_for(db, user),
            'rate_limit_per_minute': RATE_LIMIT_PER_MINUTE}


@router.get('/jobs')
def search_jobs(q: Optional[str] = Query(None, max_length=100), category: Optional[str] = None,
                work_type: Optional[str] = Query(None, pattern='^(remote|hybrid|onsite)$'),
                region: Optional[str] = None, posted_within: Optional[int] = Query(None, ge=1, le=90),
                page: int = Query(1, ge=1, le=200), page_size: int = Query(20, ge=1, le=50),
                db: Session = Depends(get_db), user: User = Depends(api_user)):
    """Active jobs on the board, newest first (employer postings on Baalebos first), one per role per company."""
    from backend.app.models.job import Job
    from backend.app.routes.job_board import _filtered, _one_per_role, _serialize, user_skills
    query = _filtered(db, q=(q or '').strip(), category=category, work_type=work_type, region=region,
                      posted_within=posted_within)
    rows = query.with_entities(Job.id, Job.posted_by_hr, Job.title, Job.company, Job.location,
                               Job.published_at, Job.first_seen_at, Job.scraped_at).all()
    rows.sort(key=lambda r: (bool(r.posted_by_hr),
                             (r.published_at or r.first_seen_at or r.scraped_at or datetime.min).timestamp()), reverse=True)
    rows = _one_per_role(rows)
    ids = [r.id for r in rows[(page - 1) * page_size: page * page_size]]
    jobs = {j.id: j for j in db.query(Job).filter(Job.id.in_(ids))} if ids else {}
    mine = user_skills(db, user)
    return {'total': len(rows), 'page': page, 'page_size': page_size,
            'items': [_serialize(jobs[i], mine) for i in ids if i in jobs]}


@router.get('/jobs/{job_id}')
def get_job(job_id: int, db: Session = Depends(get_db), user: User = Depends(api_user)):
    from backend.app.models.job import Job
    from backend.app.routes.job_board import _serialize, user_skills
    job = db.query(Job).filter(Job.id == job_id, Job.is_active == True).first()  # noqa: E712
    if not job:
        raise HTTPException(404, 'This job is no longer available.')
    return _serialize(job, user_skills(db, user), detail=True)


@router.post('/resumes', status_code=202)
async def tailor(background: BackgroundTasks, file: UploadFile = File(...), job_id: Optional[int] = Form(None),
                 job_title: Optional[str] = Form(None), job_description: Optional[str] = Form(None),
                 region: Optional[str] = Form(None), db: Session = Depends(get_db), user: User = Depends(api_user)):
    """Tailor a resume to one job: a job on the board (job_id) or your own title and description.
    Returns at once with a task_id; poll GET /resumes/{task_id} until it is completed or failed."""
    from backend.app.models.job import Job
    from backend.app.routes.resume import _in_flight, _region_for, run_bulk_batch
    from backend.app.utils.upload_validation import MAX_UPLOAD_BYTES, UploadRejected, validate_upload
    if job_id is not None:
        job = db.query(Job).filter(Job.id == job_id, Job.is_active == True).first()  # noqa: E712
        if not job:
            raise HTTPException(404, 'This job is no longer available.')
        title, description, meta = job.title, job.description or '', {'job_id': job.id, 'company': job.company}
    else:
        title, description, meta = (job_title or '').strip(), (job_description or '').strip(), {}
        if not title or len(title) > 200:
            raise HTTPException(400, 'Send job_id, or job_title (up to 200 characters) with job_description.')
        if len(description) < 50:
            raise HTTPException(400, 'Send the full job description (at least 50 characters).')
    if _in_flight(db, user.id) >= MAX_IN_FLIGHT:
        raise HTTPException(429, {'error': 'too_many_in_progress',
                                  'message': f'Up to {MAX_IN_FLIGHT} resumes can be prepared at once. '
                                             'Wait for some to finish, then retry.'})
    filename = file.filename or ''
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        await run_in_threadpool(validate_upload, filename, content)
    except UploadRejected as exc:
        raise HTTPException(400, str(exc)) from exc
    task_id, resolved_region = str(uuid.uuid4()), _region_for(user, region)
    db.add(Resume(owner_id=user.id, filename=f'optimized_{task_id}.pdf', status='processing',
                  analysis_data={'task_id': task_id, 'resume_id': task_id, 'job_title': title, 'status': 'processing',
                                 **meta}))
    db.commit()
    if settings.RESUME_PROCESSING_MODE == 'async':
        from backend.app.tasks.resume_tasks import process_resume_upload
        try:
            process_resume_upload.apply_async(
                args=[task_id, user.id, base64.b64encode(content).decode('ascii'), filename, description, title,
                      resolved_region],
                kwargs={'priority': True, 'job_meta': meta}, task_id=task_id, priority=0)
        except Exception as exc:
            record = db.query(Resume).filter(Resume.filename == f'optimized_{task_id}.pdf').first()
            record.status, record.error = 'failed', 'The processing queue is unavailable. Nothing was charged; please retry.'
            db.commit()
            raise HTTPException(503, f'{record.error} Reference: {task_id}') from exc
    else:
        background.add_task(run_bulk_batch, None, user.id, content, filename, resolved_region,
                            [{'title': title, 'description': description, 'meta': meta, 'task_id': task_id}])
    return JSONResponse({'task_id': task_id, 'status': 'processing', 'links': _links(task_id)}, status_code=202,
                        headers={'Location': _links(task_id)['self']})


@router.get('/resumes/{task_id}')
def resume_status(task_id: str, db: Session = Depends(get_db), user: User = Depends(api_user)):
    from backend.app.routes.resume import _expire_stuck, owned_resume
    record = owned_resume(task_id, db, user)
    _expire_stuck(db, record)
    analysis = record.analysis_data or {}
    scores = analysis.get('scores') or {}
    body = {'task_id': task_id, 'status': record.status, 'job_title': analysis.get('job_title'),
            'company': analysis.get('company'), 'job_id': analysis.get('job_id'),
            'created_at': record.created_at.isoformat() + 'Z' if record.created_at else None}
    if record.status == 'completed':
        body.update(match_before=scores.get('before', analysis.get('original_score')),
                    match_after=scores.get('after', analysis.get('overall_score')),
                    missing_keywords=(analysis.get('suggested_skills') or analysis.get('missing_list') or [])[:20],
                    links=_links(task_id))
    elif record.status == 'failed':
        body['error'] = record.error or 'Resume preparation failed. Please retry.'
    return body


@router.get('/resumes/{task_id}/pdf')
def resume_pdf(task_id: str, branded: bool = False, db: Session = Depends(get_db), user: User = Depends(api_user)):
    from backend.app.routes.resume import _pdf_response, branding_or_error, owned_resume
    record = owned_resume(task_id, db, user)
    return _pdf_response(record, 'attachment', branding_or_error(db, user) if branded else None)


@router.get('/resumes/{task_id}/docx')
def resume_docx(task_id: str, branded: bool = False, db: Session = Depends(get_db), user: User = Depends(api_user)):
    from backend.app.routes.resume import download_docx
    return download_docx(task_id, branded, db, user)
