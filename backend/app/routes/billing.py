# =============================================================================
# backend/app/routes/billing.py
# Stripe subscription system — checkout, webhook, portal, status
# =============================================================================
import os
import stripe
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.dependencies.auth import get_current_user
from backend.app.models.user import User
from backend.app.models.subscription import Subscription, PLANS

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

PRICE_IDS = {
    "pro":        os.getenv("STRIPE_PRICE_PRO", ""),        # $19/mo price ID
    "enterprise": os.getenv("STRIPE_PRICE_ENTERPRISE", ""), # $49/mo price ID
}

FRONTEND_URL = os.getenv("FRONTEND_URL", "https://baalebo.xyz")

router = APIRouter(tags=["Billing"])


def _get_or_create_sub(user_id: int, db: Session) -> Subscription:
    """Return existing subscription or create a free one."""
    sub = db.query(Subscription).filter(Subscription.user_id == user_id).first()
    if not sub:
        sub = Subscription(user_id=user_id, plan="free")
        db.add(sub)
        db.commit()
        db.refresh(sub)
    return sub


# ── GET /billing/status ───────────────────────────────────────────────────────
@router.get("/status")
def get_billing_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Return current plan, scan usage, and limits."""
    sub = _get_or_create_sub(current_user.id, db)
    plan_info = PLANS.get(sub.plan, PLANS["free"])

    # Reset monthly scan count if a new month has started
    now = datetime.utcnow()
    if sub.reset_date.month != now.month or sub.reset_date.year != now.year:
        sub.scans_this_month = 0
        sub.reset_date = now
        db.commit()

    scans_limit = plan_info["scans_per_month"]
    scans_left  = max(0, scans_limit - sub.scans_this_month) if scans_limit != -1 else -1

    return {
        "plan":             sub.plan,
        "plan_name":        plan_info["name"],
        "status":           sub.status,
        "scans_this_month": sub.scans_this_month,
        "scans_limit":      scans_limit,    # -1 = unlimited
        "scans_left":       scans_left,     # -1 = unlimited
        "is_pro":           sub.plan in ("pro", "enterprise"),
        "price_monthly":    plan_info["price"],
    }


# ── POST /billing/checkout ────────────────────────────────────────────────────
@router.post("/checkout")
def create_checkout_session(
    plan: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a Stripe Checkout session for the selected plan."""
    if plan not in PRICE_IDS or not PRICE_IDS[plan]:
        raise HTTPException(status_code=400, detail=f"Invalid plan or Stripe price ID not configured for '{plan}'")

    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe is not configured on this server.")

    sub = _get_or_create_sub(current_user.id, db)

    # Get or create Stripe customer
    if sub.stripe_customer_id:
        customer_id = sub.stripe_customer_id
    else:
        customer = stripe.Customer.create(
            email=current_user.email,
            name=current_user.full_name or current_user.email,
            metadata={"user_id": str(current_user.id)}
        )
        customer_id = customer.id
        sub.stripe_customer_id = customer_id
        db.commit()

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": PRICE_IDS[plan], "quantity": 1}],
        mode="subscription",
        success_url=f"{FRONTEND_URL}/?upgraded=true",
        cancel_url=f"{FRONTEND_URL}/pricing",
        metadata={"user_id": str(current_user.id), "plan": plan},
    )
    return {"checkout_url": session.url}


# ── POST /billing/portal ──────────────────────────────────────────────────────
@router.post("/portal")
def create_billing_portal(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Redirect user to Stripe Customer Portal to manage/cancel subscription."""
    sub = _get_or_create_sub(current_user.id, db)
    if not sub.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No billing account found. Please subscribe first.")

    portal = stripe.billing_portal.Session.create(
        customer=sub.stripe_customer_id,
        return_url=f"{FRONTEND_URL}/",
    )
    return {"portal_url": portal.url}


# ── POST /billing/webhook ─────────────────────────────────────────────────────
@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None),
    db: Session = Depends(get_db)
):
    """Handle Stripe webhook events — payment success, cancellation, past due."""
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(payload, stripe_signature, webhook_secret)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook signature")

    data = event["data"]["object"]

    # ── Payment succeeded / subscription activated ────────────────────────────
    if event["type"] in ("checkout.session.completed", "invoice.payment_succeeded"):
        user_id  = int(data.get("metadata", {}).get("user_id", 0))
        plan     = data.get("metadata", {}).get("plan", "pro")
        stripe_sub_id = data.get("subscription") or data.get("id")

        if user_id:
            sub = _get_or_create_sub(user_id, db)
            sub.plan             = plan
            sub.status           = "active"
            sub.stripe_sub_id    = stripe_sub_id
            sub.scans_this_month = 0
            sub.reset_date       = datetime.utcnow()
            db.commit()
            print(f"✅ User {user_id} upgraded to {plan}")

    # ── Subscription cancelled ────────────────────────────────────────────────
    elif event["type"] == "customer.subscription.deleted":
        stripe_sub_id = data.get("id")
        sub = db.query(Subscription).filter(Subscription.stripe_sub_id == stripe_sub_id).first()
        if sub:
            sub.plan   = "free"
            sub.status = "cancelled"
            db.commit()
            print(f"⚠️ Subscription {stripe_sub_id} cancelled — downgraded to free")

    # ── Payment failed ────────────────────────────────────────────────────────
    elif event["type"] == "invoice.payment_failed":
        stripe_sub_id = data.get("subscription")
        sub = db.query(Subscription).filter(Subscription.stripe_sub_id == stripe_sub_id).first()
        if sub:
            sub.status = "past_due"
            db.commit()
            print(f"❌ Payment failed for subscription {stripe_sub_id}")

    return {"received": True}
