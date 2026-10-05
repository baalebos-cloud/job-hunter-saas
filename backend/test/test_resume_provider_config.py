"""Verify model configuration without sending candidate data to providers."""
from backend.app.core.config import Settings
from backend.app.utils import ats_engine


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
