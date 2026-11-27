import base64
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.database import get_db
from backend.app.dependencies.auth import get_current_user
from backend.app.dependencies.plan_guard import require_scan_quota
from backend.app.models.resume import Resume
from backend.app.services.resume_pipeline import (PipelineFailure, complete_record, export_strict,
                                                  provider_diagnostics, run_pipeline)  # noqa: F401 (re-export)

router = APIRouter(tags=['Resume'])
logger = logging.getLogger(__name__)


def _region_for(user, requested=None):
    from backend.app.utils.pdf_generator import resolve_region
    return resolve_region(requested, getattr(user, 'country', None))


def _pages_for(region, requested=None):
    """1, 2 or 'auto' for this export; 400 for anything else."""
    from backend.app.utils.pdf_generator import ResumeExportError, resolve_max_pages
    try:
        return resolve_max_pages(region, requested)
    except ResumeExportError as exc:
        raise HTTPException(400, str(exc)) from exc


def _commit(db, record, failure_message='Could not save the resume. Nothing was charged; please retry.'):
    """Postgres + object storage are the source of truth (Railway disk is ephemeral)."""
    from backend.app.services.resume_storage import commit_with_storage
    try:
        commit_with_storage(db, record)
    except Exception as exc:
        logger.error('resume_save_failed error_type=%s', type(exc).__name__)
        raise HTTPException(500, failure_message) from exc


def branding_or_error(db, user):
    """The branding to apply to a download the user asked to brand."""
    from backend.app.dependencies.plan_guard import plan_for
    from backend.app.services.branding import branding_for
    if plan_for(db, user) != 'enterprise':
        raise HTTPException(403, {'error': 'enterprise_required', 'message': 'Custom branding is part of the Enterprise plan.',
                                  'upgrade_url': '/pricing'})
    branding = branding_for(db, user)
    if branding is None:
        raise HTTPException(409, 'Set up your branding in Settings first: a brand name, a logo, or both.')
    return branding


def _pdf_response(record, disposition, branding=None):
    from backend.app.services.resume_storage import StorageIntegrityError, load_pdf
    from backend.app.utils.pdf_generator import download_filename
    if record.status != 'completed':
        raise HTTPException(409, 'This resume is still being prepared.' if record.status == 'processing'
                            else 'This resume could not be prepared. Please run the analysis again.')
    try:
        body = load_pdf(record)
    except StorageIntegrityError as exc:
        raise HTTPException(500, 'The stored resume failed an integrity check. Please regenerate it.') from exc
    if branding is not None:
        from backend.app.services.branding import brand_pdf
        body = brand_pdf(body, branding)
    try:
        name = json.loads(record.parsed_data or '{}').get('name')
    except (TypeError, ValueError):
        name = None
    ascii_name, utf8_name = download_filename(name)
    header = f'{disposition}; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(utf8_name)}'
    return Response(body, media_type='application/pdf',
                    headers={'Content-Disposition': header, 'Cache-Control': 'private, no-store'})


def owned_resume(identifier, db, user):
    record = db.query(Resume).filter(Resume.filename == f'optimized_{identifier}.pdf', Resume.owner_id == user.id).first()
    if not record:
        raise HTTPException(404, 'Resume not found.')
    return record


def _expire_stuck(db, record):
    """A job a worker never finished must not poll forever."""
    timeout = timedelta(minutes=settings.RESUME_JOB_TIMEOUT_MINUTES)
    started = record.updated_at or record.created_at
    if record.status == 'processing' and started and datetime.utcnow() - started > timeout:
        record.status, record.error = 'failed', 'Preparation took too long and was stopped. Nothing was charged; please retry.'
        db.commit()


def _in_flight(db, user_id) -> int:
    return db.query(Resume).filter(Resume.owner_id == user_id, Resume.status == 'processing').count()


