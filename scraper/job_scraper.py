import requests
import sys
from pathlib import Path

# Ensure backend package is in path
sys.path.append(str(Path(__file__).resolve().parent.parent / "backend"))

from backend.app.database import SessionLocal
from backend.app.services.job_service import save_job

# RemoteOK API endpoint
URL = "https://remoteok.com/api"

# Define all job tracks and the matching tags
TRACKS = {
    "DevOps": ["devops"],
    "Cloud": ["cloud"],
    "Cybersecurity": ["security", "cybersecurity"],
    "Data Analytics": ["data", "analytics", "data science", "machine learning"],
    "Full-Stack": ["fullstack", "full-stack", "frontend", "backend"],
    "Backend": ["backend", "server"]
}


def scrape_jobs():
    """
    Scrapes jobs for all defined tracks from RemoteOK
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(URL, headers=headers)
    response.raise_for_status()
    data = response.json()

    jobs = []

    for item in data:
        if not isinstance(item, dict):
            continue

        tags = [t.lower() for t in item.get("tags", [])]

        for category, keywords in TRACKS.items():
            if any(k in tags for k in keywords):
                job = {
                    "title": item.get("position"),
                    "company": item.get("company"),
                    "category": category,
                    "url": item.get("url"),
                    "source": "RemoteOK"
                }
                jobs.append(job)
                break  # Stop checking other categories for this job

    return jobs


def scrape_and_save():
    """
    Scrapes all jobs and saves them to the database with duplicate protection
    """
    db = SessionLocal()
    jobs = scrape_jobs()
    print(f"Jobs found: {len(jobs)}")

    for job in jobs:
        saved_job = save_job(db, job)
        print(f"Saved: {saved_job.title} at {saved_job.company} ({saved_job.category})")


if __name__ == "__main__":
    scrape_and_save()
