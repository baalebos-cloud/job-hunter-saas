import httpx
import pytest
from backend.app.core.config import Settings
from backend.app.utils import email


@pytest.fixture
def resend_settings(monkeypatch):
    monkeypatch.setattr(email, 'settings', Settings(_env_file=None,
        RESEND_API_KEY='synthetic-private-key', EMAILS_FROM_EMAIL='noreply@baalebo.xyz',
        EMAILS_FROM_NAME='Baalebos Cloud', FRONTEND_URL='https://www.baalebo.xyz'))
    def forbidden(*args, **kwargs): raise AssertionError('SMTP must not be used')
    monkeypatch.setattr(email.smtplib, 'SMTP_SSL', forbidden)


def test_resend_verification_request(resend_settings, monkeypatch):
    calls = []
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(200, json={'id': 'synthetic-email-id'})
    monkeypatch.setattr(email.httpx, 'post', post)
    assert email.send_verification_email('candidate@example.invalid', 'synthetic-token')
    url, request = calls[0]
    assert url == 'https://api.resend.com/emails'
    assert request['headers'] == {'Authorization': 'Bearer synthetic-private-key'}
    assert request['timeout'] == 15.0
    assert request['json']['from'] == 'Baalebos Cloud <noreply@baalebo.xyz>'
    assert request['json']['to'] == ['candidate@example.invalid']
    assert 'https://www.baalebo.xyz/verify-email?token=synthetic-token' in request['json']['html']


@pytest.mark.parametrize('failure', ['403', '429', 'timeout', 'invalid_ack'])
def test_resend_failure_is_safe_and_does_not_retry_or_fallback(resend_settings, monkeypatch, caplog, failure):
    calls = []
    def post(url, **kwargs):
        calls.append(url)
        if failure == 'timeout': raise httpx.ReadTimeout('synthetic-private-key secret-candidate-data')
        if failure == 'invalid_ack': return httpx.Response(200, json={'message': 'secret-candidate-data'})
        return httpx.Response(int(failure), json={'message': 'synthetic-private-key secret-candidate-data'})
    monkeypatch.setattr(email.httpx, 'post', post)
    assert not email._send_resend_verification('candidate@example.invalid', 'Verification', '<p>secret-candidate-data</p>')
    assert len(calls) == 1
    assert 'synthetic-private-key' not in caplog.text
    assert 'secret-candidate-data' not in caplog.text


def test_resend_key_loads_from_environment(monkeypatch):
    monkeypatch.setenv('RESEND_API_KEY', 'synthetic-env-key')
    assert Settings(_env_file=None).RESEND_API_KEY == 'synthetic-env-key'


@pytest.mark.parametrize('function', ['send_welcome_email', 'send_password_reset_email', 'send_verification_email'])
def test_every_account_email_goes_through_resend_not_smtp(resend_settings, monkeypatch, function):
    # Railway blocks outbound SMTP: an email that relies on it never arrives.
    calls = []
    def post(url, **kwargs):
        calls.append(kwargs['json'])
        return httpx.Response(200, json={'id': 'synthetic-email-id'})
    monkeypatch.setattr(email.httpx, 'post', post)
    kwargs = {'token': 'synthetic-reset-token'} if function != 'send_welcome_email' else {}
    assert getattr(email, function)('candidate@example.invalid', **kwargs)
    assert len(calls) == 1 and calls[0]['to'] == ['candidate@example.invalid']


def test_reset_email_link_and_expiry(resend_settings, monkeypatch):
    calls = []
    monkeypatch.setattr(email.httpx, 'post', lambda url, **k: calls.append(k['json']) or httpx.Response(200, json={'id': 'x'}))
    assert email.send_password_reset_email('candidate@example.invalid', 'tok123', 'Ada Okafor', hours=24)
    html = calls[0]['html']
    assert 'https://www.baalebo.xyz/reset-password?token=tok123' in html and 'expires in 24 hours' in html
    assert calls[0]['subject'] == 'Reset your Baalebos password'


def test_no_transport_configured_fails_without_trying_smtp(monkeypatch):
    monkeypatch.setattr(email, 'settings', Settings(_env_file=None, RESEND_API_KEY='', SMTP_HOST=''))
    monkeypatch.setattr(email.smtplib, 'SMTP_SSL', lambda *a, **k: (_ for _ in ()).throw(AssertionError('no SMTP host')))
    assert email.send_password_reset_email('candidate@example.invalid', 'tok') is False
