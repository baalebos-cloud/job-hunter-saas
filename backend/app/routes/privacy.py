"""Data-subject rights endpoints (GDPR Art. 15 / 17 / 20)."""
import json

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from backend.app.core.rate_limit import hit
from backend.app.database import get_db
from backend.app.dependencies.auth import get_current_user
from backend.app.dependencies.roles import require_permission
from backend.app.models.user import User

router = APIRouter(tags=["Privacy"])


@router.get("/export")
def export_my_data(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from backend.app.services.audit import record_event
    from backend.app.services.privacy import export_user_data
    allowed, retry = hit(f"dsar-export:{current_user.id}", 5, 3600)
    if not allowed:
        raise HTTPException(429, "Export limit reached. Please retry later.", headers={"Retry-After": str(retry)})
    bundle = export_user_data(db, current_user)
    record_event("privacy.export", actor=current_user, trace_id=getattr(request.state, "trace_id", None),
                 details={"sections": sorted(k for k, v in bundle.items() if isinstance(v, (list, dict)))})
    return Response(json.dumps(bundle, default=str, indent=2), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="baalebos-data-export.json"',
                             "Cache-Control": "private, no-store"})


def erase_and_revoke(request: Request, db: Session, user: User, requested_by: str) -> dict:
    from backend.app.services.audit import record_event
    from backend.app.services.auth_service import revoke_access_token
    from backend.app.services.privacy import erase_user
    claims = getattr(request.state, "token_claims", {}) or {}
    result = erase_user(db, user, requested_by=requested_by)
    if requested_by == "self":
        revoke_access_token(claims.get("jti"), claims.get("exp"))
    record_event("privacy.erasure", actor=None, trace_id=getattr(request.state, "trace_id", None),
                 details={"subject": result["subject"], "requested_by": requested_by, "deleted": result["deleted"],
                          "objects_deleted": result["objects_deleted"], "objects_pending": result["objects_pending"]})
    return result


@router.delete("/users/{user_id}")
def erase_user_on_request(user_id: int, request: Request, db: Session = Depends(get_db),
                          officer=Depends(require_permission("privacy:manage"))):
    """Compliance officer fulfils a verified erasure request received offline."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    if user.role == "super_admin":
        raise HTTPException(409, "Remove the super_admin role before erasing this account.")
    result = erase_and_revoke(request, db, user, requested_by="officer")
    return {"message": "Account erased.", **{k: v for k, v in result.items() if k != "subject"}}
