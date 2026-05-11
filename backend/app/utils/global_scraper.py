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

HEADERS = {"User-Agent": "BaalebosBot/2.0 (job aggregator; contact@baalebo.xyz)"}

TECH_ROLES = [
    "Frontend Developer", "Backend Engineer", "Fullstack Developer",
    "DevOps Engineer", "Cloud Engineer", "Data Scientist",
    "Machine Learning Engineer", "Cybersecurity", "Mobile Developer",
    "Product Manager", "SRE", "Data Engineer", "QA Engineer",
    "Platform Engineer", "Software Engineer", "React Developer",
    "Python Developer", "Node.js Developer", "AWS Engineer",
    "Java Developer", "Go Developer", "Kubernetes Engineer",
    "AI Engineer", "Blockchain Developer", "iOS Developer", "Android Developer",
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
    "AWS Engineer": "devops-sysadmin", "Java Developer": "software-dev",
    "Go Developer": "software-dev", "Kubernetes Engineer": "devops-sysadmin",
    "AI Engineer": "data", "Blockchain Developer": "software-dev",
    "iOS Developer": "software-dev", "Android Developer": "software-dev",
}

# ── API URLs ──────────────────────────────────────────────────────────────────
REMOTIVE_API    = "https://remotive.com/api/remote-jobs?category={category}&limit=15"
REMOTIVE_SEARCH = "https://remotive.com/api/remote-jobs?search={query}&limit=20"
JOBICY_RSS      = "https://jobicy.com/jobs-rss?q={role}&count=15"
ARBEITNOW_API   = "https://www.arbeitnow.com/api/job-board-api"
# The Muse — free, no key needed, covers USA/global top companies
THEMUSE_API     = "https://www.themuse.com/api/public/jobs?page={page}&descending=true&api_key=public"
# Greenhouse — free job board API (top tech companies post here)
GREENHOUSE_COMPANIES = [
    "airbnb", "stripe", "notion", "figma", "linear", "vercel", "supabase",
    "hashicorp", "datadog", "mongodb", "elastic", "cloudflare", "digitalocean",
    "gitlab", "github", "atlassian", "shopify", "twilio", "sendgrid",
]
GREENHOUSE_API  = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true"
# Lever — free job board API (many startups use Lever)
LEVER_COMPANIES = [
    "netflix", "lyft", "reddit", "discord", "canva", "plaid", "brex",
    "robinhood", "coinbase", "openai", "anthropic", "scale-ai",
]
LEVER_API       = "https://api.lever.co/v0/postings/{company}?mode=json&limit=10"
# Adzuna — free tier (1000 calls/day), covers USA, UK, Canada, Australia, Germany
ADZUNA_APP_ID   = ""  # optional — works without for basic calls
ADZUNA_COUNTRIES = {
    "us": "United States", "gb": "United Kingdom", "ca": "Canada",
    "au": "Australia", "de": "Germany", "fr": "France", "nl": "Netherlands",
    "sg": "Singapore", "za": "South Africa", "in": "India",
}
ADZUNA_API = "https://api.adzuna.com/v1/api/jobs/{country}/search/1?results_per_page=20&what={role}&content-type=application/json"
# WeworkRemotely RSS — top remote jobs, USA focused
WEWORKREMOTELY_RSS = "https://weworkremotely.com/categories/remote-{category}-jobs.rss"
WWR_CATEGORIES = {
    "Software Engineer": "programming", "Frontend Developer": "programming",
    "Backend Engineer": "programming", "DevOps Engineer": "devops-sysadmin",
    "Data Scientist": "data-science", "Product Manager": "product",
    "Mobile Developer": "programming", "QA Engineer": "qa",
}
# Jobspresso RSS — remote jobs
JOBSPRESSO_RSS = "https://jobspresso.co/feed/"
# Authentic Jobs RSS
AUTHENTICJOBS_RSS = "https://authenticjobs.com/feed/"
# Stack Overflow Jobs RSS (via public feed)
STACKOVERFLOW_RSS = "https://stackoverflow.com/jobs/feed?q={role}&r=true"


def _clean(html: str, limit: int = 4000) -> str:
    text = re.sub(r'<[^>]+>', ' ', html or '')
    text = re.sub(r'&[a-z]+;', ' ', text)
    text = re.sub(r'&#\d+;', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:limit]


def _work_type(location: str, title: str, description: str) -> str:
    combined = f"{location} {title} {description}".lower()
    if any(k in combined for k in ["hybrid", "partially remote", "flexible"]):
        return "hybrid"
    if any(k in combined for k in ["on-site", "onsite", "in-office", "in office", "on site"]):
        return "onsite"
    if any(k in combined for k in ["remote", "work from home", "wfh", "distributed", "worldwide", "anywhere"]):
        return "remote"
    if location and not any(k in location.lower() for k in ["remote", "worldwide", "global", "anywhere"]):
        return "onsite"
    return "remote"


