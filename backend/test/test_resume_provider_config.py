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


def _rate_limited(retry_after=None):
    import httpx
    from openai import RateLimitError
    headers = {'retry-after': retry_after} if retry_after else {}
    response = httpx.Response(429, headers=headers, request=httpx.Request('POST', 'https://api.example.test/v1/chat/completions'))
    return RateLimitError('rate limited', response=response, body=None)


def _client(outcomes, calls):
    def create(**kwargs):
        calls.append(kwargs['model'])
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop', message=SimpleNamespace(content=outcome))],
                               usage=SimpleNamespace(completion_tokens=5))
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def test_short_rate_limit_is_waited_out_on_the_same_provider(monkeypatch):
    calls, slept = [], []
    primary = _client([_rate_limited('3'), '{"ok": 1}'], calls)
    monkeypatch.setattr(ats_engine, 'get_client', lambda: (primary, 'openai/gpt-oss-20b'))
    monkeypatch.setattr(ats_engine.time, 'sleep', slept.append)
    assert ats_engine._json('Return JSON.') == {'ok': 1}
    assert calls == ['openai/gpt-oss-20b'] * 2 and slept == [3.5]


def test_long_rate_limit_falls_back_to_the_next_configured_provider(monkeypatch):
    calls, slept = [], []
    primary = _client([_rate_limited('3600')], calls)
    backup = _client(['{"ok": 2}'], calls)
    monkeypatch.setattr(ats_engine, 'get_client', lambda: (primary, 'openai/gpt-oss-20b'))
    monkeypatch.setattr(ats_engine, 'provider_chain', lambda: [('groq', primary, 'openai/gpt-oss-20b'),
                                                              ('openrouter', backup, 'anthropic/claude-3-haiku')])
    monkeypatch.setattr(ats_engine.time, 'sleep', slept.append)
    assert ats_engine._json('Return JSON.') == {'ok': 2}
    assert calls == ['openai/gpt-oss-20b', 'anthropic/claude-3-haiku'] and slept == []


def test_rate_limit_with_no_other_provider_is_reported(monkeypatch):
    from openai import RateLimitError
    calls = []
    primary = _client([_rate_limited(), _rate_limited()], calls)
    monkeypatch.setattr(ats_engine, 'get_client', lambda: (primary, 'openai/gpt-oss-20b'))
    monkeypatch.setattr(ats_engine, 'provider_chain', lambda: [('groq', primary, 'openai/gpt-oss-20b')])
    with pytest.raises(RateLimitError):
        ats_engine._json('Return JSON.')
    assert calls == ['openai/gpt-oss-20b']          # no retry-after: no blind waiting


def test_groq_style_reset_header_is_understood():
    import httpx
    from openai import RateLimitError
    response = httpx.Response(429, headers={'x-ratelimit-reset-tokens': '1m2.5s'},
                              request=httpx.Request('POST', 'https://api.example.test'))
    assert ats_engine._retry_after(RateLimitError('x', response=response, body=None)) == 62.5
