import base64
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
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


def _commit(db, record, failure_message='Could not save the resume. Nothing was charged; please retry.'):
    """Postgres + object storage are the source of truth (Railway disk is ephemeral)."""
    from backend.app.services.resume_storage import commit_with_storage
    try:
        commit_with_storage(db, record)
    except Exception as exc:
        logger.error('resume_save_failed error_type=%s', type(exc).__name__)
        raise HTTPException(500, failure_message) from exc


def _pdf_response(record, disposition):
    from backend.app.services.resume_storage import StorageIntegrityError, load_pdf
    from backend.app.utils.pdf_generator import download_filename
    if record.status != 'completed':
        raise HTTPException(409, 'This resume is still being prepared.' if record.status == 'processing'
                            else 'This resume could not be prepared. Please run the analysis again.')
    try:
        body = load_pdf(record)
    except StorageIntegrityError as exc:
        raise HTTPException(500, 'The stored resume failed an integrity check. Please regenerate it.') from exc
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
async def upload_resume(file: UploadFile=File(...), job_description: str=Form(...), job_title: str=Form(...),
                        region: Optional[str]=Form(None),
                        db: Session=Depends(get_db), current_user=Depends(require_scan_quota)):
    from backend.app.utils.upload_validation import MAX_UPLOAD_BYTES, UploadRejected, validate_upload
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

    if settings.RESUME_PROCESSING_MODE == 'async':
        return _enqueue(db, current_user, task_id, content, filename, job_description, job_title, resolved_region)

    try:
        tailored, analysis, pdf = await run_in_threadpool(run_pipeline, content, filename, job_description,
                                                          job_title, resolved_region, task_id)
    except PipelineFailure as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    record = Resume(owner_id=current_user.id, filename=f'optimized_{task_id}.pdf', status='processing')
    try:
        complete_record(db, record, tailored, analysis, pdf)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error('resume_save_failed error_type=%s', type(exc).__name__)
        raise HTTPException(500, 'Could not save the resume. Nothing was charged; please retry.') from exc
    return {'task_id': task_id, 'status': 'completed', 'result': analysis}


def _enqueue(db, user, task_id, content, filename, job_description, job_title, region):
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
            task_id=task_id)
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
    requirements = [{'phrase': r.get('requirement'), 'priority': r.get('priority')}
                    for r in analysis.get('requirements', []) if isinstance(r, dict)]
    try:
        updated = merge_confirmed_keywords(tailored, confirmed)
        exported_resume = export_strict(updated, region, requirements)
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
def download(task_id: str, db: Session=Depends(get_db), current_user=Depends(get_current_user)):
    return _pdf_response(owned_resume(task_id, db, current_user), 'attachment')


@router.get('/download/{task_id}/docx')
def download_docx(task_id: str, db: Session=Depends(get_db), current_user=Depends(get_current_user)):
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
    region = ((record.analysis_data or {}).get('document') or {}).get('region')
    body = build_docx(tailored, region)
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
