"""Verify model configuration without sending candidate data to providers."""
from backend.app.core.config import Settings
from backend.app.utils import ats_engine
from types import SimpleNamespace
import pytest


def test_groq_model_default_and_environment_override(monkeypatch):
    monkeypatch.delenv('GROQ_MODEL', raising=False)
    assert Settings(_env_file=None).GROQ_MODEL == 'openai/gpt-oss-20b'
    monkeypatch.setenv('GROQ_MODEL', 'openai/gpt-oss-120b')
    assert Settings(_env_file=None).GROQ_MODEL == 'openai/gpt-oss-120b'


def test_groq_client_uses_configured_model_and_endpoint(monkeypatch):
    calls = []
    sentinel = object()
    def fake_client(**kwargs):
        calls.append(kwargs)
        return sentinel
    monkeypatch.setattr(ats_engine, 'OpenAI', fake_client)
    monkeypatch.setattr(ats_engine.settings, 'GROQ_API_KEY', 'synthetic-test-key')
    monkeypatch.setattr(ats_engine.settings, 'GROQ_MODEL', 'openai/gpt-oss-120b')
    client, model = ats_engine.get_client()
    assert client is sentinel
    assert model == 'openai/gpt-oss-120b'
    assert calls[0]['base_url'] == 'https://api.groq.com/openai/v1'


def test_groq_json_request_reserves_budget_and_rejects_truncation(monkeypatch):
    calls = []
    response = SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop', message=SimpleNamespace(content='{"name":"Candidate"}'))], usage=SimpleNamespace(completion_tokens=80))
    def create(**kwargs):
        calls.append(kwargs)
        return response
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(ats_engine, 'get_client', lambda: (client, 'openai/gpt-oss-20b'))
    monkeypatch.setattr(ats_engine.settings, 'GROQ_API_KEY', 'synthetic-test-key')
    monkeypatch.setattr(ats_engine.settings, 'GROQ_MAX_COMPLETION_TOKENS', 8192)
    assert ats_engine._json('Return JSON.') == {'name': 'Candidate'}
    assert calls[0]['extra_body'] == {'reasoning_effort': 'low', 'max_completion_tokens': 8192}
    assert calls[0]['response_format'] == {'type': 'json_object'}
    assert 'max_tokens' not in calls[0]
    response.choices[0].finish_reason = 'length'
    with pytest.raises(ValueError, match='incomplete'):
        ats_engine._json('Return JSON.')