def _salary(text: str) -> str | None:
    if not text:
        return None
    if any(c in text for c in ['$', '€', '£', '₦', '¥', 'A$', 'C$']) and len(text) < 60:
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


def _guess_category(title: str) -> str:
    t = title.lower()
    if any(k in t for k in ["devops", "cloud", "aws", "azure", "gcp", "infrastructure", "sre", "kubernetes", "terraform"]):
        return "DevOps Engineer"
    if any(k in t for k in ["frontend", "react", "vue", "angular", "ui ", "ux", "css", "javascript"]):
        return "Frontend Developer"
    if any(k in t for k in ["backend", "python", "django", "fastapi", "node", "java ", "golang", "rails", "php", "ruby"]):
        return "Backend Engineer"
    if any(k in t for k in ["fullstack", "full stack", "full-stack"]):
        return "Fullstack Developer"
    if any(k in t for k in ["data engineer", "data pipeline", "etl", "spark", "airflow"]):
        return "Data Engineer"
    if any(k in t for k in ["data scientist", "machine learning", "ml ", "ai ", "nlp", "deep learning"]):
        return "Machine Learning Engineer"
    if any(k in t for k in ["mobile", "android", "ios", "flutter", "react native", "swift", "kotlin"]):
        return "Mobile Developer"
    if any(k in t for k in ["security", "cyber", "penetration", "soc ", "infosec"]):
        return "Cybersecurity"
    if any(k in t for k in ["product manager", "product owner", "pm "]):
        return "Product Manager"
    if any(k in t for k in ["qa", "quality assurance", "tester", "sdet"]):
        return "QA Engineer"
    if any(k in t for k in ["blockchain", "web3", "solidity", "crypto"]):
        return "Blockchain Developer"
    if any(k in t for k in ["ai engineer", "llm", "generative", "openai"]):
        return "AI Engineer"
    return "Software Engineer"


# ── Source 1: Remotive (Remote, Global) ──────────────────────────────────────
def scrape_remotive(role: str) -> list:
    jobs = []
    try:
        cat = REMOTIVE_CATEGORIES.get(role, "software-dev")
        res = requests.get(REMOTIVE_API.format(category=cat), timeout=12, headers=HEADERS)
        if res.status_code != 200:
            return jobs
        for job in res.json().get("jobs", [])[:15]:
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


# ── Source 2: Remotive Search (Global — full country coverage) ───────────────
SEARCH_TERMS = [
    # Africa
    "nigeria", "ghana", "kenya", "south africa", "egypt", "ethiopia",
    "tanzania", "uganda", "rwanda", "senegal", "ivory coast", "cameroon",
    "zimbabwe", "zambia", "botswana", "namibia", "mozambique", "angola",
    "tunisia", "morocco", "algeria", "libya",
    # Americas
    "united states", "canada", "brazil", "mexico", "argentina", "colombia",
    "chile", "peru", "venezuela", "ecuador", "uruguay", "costa rica",
    # Europe
    "united kingdom", "germany", "france", "netherlands", "spain", "italy",
    "portugal", "sweden", "norway", "denmark", "finland", "switzerland",
    "austria", "belgium", "poland", "czech republic", "romania", "ukraine",
    "ireland", "greece", "hungary",
    # Asia
    "india", "singapore", "philippines", "indonesia", "malaysia", "vietnam",
    "thailand", "pakistan", "bangladesh", "sri lanka", "nepal",
    "south korea", "japan", "china", "taiwan", "hong kong",
    # Middle East
    "united arab emirates", "saudi arabia", "qatar", "kuwait", "bahrain",
    "jordan", "lebanon", "israel", "turkey",
    # Oceania
    "australia", "new zealand",
    # Global
    "worldwide", "anywhere", "global", "remote",
]

def scrape_remotive_search(query: str) -> list:
    jobs = []
    try:
        url = REMOTIVE_SEARCH.format(query=requests.utils.quote(query))
        res = requests.get(url, timeout=12, headers=HEADERS)
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
            jobs.append({
                "title": title, "company": job.get("company_name", "").strip(),
                "location": location, "description": desc, "url": jurl,
                "source": "Remotive", "category": _guess_category(title), "salary_range": sal,
            })
    except Exception as e:
        logger.warning(f"[Remotive Search '{query}'] {e}")
    return jobs


