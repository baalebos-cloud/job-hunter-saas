import re
import requests
import xml.etree.ElementTree as ET
import logging
from datetime import datetime
from sqlalchemy.orm import Session

from backend.app.database import SessionLocal
from backend.app.models.job import Job
from backend.app.models.user import User, OutreachMessage  # noqa
from backend.app.models.resume import Resume  # noqa
from backend.app.models.application import Application  # noqa

logger = logging.getLogger(__name__)

TECH_ROLES = [
    "Frontend Developer", "Backend Engineer", "Fullstack Developer",
    "DevOps Engineer", "Cloud Engineer", "Data Scientist",
    "Machine Learning Engineer", "Cybersecurity", "Mobile Developer",
    "Product Manager", "SRE", "Data Engineer", "QA Engineer",
    "Platform Engineer", "Software Engineer", "React Developer",
    "Python Developer", "Node.js Developer", "AWS Engineer",
]

REMOTIVE_CATEGORIES = {
    "Frontend Developer": "software-dev", "Backend Engineer": "software-dev",
    "Fullstack Developer": "software-dev", "DevOps Engineer": "devops-sysadmin",
    "Cloud Engineer": "devops-sysadmin", "Data Scientist": "data",
    "Machine Learning Engineer": "data", "Cybersecurity": "software-dev",
    "Mobile Developer": "software-dev", "Product Manager": "product",
    "SRE": "devops-sysadmin", "Data Engineer": "data",
    "QA Engineer": "qa", "Platform Engineer": "devops-sysadmin",
    "Software Engineer": "software-dev", "React Developer": "software-dev",
    "Python Developer": "software-dev", "Node.js Developer": "software-dev",
    "AWS Engineer": "devops-sysadmin",
}

JOBICY_RSS    = "https://jobicy.com/jobs-rss?q={role}&count=12"
REMOTIVE_API  = "https://remotive.com/api/remote-jobs?category={category}&limit=12"
REMOTIVE_SEARCH = "https://remotive.com/api/remote-jobs?search={query}&limit=20"
ARBEITNOW_API = "https://www.arbeitnow.com/api/job-board-api"


def _clean(html: str, limit: int = 4000) -> str:
    text = re.sub(r'<[^>]+>', ' ', html or '')
    text = re.sub(r'&[a-z]+;', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:limit]


def _work_type(location: str, title: str, description: str) -> str:
    """Detect work type from location, title and description text."""
    combined = f"{location} {title} {description}".lower()
    if any(k in combined for k in ["hybrid", "partially remote", "flexible"]):
        return "hybrid"
    if any(k in combined for k in ["on-site", "onsite", "in-office", "in office", "on site"]):
        return "onsite"
    if any(k in combined for k in ["remote", "work from home", "wfh", "distributed", "worldwide", "anywhere"]):
        return "remote"
    # Default: if location is a city name only, assume onsite
    if location and not any(k in location.lower() for k in ["remote", "worldwide", "global", "anywhere"]):
        return "onsite"
    return "remote"


