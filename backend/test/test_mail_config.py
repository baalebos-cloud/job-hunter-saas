from backend.app.core.config import Settings
from backend.app.utils import email


def test_smtp_sender_settings_load_from_environment(monkeypatch):
    expected = {'SMTP_HOST': 'smtp.example.invalid', 'SMTP_PORT': '465',
                'SMTP_USER': 'noreply@baalebo.xyz', 'SMTP_PASSWORD': 'synthetic-password',
                'EMAILS_FROM_EMAIL': 'noreply@baalebo.xyz', 'EMAILS_FROM_NAME': 'Baalebos Cloud',
                'FRONTEND_URL': 'https://www.baalebo.xyz'}
    for key, value in expected.items(): monkeypatch.setenv(key, value)
    settings = Settings(_env_file=None)
    for key, value in expected.items():
        assert str(getattr(settings, key)) == value


def test_verification_uses_configured_sender_and_frontend(monkeypatch):
    settings = Settings(_env_file=None, SMTP_HOST='smtp.example.invalid', SMTP_PORT=465,
                        SMTP_USER='noreply@baalebo.xyz', SMTP_PASSWORD='synthetic-password',
                        EMAILS_FROM_EMAIL='noreply@baalebo.xyz', EMAILS_FROM_NAME='Baalebos Cloud',
                        FRONTEND_URL='https://www.baalebo.xyz')
    monkeypatch.setattr(email, 'settings', settings)
    calls = []
    class FakeSMTP:
        def __init__(self, host, port): calls.append(('connect', host, port))
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def login(self, user, password): calls.append(('login', user, password))
        def sendmail(self, sender, recipient, message):
            calls.append(('send', sender, recipient))
            from email import message_from_string
            parsed = message_from_string(message)
            html = parsed.get_payload()[0].get_payload(decode=True).decode('utf-8')
            assert 'https://www.baalebo.xyz/verify-email?token=synthetic-token' in html
    monkeypatch.setattr(email.smtplib, 'SMTP_SSL', FakeSMTP)
    assert email.send_verification_email('candidate@example.invalid', 'synthetic-token') is True
    assert calls == [('connect', 'smtp.example.invalid', 465),
                     ('login', 'noreply@baalebo.xyz', 'synthetic-password'),
                     ('send', 'noreply@baalebo.xyz', 'candidate@example.invalid')]
