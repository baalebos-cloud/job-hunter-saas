import uuid
import json
import logging
from typing import Optional
from urllib.parse import quote
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.dependencies.auth import get_current_user
from backend.app.dependencies.plan_guard import require_scan_quota
from backend.app.models.resume import Resume

router = APIRouter(tags=['Resume'])
logger = logging.getLogger(__name__)


def provider_diagnostics(exc):
    """Allowlisted metadata only; provider messages can contain candidate data."""
    allowed = {
        'code': {'json_validate_failed', 'invalid_api_key', 'model_not_found', 'rate_limit_exceeded', 'context_length_exceeded', 'invalid_request_error'},
        'type': {'invalid_request_error', 'authentication_error', 'rate_limit_error'},
        'param': {'response_format', 'response_format.json_schema', 'model', 'reasoning_effort', 'max_completion_tokens', 'temperature'},
    }
    result = {}
    for field, values in allowed.items():
        value = getattr(exc, field, None)
        result[field] = value if isinstance(value, str) and value in values else ('other' if value is not None else 'none')
    return result


def _region_for(user, requested=None):
    from backend.app.utils.pdf_generator import resolve_region
    return resolve_region(requested, getattr(user, 'country', None))


def _export(tailored, region, requirements):
    """Render the strictly one-page resume; candidate content only."""
    from backend.app.utils.pdf_generator import export_resume, ResumeExportError
    from pypdf import PdfReader
    from io import BytesIO
    keywords = [r.get('phrase') or r.get('requirement') for r in requirements or [] if isinstance(r, dict)]
    result = export_resume(tailored, region=region, priority_keywords=keywords)
    if len(PdfReader(BytesIO(result.pdf)).pages) != 1:  # hard invariant, checked again before storing
        raise ResumeExportError('The resume could not be fitted on one page.')
    return result


def _save(db, record):
    """Postgres is the source of truth (Railway's filesystem is ephemeral)."""
    try:
        db.add(record)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error('resume_save_failed error_type=%s', type(exc).__name__)
        raise HTTPException(500, 'Could not save the resume. Nothing was charged; please retry.') from exc


def _pdf_response(record, disposition):
    from backend.app.utils.pdf_generator import download_filename
    try:
        name = json.loads(record.parsed_data or '{}').get('name')
    except (TypeError, ValueError):
        name = None
    ascii_name, utf8_name = download_filename(name)
    header = f'{disposition}; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(utf8_name)}'
    return Response(record.content, media_type='application/pdf',
                    headers={'Content-Disposition': header, 'Cache-Control': 'private, no-store'})


def owned_resume(identifier, db, user):
    record = db.query(Resume).filter(Resume.filename == f'optimized_{identifier}.pdf', Resume.owner_id == user.id).first()
    if not record:
        raise HTTPException(404, 'Resume not found.')
    return record