@router.post('/upload')
async def upload_resume(file: Optional[UploadFile]=File(None), job_description: str=Form(...), job_title: str=Form(...),
                        region: Optional[str]=Form(None), job_id: Optional[int]=Form(None),
                        use_profile_resume: bool=Form(False), max_pages: Optional[str]=Form(None),
                        db: Session=Depends(get_db), current_user=Depends(require_scan_quota)):
    from backend.app.utils.upload_validation import MAX_UPLOAD_BYTES, UploadRejected, validate_upload
    if use_profile_resume:
        # The resume kept on the profile: no need to upload it again for every job.
        from backend.app.models.user import ProfileResume
        kept = db.get(ProfileResume, current_user.id)
        if kept is None:
            raise HTTPException(400, 'There is no resume on your profile. Upload one here or on your profile.')
        filename, content = kept.filename, kept.content
    elif file is None:
        raise HTTPException(400, 'Add your resume (PDF or Word).')
    else:
        filename = file.filename or ''
        content = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        # Magic bytes, page cap and zip-bomb checks before any parser runs.
        await run_in_threadpool(validate_upload, filename, content)
    except UploadRejected as exc:
        raise HTTPException(400, str(exc)) from exc
    if not job_title.strip() or len(job_title) > 200:
        raise HTTPException(400, 'Provide a target job title up to 200 characters.')
    task_id = str(uuid.uuid4())
    resolved_region = _region_for(current_user, region)
    pages = _pages_for(resolved_region, max_pages)     # validated; None means the region's default

    from backend.app.services.processing_gate import has_priority, processing_slot
    priority = has_priority(db, current_user)
    job_meta = _job_meta(db, job_id)
    if settings.RESUME_PROCESSING_MODE == 'async':
        return _enqueue(db, current_user, task_id, content, filename, job_description, job_title, resolved_region,
                        priority, job_meta, pages if max_pages else None)

    def tailor():
        with processing_slot(priority):
            return run_pipeline(content, filename, job_description, job_title, resolved_region, task_id, priority, pages)
    try:
        tailored, analysis, pdf = await run_in_threadpool(tailor)
    except PipelineFailure as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    analysis.update(job_meta)
    record = Resume(owner_id=current_user.id, filename=f'optimized_{task_id}.pdf', status='processing')
    try:
        complete_record(db, record, tailored, analysis, pdf)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error('resume_save_failed error_type=%s', type(exc).__name__)
        raise HTTPException(500, 'Could not save the resume. Nothing was charged; please retry.') from exc
    return {'task_id': task_id, 'status': 'completed', 'result': analysis}


def _job_meta(db, job_id) -> dict:
    """Which job a resume was tailored for, shown in My resumes ("Tailor again")."""
    if not job_id:
        return {}
    from backend.app.models.job import Job
    job = db.get(Job, job_id)
    return {'job_id': job.id, 'company': job.company} if job else {}


def _enqueue(db, user, task_id, content, filename, job_description, job_title, region, priority=False, job_meta=None,
             max_pages=None):
    """202 Accepted: the heavy OCR/LLM/PDF work runs on a Celery worker."""
    from backend.app.dependencies.plan_guard import remaining_scans
    remaining = remaining_scans(user.id, db)
    if remaining is not None and remaining - _in_flight(db, user.id) <= 0:
        raise HTTPException(403, 'All of this month’s scans are in use or already being prepared.')
    record = Resume(owner_id=user.id, filename=f'optimized_{task_id}.pdf', status='processing',
                    analysis_data={'task_id': task_id, 'resume_id': task_id, 'job_title': job_title, 'status': 'processing'})
    db.add(record)
    db.commit()
    try:
        from backend.app.tasks.resume_tasks import process_resume_upload
        process_resume_upload.apply_async(
            args=[task_id, user.id, base64.b64encode(content).decode('ascii'), filename, job_description, job_title, region],
            # max_pages only when chosen, so a worker on the previous release still accepts the task.
            kwargs={'priority': priority, 'job_meta': job_meta or {}, **({'max_pages': max_pages} if max_pages else {})},
            task_id=task_id,
            # Redis priority queue: 0 is served first (paid), 6 after (free).
            priority=0 if priority else 6)
    except Exception as exc:
        logger.error('resume_enqueue_failed reference=%s error_type=%s', task_id, type(exc).__name__)
        record.status, record.error = 'failed', 'The processing queue is unavailable. Nothing was charged; please retry.'
        db.commit()
        raise HTTPException(503, f'{record.error} Reference: {task_id}') from exc
    return JSONResponse({'task_id': task_id, 'status': 'processing'}, status_code=202,
                        headers={'Location': f'/api/v1/resume/status/{task_id}'})


