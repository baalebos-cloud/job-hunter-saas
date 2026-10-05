import uuid
import json
import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import Response
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.dependencies.auth import get_current_user
from backend.app.dependencies.plan_guard import require_scan_quota
from backend.app.models.resume import Resume

router = APIRouter(tags=['Resume'])
logger = logging.getLogger(__name__)


def owned_resume(identifier, db, user):
    record = db.query(Resume).filter(Resume.filename == f'optimized_{identifier}.pdf', Resume.owner_id == user.id).first()
    if not record:
        raise HTTPException(404, 'Resume not found.')
    return record


@router.post('/upload')
async def upload_resume(file: UploadFile=File(...), job_description: str=Form(...), job_title: str=Form(...),
                        db: Session=Depends(get_db), current_user=Depends(require_scan_quota)):
    filename = file.filename or ''
    if not filename.lower().endswith(('.pdf','.docx')):
        raise HTTPException(400, 'Use PDF or DOCX.')
    content = await file.read(10*1024*1024+1)
    if len(content)>10*1024*1024: raise HTTPException(400, 'Maximum file size is 10MB.')
    if filename.lower().endswith('.pdf') and not content.startswith(b'%PDF'):
        raise HTTPException(400, 'Invalid PDF.')
    if filename.lower().endswith('.docx') and not content.startswith(b'PK\x03\x04'):
        raise HTTPException(400, 'Invalid DOCX.')
    if not job_title.strip() or len(job_title)>200: raise HTTPException(400, 'Provide a target job title up to 200 characters.')
    task_id = str(uuid.uuid4())
    stage = 'load_pipeline'
    def prepare():
        nonlocal stage
        from backend.app.utils.ats_engine import extract_text, extract_resume_data, extract_requirements, rewrite_resume_for_job
        from backend.app.utils.resume_quality import merge_rewrite, score_requirements
        from backend.app.utils.pdf_generator import generate_optimized_resume
        stage = 'extract_text'
        text = extract_text(content, filename)
        stage = 'extract_resume_data'
        original = extract_resume_data(text)
        stage = 'extract_requirements'
        requirements = extract_requirements(job_description)
        stage = 'score_original'
        before = score_requirements(text, job_description, requirements)
        stage = 'rewrite_resume'
        rewrite = rewrite_resume_for_job(resume_text=text, resume_data=original, job_description=job_description, job_title=job_title)
        stage = 'validate_rewrite'
        tailored = merge_rewrite(original, rewrite, text)
        stage = 'export_pdf'
        pdf = generate_optimized_resume(filename, resume_data=tailored).getvalue()
        stage = 'read_exported_pdf'
        exported = extract_text(pdf, 'resume.pdf')
        stage = 'score_exported_pdf'
        analysis = score_requirements(exported, job_description, requirements)
        analysis.update(original_score=before['overall_score'], confirmation_questions=rewrite.get('confirmation_questions',[]),
                        suggestions_applied=rewrite.get('suggestions_applied',[]), job_title=job_title, job_description=job_description,
                        task_id=task_id, resume_id=task_id, status='success')
        return tailored, analysis, pdf
    try:
        tailored, analysis, pdf = await run_in_threadpool(prepare)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        # Do not log exception bodies: provider errors may echo candidate data.
        provider_status = getattr(exc, 'status_code', None)
        logger.error('resume_preparation_failed reference=%s stage=%s error_type=%s provider_status=%s',
                     task_id, stage, type(exc).__name__, provider_status)
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
    try:
        db.add(record); db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(503, 'Could not save the resume. Please retry.') from exc
    return {'task_id':task_id,'status':'completed','result':analysis}


@router.get('/preview/{resume_id}')
def preview(resume_id: str, db: Session=Depends(get_db), current_user=Depends(get_current_user)):
    record = owned_resume(resume_id,db,current_user)
    return Response(record.content,media_type='application/pdf',headers={'Content-Disposition':'inline; filename="resume.pdf"','Cache-Control':'private, no-store'})


@router.get('/status/{task_id}')
def status(task_id: str, db: Session=Depends(get_db), current_user=Depends(get_current_user)):
    record = owned_resume(task_id,db,current_user)
    return {'task_id':task_id,'status':'completed','result':record.analysis_data}


@router.get('/download/{task_id}')
def download(task_id: str, db: Session=Depends(get_db), current_user=Depends(get_current_user)):
    record = owned_resume(task_id,db,current_user)
    return Response(record.content,media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="Baalebos_Resume.pdf"','Cache-Control':'private, no-store'})
