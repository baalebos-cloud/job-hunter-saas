import re
import asyncio
import logging
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from threading import local
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy.orm import Session

from backend.app.database import SessionLocal
from backend.app.models.job import Job
from backend.app.models.user import User, OutreachMessage  # noqa
from backend.app.models.resume import Resume               # noqa
from backend.app.models.application import Application     # noqa

logger = logging.getLogger(__name__)


_source_context = local()


def _source_error(exc):
    metrics = getattr(_source_context, "metrics", None)
    if metrics is not None:
        metrics["errors"] += 1


def _source_get(*args, **kwargs):
    """Record request outcomes without storing credential-bearing URLs/bodies."""
    metrics = getattr(_source_context, "metrics", None)
    if metrics is not None:
        metrics["requests"] += 1
    try:
        response = requests.get(*args, **kwargs)
    except Exception:
        if metrics is not None:
            metrics["failed_requests"] += 1
        raise
    if metrics is not None and response.status_code != 200:
        metrics["failed_requests"] += 1
    return response


def _observe_source(name, fn):
    metrics = {"requests": 0, "failed_requests": 0, "errors": 0}
    _source_context.metrics = metrics
    try:
        jobs = fn()
    except Exception as exc:
        _source_error(exc)
        jobs = []
    finally:
        _source_context.metrics = None
    issues = metrics["failed_requests"] or metrics["errors"]
    status = "success" if jobs else "empty"
    if issues:
        status = "partial" if jobs or (metrics["requests"] > metrics["failed_requests"] and not metrics["errors"]) else "failed"
    return jobs, {"name": name, "status": status, "job_count": len(jobs), **metrics}


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
THEMUSE_API     = "https://www.themuse.com/api/public/jobs?page={page}&descending=true&api_key=public"
GREENHOUSE_API  = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true"
LEVER_API       = "https://api.lever.co/v0/postings/{company}?mode=json&limit=10"
WEWORKREMOTELY_RSS = "https://weworkremotely.com/categories/remote-{category}-jobs.rss"
JOBSPRESSO_RSS    = "https://jobspresso.co/feed/"
AUTHENTICJOBS_RSS = "https://authenticjobs.com/feed/"

# ── NEW SOURCE URLS ───────────────────────────────────────────────────────────

# Source 10: Skillsire — AI/tech job board with RSS feed
SKILLSIRE_RSS = "https://skillsire.com/jobs/feed/"

# Source 11: Micro1 — AI-vetted remote jobs, has JSON API
MICRO1_API = "https://jobs.micro1.ai/api/jobs?limit=50&page=1"
MICRO1_RSS = "https://jobs.micro1.ai/feed"

# Source 12: Amazon Jobs — public JSON API (no auth needed)
AMAZON_JOBS_API = (
    "https://www.amazon.jobs/en/search.json"
    "?base_query={role}&category=software-development"
    "&result_limit=10&country={country}&radius=25km"
)
AMAZON_COUNTRIES = ["us", "gb", "ie", "de", "in", "ca", "au", "sg", "jp", "nl"]
AMAZON_ROLES = [
    "Software Engineer", "DevOps Engineer", "Cloud Engineer",
    "Data Engineer", "Machine Learning Engineer", "Backend Engineer",
    "Frontend Developer", "Data Scientist", "Security Engineer",
]

# Source 13: Remoteok — popular remote job board with public API
REMOTEOK_API = "https://remoteok.com/api"

# Source 14: Jobstash — aggregator focused on Web3, AI, fintech
JOBSTASH_API = "https://api.jobstash.xyz/jobs/list?page=1&limit=50"

# Source 15: EuroJobs Tech — EU-focused tech jobs
EUREMOTEJOBS_RSS = "https://euremotejobs.com/feed/"

