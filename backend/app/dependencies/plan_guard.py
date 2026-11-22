# =============================================================================
# backend/app/dependencies/plan_guard.py
# Usage tracking + plan enforcement middleware
# Drop-in Depends() for any route that should be gated by plan limits
# =============================================================================
from datetime import datetime
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.dependencies.auth import get_current_user
from backend.app.models.user import User
from backend.app.models.subscription import Subscription, PLANS


def is_plan_exempt(user) -> bool:
    """Verified administrators and the platform owner are never limited by plan quotas.

    Admin is the ``users.is_admin`` flag (set for the owner by
    ``scripts/provision_owner.py``) or the RBAC owner role ``super_admin``.
    """
    return bool(user and getattr(user, "is_verified", False)
                and (getattr(user, "is_admin", False) or getattr(user, "role", None) == "super_admin"))


OWNER_PLAN = "enterprise"


def effective_plan(user, stored_plan: str | None, status: str | None = "active") -> str:
    """The plan a user actually has. The platform owner and verified admins hold
    Enterprise for life: derived from their role, so it never expires, needs no
    payment record, and no billing event can downgrade it."""
    if is_plan_exempt(user):
        return OWNER_PLAN
    return stored_plan if stored_plan and status == "active" else "free"


def _get_or_create_sub(user_id: int, db: Session) -> Subscription:
    sub = db.query(Subscription).filter(Subscription.user_id == user_id).first()
    if not sub:
        sub = Subscription(user_id=user_id, plan="free")
        db.add(sub)
        db.commit()
        db.refresh(sub)
    return sub


def require_scan_quota(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    """
    Enforce monthly scan limits based on plan.
    - Free:       3 scans/month
    - Pro/Enterprise: unlimited
    - Verified admins / the owner: unlimited (``is_plan_exempt``)
    Raises 403 with upgrade message when limit is reached.
    Usage:
        @router.post("/upload")
        async def upload_resume(..., _=Depends(require_scan_quota)):
    """
    if is_plan_exempt(current_user):
        return current_user
    sub = _get_or_create_sub(current_user.id, db)
    plan_info = PLANS.get(sub.plan if sub.status == "active" else "free", PLANS["free"])

    # Reset count at the start of a new month
    now = datetime.utcnow()
    if sub.reset_date.month != now.month or sub.reset_date.year != now.year:
        sub.scans_this_month = 0
        sub.reset_date = now
        db.commit()

    limit = plan_info["scans_per_month"]

    # -1 means unlimited (Pro/Enterprise)
    if limit != -1 and sub.scans_this_month >= limit:
        raise HTTPException(
            status_code=403,
            detail={
                "error":        "scan_limit_reached",
                "message":      f"You've used all {limit} free scan{'s' if limit != 1 else ''} this month.",
                "scans_used":   sub.scans_this_month,
                "scans_limit":  limit,
                "plan":         sub.plan,
                "upgrade_url":  "/pricing",
            }
        )

    # Usage is charged only when a complete resume is saved.

    return current_user


def require_pro(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    """
    Block free users from Pro-only features (bulk export, API access, team features).
    Usage:
        @router.get("/export/all")
        def export_all(..., _=Depends(require_pro)):
    """
    if is_plan_exempt(current_user):
        return current_user
    sub = _get_or_create_sub(current_user.id, db)
    if sub.status != 'active' or sub.plan not in ("pro", "enterprise"):
        raise HTTPException(
            status_code=403,
            detail={
                "error":       "pro_required",
                "message":     "This feature requires a Pro or Enterprise plan.",
                "plan":        sub.plan,
                "upgrade_url": "/pricing",
            }
        )
    return current_user


def consume_scan(user_id, db):
    if is_plan_exempt(db.get(User, user_id)):
        return  # unlimited: nothing to count against a quota
    sub = db.query(Subscription).filter(Subscription.user_id == user_id).with_for_update().first()
    if not sub: raise HTTPException(409, "Subscription not initialized")
    limit = PLANS.get(sub.plan if sub.status == 'active' else 'free', PLANS['free'])['scans_per_month']
    if limit != -1 and sub.scans_this_month >= limit:
        raise HTTPException(403, "Monthly scan limit reached")
    sub.scans_this_month += 1


def remaining_scans(user_id, db):
    """Scans left this month, or None for unlimited plans and exempt users."""
    if is_plan_exempt(db.get(User, user_id)):
        return None
    sub = db.query(Subscription).filter(Subscription.user_id == user_id).first()
    if not sub:
        return None
    limit = PLANS.get(sub.plan if sub.status == 'active' else 'free', PLANS['free'])['scans_per_month']
    return None if limit == -1 else max(limit - (sub.scans_this_month or 0), 0)
