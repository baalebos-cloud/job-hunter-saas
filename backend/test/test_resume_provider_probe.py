import json
from types import SimpleNamespace
from backend.scripts.diagnose_resume_provider import run_probe, SYNTHETIC_RESUME
from backend.app.utils import ats_engine


def test_probe_uses_only_synthetic_input_and_redacts_credentials(monkeypatch):
    calls, output = [], []
    monkeypatch.setattr(ats_engine.settings, 'GROQ_API_KEY', 'secret-test-key')
    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop', message=SimpleNamespace(content='secret-test-key not JSON'))])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    assert run_probe(client, 'openai/gpt-oss-20b', output.append) == 1
    assert SYNTHETIC_RESUME in calls[0]['messages'][1]['content']
    assert 'secret-test-key' not in '\n'.join(output)
    assert '[REDACTED]' in '\n'.join(output)
    assert json.loads(output[-1])['error'] == 'ValueError'


def test_probe_does_not_print_failed_generation_or_exception_message(monkeypatch):
    import httpx
    from openai import BadRequestError
    output = []
    monkeypatch.setattr(ats_engine.settings, 'GROQ_API_KEY', 'synthetic-key')
    def create(**kwargs):
        raise BadRequestError('do-not-print-exception', response=httpx.Response(400, request=httpx.Request('POST', 'https://example.invalid')),
                              body={'code': 'invalid_request_error', 'message': 'synthetic diagnostic reason', 'failed_generation': 'do-not-print-generation'})
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    assert run_probe(client, 'openai/gpt-oss-20b', output.append) == 1
    assert 'synthetic diagnostic reason' in '\n'.join(output)
    assert 'do-not-print' not in '\n'.join(output)