GREENHOUSE_COMPANIES = [
    "airbnb", "stripe", "notion", "figma", "linear", "vercel", "supabase",
    "hashicorp", "datadog", "mongodb", "elastic", "cloudflare", "digitalocean",
    "gitlab", "github", "atlassian", "shopify", "twilio", "sendgrid",
]
LEVER_COMPANIES = [
    "netflix", "lyft", "reddit", "discord", "canva", "plaid", "brex",
    "robinhood", "coinbase", "openai", "anthropic", "scale-ai",
]

ADZUNA_APP_ID  = ""
ADZUNA_APP_KEY = ""
ADZUNA_COUNTRIES = {
    "us": "United States", "gb": "United Kingdom", "ca": "Canada",
    "au": "Australia", "de": "Germany", "fr": "France", "nl": "Netherlands",
    "sg": "Singapore", "za": "South Africa", "in": "India",
}
ADZUNA_API = (
    "https://api.adzuna.com/v1/api/jobs/{country}/search/1"
    "?results_per_page=20&what={role}&content-type=application/json"
    "&app_id={app_id}&app_key={app_key}"
)
ADZUNA_API_ANON = (
    "https://api.adzuna.com/v1/api/jobs/{country}/search/1"
    "?results_per_page=10&what={role}&content-type=application/json"
)

SEARCH_TERMS = [
    "nigeria", "ghana", "kenya", "south africa", "egypt", "ethiopia",
    "tanzania", "uganda", "rwanda", "senegal", "ivory coast", "cameroon",
    "zimbabwe", "zambia", "botswana", "namibia", "mozambique", "angola",
    "tunisia", "morocco", "algeria",
    "united states", "canada", "brazil", "mexico", "argentina", "colombia",
    "chile", "peru", "uruguay", "costa rica",
    "united kingdom", "germany", "france", "netherlands", "spain", "italy",
    "portugal", "sweden", "norway", "denmark", "finland", "switzerland",
    "austria", "belgium", "poland", "czech republic", "romania", "ukraine",
    "ireland", "greece",
    "india", "singapore", "philippines", "indonesia", "malaysia", "vietnam",
    "thailand", "pakistan", "bangladesh", "sri lanka",
    "south korea", "japan", "taiwan", "hong kong",
    "united arab emirates", "saudi arabia", "qatar", "kuwait", "jordan",
    "australia", "new zealand",
    "worldwide", "anywhere", "global", "remote",
]

WWR_CATEGORIES = {
    "Software Engineer": "programming", "Frontend Developer": "programming",
    "Backend Engineer": "programming", "DevOps Engineer": "devops-sysadmin",
    "Data Scientist": "data-science", "Product Manager": "product",
    "Mobile Developer": "programming", "QA Engineer": "qa",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clean(html: str, limit=None) -> str:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html or '', 'html.parser')
    for element in soup(['script','style']): element.decompose()
    for element in soup.find_all('li'): element.insert_before('- ')
    for element in soup.find_all(['p','li','div','h1','h2','h3','h4','br']): element.insert_after('\n')
    lines = [re.sub(r'[ \t]+',' ',line).strip() for line in soup.get_text().splitlines()]
    return '\n'.join(line for line in lines if line)


def _work_type(location: str, title: str, description: str) -> str:
    combined = f"{location} {title} {description}".lower()
    if any(k in combined for k in ["hybrid", "partially remote"]):
        return "hybrid"
    if any(k in combined for k in ["on-site", "onsite", "in-office", "in office", "on site"]):
        return "onsite"
    if any(k in combined for k in ["remote", "work from home", "wfh", "distributed", "worldwide", "anywhere"]):
        return "remote"
    if location and not any(k in location.lower() for k in ["remote", "worldwide", "global", "anywhere"]):
        return "onsite"
    return "unknown"


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


# ── Existing Sources ──────────────────────────────────────────────────────────

def scrape_remotive(role: str) -> list:
    jobs = []
    try:
        cat = REMOTIVE_CATEGORIES.get(role, "software-dev")
        res = _source_get(REMOTIVE_API.format(category=cat), timeout=12, headers=HEADERS)
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
        _source_error(e)
        logger.warning(f"[Remotive] {role}: {type(e).__name__}")
    return jobs