class RegenerateRequest(BaseModel):
    confirmed_keywords: list[str] = Field(default_factory=list, max_length=50)
    region: Optional[str] = None
    max_pages: Optional[str] = None          # '1', '2' or 'auto'; default: what this resume used


@router.post('/regenerate/{task_id}')
def regenerate(task_id: str, body: RegenerateRequest, db: Session=Depends(get_db), current_user=Depends(get_current_user)):
    """Re-export with keywords the candidate explicitly confirmed. Only
    requirements reported as missing for this analysis can be confirmed."""
    from backend.app.services.resume_storage import store_pdf
    from backend.app.utils.ats_engine import extract_text
    from backend.app.utils.pdf_generator import ResumeExportError, merge_confirmed_keywords
    from backend.app.utils.resume_quality import normalize, score_requirements
    record = owned_resume(task_id, db, current_user)
    if record.status != 'completed':
        raise HTTPException(409, 'This resume is not ready yet.')
    analysis = dict(record.analysis_data or {})
    try:
        tailored = json.loads(record.parsed_data or '{}')
    except ValueError:
        tailored = {}
    allowed = {normalize(k): k for k in analysis.get('suggested_skills') or analysis.get('missing_list') or []}
    previous = list(analysis.get('confirmed_keywords') or [])
    requested = [k.strip() for k in body.confirmed_keywords if isinstance(k, str) and k.strip()]
    unknown = [k for k in requested if normalize(k) not in allowed and normalize(k) not in {normalize(p) for p in previous}]
    if unknown:
        raise HTTPException(422, 'Only suggested skills from this analysis can be confirmed.')
    confirmed = previous + [allowed.get(normalize(k), k) for k in requested if normalize(k) not in {normalize(p) for p in previous}]
    region = _region_for(current_user, body.region or analysis.get('document', {}).get('region'))
    pages = _pages_for(region, body.max_pages or analysis.get('document', {}).get('max_pages'))
    requirements = [{'phrase': r.get('requirement'), 'priority': r.get('priority')}
                    for r in analysis.get('requirements', []) if isinstance(r, dict)]
    try:
        updated = merge_confirmed_keywords(tailored, confirmed)
        exported_resume = export_strict(updated, region, requirements, pages)
        rescored = score_requirements(extract_text(exported_resume.pdf, 'resume.pdf'),
                                      analysis.get('job_description', ''), requirements)
    except ResumeExportError as exc:
        raise HTTPException(422, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, 'The resume could not be regenerated. Please retry.') from exc
    confirmed_keys = {normalize(k) for k in confirmed}
    analysis.update(rescored, suggested_skills=[k for k in rescored.get('missing_list', []) if normalize(k) not in confirmed_keys],
                    confirmed_keywords=confirmed, document=exported_resume.info(),
                    scores={'before': analysis.get('original_score'), 'after': rescored['overall_score']},
                    task_id=task_id, resume_id=task_id, status='success')
    store_pdf(record, exported_resume.pdf)
    record.parsed_data = json.dumps(updated)
    record.ats_score = analysis['overall_score']
    record.analysis_data = analysis
    _commit(db, record)
    return {'task_id': task_id, 'status': 'completed', 'result': analysis}


@router.get('/preview/{resume_id}')
def preview(resume_id: str, db: Session=Depends(get_db), current_user=Depends(get_current_user)):
    return _pdf_response(owned_resume(resume_id, db, current_user), 'inline')


