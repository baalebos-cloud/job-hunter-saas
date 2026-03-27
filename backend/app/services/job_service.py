from backend.app.models.job import Job
from sqlalchemy.orm import Session


# -----------------------------
# Save scraped job
# -----------------------------
def save_job(db: Session, job_data: dict):
    # Check if job already exists by URL
    existing_job = db.query(Job).filter(Job.url == job_data["url"]).first()

    if existing_job:
        return existing_job  # skip duplicates

    new_job = Job(
        title=job_data["title"],
        company=job_data["company"],
        category=job_data["category"],
        url=job_data["url"],
        source=job_data["source"]
    )

    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    return new_job


# -----------------------------
# Get all jobs (used in dashboard)
# -----------------------------
def list_jobs(db: Session):
    return db.query(Job).order_by(Job.id.desc()).all()


# -----------------------------
# Get single job by ID
# -----------------------------
def get_job(db: Session, job_id: int):
    return db.query(Job).filter(Job.id == job_id).first()