def scrape_remotive_search(query: str) -> list:
    jobs = []
    try:
        url = REMOTIVE_SEARCH.format(query=requests.utils.quote(query))
        res = _source_get(url, timeout=12, headers=HEADERS)
        if res.status_code != 200:
            return jobs
        for job in res.json().get("jobs", []):
            title = job.get("title", "").strip()
            jurl  = job.get("url", "").strip()
            if not title or not jurl:
                continue
            desc = _clean(job.get("description", ""))
            sal  = _salary(job.get("salary") or "") or _salary(desc)
            jobs.append({
                "title": title, "company": job.get("company_name", "").strip(),
                "location": job.get("candidate_required_location", "Worldwide"),
                "description": desc, "url": jurl,
                "source": "Remotive", "category": _guess_category(title),
                "salary_range": sal,
            })
    except Exception as e:
        _source_error(e)
        logger.warning(f"[Remotive Search '{query}'] {type(e).__name__}")
    return jobs


def scrape_jobicy(role: str) -> list:
    jobs = []
    try:
        url = JOBICY_RSS.format(role=role.replace(" ", "+"))
        res = _source_get(url, timeout=12, headers=HEADERS)
        if res.status_code != 200:
            return jobs
        root    = ET.fromstring(res.content)
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
        _source_error(e)
        logger.warning(f"[Jobicy] {role}: {type(e).__name__}")
    return jobs


def scrape_arbeitnow() -> list:
    jobs = []
    try:
        res = _source_get(ARBEITNOW_API, timeout=12, headers=HEADERS)
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
                "source": "Arbeitnow", "category": _guess_category(title),
                "salary_range": None,
            })
    except Exception as e:
        _source_error(e)
        logger.warning(f"[Arbeitnow] {type(e).__name__}")
    return jobs


def scrape_weworkremotely() -> list:
    jobs = []
    categories = ["programming", "devops-sysadmin", "data-science", "product", "qa"]
    for cat in categories:
        try:
            url = WEWORKREMOTELY_RSS.format(category=cat)
            res = _source_get(url, timeout=12, headers=HEADERS)
            if res.status_code != 200:
                continue
            root    = ET.fromstring(res.content)
            channel = root.find("channel")
            if not channel:
                continue
            for item in channel.findall("item")[:10]:
                title = item.findtext("title", "").strip()
                link  = item.findtext("link", "").strip()
                if not title or not link:
                    continue
                if ": " in title:
                    company, title = title.split(": ", 1)
                else:
                    company = ""
                desc   = _clean(item.findtext("description", ""))
                region = item.findtext("region", "USA / Remote").strip() if item.findtext("region") else "USA / Remote"
                jobs.append({
                    "title": title.strip(), "company": company.strip(),
                    "location": region, "description": desc, "url": link,
                    "source": "WeWorkRemotely", "category": _guess_category(title),
                    "salary_range": _salary(desc),
                })
        except Exception as e:
            _source_error(e)
            logger.warning(f"[WWR] {cat}: {type(e).__name__}")
    return jobs


def scrape_greenhouse() -> list:
    jobs = []
    for company in GREENHOUSE_COMPANIES:
        try:
            res = _source_get(GREENHOUSE_API.format(company=company), timeout=10, headers=HEADERS)
            if res.status_code != 200:
                continue
            for job in res.json().get("jobs", [])[:5]:
                title = job.get("title", "").strip()
                url   = job.get("absolute_url", "").strip()
                if not title or not url:
                    continue
                raw_loc  = job.get("location", {})
                if isinstance(raw_loc, dict):
                    location = raw_loc.get("name", "USA")
                elif isinstance(raw_loc, str) and raw_loc.strip():
                    location = raw_loc.strip()
                else:
                    location = "USA"
                desc = _clean(job.get("content", ""))
                jobs.append({
                    "title": title,
                    "company": company.replace("-", " ").title(),
                    "location": location, "description": desc, "url": url,
                    "source": "Greenhouse", "category": _guess_category(title),
                    "salary_range": _salary(desc),
                })
        except Exception as e:
            _source_error(e)
            logger.warning(f"[Greenhouse] {company}: {type(e).__name__}")
    return jobs


