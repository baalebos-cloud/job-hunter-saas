from types import SimpleNamespace
import pytest
from backend.app.services import automation_service as service


@pytest.mark.parametrize('outcome', ['accepted', 'rejected', 'invalid', 'timeout'])
def test_webhook_contract_and_safe_failures(monkeypatch, caplog, outcome):
    monkeypatch.setattr(service, 'settings', SimpleNamespace(N8N_APPLICATION_WEBHOOK_URL='https://example.com/webhook', N8N_WEBHOOK_SECRET='private-secret'))
    calls = []
    def post(url, **kwargs):
        calls.append((url, kwargs))
        if outcome == 'timeout': raise TimeoutError('private-secret recipient@example.com')
        return SimpleNamespace(status_code=403 if outcome == 'rejected' else 200,
                               json=lambda: {'accepted':True, 'provider_message_id':'example-id'} if outcome == 'accepted' else {})
    monkeypatch.setattr(service.httpx, 'post', post)
    assert service.notify_new_application(10, 'Python Engineer', 'recipient@example.com') == (outcome == 'accepted')
    assert len(calls) == 1
    assert calls[0][1]['json'] == {'event_id':'baalebos-application-10', 'application_id':10, 'job_title':'Python Engineer', 'employer_email':'recipient@example.com'}
    assert calls[0][1]['headers'] == {'X-Baalebos-Webhook-Key':'private-secret'}
    assert calls[0][1]['follow_redirects'] is False
    assert 'private-secret' not in caplog.text and 'recipient@example.com' not in caplog.text


@pytest.mark.parametrize('url,secret', [('', 'secret'), ('https://example.com', ''), ('http://example.com', 'secret'), ('https://user:pwd@example.com', 'secret')])
def test_missing_or_invalid_configuration_never_calls_webhook(monkeypatch, url, secret):
    monkeypatch.setattr(service, 'settings', SimpleNamespace(N8N_APPLICATION_WEBHOOK_URL=url, N8N_WEBHOOK_SECRET=secret))
    def unexpected(*args, **kwargs): pytest.fail('Unexpected webhook call')
    monkeypatch.setattr(service.httpx, 'post', unexpected)
    assert service.notify_new_application(10, 'Engineer', 'recipient@example.com') is False