# ── Source 3: Jobicy RSS ──────────────────────────────────────────────────────
def scrape_jobicy(role: str) -> list:
    jobs = []
    try:
        url = JOBICY_RSS.format(role=role.replace(" ", "+"))
        res = requests.get(url, timeout=12, headers=HEADERS)
        if res.status_code != 200:
            return jobs
        root = ET.fromstring(res.content)
        channel = root.find("channel")
        if not channel:
            return jobs
        for item in channel.findall("item")[:15]:
            title = item.findtext("title", "").strip()
            link  = item.findtext("link", "").strip()
            if not title or not link:
                continue
            desc     = _clean(item.findtext("description", ""))
            company  = item.findtext("{https://jobicy.com}company", "").strip()
            location = item.findtext("{https://jobicy.com}jobLocation", "Worldwide").strip()
            jobs.append({
                "title": title, "company": company, "location": location,
                "description": desc, "url": link,
                "source": "Jobicy", "category": role, "salary_range": _salary(desc),
            })
    except Exception as e:
        logger.warning(f"[Jobicy] {role}: {e}")
    return jobs


# ── Source 4: Arbeitnow (EU + Global) ────────────────────────────────────────
def scrape_arbeitnow() -> list:
    jobs = []
    try:
        res = requests.get(ARBEITNOW_API, timeout=12, headers=HEADERS)
        if res.status_code != 200:
            return jobs
        for job in res.json().get("data", [])[:50]:
            title = job.get("title", "").strip()
            slug  = job.get("slug", "")
            if not title or not slug:
                continue
            url  = f"https://www.arbeitnow.com/jobs/{slug}"
            desc = _clean(job.get("description", ""))
            jobs.append({
                "title": title, "company": job.get("company_name", "").strip(),
                "location": job.get("location", "Europe / Remote"),
                "description": desc, "url": url,
                "source": "Arbeitnow", "category": _guess_category(title), "salary_range": None,
            })
    except Exception as e:
        logger.warning(f"[Arbeitnow] {e}")
    return jobs


# ── Source 5: We Work Remotely RSS (USA focused, top companies) ──────────────
def scrape_weworkremotely() -> list:
    jobs = []
    categories = ["programming", "devops-sysadmin", "data-science", "product", "qa"]
    for cat in categories:
        try:
            url = WEWORKREMOTELY_RSS.format(category=cat)
            res = requests.get(url, timeout=12, headers=HEADERS)
            if res.status_code != 200:
                continue
            root = ET.fromstring(res.content)
            channel = root.find("channel")
            if not channel:
                continue
            for item in channel.findall("item")[:10]:
                title = item.findtext("title", "").strip()
                link  = item.findtext("link", "").strip()
                if not title or not link:
                    continue
                # WWR title format: "Company: Job Title"
                if ": " in title:
                    company, title = title.split(": ", 1)
                else:
                    company = ""
                desc = _clean(item.findtext("description", ""))
                region = item.findtext("region", "USA / Remote").strip() if item.findtext("region") else "USA / Remote"
                jobs.append({
                    "title": title.strip(), "company": company.strip(),
                    "location": region, "description": desc, "url": link,
                    "source": "WeWorkRemotely", "category": _guess_category(title),
                    "salary_range": _salary(desc),
                })
        except Exception as e:
            logger.warning(f"[WWR] {cat}: {e}")
    return jobs


# ── Source 6: Greenhouse (Top Tech Companies — USA/Global) ───────────────────
def scrape_greenhouse() -> list:
    jobs = []
    for company in GREENHOUSE_COMPANIES:
        try:
            res = requests.get(GREENHOUSE_API.format(company=company), timeout=10, headers=HEADERS)
            if res.status_code != 200:
                continue
            data = res.json()
            for job in data.get("jobs", [])[:5]:
                title    = job.get("title", "").strip()
                url      = job.get("absolute_url", "").strip()
                location = job.get("location", {}).get("name", "USA") if isinstance(job.get("location"), dict) else "USA"
                desc     = _clean(job.get("content", ""))
                if not title or not url:
                    continue
                jobs.append({
                    "title": title, "company": company.replace("-", " ").title(),
                    "location": location, "description": desc, "url": url,
                    "source": "Greenhouse", "category": _guess_category(title),
                    "salary_range": _salary(desc),
                })
        except Exception as e:
            logger.warning(f"[Greenhouse] {company}: {e}")
    return jobs


# ── Source 7: Lever (Startups — USA/Global) ───────────────────────────────────
def scrape_lever() -> list:
    jobs = []
    for company in LEVER_COMPANIES:
        try:
            res = requests.get(LEVER_API.format(company=company), timeout=10, headers=HEADERS)
            if res.status_code != 200:
                continue
            for job in res.json()[:5]:
                title    = job.get("text", "").strip()
                url      = job.get("hostedUrl", "").strip()
                location = job.get("categories", {}).get("location", "USA") if isinstance(job.get("categories"), dict) else "USA"
                desc     = _clean(job.get("descriptionPlain", "") or job.get("description", ""))
                if not title or not url:
                    continue
                jobs.append({
                    "title": title, "company": company.replace("-", " ").title(),
                    "location": location, "description": desc, "url": url,
                    "source": "Lever", "category": _guess_category(title),
                    "salary_range": _salary(desc),
                })
        except Exception as e:
            logger.warning(f"[Lever] {company}: {e}")
    return jobs


