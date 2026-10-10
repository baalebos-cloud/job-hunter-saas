"""Job alerts and operational notifications, with bounded, persistent retries.

The database is the source of recipients and consent. No resume content, scores,
applicant contact details, or recruiter messages are exported to n8n.
"""
import logging
import re
import time
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlsplit

import httpx
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from backend.app.core.config import settings
from backend.app.database import SessionLocal
from backend.app.dependencies.roles import is_owner, require_hr
from backend.app.models.application import Application
from backend.app.models.automation import AutomationEvent, AutomationState, ScrapeRun
from backend.app.models.job import Job
from backend.app.models.user import User
from backend.app.services.automation_service import notify_new_application

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 5
# Resend keeps idempotency keys for 24h. Never automatically retry a possibly
# accepted request outside that window, even following a prolonged outage.
RETRY_WINDOW = timedelta(hours=23)
ROLE_STOP_WORDS = {"senior", "junior", "lead", "engineer", "engineering", "developer", "development", "specialist"}


def enqueue(db, event_id, event_type, recipient, payload, now=None):
    now = now or datetime.utcnow()
    if db.get(AutomationEvent, event_id):
        return False
    try:
        with db.begin_nested():
            db.add(AutomationEvent(event_id=event_id, event_type=event_type,
                                   recipient_id=recipient.id,
                                   payload={**payload, "to_email": recipient.email},
                                   created_at=now, next_attempt_at=now))
            db.flush()
    except IntegrityError:
        # Unique event IDs also cover concurrent scheduler ticks.
        return False
    return True


def enqueue_application(db, application, employer, job):
    return enqueue(db, f"baalebos-application-{application.id}", "application.created", employer, {
        "application_id": application.id, "job_id": job.id,
        "job_title": job.title, "employer_email": employer.email,
        "subject": f"New application: {job.title}",
        "text": f"A new application was received for {job.title}.\nApplication ID: {application.id}\nReview it at https://www.baalebo.xyz/hr",
    })


def _words(value):
    return re.findall(r"[\w+#]+", (value or "").casefold())


def matches_preferences(job, user):
    if not job.is_active or not user.career_track:
        return False
    role_words = set(_words(user.career_track)) - ROLE_STOP_WORDS
    if not role_words or not role_words.issubset(set(_words(f"{job.title or ''} {job.category or ''}"))):
        return False
    if user.job_alert_work_type not in (None, "all") and job.work_type != user.job_alert_work_type:
        return False
    country = " ".join(_words(user.country))
    location = " ".join(_words(job.location))
    if country and country not in ("all", "worldwide", "global"):
        country_match = re.search(r"(?<!\w)" + re.escape(country) + r"(?!\w)", location)
        excluded = re.search(r"(?:except|excluding|not)\s+" + re.escape(country) + r"(?!\w)", location)
        # 'Remote' alone does not establish a country's eligibility.
        if excluded or not (country_match or "worldwide" in _words(location) or "anywhere" in _words(location)):
            return False
    return True


def _owners(db):
    return [user for user in db.query(User).filter(User.is_admin.is_(True), User.is_verified.is_(True)).all() if is_owner(user)]


