from backend.app.database import SessionLocal
from backend.app.models.resume import Resume
from backend.app.models.job import Job
from backend.app.models.application import Application

def seed_data():
    db = SessionLocal()
    try:
        # 1. Create a dummy resume
        test_resume = Resume(
            filename="my_resume.pdf",
            content="DevOps Engineer with Python experience...",
            ats_score=85.0,
            user_id=1  # Added user_id
        )
        db.add(test_resume)
        
        # 2. Create a dummy job 
        # (Added location and user_id to satisfy database constraints)
        test_job = Job(
            title="DevOps Engineer",
            company="Baalebos Cloud",
            location="Lagos / Remote",           # Fixed: Was missing
            category="DevOps",
            source="LinkedIn",
            url="https://linkedin.com/jobs/123",
            user_id=1                    # Fixed: Was missing
        )
        db.add(test_job)
        db.flush() 

        # 3. Create an application entry
        test_app = Application(
            job_id=test_job.id, #The Link
            status="interview",
            ats_score=92.5,
            user_id=1                    # Added user_id
        )
        db.add(test_app)
        
        db.commit()
        print("✅ Phase 1 Data Seeded Successfully!")
        print("Now check http://127.0.0.1:8000/dashboard/stats")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