def scrape_lever() -> list:
    jobs = []
    for company in LEVER_COMPANIES:
        try:
            res = _source_get(LEVER_API.format(company=company), timeout=10, headers=HEADERS)
            if res.status_code != 200:
                continue
            data = res.json()
            if not isinstance(data, list):
                continue
            for job in data[:5]:
                title = job.get("text", "").strip()
                url   = job.get("hostedUrl", "").strip()
                if not title or not url:
                    continue
                cats     = job.get("categories", {})
                location = cats.get("location", "USA") if isinstance(cats, dict) else "USA"
                desc     = _clean(job.get("descriptionPlain", "") or job.get("description", ""))
                jobs.append({
                    "title": title,
                    "company": company.replace("-", " ").title(),
                    "location": location, "description": desc, "url": url,
                    "source": "Lever", "category": _guess_category(title),
                    "salary_range": _salary(desc),
                })
        except Exception as e:
            _source_error(e)
            logger.warning(f"[Lever] {company}: {type(e).__name__}")
    return jobs


def scrape_themuse() -> list:
    jobs = []
    try:
        res = _source_get(THEMUSE_API.format(page=0), timeout=12, headers=HEADERS)
        if res.status_code != 200:
            return jobs
        for job in res.json().get("results", [])[:20]:
            title   = job.get("name", "").strip()
            url     = job.get("refs", {}).get("landing_page", "")
            company = job.get("company", {}).get("name", "") if isinstance(job.get("company"), dict) else ""
            locs    = job.get("locations", [])
            location = locs[0].get("name", "USA") if locs else "USA"
            desc    = _clean(job.get("contents", ""))
            if not title or not url:
                continue
            category = _guess_category(title)
            if category == "Software Engineer" and not any(
                k in title.lower() for k in ["engineer", "developer", "devops", "data", "cloud", "tech"]
            ):
                continue
            jobs.append({
                "title": title, "company": company,
                "location": location, "description": desc, "url": url,
                "source": "TheMuse", "category": category,
                "salary_range": _salary(desc),
            })
    except Exception as e:
        _source_error(e)
        logger.warning(f"[TheMuse] {type(e).__name__}")
    return jobs


def scrape_adzuna(role: str, countries: list | None = None) -> list:
    jobs     = []
    target   = countries or list(ADZUNA_COUNTRIES.keys())
    role_enc = requests.utils.quote(role)
    for country in target:
        try:
            if ADZUNA_APP_ID and ADZUNA_APP_KEY:
                url = ADZUNA_API.format(country=country, role=role_enc, app_id=ADZUNA_APP_ID, app_key=ADZUNA_APP_KEY)
            else:
                url = ADZUNA_API_ANON.format(country=country, role=role_enc)
            res = _source_get(url, timeout=12, headers=HEADERS)
            if res.status_code != 200:
                continue
            for job in res.json().get("results", []):
                title   = job.get("title", "").strip()
                jurl    = job.get("redirect_url", "").strip()
                if not title or not jurl:
                    continue
                company  = job.get("company", {}).get("display_name", "") if isinstance(job.get("company"), dict) else ""
                location = job.get("location", {}).get("display_name", ADZUNA_COUNTRIES.get(country, country)) if isinstance(job.get("location"), dict) else ADZUNA_COUNTRIES.get(country, country)
                desc     = _clean(job.get("description", ""))
                sal_min  = job.get("salary_min")
                sal_max  = job.get("salary_max")
                salary   = None
                if sal_min and sal_max:
                    currency = {"us": "$", "gb": "£", "ca": "C$", "au": "A$", "de": "€", "fr": "€", "nl": "€"}.get(country, "")
                    salary   = f"{currency}{int(sal_min):,} – {currency}{int(sal_max):,}"
                elif sal_min:
                    salary = f"{int(sal_min):,}"
                jobs.append({
                    "title": title, "company": company,
                    "location": location, "description": desc, "url": jurl,
                    "source": f"Adzuna-{country.upper()}", "category": _guess_category(title),
                    "salary_range": salary or _salary(desc),
                })
        except Exception as e:
            _source_error(e)
            logger.warning(f"[Adzuna] {country}/{role}: {type(e).__name__}")
    return jobs