def _salary(text: str) -> str | None:
    if not text:
        return None
    if any(c in text for c in ['$', '€', '£', '₦', '¥']) and len(text) < 60:
        return text.strip()
    patterns = [
        r'[\$€£₦¥]\s?\d{2,3}[kK]\s?[-–]\s?[\$€£₦¥]?\s?\d{2,3}[kK]',
        r'[\$€£₦¥]\s?\d{2,3},\d{3}\s?[-–]\s?[\$€£₦¥]?\s?\d{2,3},\d{3}',
        r'\d{2,3}[kK]\s?[-–]\s?\d{2,3}[kK]\s?(?:USD|EUR|GBP|NGN|CAD|AUD)?',
        r'[\$€£₦¥]\s?\d{2,3}[kK]',
        r'[\$€£₦¥]\s?\d{2,3},\d{3}',
        r'\d{2,3}\s?[-–]\s?\d{2,3}\s?(?:USD|EUR|GBP|NGN)/(?:yr|year|month|hr)',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(0).strip()
    return None


# ─── Source 1: Remotive ───────────────────────────────────────────────────────

def scrape_remotive(role: str) -> list:
    jobs = []
    try:
        cat = REMOTIVE_CATEGORIES.get(role, "software-dev")
        res = requests.get(REMOTIVE_API.format(category=cat), timeout=12,
                           headers={"User-Agent": "BaalebosBot/2.0"})
        if res.status_code != 200:
            return jobs
        for job in res.json().get("jobs", [])[:12]:
            title = job.get("title", "").strip()
            url   = job.get("url", "").strip()
            if not title or not url:
                continue
            desc = _clean(job.get("description", ""))
            sal  = _salary(job.get("salary") or "") or _salary(desc)
            jobs.append({
                "title": title, "company": job.get("company_name", "").strip(),
                "location": job.get("candidate_required_location", "Worldwide"),
                "description": desc, "url": url,
                "source": "Remotive", "category": role, "salary_range": sal,
            })
    except Exception as e:
        logger.warning(f"[Remotive] {role}: {e}")
    return jobs


# ─── Source 2: Jobicy RSS ─────────────────────────────────────────────────────

def scrape_jobicy(role: str) -> list:
    jobs = []
    try:
        url = JOBICY_RSS.format(role=role.replace(" ", "+"))
        res = requests.get(url, timeout=12, headers={"User-Agent": "BaalebosBot/2.0"})
        if res.status_code != 200:
            return jobs
        root = ET.fromstring(res.content)
        channel = root.find("channel")
        if not channel:
            return jobs
        for item in channel.findall("item")[:12]:
            title = item.findtext("title", "").strip()
            link  = item.findtext("link", "").strip()
            if not title or not link:
                continue
            desc = _clean(item.findtext("description", ""))
            company  = item.findtext("{https://jobicy.com}company", "").strip()
            location = item.findtext("{https://jobicy.com}jobLocation", "Worldwide").strip()
            jobs.append({
                "title": title, "company": company, "location": location,
                "description": desc, "url": link,
                "source": "Jobicy", "category": role,
                "salary_range": _salary(desc),
            })
    except Exception as e:
        logger.warning(f"[Jobicy] {role}: {e}")
    return jobs


# ─── Source 3: Arbeitnow (EU + Global) ───────────────────────────────────────

def scrape_arbeitnow() -> list:
    """Arbeitnow covers EU, Africa, Asia, Americas — no API key needed."""
    jobs = []
    try:
        res = requests.get(ARBEITNOW_API, timeout=12,
                           headers={"User-Agent": "BaalebosBot/2.0"})
        if res.status_code != 200:
            return jobs
        for job in res.json().get("data", [])[:40]:
            title = job.get("title", "").strip()
            slug  = job.get("slug", "")
            if not title or not slug:
                continue
            url  = f"https://www.arbeitnow.com/jobs/{slug}"
            desc = _clean(job.get("description", ""))
            tags = job.get("tags", [])
            # Map tags to category
            cat = "Software Engineer"
            for tag in tags:
                t = tag.lower()
                if "devops" in t or "cloud" in t: cat = "DevOps Engineer"; break
                if "data" in t: cat = "Data Engineer"; break
                if "frontend" in t or "react" in t: cat = "Frontend Developer"; break
                if "backend" in t or "python" in t: cat = "Backend Engineer"; break
                if "mobile" in t: cat = "Mobile Developer"; break
                if "machine" in t or "ml" in t or "ai" in t: cat = "Machine Learning Engineer"; break
            jobs.append({
                "title": title,
                "company": job.get("company_name", "").strip(),
                "location": job.get("location", "Europe / Remote"),
                "description": desc,
                "url": url,
                "source": "Arbeitnow",
                "category": cat,
                "salary_range": None,
            })
    except Exception as e:
        logger.warning(f"[Arbeitnow] {e}")
    return jobs


# ─── DB Saver ─────────────────────────────────────────────────────────────────

def save_jobs_to_db(jobs: list, db: Session) -> int:
    saved = 0
    now = datetime.utcnow()
    for jd in jobs:
        try:
            existing = db.query(Job).filter(Job.url == jd["url"]).first()
            if existing:
                # Refresh scraped_at so it stays within freshness window
                existing.scraped_at = now
                continue
            db.add(Job(
                title=jd["title"], company=jd["company"],
                location=jd["location"], description=jd.get("description"),
                url=jd["url"], source=jd["source"],
                category=jd["category"], salary_range=jd.get("salary_range"),
                scraped_at=now,
                work_type=jd.get("work_type") or _work_type(
                    jd.get("location", ""), jd.get("title", ""), jd.get("description", "")
                ),
            ))
            saved += 1
        except Exception as e:
            logger.warning(f"[DB] '{jd.get('title')}': {e}")
            db.rollback()
    if saved > 0 or True:  # always commit to update scraped_at
        db.commit()
    return saved


# ─── Source 4: Remotive Search — Africa / Nigeria / Global South ────────────────

AFRICA_SEARCH_TERMS = [
    "nigeria", "africa", "ghana", "kenya", "south africa",
    "remote africa", "worldwide", "anywhere",
]

def scrape_remotive_search(query: str) -> list:
    """Search Remotive by keyword — returns jobs open to that region."""
    jobs = []
    try:
        url = REMOTIVE_SEARCH.format(query=requests.utils.quote(query))
        res = requests.get(url, timeout=12, headers={"User-Agent": "BaalebosBot/2.0"})
        if res.status_code != 200:
            return jobs
        for job in res.json().get("jobs", []):
            title = job.get("title", "").strip()
            jurl  = job.get("url", "").strip()
            if not title or not jurl:
                continue
            desc = _clean(job.get("description", ""))
            sal  = _salary(job.get("salary") or "") or _salary(desc)
            location = job.get("candidate_required_location", "Worldwide")
            # Tag Nigeria-targeted jobs explicitly
            if query.lower() in ("nigeria", "africa", "remote africa"):
                location = f"{location} (Open to Nigeria/Africa)"
            jobs.append({
                "title": title,
                "company": job.get("company_name", "").strip(),
                "location": location,
                "description": desc, "url": jurl,
                "source": "Remotive",
                "category": _guess_category(title),
                "salary_range": sal,
            })
    except Exception as e:
        logger.warning(f"[Remotive Search '{query}'] {e}")
    return jobs


def _guess_category(title: str) -> str:
    t = title.lower()
    if any(k in t for k in ["devops", "cloud", "aws", "azure", "gcp", "infrastructure", "sre"]):
        return "DevOps Engineer"
    if any(k in t for k in ["frontend", "react", "vue", "angular", "ui ", "ux"]):
        return "Frontend Developer"
    if any(k in t for k in ["backend", "python", "django", "fastapi", "node", "java ", "golang", "rails"]):
        return "Backend Engineer"
    if any(k in t for k in ["fullstack", "full stack", "full-stack"]):
        return "Fullstack Developer"
    if any(k in t for k in ["data engineer", "data pipeline", "etl", "spark"]):
        return "Data Engineer"
    if any(k in t for k in ["data scientist", "machine learning", "ml ", "ai ", "nlp"]):
        return "Machine Learning Engineer"
    if any(k in t for k in ["mobile", "android", "ios", "flutter", "react native"]):
        return "Mobile Developer"
    if any(k in t for k in ["security", "cyber", "penetration", "soc "]):
        return "Cybersecurity"
    if any(k in t for k in ["product manager", "product owner"]):
        return "Product Manager"
    if any(k in t for k in ["qa", "quality assurance", "tester"]):
        return "QA Engineer"
    return "Software Engineer"


# ─── Main Entry ───────────────────────────────────────────────────────────────

def scrape_global_jobs() -> dict:
    db = SessionLocal()
    total_scraped = total_saved = 0
    try:
        # Africa / Nigeria targeted searches
        for term in AFRICA_SEARCH_TERMS:
            jobs = scrape_remotive_search(term)
            total_scraped += len(jobs)
            saved = save_jobs_to_db(jobs, db)
            total_saved += saved
            logger.info(f"[Remotive Search '{term}'] {len(jobs)} scraped, {saved} new")

        # Arbeitnow — EU + global
        arbeitnow_jobs = scrape_arbeitnow()
        total_scraped += len(arbeitnow_jobs)
        total_saved += save_jobs_to_db(arbeitnow_jobs, db)
        logger.info(f"[Arbeitnow] {len(arbeitnow_jobs)} scraped")

        # Remotive + Jobicy per role
        for role in TECH_ROLES:
            all_jobs = scrape_remotive(role) + scrape_jobicy(role)
            total_scraped += len(all_jobs)
            saved = save_jobs_to_db(all_jobs, db)
            total_saved += saved
            logger.info(f"[Scraper] {role}: {len(all_jobs)} found, {saved} new")

    except Exception as e:
        logger.error(f"[Scraper] Fatal: {e}", exc_info=True)
    finally:
        db.close()

    summary = {
        "total_scraped": total_scraped,
        "total_saved": total_saved,
        "timestamp": datetime.utcnow().isoformat()
    }
    logger.info(f"[Scraper] Done: {summary}")
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(scrape_global_jobs())
