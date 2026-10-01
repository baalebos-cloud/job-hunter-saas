"""Run once after the owner has registered and verified email. No password changes."""
from backend.app.database import SessionLocal
from backend.app.models import user, job, resume, application, subscription, referral
from backend.app.dependencies.roles import OWNER_EMAIL

if __name__ == "__main__":
    with SessionLocal() as db:
        owner = db.query(user.User).filter(user.User.email == OWNER_EMAIL).first()
        if not owner or not owner.is_verified:
            raise SystemExit("Register and verify the owner email first.")
        owner.is_admin = True
        db.commit()
        print("Verified owner administrator enabled.")
