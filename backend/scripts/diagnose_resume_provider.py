"""Run the actual extraction pipeline on fixed synthetic data only.

From the repository root, with backend environment variables available:
    python -m backend.scripts.diagnose_resume_provider
No resume/file arguments, database access, or user quota consumption.
"""
import json
from types import SimpleNamespace
from unittest.mock import patch

from backend.app.utils import ats_engine

SYNTHETIC_RESUME = """SYNTHETIC TEST CANDIDATE
DevOps Engineer
candidate@example.invalid
Summary: Engineer working with Python and Docker.
Experience: Engineer at Example Company, 2025-2026.
Built Python automation tools and deployed Docker containers.
Skills: Python, Docker, Linux.
Education: BSc Computer Science, Example University, 2024.
"""


def run_probe(client, model, emit=print):
    """Observe only the provider replies to the fixed synthetic resume."""
    secrets = [getattr(ats_engine.settings, key, '') for key in
               ('GROQ_API_KEY', 'OPENAI_API_KEY', 'OPENROUTER_API_KEY')]

    def safe(value, limit=2400):
        text = str(value)
        for secret in secrets:
            if secret:
                text = text.replace(secret, '[REDACTED]')
        return text[:limit]

    def report(**data):
        emit(json.dumps(data, ensure_ascii=True))

    report(probe='synthetic_resume_only', model=safe(model, 100))
    attempts = 0

    def create(**kwargs):
        nonlocal attempts
        attempts += 1
        mode = kwargs.get('response_format', {}).get('type', 'default')
        try:
            response = client.chat.completions.create(**kwargs)
        except Exception as exc:
            body = getattr(exc, 'body', None)
            if isinstance(body, dict) and isinstance(body.get('error'), dict):
                body = body['error']
            # Only the error message from this synthetic request; never headers,
            # full error body, failed_generation, or exception repr/traceback.
            message = body.get('message', '') if isinstance(body, dict) else ''
            report(attempt=attempts, format=mode, error=type(exc).__name__,
                   status=getattr(exc, 'status_code', None),
                   code=safe(getattr(exc, 'code', None), 100),
                   message=safe(message, 800))
            raise
        choice = response.choices[0]
        content = choice.message.content or ''
        report(attempt=attempts, format=mode, finish_reason=choice.finish_reason,
               content_type=type(choice.message.content).__name__,
               content_characters=len(content),
               content_preview=safe(content),
               has_reasoning=bool(getattr(choice.message, 'reasoning', None)))
        return response

    observed = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    try:
        with patch.object(ats_engine, 'get_client', return_value=(observed, model)):
            ats_engine.extract_resume_data(SYNTHETIC_RESUME)
    except Exception as exc:
        report(result='failed', error=type(exc).__name__, attempts=attempts)
        return 1
    report(result='passed', attempts=attempts)
    return 0


def main():
    if not ats_engine.settings.GROQ_API_KEY:
        print('GROQ_API_KEY is not configured in this process. No request sent.')
        return 2
    try:
        client, model = ats_engine.get_client()
        return run_probe(client, model)
    except Exception as exc:
        print(json.dumps({'result': 'setup_failed', 'error': type(exc).__name__}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
