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
    - Free:       2 scans/month
    - Pro/Enterprise: unlimited
    Raises 403 with upgrade message when limit is reached.
    Usage:
        @router.post("/upload")
        async def upload_resume(..., _=Depends(require_scan_quota)):
    """
    sub = _get_or_create_sub(current_user.id, db)
    plan_info = PLANS.get(sub.plan, PLANS["free"])

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

    # Increment scan counter and save
    sub.scans_this_month += 1
    db.commit()

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
    sub = _get_or_create_sub(current_user.id, db)
    if sub.plan not in ("pro", "enterprise"):
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