# ── NEW Source 10: Skillsire ──────────────────────────────────────────────────
def scrape_skillsire() -> list:
    """
    Skillsire — AI & tech job board targeting emerging markets including Nigeria.
    Scrapes via RSS feed.
    """
    jobs = []
    try:
        res = _source_get(SKILLSIRE_RSS, timeout=12, headers=HEADERS)
        if res.status_code != 200:
            logger.warning(f"[Skillsire] HTTP {res.status_code}")
            return jobs
        root    = ET.fromstring(res.content)
        channel = root.find("channel")
        if not channel:
            return jobs
        for item in channel.findall("item")[:30]:
            title = item.findtext("title", "").strip()
            link  = item.findtext("link", "").strip()
            if not title or not link:
                continue
            desc     = _clean(item.findtext("description", ""))
            company  = item.findtext("{https://skillsire.com}company", "").strip() or ""
            location = item.findtext("{https://skillsire.com}location", "Remote").strip()
            jobs.append({
                "title": title, "company": company,
                "location": location, "description": desc, "url": link,
                "source": "Skillsire", "category": _guess_category(title),
                "salary_range": _salary(desc),
            })
    except Exception as e:
        _source_error(e)
        logger.warning(f"[Skillsire] {type(e).__name__}")
    return jobs


# ── NEW Source 11: Micro1 ─────────────────────────────────────────────────────
def scrape_micro1() -> list:
    """
    Micro1 — AI-vetted remote jobs platform. Engineers pass an AI interview
    to get matched to jobs. Has a JSON API and RSS feed.
    Targets: Worldwide remote, strong in AI/ML, DevOps, Backend.
    """
    jobs = []

    # Try JSON API first
    try:
        res = _source_get(MICRO1_API, timeout=12, headers={
            **HEADERS,
            "Accept": "application/json",
        })
        if res.status_code == 200:
            data = res.json()
            job_list = data if isinstance(data, list) else data.get("jobs", data.get("data", []))
            for job in job_list[:30]:
                title   = (job.get("title") or job.get("job_title") or "").strip()
                url     = (job.get("url") or job.get("apply_url") or job.get("link") or "").strip()
                if not title or not url:
                    continue
                company  = (job.get("company") or job.get("company_name") or "").strip()
                location = (job.get("location") or "Remote").strip()
                desc     = _clean(job.get("description") or job.get("summary") or "")
                salary   = _salary(job.get("salary") or job.get("compensation") or "") or _salary(desc)
                jobs.append({
                    "title": title, "company": company,
                    "location": location, "description": desc, "url": url,
                    "source": "Micro1", "category": _guess_category(title),
                    "salary_range": salary,
                })
            if jobs:
                return jobs
    except Exception as e:
        _source_error(e)
        logger.warning(f"[Micro1 API] {type(e).__name__}")

    # Fallback to RSS
    try:
        res = _source_get(MICRO1_RSS, timeout=12, headers=HEADERS)
        if res.status_code == 200:
            root    = ET.fromstring(res.content)
            channel = root.find("channel")
            if channel:
                for item in channel.findall("item")[:30]:
                    title = item.findtext("title", "").strip()
                    link  = item.findtext("link", "").strip()
                    if not title or not link:
                        continue
                    desc = _clean(item.findtext("description", ""))
                    jobs.append({
                        "title": title, "company": "",
                        "location": "Remote", "description": desc, "url": link,
                        "source": "Micro1", "category": _guess_category(title),
                        "salary_range": _salary(desc),
                    })
    except Exception as e:
        _source_error(e)
        logger.warning(f"[Micro1 RSS] {type(e).__name__}")

    return jobs


