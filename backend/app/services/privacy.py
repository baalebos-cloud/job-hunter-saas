"""GDPR data-subject rights: Art. 15 export and Art. 17 erasure, plus the
retention job that enforces storage limits."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta

from sqlalchemy import or_

logger = logging.getLogger(__name__)
SECRET_USER_FIELDS = {'hashed_password', 'verification_token', 'reset_token', 'reset_token_expires', 'token_version'}


def _row(obj, exclude=()):
    data = {}
    for column in obj.__table__.columns:
        if column.name in exclude:
            continue
        value = getattr(obj, column.name)
        if isinstance(value, (bytes, bytearray, memoryview)):
            continue
        data[column.name] = value.isoformat() if isinstance(value, datetime) else value
    return data


def _team_export(db, user) -> dict:
    from backend.app.models.team import TeamMember
    member_of = db.query(TeamMember).filter(TeamMember.user_id == user.id).first()
    return {'member_of_owner_id': member_of.owner_id if member_of else None,
            'invited_by_you': [{'email': r.email, 'status': r.status, 'invited_at': r.invited_at.isoformat()}
                               for r in db.query(TeamMember).filter(TeamMember.owner_id == user.id)]}


def _slack_export(db, user) -> list:
    from backend.app.models.support import SlackRequest
    return [{'company': r.company, 'emails': r.emails, 'status': r.status, 'created_at': r.created_at.isoformat()}
            for r in db.query(SlackRequest).filter(SlackRequest.account_id == user.id)]


def _profile_resume_export(db, user):
    from backend.app.models.user import ProfileResume
    kept = db.get(ProfileResume, user.id)
    if kept is None:
        return None
    return {'filename': kept.filename, 'size_bytes': kept.size_bytes, 'uploaded_at': kept.uploaded_at.isoformat() + 'Z',
            'read_from_file': kept.extracted, 'download_path': '/api/v1/profile/resume/file'}


def export_user_data(db, user) -> dict:
    """Machine-readable copy of everything held about ``user``."""
    from backend.app.models.application import Application
    from backend.app.models.audit import AuditLog
    from backend.app.models.automation import AutomationEvent
    from backend.app.models.referral import Referral
    from backend.app.models.resume import Resume
    from backend.app.models.security import RefreshToken
    from backend.app.models.security_event import SecurityEvent
    from backend.app.models.subscription import Subscription
    from backend.app.models.user import OutreachMessage
    from backend.app.services.audit import actor_hash

    resumes = []
    for record in db.query(Resume).filter(Resume.owner_id == user.id).order_by(Resume.id):
        item = _row(record, exclude={'content'})
        for field in ('parsed_data',):
            try:
                item[field] = json.loads(item[field]) if item.get(field) else None
            except ValueError:
                pass
        task_id = (record.filename or '').removeprefix('optimized_').removesuffix('.pdf')
        item['download_path'] = f'/api/v1/resume/download/{task_id}' if record.status == 'completed' else None
        resumes.append(item)
    subject = actor_hash(user.email)
    profile_children = {name: [_row(child, exclude={'user_id'}) for child in getattr(user, name)]
                        for name in ('certified_skills', 'other_skills', 'education_entries', 'experience_entries', 'languages')}
    return {
        'format': 'baalebos.dsar.v1',
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'legal_basis': 'GDPR Art. 15 (right of access) and Art. 20 (data portability)',
        'profile': _row(user, exclude=SECRET_USER_FIELDS),
        'profile_details': profile_children,
        'resumes': resumes,
        'profile_resume': _profile_resume_export(db, user),
        'applications': [_row(a) for a in db.query(Application).filter(Application.user_id == user.id)],
        'outreach_messages': [_row(m) for m in db.query(OutreachMessage).filter(OutreachMessage.user_id == user.id)],
        'subscription': [_row(s) for s in db.query(Subscription).filter(Subscription.user_id == user.id)],
        'referrals': [_row(r) for r in db.query(Referral).filter(or_(Referral.referrer_id == user.id,
                                                                     Referral.referred_user_id == user.id))],
        'notifications': [_row(e) for e in db.query(AutomationEvent).filter(AutomationEvent.recipient_id == user.id)],
        'team': _team_export(db, user),
        'slack_support_requests': _slack_export(db, user),
        'active_sessions': [{'created_at': t.created_at.isoformat(), 'expires_at': t.expires_at.isoformat()}
                            for t in db.query(RefreshToken).filter(RefreshToken.user_id == user.id,
                                                                    RefreshToken.revoked_at.is_(None))],
        'security_audit_events': [_row(e, exclude={'actor_hash'}) for e in db.query(AuditLog)
                                  .filter(AuditLog.actor_hash == subject).order_by(AuditLog.ts.desc()).limit(1000)],
        'security_events': [_row(e) for e in db.query(SecurityEvent).filter(
                                or_(SecurityEvent.user_id == user.id, SecurityEvent.email == user.email))
                            .order_by(SecurityEvent.ts.desc()).limit(1000)],
    }


def erase_user(db, user, requested_by: str = 'self') -> dict:
    """Delete or anonymise every record of ``user`` in one transaction, then
    delete stored objects. A tombstone (no personal data) proves the erasure
    and tracks object deletions still to retry."""
    from backend.app.models.application import Application
    from backend.app.models.audit import ErasureTombstone
    from backend.app.models.automation import AutomationEvent
    from backend.app.models.job import Job
    from backend.app.models.referral import Referral
    from backend.app.models.resume import Resume
    from backend.app.models.security import RefreshToken
    from backend.app.models.security_event import SecurityEvent
    from backend.app.models.subscription import Subscription
    from backend.app.models.user import OutreachMessage
    from backend.app.services import resume_storage
    from backend.app.services.audit import actor_hash

    subject = actor_hash(user.email)
    photo_url = user.photo_url
    resume_rows = db.query(Resume).filter(Resume.owner_id == user.id).all()
    resume_ids = [r.id for r in resume_rows]
    object_keys = [r.storage_key for r in resume_rows if r.storage_key]
    counts = {}
    try:
        own_apps = db.query(Application.id).filter(Application.user_id == user.id)
        counts['outreach_messages'] = db.query(OutreachMessage).filter(
            or_(OutreachMessage.user_id == user.id, OutreachMessage.application_id.in_(own_apps))).delete(synchronize_session=False)
        if resume_ids:
            # Other people's records never point at this user's resumes, but be safe.
            db.query(Application).filter(Application.resume_id.in_(resume_ids)).update(
                {Application.resume_id: None}, synchronize_session=False)
        counts['applications'] = db.query(Application).filter(Application.user_id == user.id).delete(synchronize_session=False)
        counts['resumes'] = db.query(Resume).filter(Resume.owner_id == user.id).delete(synchronize_session=False)
        counts['refresh_tokens'] = db.query(RefreshToken).filter(RefreshToken.user_id == user.id).delete(synchronize_session=False)
        counts['security_events'] = db.query(SecurityEvent).filter(
            or_(SecurityEvent.user_id == user.id, SecurityEvent.email == user.email)).delete(synchronize_session=False)
        counts['subscriptions'] = db.query(Subscription).filter(Subscription.user_id == user.id).delete(synchronize_session=False)
        from backend.app.models.user import ProfilePhoto, ProfileResume
        counts['profile_photos'] = db.query(ProfilePhoto).filter(ProfilePhoto.user_id == user.id).delete(synchronize_session=False)
        counts['profile_resumes'] = db.query(ProfileResume).filter(ProfileResume.user_id == user.id).delete(synchronize_session=False)
        from backend.app.models.support import SupportMessage, SupportTicket
        tickets = db.query(SupportTicket.id).filter(or_(SupportTicket.user_id == user.id, SupportTicket.email == user.email))
        db.query(SupportMessage).filter(SupportMessage.ticket_id.in_(tickets.scalar_subquery())).delete(synchronize_session=False)
        from backend.app.models.support import SlackRequest
        counts['slack_requests'] = db.query(SlackRequest).filter(SlackRequest.account_id == user.id).delete(synchronize_session=False)
        counts['support_tickets'] = db.query(SupportTicket).filter(
            or_(SupportTicket.user_id == user.id, SupportTicket.email == user.email)).delete(synchronize_session=False)
        counts['notifications'] = db.query(AutomationEvent).filter(AutomationEvent.recipient_id == user.id).delete(synchronize_session=False)
        from backend.app.models.team import TeamMember
        counts['team_memberships'] = db.query(TeamMember).filter(
            or_(TeamMember.owner_id == user.id, TeamMember.user_id == user.id,
                TeamMember.email_canonical == (user.email_canonical or user.email.lower()))).delete(synchronize_session=False)
        counts['referrals_made'] = db.query(Referral).filter(Referral.referrer_id == user.id).delete(synchronize_session=False)
        counts['referrals_anonymised'] = db.query(Referral).filter(Referral.referred_user_id == user.id).update(
            {Referral.referred_user_id: None, Referral.referred_email: 'erased'}, synchronize_session=False)
        # Vacancies stay for other candidates' applications; the link to the person goes.
        counts['jobs_detached'] = db.query(Job).filter(or_(Job.hr_user_id == user.id, Job.user_id == user.id)).update(
            {Job.hr_user_id: None, Job.user_id: None, Job.is_active: False}, synchronize_session=False)
        db.delete(user)  # profile children cascade (delete-orphan)
        tombstone = ErasureTombstone(subject_hash=subject, requested_by=requested_by, deleted_counts=counts,
                                     pending_object_keys=object_keys or None)
        db.add(tombstone)
        db.commit()
    except Exception:
        db.rollback()
        raise
    pending = []
    for key in object_keys:
        try:
            resume_storage.client().delete_object(Bucket=os.getenv('RESUME_S3_BUCKET', ''), Key=key)
        except Exception as exc:
            logger.warning('erasure_object_delete_failed error_type=%s', type(exc).__name__)
            pending.append(key)
    _delete_local_photo(photo_url)
    tombstone.pending_object_keys = pending or None
    tombstone.completed_at = None if pending else datetime.utcnow()
    db.commit()
    return {'subject': subject, 'deleted': counts, 'objects_deleted': len(object_keys) - len(pending),
            'objects_pending': len(pending)}


def _delete_local_photo(photo_url):
    if not photo_url or '/photo/' not in photo_url:
        return
    filename = os.path.basename(photo_url.split('?')[0])
    path = os.path.join(os.getenv('OUTPUT_DIR', '/app/output'), 'avatars', filename)
    try:
        if filename.startswith('avatar_') and os.path.isfile(path):
            os.remove(path)
    except OSError:
        logger.warning('erasure_photo_delete_failed')


def run_retention(db, now: datetime | None = None) -> dict:
    """Storage limitation: purge expired data. Safe to run repeatedly."""
    from backend.app.models.audit import AuditLog, ErasureTombstone
    from backend.app.models.resume import Resume
    from backend.app.models.security import RefreshToken
    from backend.app.models.security_event import SecurityEvent
    from backend.app.services import resume_storage
    now = now or datetime.utcnow()
    result = {}
    result['refresh_tokens'] = db.query(RefreshToken).filter(
        or_(RefreshToken.expires_at < now, RefreshToken.revoked_at < now - timedelta(days=30))).delete(synchronize_session=False)
    audit_days = int(os.getenv('AUDIT_RETENTION_DAYS', '400'))
    if db.get_bind().dialect.name == 'postgresql':
        from sqlalchemy import text
        db.execute(text("SET LOCAL app.audit_retention = 'on'"))  # the only path past the append-only trigger
    result['audit_logs'] = db.query(AuditLog).filter(AuditLog.ts < now - timedelta(days=audit_days)).delete(synchronize_session=False)
    from backend.app.models.security_event import SecurityEvent
    from backend.app.services.security_events import retention_days
    result['security_events'] = db.query(SecurityEvent).filter(
        SecurityEvent.ts < now - timedelta(days=retention_days())).delete(synchronize_session=False)
    resume_days = int(os.getenv('RESUME_RETENTION_DAYS', '0'))  # 0 = keep until the user deletes them
    expired_keys = []
    if resume_days > 0:
        expired = db.query(Resume).filter(Resume.created_at < now - timedelta(days=resume_days)).all()
        expired_keys = [r.storage_key for r in expired if r.storage_key]
        from backend.app.models.application import Application
        ids = [r.id for r in expired]
        if ids:
            db.query(Application).filter(Application.resume_id.in_(ids)).update({Application.resume_id: None}, synchronize_session=False)
        result['resumes'] = db.query(Resume).filter(Resume.id.in_(ids)).delete(synchronize_session=False) if ids else 0
    db.commit()
    for key in expired_keys:
        resume_storage.delete_object(key)
    retried = 0
    for tombstone in db.query(ErasureTombstone).filter(ErasureTombstone.completed_at.is_(None)).all():
        still = []
        for key in tombstone.pending_object_keys or []:
            try:
                resume_storage.client().delete_object(Bucket=os.getenv('RESUME_S3_BUCKET', ''), Key=key)
                retried += 1
            except Exception:
                still.append(key)
        tombstone.pending_object_keys = still or None
        tombstone.completed_at = None if still else now
    db.commit()
    result['erasure_objects_retried'] = retried
    return result
