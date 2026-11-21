from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime
import os
import json
from threading import Lock
from time import monotonic

from backend.app.database import get_db, get_read_db
from backend.app.dependencies.auth import get_current_user
from backend.app.models.user import User
from backend.app.models.job import Job
from backend.app.models.application import Application
from backend.app.models.resume import Resume

router = APIRouter(tags=["Admin"])


from backend.app.dependencies.roles import require_admin, require_permission
from backend.app.services.job_automation import automation_status, run_tick
from backend.app.services import security_events


# ── Security oversight (owner/admin only) ─────────────────────────────────────
def _csv_response(rows, filename: str):
    """Stream CSV; cells that a spreadsheet would run as formulas are neutralised."""
    import csv
    import io
    from fastapi.responses import StreamingResponse

    def safe(value):
        text = '' if value is None else str(value)
        return "'" + text if text[:1] in ('=', '+', '-', '@', '\t', '\r') else text

    def generate():
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        for row in rows:
            writer.writerow([safe(v) for v in row])
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)
    return StreamingResponse(generate(), media_type='text/csv; charset=utf-8',
                             headers={'Content-Disposition': f'attachment; filename="{filename}"',
                                      'Cache-Control': 'no-store'})


@router.get("/security/summary")
def security_summary(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Last 24 hours: sign-ins, failures, sign-ups, IPs, suspicious IPs, countries, posture."""
    from backend.app.models.security import RefreshToken
    from backend.app.services import admin_console, security_controls
    summary = security_events.summary(db)
    blocked = {b['ip'] for b in security_controls.blocked_ips(db) if b['active']}
    for item in summary['suspicious_ips']:
        item['blocked'] = item['ip'] in blocked
    now = datetime.utcnow()
    summary['active_sessions'] = (db.query(func.count(func.distinct(RefreshToken.family_id)))
                                  .filter(RefreshToken.revoked_at.is_(None), RefreshToken.expires_at > now).scalar() or 0)
    summary['posture'] = admin_console.posture(db)
    summary['blocked_ips'] = security_controls.blocked_ips(db)
    return summary


@router.get("/security/events")
def security_event_log(request: Request, event: Optional[str] = None, category: Optional[str] = None,
                       q: Optional[str] = None, ip: Optional[str] = None, user_id: Optional[int] = None,
                       limit: int = 100, before_id: Optional[int] = None,
                       db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Full security events (IP, location, account). Every read is itself recorded."""
    events = security_events.list_events(db, event=event, category=category, q=q, ip=ip, user_id=user_id,
                                         limit=limit, before_id=before_id)
    if before_id is None:  # record the first page of each search, not every scroll
        filters = {'event': event, 'category': category, 'q': q, 'ip': ip, 'user_id': user_id}
        security_events.record('admin.security_viewed', request, user=admin,
                               details={'filters': {k: v for k, v in filters.items() if v}})
    return {'events': events, 'next_before_id': events[-1]['id'] if len(events) == max(1, min(limit, 500)) else None}


@router.get("/security/events.csv")
def security_event_export(request: Request, event: Optional[str] = None, category: Optional[str] = None,
                          q: Optional[str] = None, ip: Optional[str] = None, user_id: Optional[int] = None,
                          db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    filters = {'event': event, 'category': category, 'q': q, 'ip': ip, 'user_id': user_id}
    security_events.record('admin.exported', request, user=admin,
                           details={'export': 'security_events', 'filters': {k: v for k, v in filters.items() if v}})
    return _csv_response(security_events.csv_rows(db, **filters),
                         f'security-events-{datetime.utcnow():%Y%m%d-%H%M}.csv')


class BlockIPRequest(BaseModel):
    ip: str
    reason: str = ''
    hours: Optional[int] = None      # None = until unblocked


@router.get("/security/blocked-ips")
def list_blocked_ips(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    from backend.app.services import security_controls
    return security_controls.blocked_ips(db)


@router.post("/security/blocked-ips")
def block_ip(payload: BlockIPRequest, request: Request, db: Session = Depends(get_db),
             admin: User = Depends(require_admin)):
    from backend.app.core.client_ip import client_ip
    from backend.app.services import security_controls
    if payload.ip.strip() == client_ip(request):
        raise HTTPException(400, 'That is the address you are using now; blocking it would lock you out.')
    if payload.hours is not None and not 1 <= payload.hours <= 24 * 365:
        raise HTTPException(400, 'Choose between 1 hour and 1 year, or leave empty to block until removed.')
    result = security_controls.block_ip(db, payload.ip, reason=payload.reason, hours=payload.hours, admin=admin)
    security_events.record('admin.ip_blocked', request, user=admin,
                           details={'target_ip': result['ip'], 'reason': payload.reason or None,
                                    'hours': payload.hours})
    return result


@router.delete("/security/blocked-ips/{ip}")
def unblock_ip(ip: str, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    from backend.app.services import security_controls
    if not security_controls.unblock_ip(db, ip):
        raise HTTPException(404, 'That IP address is not blocked.')
    security_events.record('admin.ip_unblocked', request, user=admin, details={'target_ip': ip})
    return {'message': f'{ip} unblocked'}


# ── Overview ──────────────────────────────────────────────────────────────────
@router.get("/overview")
def console_overview(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from backend.app.services import admin_console
    return JSONResponse(jsonable_encoder(admin_console.overview(db)), headers={'Cache-Control': 'no-store'})


# ── Accounts: search, controls, duplicates ───────────────────────────────────
@router.get("/accounts")
def search_accounts(q: Optional[str] = None, role: Optional[str] = None, status: Optional[str] = None,
                    page: int = 1, page_size: int = 25, db: Session = Depends(get_read_db),
                    admin: User = Depends(require_admin)):
    from backend.app.services import admin_console
    return admin_console.list_users(db, q=q, role=role, status=status, page=page, page_size=page_size)


@router.get("/accounts.csv")
def export_accounts(request: Request, q: Optional[str] = None, role: Optional[str] = None,
                    status: Optional[str] = None, db: Session = Depends(get_read_db),
                    admin: User = Depends(require_admin)):
    from backend.app.services import admin_console
    security_events.record('admin.exported', request, user=admin,
                           details={'export': 'users', 'filters': {k: v for k, v in
                                                                    {'q': q, 'role': role, 'status': status}.items() if v}})
    return _csv_response(admin_console.users_csv(db, q=q, role=role, status=status),
                         f'users-{datetime.utcnow():%Y%m%d-%H%M}.csv')


def _target(db: Session, user_id: int, admin: User) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, 'User not found')
    if user.id == admin.id:
        raise HTTPException(400, 'You cannot do this to your own account.')
    return user


class SuspendRequest(BaseModel):
    reason: str = ''


@router.post("/users/{user_id}/suspend")
def suspend_user(user_id: int, payload: SuspendRequest, request: Request, db: Session = Depends(get_db),
                 admin: User = Depends(require_admin)):
    from backend.app.services.auth_service import revoke_all_sessions
    user = _target(db, user_id, admin)
    user.suspended_at = datetime.utcnow()
    user.suspended_reason = (payload.reason or '').strip()[:255] or None
    revoke_all_sessions(db, user)
    db.commit()
    security_events.record('admin.user_suspended', request, user=admin,
                           details={'target_user_id': user.id, 'target_email': user.email,
                                    'reason': user.suspended_reason})
    return {'message': f'{user.email} suspended and signed out everywhere'}


@router.post("/users/{user_id}/unsuspend")
def unsuspend_user(user_id: int, request: Request, db: Session = Depends(get_db),
                   admin: User = Depends(require_admin)):
    user = _target(db, user_id, admin)
    user.suspended_at = None
    user.suspended_reason = None
    db.commit()
    security_events.record('admin.user_unsuspended', request, user=admin,
                           details={'target_user_id': user.id, 'target_email': user.email})
    return {'message': f'{user.email} restored'}


@router.post("/users/{user_id}/sign-out")
def sign_out_user(user_id: int, request: Request, db: Session = Depends(get_db),
                  admin: User = Depends(require_admin)):
    from backend.app.services.auth_service import revoke_all_sessions
    user = _target(db, user_id, admin)
    revoke_all_sessions(db, user)
    db.commit()
    security_events.record('admin.sessions_revoked', request, user=admin,
                           details={'target_user_id': user.id, 'target_email': user.email})
    return {'message': f'{user.email} signed out of every device'}


@router.post("/users/{user_id}/force-password-reset")
def force_password_reset(user_id: int, request: Request, background_tasks: BackgroundTasks,
                         db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    from datetime import timedelta
    from backend.app.services.auth_service import new_opaque_token, revoke_all_sessions
    from backend.app.utils.email import send_password_reset_email
    user = _target(db, user_id, admin)
    raw, digest = new_opaque_token()
    user.reset_token = digest
    user.reset_token_expires = datetime.utcnow() + timedelta(hours=24)
    user.force_password_reset = True
    revoke_all_sessions(db, user)
    db.commit()
    background_tasks.add_task(send_password_reset_email, to_email=user.email, token=raw, full_name=user.full_name or "")
    security_events.record('admin.password_reset_forced', request, user=admin,
                           details={'target_user_id': user.id, 'target_email': user.email})
    return {'message': f'{user.email} must set a new password; a reset link was emailed (valid 24 hours)'}


@router.get("/duplicates")
def list_duplicates(include_dismissed: bool = False, db: Session = Depends(get_db),
                    admin: User = Depends(require_admin)):
    from backend.app.services.account_integrity import duplicate_groups
    return duplicate_groups(db, include_dismissed=include_dismissed)


class DuplicateDismiss(BaseModel):
    key: str


@router.post("/duplicates/dismiss")
def dismiss_duplicate(payload: DuplicateDismiss, request: Request, db: Session = Depends(get_db),
                      admin: User = Depends(require_admin)):
    from backend.app.models.security import DismissedDuplicate
    key = payload.key.strip()[:160]
    if not db.query(DismissedDuplicate).filter(DismissedDuplicate.group_key == key).first():
        db.add(DismissedDuplicate(group_key=key, dismissed_by=admin.email))
        db.commit()
    security_events.record('admin.duplicate_dismissed', request, user=admin, details={'group': key})
    return {'message': 'Marked as not duplicates'}


class DuplicateReject(BaseModel):
    user_ids: List[int]
    action: str = 'suspend'          # suspend (reversible) | delete


@router.post("/duplicates/reject")
def reject_duplicates(payload: DuplicateReject, request: Request, db: Session = Depends(get_db),
                      admin: User = Depends(require_admin)):
    """Reject duplicate accounts: suspend them (reversible) or delete them."""
    from backend.app.services.auth_service import revoke_all_sessions
    from backend.app.services.security_controls import is_admin_account
    if payload.action not in ('suspend', 'delete'):
        raise HTTPException(400, 'Action must be suspend or delete.')
    done = []
    for user_id in dict.fromkeys(payload.user_ids):
        user = _target(db, user_id, admin)
        if is_admin_account(user):
            raise HTTPException(400, f'{user.email} is an admin account; change its role first.')
        target = {'target_user_id': user.id, 'target_email': user.email, 'reason': 'duplicate_account'}
        if payload.action == 'delete':
            db.delete(user)
            db.commit()
            security_events.record('admin.user_deleted', request, user=admin, details=target)
        else:
            user.suspended_at = datetime.utcnow()
            user.suspended_reason = 'Duplicate account'
            revoke_all_sessions(db, user)
            db.commit()
            security_events.record('admin.user_suspended', request, user=admin, details=target)
        done.append(target['target_email'])
    return {'message': f"{len(done)} duplicate account(s) {'deleted' if payload.action == 'delete' else 'suspended'}",
            'accounts': done}


# ── Employers ────────────────────────────────────────────────────────────────
@router.get("/employers")
def list_employers(status: str = 'pending', db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    from backend.app.services.account_integrity import employer_card
    base = db.query(User).filter(User.is_hr == True)  # noqa: E712
    queries = {'pending': base.filter(User.hr_approved == False, User.hr_rejected_at.is_(None)),  # noqa: E712
               'approved': base.filter(User.hr_approved == True),  # noqa: E712
               'rejected': base.filter(User.hr_rejected_at.isnot(None))}
    if status not in queries:
        raise HTTPException(400, 'status must be pending, approved or rejected')
    suspicious = {s['ip'] for s in security_events.summary(db)['suspicious_ips']}
    rows = queries[status].order_by(User.created_at.asc() if status == 'pending' else User.created_at.desc()).limit(200)
    return {'counts': {k: q.count() for k, q in queries.items()},
            'items': [employer_card(db, u, suspicious) for u in rows]}


# ── Clear scraped jobs (fresh start) ─────────────────────────────────────────
class ClearJobsRequest(BaseModel):
    confirm: str
    refresh: bool = True


def _refresh_jobs_in_background():
    from backend.app.utils.global_scraper import scrape_global_jobs
    try:
        scrape_global_jobs()
    except Exception as exc:  # the run records its own failure; never crash the worker thread
        import logging
        logging.getLogger(__name__).error("job_refresh_failed error_type=%s", type(exc).__name__)


@router.post("/jobs/clear-scraped")
def clear_scraped(payload: ClearJobsRequest, request: Request, background_tasks: BackgroundTasks,
                  db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Delete every scraped listing (employer jobs are kept; listings with
    applications are closed, not deleted) and optionally refill the board."""
    if payload.confirm.strip() != "CLEAR JOBS":
        raise HTTPException(400, 'Type CLEAR JOBS to confirm.')
    from backend.app.utils.global_scraper import clear_scraped_jobs
    result = clear_scraped_jobs(db)
    security_events.record('admin.jobs_cleared', request, user=admin, details={**result, 'refresh': payload.refresh})
    if payload.refresh:
        background_tasks.add_task(_refresh_jobs_in_background)
    return {**result, 'refreshing': payload.refresh}


# ── Jobs search ────────────────────────────────────────────────────────────
@router.get("/jobs/search")
def search_jobs(q: Optional[str] = None, source: Optional[str] = None, status: str = 'active', page: int = 1,
                page_size: int = 25, db: Session = Depends(get_read_db), admin: User = Depends(require_admin)):
    from backend.app.services import admin_console
    return admin_console.list_jobs(db, q=q, source=source, status=status, page=page, page_size=page_size)


@router.get("/automation")
def get_automation_status(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    from fastapi.responses import JSONResponse
    from fastapi.encoders import jsonable_encoder
    return JSONResponse(jsonable_encoder(automation_status(db)), headers={"Cache-Control": "no-store"})


@router.post("/automation/run")
def run_automation(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return run_tick(db)


@router.get("/stats")
def admin_stats(db: Session = Depends(get_read_db), admin: User = Depends(require_admin)):
    return {
        "total_users":        db.query(User).count(),
        "total_jobs":         db.query(Job).count(),
        "total_applications": db.query(Application).count(),
        "total_resumes":      db.query(Resume).count(),
        "hr_users":           db.query(User).filter(User.is_hr == True).count(),
        "hr_posted_jobs":     db.query(Job).filter(Job.posted_by_hr == True).count(),
        "new_users_today":    db.query(User).filter(
            func.date(User.created_at) == datetime.utcnow().date()
        ).count(),
    }


@router.get("/users")
def list_users(
    skip: int = 0, limit: int = 50,
    db: Session = Depends(get_read_db),
    admin: User = Depends(require_admin)
):
    # One aggregate query instead of lazy-loading every user's applications (N+1).
    counts = (db.query(Application.user_id, func.count(Application.id).label("n"))
                .group_by(Application.user_id).subquery())
    rows = (db.query(User, func.coalesce(counts.c.n, 0))
              .outerjoin(counts, counts.c.user_id == User.id)
              .order_by(User.created_at.desc()).offset(skip).limit(min(max(limit, 1), 200)).all())
    return [
        {
            "id": u.id, "email": u.email, "full_name": u.full_name,
            "career_track": u.career_track, "country": u.country,
            "is_admin": u.role == "super_admin", "role": u.role, "is_hr": u.is_hr,
            "company_name": u.company_name,
            "created_at": u.created_at,
            "applications": int(n),
        }
        for u, n in rows
    ]


@router.patch("/users/{user_id}/make-hr")
def make_hr(user_id: int, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_verified:
        raise HTTPException(400, "Verify the account email before approval")
    user.is_hr = True
    user.hr_approved = True
    db.commit()
    security_events.record('admin.made_hr', request, user=admin, details={'target_user_id': user.id, 'target_email': user.email})
    return {"message": f"{user.email} is now an HR user"}


@router.patch("/users/{user_id}/make-admin")
def make_admin(user_id: int, admin: User = Depends(require_admin)):
    """Replaced by RBAC role assignment (PUT /api/v1/rbac/users/{id}/role)."""
    raise HTTPException(410, "Use PUT /api/v1/rbac/users/{id}/role to assign governance roles.")


@router.delete("/users/{user_id}")
def delete_user(user_id: int, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    target = {'target_user_id': user.id, 'target_email': user.email}
    db.delete(user)
    db.commit()
    security_events.record('admin.user_deleted', request, user=admin, details=target)
    return {"message": "User deleted"}


@router.get("/jobs")
def list_all_jobs(
    skip: int = 0, limit: int = 50,
    db: Session = Depends(get_read_db),
    admin: User = Depends(require_admin)
):
    jobs = db.query(Job).order_by(Job.scraped_at.desc()).offset(skip).limit(limit).all()
    return jobs


@router.delete("/jobs/{job_id}")
def delete_job(job_id: int, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    target = {'job_id': job.id, 'title': job.title, 'company': job.company}
    db.delete(job)
    db.commit()
    security_events.record('admin.job_deleted', request, user=admin, details=target)
    return {"message": "Job deleted"}


@router.post("/scrape")
async def trigger_scrape(
    request: Request,
    admin: User = Depends(require_admin)
):
    """Trigger job scraper — admin only."""
    from fastapi.concurrency import run_in_threadpool
    from backend.app.utils.global_scraper import scrape_global_jobs
    result = await run_in_threadpool(scrape_global_jobs)
    return result


@router.get("/applications")
def list_applications(
    skip: int = 0, limit: int = 50,
    db: Session = Depends(get_read_db),
    admin: User = Depends(require_admin)
):
    from sqlalchemy.orm import joinedload
    # Eager-load user and job in the same query (was 2 lazy queries per row).
    apps = (db.query(Application).options(joinedload(Application.user), joinedload(Application.job))
              .order_by(Application.created_at.desc()).offset(skip).limit(min(max(limit, 1), 200)).all())
    return [
        {
            "id": a.id,
            "user_email": a.user.email if a.user else None,
            "job_title": a.job.title if a.job else None,
            "company": a.job.company if a.job else None,
            "status": a.status,
            "ats_score": a.ats_score,
            "created_at": a.created_at,
        }
        for a in apps
    ]

# One synthetic probe at a time per process; avoid accidental repeated clicks.
_probe_lock = Lock()
_probe_last_started = None


@router.post("/resume-diagnostic")
def resume_diagnostic(admin: User = Depends(require_permission('system:diagnostics'))):
    """Owner-only, synthetic input; no database writes or candidate resumes."""
    global _probe_last_started
    if not _probe_lock.acquire(blocking=False):
        raise HTTPException(429, "A diagnostic is already running. Please wait.")
    try:
        now = monotonic()
        if _probe_last_started is not None and now - _probe_last_started < 60:
            raise HTTPException(429, "Wait one minute before running another diagnostic.")
        _probe_last_started = now
        from backend.app.utils.ats_engine import get_client
        from backend.scripts.diagnose_resume_provider import run_probe
        events = []
        try:
            client, model = get_client()
            result = run_probe(client, model, emit=lambda line: events.append(json.loads(line)))
        except Exception as exc:
            # Never expose credential-bearing exception messages or tracebacks.
            events.append({"result": "setup_failed", "error": type(exc).__name__})
            result = 2
        from fastapi.responses import JSONResponse
        return JSONResponse({"passed": result == 0, "events": events},
                            headers={"Cache-Control": "no-store"})
    finally:
        _probe_lock.release()