# ── NEW Source 12: Amazon Jobs ────────────────────────────────────────────────
def scrape_amazon_jobs() -> list:
    """
    Amazon Jobs — public JSON API, no auth needed.
    Covers 10 countries. Targets software, cloud, and data engineering roles.
    Amazon is one of the highest-paying employers globally.
    """
    jobs = []
    for role in AMAZON_ROLES:
        for country in AMAZON_COUNTRIES[:5]:  # US, UK, IE, DE, IN — top 5 for volume
            try:
                url = AMAZON_JOBS_API.format(
                    role=requests.utils.quote(role),
                    country=country
                )
                res = _source_get(url, timeout=15, headers={
                    **HEADERS,
                    "Accept": "application/json",
                    "Referer": "https://www.amazon.jobs/",
                })
                if res.status_code != 200:
                    continue
                data     = res.json()
                job_list = data.get("jobs", [])
                for job in job_list[:5]:
                    title = job.get("title", "").strip()
                    job_id = job.get("id_icims", "")
                    if not title or not job_id:
                        continue
                    url_slug = job.get("job_path", f"/en/jobs/{job_id}")
                    job_url  = f"https://www.amazon.jobs{url_slug}"
                    location = job.get("location", "").strip() or country.upper()
                    desc     = _clean(job.get("description", "") or job.get("basic_qualifications", ""))
                    jobs.append({
                        "title": title,
                        "company": "Amazon",
                        "location": location,
                        "description": desc,
                        "url": job_url,
                        "source": "Amazon Jobs",
                        "category": _guess_category(title),
                        "salary_range": None,  # Amazon rarely publishes salary
                    })
            except Exception as e:
                _source_error(e)
                logger.warning(f"[Amazon Jobs] {role}/{country}: {type(e).__name__}")
    return jobs


# ── NEW Source 13: Remote OK ──────────────────────────────────────────────────
def scrape_remoteok() -> list:
    """
    RemoteOK — one of the largest remote job boards.
    Public API with no auth. Returns tech jobs worldwide.
    """
    jobs = []
    try:
        res = _source_get(REMOTEOK_API, timeout=15, headers={
            **HEADERS,
            "Accept": "application/json",
        })
        if res.status_code != 200:
            return jobs
        data = res.json()
        # First item is a legal notice, skip it
        job_list = [j for j in data if isinstance(j, dict) and j.get("position")]
        for job in job_list[:50]:
            title   = job.get("position", "").strip()
            url     = job.get("url", "").strip()
            if not title or not url:
                continue
            company  = job.get("company", "").strip()
            location = job.get("location", "Worldwide").strip() or "Worldwide"
            desc     = _clean(job.get("description", ""))
            tags     = " ".join(job.get("tags", []))
            salary   = _salary(job.get("salary", "") or "") or _salary(desc)
            jobs.append({
                "title": title, "company": company,
                "location": location, "description": f"{desc} {tags}".strip(),
                "url": url, "source": "RemoteOK",
                "category": _guess_category(title),
                "salary_range": salary,
            })
    except Exception as e:
        _source_error(e)
        logger.warning(f"[RemoteOK] {type(e).__name__}")
    return jobs


