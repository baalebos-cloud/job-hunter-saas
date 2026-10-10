"""Best-effort application alerts; never transmit applicant data or resumes."""
import logging
from urllib.parse import urlsplit

import httpx

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


def notify_new_application(application_id: int, job_title: str, employer_email: str):
    url = settings.N8N_APPLICATION_WEBHOOK_URL
    secret = settings.N8N_WEBHOOK_SECRET
    if not url or not secret:
        return False
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        logger.warning('application_notification_failed reason=invalid_configuration')
        return False
    payload = {
        'event_id': f'baalebos-application-{application_id}',
        'application_id': application_id,
        'job_title': job_title,
        'employer_email': employer_email,
    }
    try:
        response = httpx.post(url, json=payload,
                              headers={'X-Baalebos-Webhook-Key': secret},
                              timeout=20.0, follow_redirects=False)
        if not 200 <= response.status_code < 300:
            logger.warning('application_notification_failed application_id=%s status=%s',
                           application_id, response.status_code)
            return False
        result = response.json()
        if not isinstance(result, dict) or result.get('accepted') is not True or not result.get('provider_message_id'):
            logger.warning('application_notification_failed application_id=%s reason=invalid_acknowledgement', application_id)
            return False
    except Exception as exc:
        logger.warning('application_notification_failed application_id=%s error_type=%s',
                       application_id, type(exc).__name__)
        return False
    logger.info('application_notification_accepted application_id=%s', application_id)
    return True