def queue_job_digests(db, now):
    """At most one digest per opted-in user per UTC day, for newly seen jobs."""
    users = db.query(User).filter(User.job_alerts_enabled.is_(True), User.is_verified.is_(True),
                                 User.available_for_work.is_(True), User.is_hr.is_(False),
                                 User.is_admin.is_(False)).all()
    queued = 0
    for user in users:
        if not user.job_alerts_enabled_at:
            continue
        event_id = f"baalebos-job-digest-{user.id}-{now.date().isoformat()}"
        if db.get(AutomationEvent, event_id):
            continue
        previous = db.query(AutomationEvent).filter_by(recipient_id=user.id, event_type="jobs.matched").order_by(AutomationEvent.created_at.desc()).first()
        since = max(user.job_alerts_enabled_at, now - timedelta(days=3), previous.created_at if previous else user.job_alerts_enabled_at)
        candidates = db.query(Job).filter(Job.is_active.is_(True), Job.first_seen_at >= since,
                                          Job.first_seen_at < now).order_by(Job.first_seen_at.desc(), Job.id.desc()).all()
        matches = [job for job in candidates if matches_preferences(job, user)]
        if not matches:
            continue
        lines = [f"{len(matches)} new jobs match your role and location preferences.", ""]
        for job in matches[:10]:
            kind = "Apply on Baalebos" if job.posted_by_hr and not job.url else "Complete the employer's application form"
            lines.append(f"{job.title} at {job.company} — {job.location or 'Location not specified'}\n{kind}. Job ID: {job.id}\n")
        lines += ["See the job feed: https://www.baalebo.xyz/jobs",
                  "Review the full requirements and location restrictions before applying. A match is not a hiring or eligibility assessment.",
                  "Turn off job alerts in My Profile: https://www.baalebo.xyz/profile"]
        queued += int(enqueue(db, event_id, "jobs.matched", user, {
            "job_ids": [job.id for job in matches[:10]], "subject": "New jobs matching your preferences",
            "text": "\n".join(lines),
        }, now))
    return queued


def queue_admin_reports(db, now):
    state = db.get(AutomationState, "monitoring_started")
    if not state:
        try:
            with db.begin_nested():
                state = AutomationState(key="monitoring_started", value={"at": now.isoformat()})
                db.add(state)
                db.flush()
        except IntegrityError:
            state = db.get(AutomationState, "monitoring_started")
    latest = db.query(ScrapeRun).order_by(ScrapeRun.started_at.desc()).first()
    reference = (latest.finished_at or latest.started_at) if latest else datetime.fromisoformat(state.value["at"])
    owners = _owners(db)
    for owner in owners:
        if now - reference > timedelta(hours=settings.SCRAPER_STALE_HOURS):
            enqueue(db, f"baalebos-scraper-stale-{latest.id if latest else 'initial'}-{owner.id}", "scraper.stale", owner, {
                "subject": "Job scraper needs attention",
                "text": f"No recent scraper heartbeat within {settings.SCRAPER_STALE_HOURS} hours. Check the existing cron service and Railway logs.\nAdmin: https://www.baalebo.xyz/admin",
            }, now)
        for run in db.query(ScrapeRun).filter(ScrapeRun.finished_at >= now - timedelta(days=1),
                                             ScrapeRun.status.in_(["partial", "failed", "empty"])).all():
            summary = run.summary or {}
            enqueue(db, f"baalebos-scraper-run-{run.id}-{owner.id}", "scraper.warning", owner, {
                "subject": f"Job scraper report: {run.status}",
                "text": f"Scrape run {run.id}: {run.status}.\nFetched: {summary.get('total_scraped', 0)}. Saved: {summary.get('total_saved', 0)}.\nFailed sources: {summary.get('failed_sources', 0)}. Partially failing sources: {summary.get('partial_sources', 0)}.\nCheck source results in Admin → Automation.\nhttps://www.baalebo.xyz/admin",
            }, now)
        # Report the completed UTC day, giving stable totals on retries.
        end = datetime.combine(now.date(), datetime.min.time())
        start = end - timedelta(days=1)
        new_jobs = db.query(Job).filter(Job.first_seen_at >= start, Job.first_seen_at < end)
        applications = db.query(Application).filter(Application.created_at >= start, Application.created_at < end)
        counts = dict(db.query(Application.status, func.count(Application.id)).filter(Application.created_at >= start, Application.created_at < end).group_by(Application.status).all())
        summary = [f"Daily platform summary for {start.date().isoformat()} (UTC).",
                   f"New external listings: {new_jobs.filter(Job.posted_by_hr.is_(False)).count()}.",
                   f"New employer-posted listings: {new_jobs.filter(Job.posted_by_hr.is_(True)).count()}.",
                   f"Internal applications received: {applications.filter(Application.submission_method == 'baalebos').count()}.",
                   f"External application handoffs: {applications.filter(Application.submission_method == 'external_handoff').count()}.",
                   f"Of these applications, external submissions marked by users: {counts.get('submitted_external', 0)} (employer receipt not verified).",
                   f"Scraper runs: {db.query(ScrapeRun).filter(ScrapeRun.started_at >= start, ScrapeRun.started_at < end).count()}.",
                   f"Notifications needing attention: {db.query(AutomationEvent).filter_by(status='failed').count()}.",
                   "Open https://www.baalebo.xyz/admin for details."]
        enqueue(db, f"baalebos-admin-summary-{owner.id}-{start.date().isoformat()}", "admin.summary", owner,
                {"subject": f"Baalebos daily summary — {start.date().isoformat()}", "text": "\n".join(summary)}, now)
    return latest


