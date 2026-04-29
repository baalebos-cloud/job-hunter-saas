import requests
import xml.etree.ElementTree as ET
import logging
from datetime import datetime
from sqlalchemy.orm import Session

from backend.app.database import SessionLocal
from backend.app.models.job import Job

logger = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────────────────────

TECH_ROLES = [
    "Frontend Developer", "Backend Engineer", "Fullstack Developer",
    "DevOps Engineer", "Cloud Engineer", "Data Scientist",
    "Machine Learning Engineer", "Cybersecurity", "Mobile Developer",
    "Product Manager", "SRE", "Data Engineer",
]

# Jobicy is a free remote jobs board with a public RSS API — no key needed
JOBICY_RSS = "https://jobicy.com/jobs-rss?q={role}&count=10"

# Remotive is another free remote jobs API
REMOTIVE_API = "https://remotive.com/api/remote-jobs?category={category}&limit=10"

REMOTIVE_CATEGORIES = {
    "Frontend Developer": "software-dev",
    "Backend Engineer": "software-dev",
    "Fullstack Developer": "software-dev",
    "DevOps Engineer": "devops-sysadmin",
    "Cloud Engineer": "devops-sysadmin",
    "Data Scientist": "data",
    "Machine Learning Engineer": "data",
    "Cybersecurity": "software-dev",
    "Mobile Developer": "software-dev",
    "Product Manager": "product",
    "SRE": "devops-sysadmin",
    "Data Engineer": "data",
}


# ─── Scrapers ─────────────────────────────────────────────────────────────────

def scrape_jobicy(role: str) -> list:
    """Scrape Jobicy RSS feed for a given role."""
    jobs = []
    try:
        url = JOBICY_RSS.format(role=role.replace(" ", "+"))
        res = requests.get(url, timeout=10, headers={"User-Agent": "Baalebos-Bot/1.0"})
        if res.status_code != 200:
            return jobs

        root = ET.fromstring(res.content)
        channel = root.find("channel")
        if not channel:
            return jobs

        for item in channel.findall("item")[:5]:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            description = item.findtext("description", "").strip()[:500]
            company = item.findtext("{https://jobicy.com}company", "Remote Company").strip()
            location = item.findtext("{https://jobicy.com}jobLocation", "Remote").strip()

            if title and link:
                jobs.append({
                    "title": title,
                    "company": company,
                    "location": location,
                    "description": description,
                    "url": link,
                    "source": "Jobicy",
                    "category": role,
                    "salary_range": None,
                })
    except Exception as e:
        logger.warning(f"[Jobicy] Error scraping {role}: {e}")
    return jobs


def scrape_remotive(role: str) -> list:
    """Scrape Remotive API for a given role."""
    jobs = []
    try:
        category = REMOTIVE_CATEGORIES.get(role, "software-dev")
        url = REMOTIVE_API.format(category=category)
        res = requests.get(url, timeout=10, headers={"User-Agent": "Baalebos-Bot/1.0"})
        if res.status_code != 200:
            return jobs

        data = res.json()
        for job in data.get("jobs", [])[:5]:
            title = job.get("title", "").strip()
            url_link = job.get("url", "").strip()
            company = job.get("company_name", "Remote Company").strip()
            location = job.get("candidate_required_location", "Remote").strip()
            description = job.get("description", "")[:500]
            salary = job.get("salary", None)

            if title and url_link:
                jobs.append({
                    "title": title,
                    "company": company,
                    "location": location,
                    "description": description,
                    "url": url_link,
                    "source": "Remotive",
                    "category": role,
                    "salary_range": salary,
                })
    except Exception as e:
        logger.warning(f"[Remotive] Error scraping {role}: {e}")
    return jobs


# ─── DB Saver ─────────────────────────────────────────────────────────────────

def save_jobs_to_db(jobs: list, db: Session) -> int:
    """Save scraped jobs to DB, skipping duplicates by URL."""
    saved = 0
    for job_data in jobs:
        try:
            # Skip if URL already exists
            existing = db.query(Job).filter(Job.url == job_data["url"]).first()
            if existing:
                continue

            new_job = Job(
                title=job_data["title"],
                company=job_data["company"],
                location=job_data["location"],
                description=job_data.get("description"),
                url=job_data["url"],
                source=job_data["source"],
                category=job_data["category"],
                salary_range=job_data.get("salary_range"),
            )
            db.add(new_job)
            saved += 1
        except Exception as e:
            logger.warning(f"[DB] Error saving job '{job_data.get('title')}': {e}")
            db.rollback()

    if saved > 0:
        db.commit()

    return saved


# ─── Main Entry Point ─────────────────────────────────────────────────────────

def scrape_global_jobs() -> dict:
    """
    Scrapes jobs from Jobicy and Remotive for all tech roles.
    Saves new jobs to the database.
    Returns a summary of what was scraped.
    """
    db = SessionLocal()
    total_scraped = 0
    total_saved = 0

    try:
        for role in TECH_ROLES:
            logger.info(f"[Scraper] Scanning: {role}")
            all_jobs = []

            # Try both sources
            all_jobs += scrape_remotive(role)
            all_jobs += scrape_jobicy(role)

            total_scraped += len(all_jobs)
            saved = save_jobs_to_db(all_jobs, db)
            total_saved += saved

            logger.info(f"[Scraper] {role}: {len(all_jobs)} found, {saved} new saved")

    except Exception as e:
        logger.error(f"[Scraper] Fatal error: {e}", exc_info=True)
    finally:
        db.close()

    summary = {
        "total_scraped": total_scraped,
        "total_saved": total_saved,
        "roles_scanned": len(TECH_ROLES),
        "timestamp": datetime.utcnow().isoformat()
    }
    logger.info(f"[Scraper] Done: {summary}")
    return summary


# ─── Manual trigger endpoint (add to main.py or a admin route) ───────────────

if __name__ == "__main__":
    # Run directly: python -m backend.app.utils.global_scraper
    import sys
    logging.basicConfig(level=logging.INFO)
    result = scrape_global_jobs()
    print(f"\n✅ Scraping complete: {result}")