"""Resume refiner pipeline shared by the API (sync mode) and Celery workers.

extract (+OCR) -> structure -> requirements -> score before -> truthful
rewrite -> validate -> strict one-page export -> score after.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PipelineFailure(Exception):
    status_code: int
    message: str


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


def export_strict(tailored, region, requirements, max_pages=None, template=None):
    """Render the 1- or 2-page resume (see ``resolve_max_pages``); candidate content only."""
    from io import BytesIO
    from pypdf import PdfReader
    from backend.app.utils.pdf_generator import ResumeExportError, export_resume, resolve_max_pages
    keywords = [r.get('phrase') or r.get('requirement') for r in requirements or [] if isinstance(r, dict)]
    result = export_resume(tailored, region=region, priority_keywords=keywords, max_pages=max_pages, template=template)
    limit = 1 if resolve_max_pages(region, max_pages) == 1 else 2
    if len(PdfReader(BytesIO(result.pdf)).pages) > limit:  # hard invariant, checked before storing
        raise ResumeExportError(f'The resume could not be fitted on {"one page" if limit == 1 else "two pages"}.')
    return result


def run_pipeline(content: bytes, filename: str, job_description: str, job_title: str, region: str, task_id: str,
                 priority: bool = False, max_pages=None):
    """Return (tailored, analysis, pdf). Raises PipelineFailure with a
    user-safe message; never logs candidate or provider text."""
    from backend.app.utils.ats_engine import PRIORITY_RUN
    token = PRIORITY_RUN.set(priority)
    try:
        return _run_pipeline(content, filename, job_description, job_title, region, task_id, max_pages)
    finally:
        PRIORITY_RUN.reset(token)


def _run_pipeline(content, filename, job_description, job_title, region, task_id, max_pages=None):
    stage = 'load_pipeline'
    try:
        from backend.app.utils.ats_engine import (clean_job_description, extract_requirements, extract_resume_data,
                                                  extract_text, extract_text_with_ocr, prepare_resume_text,
                                                  rewrite_resume_for_job)
        from backend.app.utils.resume_quality import merge_rewrite, score_requirements, target_headline, verify_extraction
        stage = 'extract_text'
        text = prepare_resume_text(extract_text_with_ocr(content, filename), filename)
        clean_jd = clean_job_description(job_description)
        stage = 'extract_resume_data'
        original = extract_resume_data(text)
        stage = 'verify_extraction'
        original, extraction_guard = verify_extraction(original, text)
        stage = 'extract_requirements'
        requirements = extract_requirements(job_description)
        stage = 'score_original'
        before = score_requirements(text, clean_jd, requirements)
        stage = 'rewrite_resume'
        rewrite = rewrite_resume_for_job(resume_text=text, resume_data=original, job_description=clean_jd, job_title=job_title)
        stage = 'validate_rewrite'
        headline = target_headline(job_title, text, original.get('title', ''))
        tailored = merge_rewrite(original, rewrite, text, headline)
        # The headline names the job being applied for, not the resume's old title.
        tailored['title'] = headline or tailored.get('title', '')
        stage = 'export_pdf'
        exported_resume = export_strict(tailored, region, requirements, max_pages)
        stage = 'score_exported_pdf'
        analysis = score_requirements(extract_text(exported_resume.pdf, 'resume.pdf'), clean_jd, requirements)
    except ValueError as exc:
        raise PipelineFailure(422, str(exc)) from exc
    except Exception as exc:
        raise PipelineFailure(503, _provider_message(exc, task_id, stage)) from exc
    from backend.app.utils.resume_quality import split_missing
    # Only short skills/tools/certifications are offered as tick boxes; conditions such as
    # "5+ years of..." or "must be authorised to work..." become questions instead.
    missing_skills, missing_questions = split_missing(analysis.get('missing_list', []))
    analysis.update(
        original_score=before['overall_score'],
        scores={'before': before['overall_score'], 'after': analysis['overall_score']},
        confirmation_questions=list(rewrite.get('confirmation_questions', [])) + missing_questions,
        suggestions_applied=rewrite.get('suggestions_applied', []),
        # What the guard reverted to source wording (invented numbers or tools).
        rewrite_guard=rewrite.get('rewrite_guard', {}), extraction_guard=extraction_guard, job_title=job_title,
        job_description=clean_jd, task_id=task_id, resume_id=task_id, status='success',
        # Missing requirements are suggestions only; they enter the resume
        # solely through /regenerate with explicit confirmation.
        suggested_skills=missing_skills, confirmed_keywords=[],
        document=exported_resume.info())
    return tailored, analysis, exported_resume.pdf


def _provider_message(exc, task_id, stage):
    # Do not log exception bodies: provider errors may echo candidate data.
    diagnostic = provider_diagnostics(exc)
    logger.error('resume_preparation_failed reference=%s stage=%s error_type=%s provider_status=%s provider_code=%s provider_type=%s provider_param=%s',
                 task_id, stage, type(exc).__name__, getattr(exc, 'status_code', None),
                 diagnostic['code'], diagnostic['type'], diagnostic['param'])
    from openai import (APIConnectionError, APITimeoutError, AuthenticationError, BadRequestError, NotFoundError,
                        PermissionDeniedError, RateLimitError)
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
    return f'{message} No completed resume was saved. Reference: {task_id}'


def complete_record(db, record, tailored, analysis, pdf, charge: bool = True):
    """Store the PDF, charge one scan and commit atomically (object cleanup on failure)."""
    from backend.app.dependencies.plan_guard import consume_scan
    from backend.app.services.resume_storage import commit_with_storage, store_pdf
    if charge:
        consume_scan(record.owner_id, db)
    store_pdf(record, pdf)
    record.parsed_data = json.dumps(tailored)
    record.ats_score = analysis['overall_score']
    record.analysis_data = analysis
    record.status, record.error = 'completed', None
    commit_with_storage(db, record)