def _recipient_allowed(db, event, user, now):
    if not user or not user.is_verified or user.email != event.payload.get("to_email"):
        return False
    if event.event_type == "application.created":
        application = db.get(Application, event.payload.get("application_id"))
        if not application or application.submission_method != "baalebos" or not application.job or application.job.hr_user_id != user.id:
            return False
        try:
            require_hr(user)
        except Exception:
            return False
        return True
    if event.event_type == "jobs.matched":
        if not user.job_alerts_enabled or not user.available_for_work or user.is_hr or user.is_admin:
            return False
        jobs = db.query(Job).filter(Job.id.in_(event.payload.get("job_ids", []))).all()
        # Cancel the entire prepared digest if any displayed listing closed or
        # preferences changed; never mutate an email after an uncertain send.
        return len(jobs) == len(event.payload.get("job_ids", [])) and all(
            matches_preferences(job, user) and (job.posted_by_hr or not job.scraped_at or job.scraped_at >= now - timedelta(days=3))
            for job in jobs)
    return is_owner(user)


def _deliver(event):
    url = settings.N8N_EVENTS_WEBHOOK_URL
    if not url and event.event_type == "application.created":
        accepted = notify_new_application(event.payload["application_id"], event.payload["job_title"], event.payload["employer_email"])
        return accepted, None if accepted else "webhook_rejected"
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return False, "invalid_configuration"
    try:
        response = httpx.post(url, json={**event.payload, "event_id": event.event_id, "event_type": event.event_type},
                              headers={"X-Baalebos-Webhook-Key": settings.N8N_WEBHOOK_SECRET},
                              timeout=12.0, follow_redirects=False)
        if not 200 <= response.status_code < 300:
            return False, f"http_{response.status_code}"
        ack = response.json()
        if not isinstance(ack, dict) or ack.get("accepted") is not True or not isinstance(ack.get("provider_message_id"), str) or not ack["provider_message_id"]:
            return False, "invalid_acknowledgement"
        return True, None
    except Exception as exc:
        # Exception messages/response bodies can contain credentials or PII.
        return False, type(exc).__name__


