# =============================================================================
# backend/app/routes/referral.py
# Referral system API — link generation, stats, conversion tracking
# =============================================================================
import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.database import get_db
from backend.app.dependencies.auth import get_current_user
from backend.app.models.user import User
from backend.app.models.referral import Referral, get_tier, TIER_CONFIG

FRONTEND_URL = os.getenv("FRONTEND_URL", "https://baalebo.xyz")

router = APIRouter(tags=["Referral"])


def _ref_code(user_id: int, username: str) -> str:
    """Generate a deterministic referral code from user id + username."""
    slug = (username or f"user{user_id}").lower().replace(" ", "")[:12]
    return f"{slug}{user_id}"


# ── GET /referral/stats ───────────────────────────────────────────────────────
@router.get("/stats")
def get_referral_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Return full referral stats for the dashboard."""
    refs = db.query(Referral).filter(Referral.referrer_id == current_user.id).all()

    total      = len(refs)
    converted  = [r for r in refs if r.status == "converted"]
    pending    = [r for r in refs if r.status == "pending"]
    paid_out   = sum(r.reward_amount for r in refs if r.paid_out)
    pending_earn = sum(r.reward_amount for r in refs if not r.paid_out and r.status == "converted")

    tier       = get_tier(total)
    next_tier  = next((t for t in TIER_CONFIG if t["min"] > total), None)

    code       = _ref_code(current_user.id, current_user.full_name or current_user.email.split("@")[0])
    ref_link   = f"{FRONTEND_URL}/?ref={code}"

    # Progress to next tier
    if next_tier:
        prev_min = tier["min"]
        progress = round(((total - prev_min) / (next_tier["min"] - prev_min)) * 100)
    else:
        progress = 100

    return {
        "ref_link":       ref_link,
        "ref_code":       code,
        "total":          total,
        "converted":      len(converted),
        "pending":        len(pending),
        "conversion_rate": round((len(converted) / total * 100) if total > 0 else 0, 1),
        "total_earned":   round(sum(r.reward_amount for r in refs), 2),
        "pending_payout": round(pending_earn, 2),
        "paid_out":       round(paid_out, 2),
        "tier":           tier,
        "next_tier":      next_tier,
        "progress_pct":   progress,
        "referrals":      [
            {
                "id":           r.id,
                "email":        _mask_email(r.referred_email),
                "status":       r.status,
                "plan":         r.plan_converted or "Free",
                "reward":       r.reward_amount,
                "created_at":   r.created_at.strftime("%d %b %Y"),
                "converted_at": r.converted_at.strftime("%d %b %Y") if r.converted_at else None,
            }
            for r in sorted(refs, key=lambda x: x.created_at, reverse=True)
        ]
    }


# ── POST /referral/track ──────────────────────────────────────────────────────
@router.post("/track")
def track_referral(
    ref_code: str,
    referred_email: str,
    db: Session = Depends(get_db)
):
    """
    Called during signup when a ref code is detected in the URL.
    Creates a pending referral record.
    """
    # Find referrer by code — match slug+id pattern
    # Extract user_id from end of code (digits at end)
    import re
    m = re.search(r'(\d+)$', ref_code)
    if not m:
        raise HTTPException(status_code=400, detail="Invalid referral code")

    user_id = int(m.group(1))
    referrer = db.query(User).filter(User.id == user_id).first()
    if not referrer:
        raise HTTPException(status_code=404, detail="Referral code not found")

    # Don't self-refer
    if referrer.email == referred_email:
        raise HTTPException(status_code=400, detail="Cannot refer yourself")

    # Check duplicate
    existing = db.query(Referral).filter(
        Referral.referrer_id == user_id,
        Referral.referred_email == referred_email
    ).first()
    if existing:
        return {"message": "Referral already tracked", "referral_id": existing.id}

    ref = Referral(
        referrer_id=user_id,
        referred_email=referred_email,
        status="pending"
    )
    db.add(ref)
    db.commit()
    db.refresh(ref)
    return {"message": "Referral tracked", "referral_id": ref.id}


# ── POST /referral/convert ────────────────────────────────────────────────────
@router.post("/convert")
def convert_referral(
    referred_user_id: int,
    plan: str,
    db: Session = Depends(get_db)
):
    """
    Called from the Stripe webhook (billing.py) when a referred user
    subscribes to a paid plan. Marks referral as converted and sets reward.
    """
    referred_user = db.query(User).filter(User.id == referred_user_id).first()
    if not referred_user:
        return {"message": "User not found"}

    ref = db.query(Referral).filter(
        Referral.referred_email == referred_user.email,
        Referral.status == "pending"
    ).first()

    if not ref:
        return {"message": "No pending referral found for this user"}

    # Calculate reward based on referrer's current tier
    referrer_refs = db.query(func.count(Referral.id)).filter(
        Referral.referrer_id == ref.referrer_id,
        Referral.status == "converted"
    ).scalar() or 0

    tier   = get_tier(referrer_refs)
    reward = tier["reward"]

    ref.status           = "converted"
    ref.plan_converted   = plan
    ref.reward_amount    = reward
    ref.referred_user_id = referred_user_id
    ref.converted_at     = datetime.utcnow()
    db.commit()

    return {
        "message":  "Referral converted",
        "reward":   reward,
        "tier":     tier["name"],
    }


# ── GET /referral/leaderboard ─────────────────────────────────────────────────
@router.get("/leaderboard")
def get_leaderboard(db: Session = Depends(get_db)):
    """Top 10 referrers by converted count — for public motivation."""
    rows = (
        db.query(
            Referral.referrer_id,
            func.count(Referral.id).label("converted"),
            func.sum(Referral.reward_amount).label("earned"),
        )
        .filter(Referral.status == "converted")
        .group_by(Referral.referrer_id)
        .order_by(func.count(Referral.id).desc())
        .limit(10)
        .all()
    )
    result = []
    for i, row in enumerate(rows):
        user = db.query(User).filter(User.id == row.referrer_id).first()
        if user:
            name = user.full_name or user.email.split("@")[0]
            result.append({
                "rank":      i + 1,
                "name":      name[:2].upper() + "***",  # anonymised
                "converted": row.converted,
                "earned":    round(row.earned or 0, 2),
                "tier":      get_tier(row.converted)["name"],
            })
    return result


def _mask_email(email: str) -> str:
    parts = email.split("@")
    if len(parts) != 2:
        return "***"
    local, domain = parts
    return f"{local[:2]}***@{domain}"