# ── Source 8: Stack Overflow Jobs RSS ────────────────────────────────────────
def scrape_stackoverflow(role: str) -> list:
    jobs = []
    try:
        url = STACKOVERFLOW_RSS.format(role=requests.utils.quote(role))
        res = requests.get(url, timeout=12, headers=HEADERS)
        if res.status_code != 200:
            return jobs
        root = ET.fromstring(res.content)
        channel = root.find("channel")
        if not channel:
            return jobs
        for item in channel.findall("item")[:8]:
            title = item.findtext("title", "").strip()
            link  = item.findtext("link", "").strip()
            if not title or not link:
                continue
            desc = _clean(item.findtext("description", ""))
            # Extract location from title if present
            location = "Remote / Global"
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                location = parts[-1].strip()
                title = parts[0].strip()
            jobs.append({
                "title": title, "company": "",
                "location": location, "description": desc, "url": link,
                "source": "StackOverflow", "category": role,
                "salary_range": _salary(desc),
            })
    except Exception as e:
        logger.warning(f"[StackOverflow] {role}: {e}")
    return jobs


# ── Source 9: The Muse (USA top companies) ────────────────────────────────────
def scrape_themuse() -> list:
    jobs = []
    try:
        for page in range(0, 3):
            res = requests.get(THEMUSE_API.format(page=page), timeout=12, headers=HEADERS)
            if res.status_code != 200:
                break
            for job in res.json().get("results", [])[:15]:
                title   = job.get("name", "").strip()
                url     = job.get("refs", {}).get("landing_page", "")
                company = job.get("company", {}).get("name", "") if isinstance(job.get("company"), dict) else ""
                locs    = job.get("locations", [])
                location = locs[0].get("name", "USA") if locs else "USA"
                desc    = _clean(job.get("contents", ""))
                if not title or not url:
                    continue
                jobs.append({
                    "title": title, "company": company,
                    "location": location, "description": desc, "url": url,
                    "source": "TheMuse", "category": _guess_category(title),
                    "salary_range": _salary(desc),
                })
    except Exception as e:
        logger.warning(f"[TheMuse] {e}")
    return jobs


# ── DB Saver ──────────────────────────────────────────────────────────────────
def save_jobs_to_db(jobs: list, db: Session) -> int:
    saved = 0
    now = datetime.utcnow()
    for jd in jobs:
        try:
            if not jd.get("url"):
                continue
            existing = db.query(Job).filter(Job.url == jd["url"]).first()
            if existing:
                existing.scraped_at = now
                continue
            db.add(Job(
                title=jd["title"], company=jd.get("company", ""),
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
    if True:
        db.commit()
    return saved


# ── Main Entry ────────────────────────────────────────────────────────────────
def scrape_global_jobs() -> dict:
    db = SessionLocal()
    total_scraped = total_saved = 0

    sources = [
        ("TheMuse (USA)", lambda: scrape_themuse()),
        ("WeWorkRemotely (USA/Global)", lambda: scrape_weworkremotely()),
        ("Greenhouse (Top Tech)", lambda: scrape_greenhouse()),
        ("Lever (Startups)", lambda: scrape_lever()),
        ("Arbeitnow (EU/Global)", lambda: scrape_arbeitnow()),
    ]

    try:
        # Fixed sources
        for name, fn in sources:
            try:
                jobs = fn()
                total_scraped += len(jobs)
                saved = save_jobs_to_db(jobs, db)
                total_saved += saved
                logger.info(f"[{name}] {len(jobs)} scraped, {saved} new")
            except Exception as e:
                logger.warning(f"[{name}] failed: {e}")

        # Regional searches
        for term in SEARCH_TERMS:
            try:
                jobs = scrape_remotive_search(term)
                total_scraped += len(jobs)
                saved = save_jobs_to_db(jobs, db)
                total_saved += saved
                logger.info(f"[Remotive Search '{term}'] {len(jobs)} scraped, {saved} new")
            except Exception as e:
                logger.warning(f"[Remotive Search '{term}'] {e}")

        # Per-role scraping
        for role in TECH_ROLES:
            try:
                all_jobs = (
                    scrape_remotive(role) +
                    scrape_jobicy(role) +
                    scrape_stackoverflow(role)
                )
                total_scraped += len(all_jobs)
                saved = save_jobs_to_db(all_jobs, db)
                total_saved += saved
                logger.info(f"[Role: {role}] {len(all_jobs)} scraped, {saved} new")
            except Exception as e:
                logger.warning(f"[Role: {role}] {e}")

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