# ── NEW Source 14: Jobstash (Web3 / AI / Fintech) ────────────────────────────
def scrape_jobstash() -> list:
    """
    Jobstash — aggregator focused on Web3, AI, and fintech startups.
    Strong for blockchain, DeFi, and AI engineer roles globally.
    """
    jobs = []
    try:
        res = _source_get(JOBSTASH_API, timeout=12, headers={
            **HEADERS,
            "Accept": "application/json",
        })
        if res.status_code != 200:
            return jobs
        data     = res.json()
        job_list = data if isinstance(data, list) else data.get("jobs", data.get("data", []))
        for job in job_list[:30]:
            title = (job.get("title") or job.get("role") or "").strip()
            url   = (job.get("url") or job.get("apply_url") or "").strip()
            if not title or not url:
                continue
            company  = (job.get("organization", {}).get("name") if isinstance(job.get("organization"), dict) else job.get("company") or "").strip()
            location = (job.get("location") or job.get("locationName") or "Remote").strip()
            desc     = _clean(job.get("summary") or job.get("description") or "")
            sal_min  = job.get("minimumSalary") or job.get("salary_min")
            sal_max  = job.get("maximumSalary") or job.get("salary_max")
            salary   = None
            if sal_min and sal_max:
                salary = f"${int(sal_min):,} – ${int(sal_max):,}"
            elif sal_min:
                salary = f"${int(sal_min):,}+"
            jobs.append({
                "title": title, "company": company,
                "location": location, "description": desc, "url": url,
                "source": "Jobstash", "category": _guess_category(title),
                "salary_range": salary or _salary(desc),
            })
    except Exception as e:
        _source_error(e)
        logger.warning(f"[Jobstash] {type(e).__name__}")
    return jobs


# ── DB Saver ──────────────────────────────────────────────────────────────────
def save_jobs_to_db(jobs: list, db: Session, save_stats=None) -> int:
    saved = 0
    now   = datetime.utcnow()
    save_stats = save_stats if save_stats is not None else {"db_errors": 0}
    for jd in jobs:
        try:
            if not jd.get("url") or not jd.get("title"):
                save_stats["db_errors"] += 1
                continue
            inserted = False
            # A malformed row must not roll back every previously saved row.
            with db.begin_nested():
                existing = db.query(Job).filter(Job.url == jd["url"]).first()
                if existing:
                    # Do not overwrite a employer-managed vacancy through a feed.
                    if existing.posted_by_hr:
                        continue
                    for field in ("title","company","location","description","salary_range","category"):
                        if jd.get(field) is not None: setattr(existing,field,jd[field])
                    existing.last_checked_at = now
                    existing.scraped_at = now
                    existing.is_active = True
                    existing.work_type = jd.get("work_type") or _work_type(jd.get("location",""),jd.get("title",""),jd.get("description",""))
                else:
                    db.add(Job(
                        title=jd["title"], company=jd.get("company", ""),
                        location=jd.get("location", ""), description=jd.get("description"),
                        url=jd["url"], source=jd.get("source", "Unknown"),
                        category=jd.get("category", "Software Engineer"), salary_range=jd.get("salary_range"),
                        scraped_at=now, last_checked_at=now, first_seen_at=now, is_active=True,
                        work_type=jd.get("work_type") or _work_type(
                            jd.get("location", ""), jd.get("title", ""), jd.get("description", "")
                        ),
                    ))
                    inserted = True
                db.flush()
            saved += int(inserted)
        except Exception as e:
            save_stats["db_errors"] += 1
            logger.warning("scraper_row_failed error_type=%s", type(e).__name__)

    if jobs:
        try:
            db.commit()
        except Exception as e:
            logger.error("scraper_commit_failed error_type=%s", type(e).__name__)
            save_stats["db_errors"] += 1
            db.rollback()
            return 0

    return saved


# ── Concurrent Executor ───────────────────────────────────────────────────────
def _run_sources_concurrent(source_fns: list, max_workers: int = 8, source_results=None) -> list:
    all_jobs = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_observe_source, name, fn): name for name, fn in source_fns}
        for future in as_completed(futures):
            name = futures[future]
            try:
                jobs, result = future.result()
                if source_results is not None:
                    source_results.append(result)
                all_jobs.extend(jobs)
                logger.info(f"[{name}] returned {len(jobs)} jobs")
            except Exception as e:
                logger.warning("scraper_source_failed name=%s error_type=%s", name, type(e).__name__)
                if source_results is not None:
                    source_results.append({"name": name, "status": "failed", "job_count": 0})
    return all_jobs