@router.post('/upload')
async def upload_resume(file: UploadFile=File(...), job_description: str=Form(...), job_title: str=Form(...),
                        region: Optional[str]=Form(None),
                        db: Session=Depends(get_db), current_user=Depends(require_scan_quota)):
    from backend.app.utils.upload_validation import validate_upload, UploadRejected, MAX_UPLOAD_BYTES
    filename = file.filename or ''
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        # Magic bytes, page cap and zip-bomb checks before any parser runs.
        await run_in_threadpool(validate_upload, filename, content)
    except UploadRejected as exc:
        raise HTTPException(400, str(exc)) from exc
    if not job_title.strip() or len(job_title)>200: raise HTTPException(400, 'Provide a target job title up to 200 characters.')
    task_id = str(uuid.uuid4())
    resolved_region = _region_for(current_user, region)
    stage = 'load_pipeline'
    def prepare():
        nonlocal stage
        from backend.app.utils.ats_engine import (extract_text, extract_text_with_ocr, extract_resume_data, extract_requirements,
                                                  rewrite_resume_for_job, prepare_resume_text, clean_job_description)
        from backend.app.utils.resume_quality import merge_rewrite, score_requirements
        stage = 'extract_text'
        text = prepare_resume_text(extract_text_with_ocr(content, filename), filename)
        clean_jd = clean_job_description(job_description)
        stage = 'extract_resume_data'
        original = extract_resume_data(text)
        stage = 'extract_requirements'
        requirements = extract_requirements(job_description)
        stage = 'score_original'
        before = score_requirements(text, clean_jd, requirements)
        stage = 'rewrite_resume'
        rewrite = rewrite_resume_for_job(resume_text=text, resume_data=original, job_description=clean_jd, job_title=job_title)
        stage = 'validate_rewrite'
        tailored = merge_rewrite(original, rewrite, text)
        stage = 'export_pdf'
        exported_resume = _export(tailored, resolved_region, requirements)
        pdf = exported_resume.pdf
        stage = 'read_exported_pdf'
        exported = extract_text(pdf, 'resume.pdf')
        stage = 'score_exported_pdf'
        analysis = score_requirements(exported, clean_jd, requirements)
        analysis.update(original_score=before['overall_score'],
                        scores={'before': before['overall_score'], 'after': analysis['overall_score']}, confirmation_questions=rewrite.get('confirmation_questions',[]),
                        suggestions_applied=rewrite.get('suggestions_applied',[]), job_title=job_title,
                        job_description=clean_jd, task_id=task_id, resume_id=task_id, status='success',
                        # Missing requirements are suggestions only; they enter the
                        # resume solely through /regenerate with explicit confirmation.
                        suggested_skills=list(analysis.get('missing_list', [])), confirmed_keywords=[],
                        document=exported_resume.info())
        return tailored, analysis, pdf
    try:
        tailored, analysis, pdf = await run_in_threadpool(prepare)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        # Do not log exception bodies: provider errors may echo candidate data.
        provider_status = getattr(exc, 'status_code', None)
        diagnostic = provider_diagnostics(exc)
        logger.error('resume_preparation_failed reference=%s stage=%s error_type=%s provider_status=%s provider_code=%s provider_type=%s provider_param=%s',
                     task_id, stage, type(exc).__name__, provider_status,
                     diagnostic['code'], diagnostic['type'], diagnostic['param'])
        from openai import AuthenticationError, PermissionDeniedError, RateLimitError, APITimeoutError, APIConnectionError, BadRequestError, NotFoundError
        if isinstance(exc, (AuthenticationError, PermissionDeniedError)):
            message = 'The AI provider rejected this service’s credentials or permissions. Please contact support.'
        elif isinstance(exc, RateLimitError):
            message = 'The AI provider’s usage limit has been reached. Please retry later or contact support.'
        elif isinstance(exc, (APITimeoutError, APIConnectionError)):
            message = 'The AI provider could not be reached in time. Please retry later.'
        elif isinstance(exc, (BadRequestError, NotFoundError)):
            message = 'The AI provider could not accept this request or model configuration. Please contact support.'
        else:
            message = 'Resume preparation is unavailable. Please retry.'
        raise HTTPException(503, f'{message} No completed resume was saved. Reference: {task_id}') from exc
    record = Resume(owner_id=current_user.id, filename=f'optimized_{task_id}.pdf', content=pdf,
                    parsed_data=json.dumps(tailored), ats_score=analysis['overall_score'], analysis_data=analysis)
    from backend.app.dependencies.plan_guard import consume_scan
    consume_scan(current_user.id, db)
    _save(db, record)
    return {'task_id':task_id,'status':'completed','result':analysis}


class RegenerateRequest(BaseModel):
    confirmed_keywords: list[str] = Field(default_factory=list, max_length=50)
    region: Optional[str] = None


@router.post('/regenerate/{task_id}')
def regenerate(task_id: str, body: RegenerateRequest, db: Session=Depends(get_db), current_user=Depends(get_current_user)):
    """Re-export with keywords the candidate explicitly confirmed. Only
    requirements reported as missing for this analysis can be confirmed."""
    from backend.app.utils.ats_engine import extract_text
    from backend.app.utils.resume_quality import score_requirements, normalize
    from backend.app.utils.pdf_generator import merge_confirmed_keywords, ResumeExportError
    record = owned_resume(task_id, db, current_user)
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
        exported_resume = _export(updated, region, requirements)
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
    record.content = exported_resume.pdf
    record.parsed_data = json.dumps(updated)
    record.ats_score = analysis['overall_score']
    record.analysis_data = analysis
    _save(db, record)
    return {'task_id': task_id, 'status': 'completed', 'result': analysis}


@router.get('/preview/{resume_id}')
def preview(resume_id: str, db: Session=Depends(get_db), current_user=Depends(get_current_user)):
    record = owned_resume(resume_id,db,current_user)
    return _pdf_response(record, 'inline')


@router.get('/status/{task_id}')
def status(task_id: str, db: Session=Depends(get_db), current_user=Depends(get_current_user)):
    record = owned_resume(task_id,db,current_user)
    return {'task_id':task_id,'status':'completed','result':{**(record.analysis_data or {}), 'task_id':task_id, 'resume_id':task_id}}


@router.get('/download/{task_id}')
def download(task_id: str, db: Session=Depends(get_db), current_user=Depends(get_current_user)):
    record = owned_resume(task_id,db,current_user)
    return _pdf_response(record, 'attachment')
