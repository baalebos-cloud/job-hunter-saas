from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.models.resume import Resume
from backend.app.models.job import Job
from backend.app.models.application import Application

def get_dashboard_stats(db: Session):
    # 1. Resume Stats
    total_resumes = db.query(Resume).count()
    
    # Use func.coalesce to handle None values directly in SQL
    avg_score = db.query(func.avg(Resume.ats_score)).scalar() or 0
    average_ats_score = round(float(avg_score), 1)

    # 2. Job Stats (Scraped/Marketplace)
    total_jobs_scraped = db.query(Job).count()

    # 3. Application Stats (User's specific tracking)
    total_applications = db.query(Application).count()
    
    # Filtered counts for the breakdown
    interviews = db.query(Application).filter(Application.status == "interview").count()
    rejected = db.query(Application).filter(Application.status == "rejected") .count()
    pending = db.query(Application).filter(Application.status == "pending") .count()

    return {
        "total_resumes": total_resumes,
        "average_ats_score": average_ats_score,
        "total_jobs_scraped": total_jobs_scraped,
        "total_applications": total_applications,
        "stats_breakdown": {
            "interviews": interviews,
            "rejected": rejected,
            "pending": pending
        }
    }