def dispatch_pending(db=None, limit=10, now=None, only_event_id=None):
    owned = db is None
    db = db or SessionLocal()
    started = time.monotonic()
    counts = {"accepted": 0, "failed": 0, "cancelled": 0, "retrying": 0}
    try:
        now = now or datetime.utcnow()
        due = or_(AutomationEvent.status == "pending",
                  (AutomationEvent.status == "processing") & (AutomationEvent.locked_until <= now))
        query = db.query(AutomationEvent.event_id).filter(due, AutomationEvent.next_attempt_at <= now)
        if not settings.N8N_EVENTS_WEBHOOK_URL:
            query = query.filter(AutomationEvent.event_type == "application.created")
        if only_event_id:
            query = query.filter(AutomationEvent.event_id == only_event_id)
        candidates = query.order_by(AutomationEvent.created_at).limit(limit).all()
        for (event_id,) in candidates:
            if time.monotonic() - started > 30:
                break
            event = db.get(AutomationEvent, event_id)
            # Leave disabled/configuration-less channels pending for setup.
            configured = settings.N8N_EVENTS_WEBHOOK_URL or (event.event_type == "application.created" and settings.N8N_APPLICATION_WEBHOOK_URL)
            if not configured or not settings.N8N_WEBHOOK_SECRET:
                continue
            token = uuid.uuid4().hex
            claimed = db.query(AutomationEvent).filter(AutomationEvent.event_id == event_id, due,
                                                      AutomationEvent.next_attempt_at <= now).update({
                "status": "processing", "locked_until": now + timedelta(minutes=2), "lease_token": token,
            }, synchronize_session=False)
            db.commit()
            if not claimed:
                continue
            db.refresh(event)
            user = db.get(User, event.recipient_id) if event.recipient_id else None
            if not _recipient_allowed(db, event, user, now):
                event.status = "cancelled"
                counts["cancelled"] += 1
            elif event.attempts >= MAX_ATTEMPTS or (event.first_attempt_at and now - event.first_attempt_at >= RETRY_WINDOW):
                event.status = "failed"
                event.last_error = "retry_window_exhausted"
                counts["failed"] += 1
            else:
                event.first_attempt_at = event.first_attempt_at or now
                event.attempts += 1
                db.commit()  # Survive process loss during HTTP delivery.
                accepted, reason = _deliver(event)
                event.last_error = None if accepted else reason
                if accepted:
                    event.status = "sent"
                    event.sent_at = now
                    counts["accepted"] += 1
                else:
                    event.status = "failed" if event.attempts >= MAX_ATTEMPTS else "pending"
                    event.next_attempt_at = now + timedelta(minutes=min(60, 2 ** event.attempts))
                    counts["failed" if event.status == "failed" else "retrying"] += 1
                logger.info("automation_event_result event_id=%s status=%s attempts=%s reason=%s", event.event_id, event.status, event.attempts, reason)
            final_values = {"status": event.status, "sent_at": event.sent_at, "last_error": event.last_error,
                            "next_attempt_at": event.next_attempt_at, "locked_until": None, "lease_token": None}
            # A delayed process must not overwrite a lease another dispatcher
            # has recovered. Discard ORM dirtiness before the conditional write.
            db.expire(event)
            db.query(AutomationEvent).filter(AutomationEvent.event_id == event_id,
                                             AutomationEvent.lease_token == token).update(final_values, synchronize_session=False)
            db.commit()
        return counts
    except Exception as exc:
        db.rollback()
        logger.warning("automation_dispatch_failed error_type=%s", type(exc).__name__)
        return {**counts, "dispatch_error": True}
    finally:
        if owned:
            db.close()


def run_tick(db, now=None):
    now = now or datetime.utcnow()
    queued = queue_job_digests(db, now) if settings.N8N_EVENTS_WEBHOOK_URL else 0
    if settings.N8N_EVENTS_WEBHOOK_URL:
        queue_admin_reports(db, now)
    db.commit()
    result = dispatch_pending(db=db, now=now)
    return {"queued_job_digests": queued, **result}


def automation_status(db):
    latest = db.query(ScrapeRun).order_by(ScrapeRun.started_at.desc()).first()
    return {
        "events_configured": bool(settings.N8N_EVENTS_WEBHOOK_URL and settings.N8N_WEBHOOK_SECRET),
        "application_notifications_configured": bool((settings.N8N_EVENTS_WEBHOOK_URL or settings.N8N_APPLICATION_WEBHOOK_URL) and settings.N8N_WEBHOOK_SECRET),
        "notification_counts": dict(db.query(AutomationEvent.status, func.count()).group_by(AutomationEvent.status).all()),
        "last_scrape": {"run_id": latest.id, "status": latest.status, "started_at": latest.started_at,
                        "finished_at": latest.finished_at, "summary": latest.summary} if latest else None,
        "failed_notifications": [{"event_id": event.event_id, "event_type": event.event_type, "attempts": event.attempts,
                                  "last_error": event.last_error} for event in db.query(AutomationEvent).filter_by(status="failed").order_by(AutomationEvent.created_at.desc()).limit(20)],
    }
