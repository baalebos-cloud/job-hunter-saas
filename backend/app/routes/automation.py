"""n8n maintenance endpoint: header authentication, no user data in replies."""
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.database import get_db
from backend.app.services.job_automation import run_tick

router = APIRouter()


def require_automation_secret(x_baalebos_webhook_key: str = Header(default=""),
                              x_cron_secret: str = Header(default="")):
    """n8n sends X-Baalebos-Webhook-Key; a plain scheduler (Railway Cron) can
    send X-Cron-Secret with CRON_SECRET instead. Constant-time comparisons."""
    pairs = ((x_baalebos_webhook_key, settings.N8N_WEBHOOK_SECRET), (x_cron_secret, settings.CRON_SECRET))
    if not any(supplied and expected and secrets.compare_digest(supplied.encode(), expected.encode())
               for supplied, expected in pairs):
        raise HTTPException(403, "Forbidden")


@router.post("/tick", dependencies=[Depends(require_automation_secret)])
def automation_tick(db: Session = Depends(get_db)):
    return run_tick(db)


# ── Job alert unsubscribe (no sign-in needed; signed per-user token) ─────────
alerts_router = APIRouter()


class UnsubscribeBody(BaseModel):
    token: Optional[str] = None


@alerts_router.post("/unsubscribe")
def unsubscribe(t: Optional[str] = None, body: Optional[UnsubscribeBody] = None, db: Session = Depends(get_db)):
    """Turns job alerts off. Called by the /unsubscribe page and by mail apps'
    own one-click button (RFC 8058 POST to the List-Unsubscribe address)."""
    from backend.app.services.job_alerts import user_from_token
    user = user_from_token(db, (body.token if body and body.token else t) or "")
    if user is None:
        raise HTTPException(400, "This unsubscribe link is not valid. Turn alerts off in My profile instead.")
    if user.job_alerts_enabled:
        user.job_alerts_enabled = False
        db.commit()
    return {"unsubscribed": True}
