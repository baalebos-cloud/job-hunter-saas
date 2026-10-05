"""Provider output must match the exporter and validator's typed contract."""
import json
from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from backend.app.utils import ats_engine
from backend.app.utils.resume_contracts import ResumeRewrite, ExtractedResume, Requirements


def valid_rewrite():
    return {'optimized_summary': 'Python developer',
            'optimized_experience': [{'role': 'Engineer', 'company': 'Example', 'dates': '2025', 'bullets': ['Built Python tools.']}],
            'optimized_skills': {'Skills': ['Python', 'Terraform']},
            'confirmation_questions': [], 'suggestions_applied': []}


@pytest.mark.parametrize('skills', [['Python'], 'Python', {'Skills': 'Python'}, {'Skills': [123]}, None])
def test_invalid_skill_shapes_are_rejected(skills):
    with pytest.raises(ValidationError):
        ResumeRewrite.model_validate({**valid_rewrite(), 'optimized_skills': skills})


def test_all_contract_objects_are_closed_and_required():
    def inspect(value):
        if isinstance(value, dict):
            if value.get('type') == 'object':
                assert value['additionalProperties'] is False
                assert set(value['required']) == set(value['properties'])
            for item in value.values(): inspect(item)
        elif isinstance(value, list):
            for item in value: inspect(item)
    for contract in (ResumeRewrite, ExtractedResume, Requirements):
        inspect(contract.model_json_schema())


def test_font_damage_is_identified_before_ai_analysis():
    with pytest.raises(ValueError, match='unreadable font characters'):
        ats_engine._text('Candidate resume with GitHubAc(cid:415)ons and Terraform experience.')


def test_provider_gets_strict_schema_and_safe_shape_diagnostics(monkeypatch, caplog):
    calls = []
    body = valid_rewrite()
    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop', message=SimpleNamespace(content=json.dumps(body)))])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(ats_engine, 'get_client', lambda: (client, 'openai/gpt-oss-20b'))
    monkeypatch.setattr(ats_engine.settings, 'GROQ_API_KEY', 'synthetic-test-key')
    assert ats_engine._json('Return JSON.', contract=ResumeRewrite) == body
    format = calls[0]['response_format']
    assert format['type'] == 'json_schema' and format['json_schema']['strict'] is True
    assert format['json_schema']['schema'] == ResumeRewrite.model_json_schema()
    body['optimized_skills'] = {'Skills': 'private-candidate-text'}
    with pytest.raises(ValueError, match='required resume structure'):
        ats_engine._json('Return JSON.', contract=ResumeRewrite)
    assert 'skill_type=dict' in caplog.text and "['str']" in caplog.text
    assert 'private-candidate-text' not in caplog.text


@pytest.mark.parametrize('mode', ['valid', 'invalid', 'second_failure', 'other_error'])
def test_groq_validation_failure_has_bounded_validated_retries(monkeypatch, caplog, mode):
    import httpx
    from openai import BadRequestError
    calls = []
    code = 'invalid_request_error' if mode == 'other_error' else 'json_validate_failed'
    error = BadRequestError('private-candidate-text', response=httpx.Response(400, request=httpx.Request('POST', 'https://api.groq.com/openai/v1/chat/completions')),
                            body={'code': code, 'failed_generation': 'private-candidate-text'})
    body = valid_rewrite()
    if mode == 'invalid': body['optimized_skills'] = {'Skills': 'private-candidate-text'}
    def create(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1 or mode == 'second_failure': raise error
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop', message=SimpleNamespace(content=json.dumps(body)))])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(ats_engine, 'get_client', lambda: (client, 'openai/gpt-oss-20b'))
    monkeypatch.setattr(ats_engine.settings, 'GROQ_API_KEY', 'synthetic-test-key')
    if mode == 'valid':
        assert ats_engine._json('Return JSON.', ResumeRewrite) == body
    else:
        with pytest.raises(ValueError if mode == 'invalid' else BadRequestError):
            ats_engine._json('Return JSON.', ResumeRewrite)
    assert len(calls) == (1 if mode == 'other_error' else 3 if mode == 'second_failure' else 2)
    if len(calls) == 2:
        assert calls[1]['response_format'] == {'type': 'json_object'}
        assert calls[1]['messages'] == calls[0]['messages']
        assert calls[1]['extra_body'] == calls[0]['extra_body']
    assert 'private-candidate-text' not in caplog.text


@pytest.mark.parametrize('outcome', ['valid', 'invalid_shape', 'invalid_json', 'truncated', 'unrelated_error'])
def test_text_recovery_preserves_validation_and_retry_bound(monkeypatch, caplog, outcome):
    import httpx
    from openai import BadRequestError
    calls = []
    def error(code):
        return BadRequestError('private-source-content', response=httpx.Response(400, request=httpx.Request('POST', 'https://api.groq.com/openai/v1/chat/completions')),
                               body={'code': code, 'failed_generation': 'private-source-content'})
    body = valid_rewrite()
    if outcome == 'invalid_shape': body['optimized_skills'] = {'Skills': 'private-source-content'}
    raw = 'private-source-content' if outcome == 'invalid_json' else json.dumps(body)
    def create(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1: raise error('json_validate_failed')
        if len(calls) == 2: raise error('invalid_request_error' if outcome == 'unrelated_error' else 'json_validate_failed')
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason='length' if outcome == 'truncated' else 'stop', message=SimpleNamespace(content=raw))], usage=None)
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(ats_engine, 'get_client', lambda: (client, 'openai/gpt-oss-20b'))
    monkeypatch.setattr(ats_engine.settings, 'GROQ_API_KEY', 'synthetic-test-key')
    if outcome == 'valid': assert ats_engine._json('Return JSON.', ResumeRewrite) == body
    else:
        with pytest.raises(BadRequestError if outcome == 'unrelated_error' else ValueError):
            ats_engine._json('Return JSON.', ResumeRewrite)
    assert len(calls) == (2 if outcome == 'unrelated_error' else 3)
    if len(calls) == 3:
        assert calls[2]['response_format'] == {'type': 'text'}
        assert calls[2]['extra_body']['include_reasoning'] is False
        assert calls[2]['messages'] == calls[0]['messages']
        assert calls[2]['extra_body']['max_completion_tokens'] == calls[0]['extra_body']['max_completion_tokens']
    assert 'private-source-content' not in caplog.text