@router.get('/status/{task_id}')
def status(task_id: str, db: Session=Depends(get_db), current_user=Depends(get_current_user)):
    # Primary database on purpose: read-your-writes right after upload/regenerate.
    record = owned_resume(task_id, db, current_user)
    _expire_stuck(db, record)
    if record.status == 'processing':
        return {'task_id': task_id, 'status': 'processing'}
    if record.status == 'failed':
        return {'task_id': task_id, 'status': 'failed', 'error': record.error or 'Resume preparation failed. Please retry.'}
    return {'task_id': task_id, 'status': 'completed',
            'result': {**(record.analysis_data or {}), 'task_id': task_id, 'resume_id': task_id}}


@router.get('/download/{task_id}')
def download(task_id: str, branded: bool=False, db: Session=Depends(get_db), current_user=Depends(get_current_user)):
    record = owned_resume(task_id, db, current_user)
    return _pdf_response(record, 'attachment', branding_or_error(db, current_user) if branded else None)


@router.get('/download/{task_id}/docx')
def download_docx(task_id: str, branded: bool=False, db: Session=Depends(get_db), current_user=Depends(get_current_user)):
    """Editable Word copy of the tailored resume (same content as the PDF)."""
    from backend.app.utils.docx_export import build_docx
    from backend.app.utils.pdf_generator import download_filename
    record = owned_resume(task_id, db, current_user)
    if record.status != 'completed':
        raise HTTPException(409, 'This resume is not ready yet.')
    try:
        tailored = json.loads(record.parsed_data or '{}')
    except (TypeError, ValueError):
        tailored = {}
    if not isinstance(tailored, dict) or not tailored:
        raise HTTPException(409, 'This resume has no editable content. Please run the analysis again.')
    document = (record.analysis_data or {}).get('document') or {}
    region = document.get('region')
    # Same content as the PDF: the same page length, region rules and condensing.
    from backend.app.utils.pdf_generator import ResumeExportError, export_resume
    requirements = [r.get('requirement') for r in (record.analysis_data or {}).get('requirements', []) if isinstance(r, dict)]
    try:
        rendered = export_resume(tailored, region=region, page_size=document.get('page_size'),
                                 priority_keywords=requirements, max_pages=document.get('max_pages', 1))
        content = rendered.content
    except ResumeExportError:
        content = tailored
    body = build_docx(content, region, document.get('page_size'))
    if branded:
        from backend.app.services.branding import brand_docx
        body = brand_docx(body, branding_or_error(db, current_user))
    ascii_name, utf8_name = download_filename(tailored.get('name'))
    ascii_name, utf8_name = (n.rsplit('.', 1)[0] + '.docx' for n in (ascii_name, utf8_name))
    header = f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(utf8_name)}'
    return Response(body, media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    headers={'Content-Disposition': header, 'Cache-Control': 'private, no-store'})


@router.get('/url/{task_id}')
def signed_url(task_id: str, db: Session=Depends(get_db), current_user=Depends(get_current_user)):
    """Short-lived presigned URL when the PDF is in object storage; otherwise
    the client streams /download (same auth either way)."""
    from backend.app.services.resume_storage import PRESIGNED_TTL_SECONDS, presigned_url
    record = owned_resume(task_id, db, current_user)
    if record.status != 'completed':
        raise HTTPException(409, 'This resume is not ready yet.')
    url = presigned_url(record)
    return {'url': url, 'expires_in': PRESIGNED_TTL_SECONDS if url else None,
            'download_path': f'/api/v1/resume/download/{task_id}'}


# ── My resumes (history) ──────────────────────────────────────────────────────
HISTORY_LIMIT_PAID = 30   # "Resume history (last 30 scans)" on Pro and Enterprise
HISTORY_LIMIT_FREE = 1    # free plan: the latest result only


