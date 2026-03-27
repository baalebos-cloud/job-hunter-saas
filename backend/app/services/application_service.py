from backend.app.models.application import Application
from backend.app.models.job import Job
from sqlalchemy.orm import Session, joinedload

# -----------------------------
# Save processed application (used by Celery)
# -----------------------------
def process_application(db: Session, job_id: int, user_id: int, ats_score: float):
    new_application = Application(
        job_id=job_id,
        user_id=user_id, # Updated from user_email to match your new model
        ats_score=ats_score,
        status="processed"
    )

    db.add(new_application)
    db.commit()
    db.refresh(new_application)
    return new_application

# -----------------------------
# Get all applied jobs (Phase 2: Clean Structured Data)
# -----------------------------
def applied_jobs(db: Session):
    # Using joinedload tells SQLAlchemy to grab the Job data in the same query.
    # This is much faster than doing a separate query for every job title.
    return db.query(Application)\
             .options(joinedload(Application.job))\
             .order_by(Application.id.desc())\
             .all()

# -----------------------------
# Update application status
# -----------------------------
def update_application_status(db: Session, application_id: int, status: str):
    # Fixed: The variable name was 'job_id' but it was searching Application.id
    application = db.query(Application).filter(Application.id == application_id).first()

    if not application:
        return None # Return None so the route can raise a 404

    application.status = status
    db.commit()
    db.refresh(application)
    return application
