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


def export_strict(tailored, region, requirements):
    """Render the strictly one-page resume; candidate content only."""
    from io import BytesIO
    from pypdf import PdfReader
    from backend.app.utils.pdf_generator import ResumeExportError, export_resume
    keywords = [r.get('phrase') or r.get('requirement') for r in requirements or [] if isinstance(r, dict)]
    result = export_resume(tailored, region=region, priority_keywords=keywords)
    if len(PdfReader(BytesIO(result.pdf)).pages) != 1:  # hard invariant, checked before storing
        raise ResumeExportError('The resume could not be fitted on one page.')
    return result


def run_pipeline(content: bytes, filename: str, job_description: str, job_title: str, region: str, task_id: str):
    """Return (tailored, analysis, pdf). Raises PipelineFailure with a
    user-safe message; never logs candidate or provider text."""
    stage = 'load_pipeline'
    try:
        from backend.app.utils.ats_engine import (clean_job_description, extract_requirements, extract_resume_data,
                                                  extract_text, extract_text_with_ocr, prepare_resume_text,
                                                  rewrite_resume_for_job)
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
        exported_resume = export_strict(tailored, region, requirements)
        stage = 'score_exported_pdf'
        analysis = score_requirements(extract_text(exported_resume.pdf, 'resume.pdf'), clean_jd, requirements)
    except ValueError as exc:
        raise PipelineFailure(422, str(exc)) from exc
    except Exception as exc:
        raise PipelineFailure(503, _provider_message(exc, task_id, stage)) from exc
    analysis.update(
        original_score=before['overall_score'],
        scores={'before': before['overall_score'], 'after': analysis['overall_score']},
        confirmation_questions=rewrite.get('confirmation_questions', []),
        suggestions_applied=rewrite.get('suggestions_applied', []), job_title=job_title,
        job_description=clean_jd, task_id=task_id, resume_id=task_id, status='success',
        # Missing requirements are suggestions only; they enter the resume
        # solely through /regenerate with explicit confirmation.
        suggested_skills=list(analysis.get('missing_list', [])), confirmed_keywords=[],
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