@router.get('/history')
def history(db: Session=Depends(get_db), current_user=Depends(get_current_user)):
    """The candidate's tailored resumes, newest first."""
    from backend.app.services.processing_gate import has_priority
    paid = has_priority(db, current_user)
    limit = HISTORY_LIMIT_PAID if paid else HISTORY_LIMIT_FREE
    query = db.query(Resume).filter(Resume.owner_id == current_user.id, Resume.status == 'completed',
                                    Resume.filename.like('optimized_%'))
    total = query.count()
    rows = query.order_by(Resume.created_at.desc(), Resume.id.desc()).limit(limit).all()
    items = []
    for record in rows:
        analysis = record.analysis_data or {}
        scores = analysis.get('scores') or {}
        items.append({
            'task_id': record.filename[len('optimized_'):-len('.pdf')],
            'created_at': record.created_at.isoformat() + 'Z' if record.created_at else None,
            'job_title': analysis.get('job_title') or 'Tailored resume',
            'company': analysis.get('company'), 'job_id': analysis.get('job_id'),
            'score_before': scores.get('before', analysis.get('original_score')),
            'score_after': scores.get('after', analysis.get('overall_score')),
            'job_description': (analysis.get('job_description') or '')[:20000],
        })
    return {'items': items, 'total': total, 'limit': limit, 'history_enabled': paid}


@router.delete('/{task_id}')
def delete_resume(task_id: str, db: Session=Depends(get_db), current_user=Depends(get_current_user)):
    """Delete one tailored resume and its stored PDF."""
    from backend.app.services.resume_storage import delete_pdf
    record = owned_resume(task_id, db, current_user)
    delete_pdf(record)
    db.delete(record)
    db.commit()
    return {'deleted': True}


# ── Bulk resume processing (Enterprise) ───────────────────────────────────────
BULK_MAX_JOBS = 10


def _has_enterprise(db, user) -> bool:
    from backend.app.dependencies.plan_guard import plan_for
    return plan_for(db, user) == 'enterprise'


def _bulk_targets(db, job_ids: str | None, pasted: str | None) -> list[dict]:
    """Jobs picked from the board (ids) plus pasted ones ({title, description})."""
    from backend.app.models.job import Job
    targets = []
    for raw in (job_ids or '').split(','):
        if raw.strip().isdigit():
            job = db.get(Job, int(raw))
            if job and job.is_active:
                targets.append({'title': job.title, 'description': job.description or '',
                                'meta': {'job_id': job.id, 'company': job.company}})
    if pasted:
        try:
            items = json.loads(pasted)
        except ValueError as exc:
            raise HTTPException(400, 'Pasted jobs could not be read.') from exc
        for item in items if isinstance(items, list) else []:
            title = str((item or {}).get('title') or '').strip()[:200]
            description = str((item or {}).get('description') or '').strip()
            if title and len(description) >= 50:
                targets.append({'title': title, 'description': description, 'meta': {}})
    if not targets:
        raise HTTPException(400, 'Choose at least one job, or paste a title and a full job description.')
    if len(targets) > BULK_MAX_JOBS:
        raise HTTPException(400, f'Choose up to {BULK_MAX_JOBS} jobs at a time.')
    return targets


def run_bulk_batch(batch_id: str | None, owner_id: int, content: bytes, filename: str, region: str, items: list[dict],
                   max_pages=None):
    """Sync mode: tailor each job in turn on priority capacity; each result lands in My resumes.
    Also used by the integrations API for single jobs (no batch)."""
    from backend.app.database import SessionLocal
    from backend.app.services.processing_gate import processing_slot
    db = SessionLocal()
    try:
        for item in items:
            record = db.query(Resume).filter(Resume.filename == f"optimized_{item['task_id']}.pdf",
                                             Resume.owner_id == owner_id).first()
            if record is None or record.status != 'processing':
                continue
            try:
                with processing_slot(True):
                    tailored, analysis, pdf = run_pipeline(content, filename, item['description'], item['title'],
                                                           region, item['task_id'], True, max_pages)
                analysis.update(item['meta'], **({'batch_id': batch_id} if batch_id else {}))
                complete_record(db, record, tailored, analysis, pdf)
            except Exception as exc:
                db.rollback()
                message = getattr(exc, 'message', None) or getattr(exc, 'detail', None)
                record = db.query(Resume).filter(Resume.filename == f"optimized_{item['task_id']}.pdf").first()
                if record is not None:
                    record.status = 'failed'
                    record.error = (message if isinstance(message, str) else
                                    f"Tailoring failed. Nothing was charged. Reference: {item['task_id']}")[:500]
                    db.commit()
    finally:
        db.close()


