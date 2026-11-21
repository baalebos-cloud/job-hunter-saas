"""Grant the platform owner admin rights. Run once after the owner has registered
and verified their email. No password changes.

    python -m backend.scripts.provision_owner you@example.com
"""
import sys

from backend.app.database import SessionLocal
from backend.app.models.registry import import_all_models
from backend.app.models.user import User


def provision(email: str) -> str:
    import_all_models()
    with SessionLocal() as db:
        owner = db.query(User).filter(User.email == email.strip().lower()).first()
        if not owner or not owner.is_verified:
            raise SystemExit("Register and verify the owner email first.")
        owner.is_admin = True            # legacy admin flag (admin dashboard, plan exemption)
        owner.role = "super_admin"       # RBAC owner role (governance, admin permissions)
        db.commit()
    return "Verified owner administrator enabled."


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m backend.scripts.provision_owner <owner-email>")
    print(provision(sys.argv[1]))