# ── Main Entry ────────────────────────────────────────────────────────────────
def scrape_global_jobs() -> dict:
    from backend.app.models.automation import ScrapeRun
    from backend.app.services.job_automation import run_tick
    db            = SessionLocal()
    total_scraped = 0
    total_saved   = 0
    source_results = []
    save_stats = {"db_errors": 0}
    fatal_error = False
    run = ScrapeRun(id=uuid.uuid4().hex, started_at=datetime.utcnow(), status="running", summary={})
    try:
        db.add(run)
        db.commit()  # A terminated process leaves a visible running heartbeat.
    except Exception:
        db.close()
        raise

    try:
        # ── Fixed sources (concurrent) ────────────────────────────────────────
        fixed_sources = [
            ("TheMuse",         scrape_themuse),
            ("WeWorkRemotely",  scrape_weworkremotely),
            ("Greenhouse",      scrape_greenhouse),
            ("Lever",           scrape_lever),
            ("Arbeitnow",       scrape_arbeitnow),
            # ── NEW fixed sources ─────────────────────────────────────────────
            ("Skillsire",       scrape_skillsire),   # AI/tech, emerging markets
            ("Micro1",          scrape_micro1),       # AI-vetted remote jobs
            ("Amazon Jobs",     scrape_amazon_jobs),  # Top-paying, global
            ("RemoteOK",        scrape_remoteok),     # Largest remote board
            ("Jobstash",        scrape_jobstash),     # Web3 / AI / fintech
        ]
        fixed_jobs = _run_sources_concurrent(fixed_sources, max_workers=10, source_results=source_results)
        total_scraped += len(fixed_jobs)
        total_saved   += save_jobs_to_db(fixed_jobs, db, save_stats)

        # ── Remotive regional searches (concurrent) ───────────────────────────
        search_fns = [
            (f"Remotive Search '{term}'", lambda t=term: scrape_remotive_search(t))
            for term in SEARCH_TERMS
        ]
        search_jobs = _run_sources_concurrent(search_fns, max_workers=10, source_results=source_results)
        total_scraped += len(search_jobs)
        total_saved   += save_jobs_to_db(search_jobs, db, save_stats)

        # ── Per-role scraping (concurrent) ────────────────────────────────────
        role_fns = []
        for role in TECH_ROLES:
            role_fns.append((f"Remotive:{role}", lambda r=role: scrape_remotive(r)))
            role_fns.append((f"Jobicy:{role}",   lambda r=role: scrape_jobicy(r)))
            role_fns.append((f"Adzuna:{role}",   lambda r=role: scrape_adzuna(r, ["us", "gb", "za", "ca"])))

        role_jobs = _run_sources_concurrent(role_fns, max_workers=12, source_results=source_results)
        total_scraped += len(role_jobs)
        total_saved   += save_jobs_to_db(role_jobs, db, save_stats)

    except Exception as e:
        fatal_error = True
        db.rollback()
        logger.error("scraper_run_failed error_type=%s", type(e).__name__)

    summary = {
        "total_scraped": total_scraped,
        "total_saved":   total_saved,
        "timestamp":     datetime.utcnow().isoformat(),
        "run_id":        run.id,
        "failed_sources": sum(result["status"] == "failed" for result in source_results),
        "partial_sources": sum(result["status"] == "partial" for result in source_results),
        "source_results": sorted(source_results, key=lambda result: result["name"]),
        **save_stats,
    }
    if fatal_error or (source_results and summary["failed_sources"] == len(source_results)):
        summary["status"] = "failed"
    elif summary["failed_sources"] or summary["partial_sources"] or save_stats["db_errors"]:
        summary["status"] = "partial"
    else:
        summary["status"] = "success" if total_scraped else "empty"
    try:
        run.status = summary["status"]
        run.finished_at = datetime.utcnow()
        run.summary = summary
        db.commit()
        run_tick(db)
    except Exception as e:
        db.rollback()
        logger.warning("scraper_automation_failed error_type=%s", type(e).__name__)
    finally:
        db.close()
    logger.info(f"[Scraper] Done: {summary}")
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(scrape_global_jobs())