@router.post('/bulk', status_code=202)
async def bulk_tailor(background: BackgroundTasks, file: UploadFile=File(...), job_ids: Optional[str]=Form(None),
                      pasted_jobs: Optional[str]=Form(None), region: Optional[str]=Form(None),
                      max_pages: Optional[str]=Form(None),
                      db: Session=Depends(get_db), current_user=Depends(get_current_user)):
    """Enterprise: tailor one resume to up to 10 jobs at once, in the background."""
    from backend.app.models.resume import ResumeBatch
    from backend.app.utils.upload_validation import MAX_UPLOAD_BYTES, UploadRejected, validate_upload
    if not _has_enterprise(db, current_user):
        raise HTTPException(403, {'error': 'enterprise_required', 'message': 'Bulk tailoring is part of the Enterprise plan.',
                                  'upgrade_url': '/pricing'})
    filename = file.filename or ''
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        await run_in_threadpool(validate_upload, filename, content)
    except UploadRejected as exc:
        raise HTTPException(400, str(exc)) from exc
    targets = _bulk_targets(db, job_ids, pasted_jobs)
    batch_id, resolved_region = str(uuid.uuid4()), _region_for(current_user, region)
    pages = _pages_for(resolved_region, max_pages)
    items = []
    for target in targets:
        task_id = str(uuid.uuid4())
        db.add(Resume(owner_id=current_user.id, filename=f'optimized_{task_id}.pdf', status='processing',
                      analysis_data={'task_id': task_id, 'resume_id': task_id, 'job_title': target['title'],
                                     'batch_id': batch_id, 'status': 'processing', **target['meta']}))
        items.append({**target, 'task_id': task_id})
    db.add(ResumeBatch(id=batch_id, owner_id=current_user.id, task_ids=[i['task_id'] for i in items]))
    db.commit()
    if settings.RESUME_PROCESSING_MODE == 'async':
        from backend.app.tasks.resume_tasks import process_resume_upload
        encoded = base64.b64encode(content).decode('ascii')
        for item in items:
            process_resume_upload.apply_async(
                args=[item['task_id'], current_user.id, encoded, filename, item['description'], item['title'], resolved_region],
                kwargs={'priority': True, 'job_meta': {**item['meta'], 'batch_id': batch_id},
                        **({'max_pages': pages} if max_pages else {})},
                task_id=item['task_id'], priority=0)
    else:
        background.add_task(run_bulk_batch, batch_id, current_user.id, content, filename, resolved_region, items, pages)
    return {'batch_id': batch_id, 'count': len(items)}


@router.get('/bulk/{batch_id}')
def bulk_status(batch_id: str, db: Session=Depends(get_db), current_user=Depends(get_current_user)):
    from backend.app.models.resume import ResumeBatch
    batch = db.query(ResumeBatch).filter(ResumeBatch.id == batch_id, ResumeBatch.owner_id == current_user.id).first()
    if batch is None:
        raise HTTPException(404, 'Batch not found.')
    records = {r.filename: r for r in db.query(Resume).filter(
        Resume.owner_id == current_user.id,
        Resume.filename.in_([f'optimized_{t}.pdf' for t in batch.task_ids])).all()}
    items = []
    for task_id in batch.task_ids:
        record = records.get(f'optimized_{task_id}.pdf')
        if record is not None:
            _expire_stuck(db, record)
        analysis = (record.analysis_data or {}) if record else {}
        scores = analysis.get('scores') or {}
        items.append({'task_id': task_id, 'status': record.status if record else 'deleted',
                      'job_title': analysis.get('job_title'), 'company': analysis.get('company'),
                      'score_after': scores.get('after') if record and record.status == 'completed' else None,
                      'error': record.error if record and record.status == 'failed' else None})
    done = sum(i['status'] in ('completed', 'failed', 'deleted') for i in items)
    return {'batch_id': batch_id, 'items': items, 'done': done, 'total': len(items)}
