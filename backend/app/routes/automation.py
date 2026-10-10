"""n8n maintenance endpoint: header authentication, no user data in replies."""
import secrets
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.database import get_db
from backend.app.services.job_automation import run_tick

router = APIRouter()


def require_automation_secret(x_baalebos_webhook_key: str = Header(default="")):
    expected = settings.N8N_WEBHOOK_SECRET
    if not expected or not secrets.compare_digest(x_baalebos_webhook_key.encode(), expected.encode()):
        raise HTTPException(403, "Forbidden")


@router.post("/tick", dependencies=[Depends(require_automation_secret)])
def automation_tick(db: Session = Depends(get_db)):
    return run_tick(db)
