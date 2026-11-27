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
from backend.app.dependencies.plan_guard import is_plan_exempt, own_plan, team_owner
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

    exempt = is_plan_exempt(current_user)   # verified admins / the owner: Enterprise for life
    if exempt:
        plan_info = PLANS["enterprise"]
    # Members of an Enterprise team use the owner's plan; their own subscription is untouched.
    owner = None if exempt or own_plan(db, current_user) == "enterprise" else team_owner(db, current_user)
    via_team = owner is not None
    if via_team:
        plan_info = PLANS["enterprise"]
    unlimited = exempt or via_team
    scans_limit = -1 if unlimited else plan_info["scans_per_month"]
    # Free scans are shared with other free accounts from the same network or device.
    from backend.app.dependencies.plan_guard import shared_free_scans
    shared = shared_free_scans(db, current_user) if scans_limit != -1 and sub.plan == "free" else 0
    scans_left  = max(0, scans_limit - sub.scans_this_month - shared) if scans_limit != -1 else -1

    return {
        "plan":             "enterprise" if unlimited else sub.plan,
        "plan_name":        plan_info["name"],
        "status":           "active" if unlimited else sub.status,
        "lifetime":         exempt,         # never billed, never expires
        "scans_this_month": sub.scans_this_month + shared,
        "scans_shared":     shared,         # used by other accounts on this network/device
        "scans_limit":      scans_limit,    # -1 = unlimited
        "scans_left":       scans_left,     # -1 = unlimited
        "is_pro":           unlimited or sub.plan in ("pro", "enterprise"),
        "plan_exempt":      exempt,
        "price_monthly":    0 if unlimited else plan_info["price"],
        "via_team":         ({"owner_name": owner.full_name or owner.email.split("@")[0], "owner_email": owner.email}
                             if via_team else None),
    }


# ── POST /billing/checkout ────────────────────────────────────────────────────
@router.post("/checkout")
def create_checkout_session(
    plan: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a Stripe Checkout session for the selected plan."""
    if is_plan_exempt(current_user):
        raise HTTPException(status_code=400, detail="Your account already has Enterprise for life. There is nothing to buy.")
    if own_plan(db, current_user) != "enterprise" and team_owner(db, current_user) is not None:
        raise HTTPException(status_code=400, detail="You already have Enterprise through your team. "
                                                    "Leave the team in Settings first if you want your own plan.")
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
        subscription_data={"metadata": {"user_id": str(current_user.id), "plan": plan}},
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
    if not webhook_secret:
        raise HTTPException(503, "Billing webhook is not configured")
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(payload, stripe_signature, webhook_secret)
    except (stripe.error.SignatureVerificationError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook signature")

    data = event["data"]["object"]

    # Only a signed, paid event qualifies. Replayed events do not reset scan usage.
    if event["type"] in ("checkout.session.completed", "checkout.session.async_payment_succeeded", "invoice.payment_succeeded"):
        paid = data.get('paid') is True if event['type']=='invoice.payment_succeeded' else data.get('payment_status')=='paid'
        if not paid: return {"received":True}
        stripe_sub_id = data.get('subscription')
        user_id = int(data.get('metadata',{}).get('user_id',0))
        sub = db.query(Subscription).filter(Subscription.stripe_sub_id==stripe_sub_id).first() if stripe_sub_id else None
        if not sub and user_id:
            sub = _get_or_create_sub(user_id,db)
        if sub:
            plan=data.get('metadata',{}).get('plan',sub.plan)
            if plan not in PRICE_IDS: return {"received":True}
            newly_paid = not (sub.plan == plan and sub.status == 'active')
            sub.plan=plan; sub.status='active'; sub.stripe_sub_id=stripe_sub_id
            from backend.app.routes.referral import convert_referral
            convert_referral(sub.user_id,plan,db)
            db.commit()
            if newly_paid:                       # renewals of an active plan are not upgrades
                from backend.app.models.growth import bump
                bump(db, 'plan:upgraded')

    # ── Subscription cancelled ────────────────────────────────────────────────
    elif event["type"] == "customer.subscription.deleted":
        stripe_sub_id = data.get("id")
        sub = db.query(Subscription).filter(Subscription.stripe_sub_id == stripe_sub_id).first()
        if sub:
            sub.plan   = "free"
            sub.status = "cancelled"
            db.commit()
            from backend.app.models.growth import bump
            bump(db, 'plan:cancelled')
            print(f"⚠️ Subscription {stripe_sub_id} cancelled — downgraded to free")

    # ── Payment failed ────────────────────────────────────────────────────────
    elif event["type"] == "invoice.payment_failed":
        stripe_sub_id = data.get("subscription")
        sub = db.query(Subscription).filter(Subscription.stripe_sub_id == stripe_sub_id).first()
        if sub:
            sub.status = "past_due"
            db.commit()
            from backend.app.models.growth import bump
            bump(db, 'plan:payment_failed')
            print(f"❌ Payment failed for subscription {stripe_sub_id}")

    return {"received": True}
