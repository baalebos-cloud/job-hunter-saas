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
                                                              ('openrouter', backup, 'openai/gpt-4o-mini')])
    monkeypatch.setattr(ats_engine.time, 'sleep', slept.append)
    assert ats_engine._json('Return JSON.') == {'ok': 2}
    assert calls == ['openai/gpt-oss-20b', 'openai/gpt-4o-mini'] and slept == []


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


def _refused(cls, status, code):
    import httpx
    response = httpx.Response(status, request=httpx.Request('POST', 'https://api.example.test/v1/chat/completions'))
    return cls('refused', response=response, body={'code': code})


@pytest.mark.parametrize('error', ['not_found', 'bad_request', 'auth'])
def test_a_refused_request_moves_to_the_next_provider(monkeypatch, error):
    """A retired model or a revoked key must not stop every resume: the backup answers."""
    from openai import AuthenticationError, BadRequestError, NotFoundError
    exc = {'not_found': _refused(NotFoundError, 404, 'model_not_found'),
           'bad_request': _refused(BadRequestError, 400, 'model_decommissioned'),
           'auth': _refused(AuthenticationError, 401, 'invalid_api_key')}[error]
    calls = []
    primary = _client([exc], calls)
    backup = _client(['{"ok": 3}'], calls)
    monkeypatch.setattr(ats_engine, 'get_client', lambda: (primary, 'openai/gpt-oss-20b'))
    monkeypatch.setattr(ats_engine, 'provider_chain', lambda: [('groq', primary, 'openai/gpt-oss-20b'),
                                                              ('openrouter', backup, 'openai/gpt-4o-mini')])
    assert ats_engine._json('Return JSON.') == {'ok': 3}
    assert calls == ['openai/gpt-oss-20b', 'openai/gpt-4o-mini']      # no retry of a refused request


def test_refusal_on_every_provider_is_reported(monkeypatch):
    from openai import NotFoundError
    calls = []
    primary = _client([_refused(NotFoundError, 404, 'model_not_found')], calls)
    backup = _client([_refused(NotFoundError, 404, 'model_not_found')], calls)
    monkeypatch.setattr(ats_engine, 'get_client', lambda: (primary, 'a'))
    monkeypatch.setattr(ats_engine, 'provider_chain', lambda: [('groq', primary, 'a'), ('openrouter', backup, 'b')])
    with pytest.raises(NotFoundError):
        ats_engine._json('Return JSON.')
    assert calls == ['a', 'b']


def test_backup_models_are_configurable_and_current(monkeypatch):
    """claude-3-haiku was removed from OpenRouter; the backups come from settings."""
    for name in ('OPENROUTER_MODEL', 'OPENAI_MODEL'):
        monkeypatch.delenv(name, raising=False)
    defaults = Settings(_env_file=None)
    assert (defaults.OPENROUTER_MODEL, defaults.OPENAI_MODEL) == ('openai/gpt-4o-mini', 'gpt-4o-mini')
    made = []
    monkeypatch.setattr(ats_engine, 'OpenAI', lambda **kw: made.append(kw) or kw)
    for key in ('GROQ_API_KEY', 'OPENROUTER_API_KEY', 'OPENAI_API_KEY'):
        monkeypatch.setattr(ats_engine.settings, key, 'synthetic-test-key')
    monkeypatch.setattr(ats_engine.settings, 'OPENROUTER_MODEL', 'anthropic/claude-haiku-4.5')
    monkeypatch.setattr(ats_engine.settings, 'OPENAI_MODEL', 'gpt-4.1-mini')
    chain = ats_engine.provider_chain()
    assert [(name, model) for name, _, model in chain] == [
        ('groq', ats_engine.settings.GROQ_MODEL), ('openrouter', 'anthropic/claude-haiku-4.5'), ('openai', 'gpt-4.1-mini')]


def test_openrouter_gpt_oss_does_not_receive_groq_only_options(monkeypatch):
    calls = []
    response = SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop', message=SimpleNamespace(content='{}'))],
                               usage=SimpleNamespace(completion_tokens=1))
    client = SimpleNamespace(base_url='https://openrouter.ai/api/v1/',
                             chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: calls.append(kw) or response)))
    monkeypatch.setattr(ats_engine.settings, 'GROQ_API_KEY', 'synthetic-test-key')
    ats_engine._json_once('Return JSON.', None, (client, 'openai/gpt-oss-120b'))
    assert 'extra_body' not in calls[0] and calls[0]['max_tokens'] == 6000


def test_outreach_uses_the_configured_groq_model(monkeypatch):
    from backend.app.services import outreach_service
    calls = []
    response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='Hello **Acme** team'))])
    fake = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: calls.append(kw) or response)))
    monkeypatch.setattr(outreach_service, 'OpenAI', lambda **kw: fake)
    monkeypatch.setattr(outreach_service.settings, 'GROQ_API_KEY', 'synthetic-test-key')
    monkeypatch.setattr(outreach_service.settings, 'GROQ_MODEL', 'openai/gpt-oss-20b')
    assert outreach_service.generate_message('DevOps', 'Acme', 'JD', 'Ada', 'resume') == 'Hello Acme team'
    assert calls[0]['model'] == 'openai/gpt-oss-20b'
    assert calls[0]['extra_body'] == {'reasoning_effort': 'low', 'max_completion_tokens': 1200}


def test_outreach_empty_reply_uses_the_plain_template(monkeypatch):
    from backend.app.services import outreach_service
    response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=None))])
    fake = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: response)))
    monkeypatch.setattr(outreach_service, 'OpenAI', lambda **kw: fake)
    monkeypatch.setattr(outreach_service.settings, 'GROQ_API_KEY', 'synthetic-test-key')
    assert 'Ada' in outreach_service.generate_message('DevOps', 'Acme', 'JD', 'Ada', 'resume')
