"""Job aggregation for the Baalebos job board.

Sources (all public, no scraping of HTML pages):
  * Employer career boards: Greenhouse, Ashby and Lever company boards
  * Remote job boards: Himalayas, Remotive, We Work Remotely, RemoteOK,
    Jobicy, Working Nomads, Arbeitnow
  * Adzuna, only when ADZUNA_APP_ID / ADZUNA_APP_KEY are set

Every run keeps only technology roles posted in the last MAX_AGE_DAYS, stores
one listing per role (the same job on several boards is saved once, preferring
the employer's own board), and expires listings that disappear from their
source. Employer-posted jobs on Baalebos are never touched by the scraper.
"""
from __future__ import annotations

import html
import logging
import os
import re
import uuid
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from threading import local

import requests
from sqlalchemy.orm import Session

from backend.app.database import SessionLocal
from backend.app.models.job import Job
from backend.app.models.user import User, OutreachMessage  # noqa: F401  (mapper registration)
from backend.app.models.resume import Resume               # noqa: F401
from backend.app.models.application import Application     # noqa: F401

logger = logging.getLogger(__name__)

MAX_AGE_DAYS = 30            # older postings are not imported and are expired
UNSEEN_DAYS = 3              # a listing not returned by its source for this long is closed
PURGE_AFTER_DAYS = 60        # closed scraped listings without applications are deleted
PER_COMPANY_LIMIT = 40       # keeps one large employer from filling the board
HEADERS = {"User-Agent": "BaalebosBot/3.0 (job aggregator; support@baalebo.xyz)"}

GREENHOUSE_BOARDS = [
    "cloudflare", "gitlab", "datadog", "mongodb", "stripe", "airbnb", "figma", "discord", "robinhood",
    "coinbase", "dropbox", "pinterest", "reddit", "twilio", "elastic", "okta", "databricks", "asana",
    "instacart", "lyft", "squarespace", "grafanalabs", "vercel", "samsara", "affirm", "brex", "chime",
    "gusto", "flexport", "scaleai", "anthropic", "duolingo", "cockroachlabs", "fivetran", "airtable",
    "canonical",
]
ASHBY_BOARDS = ["ramp", "notion", "linear", "openai", "vanta", "replit", "supabase", "posthog", "cohere",
                "perplexity", "zapier", "clickup", "hex", "modal", "runway"]
LEVER_BOARDS = ["spotify", "palantir", "jumpcloud", "outreach", "binance"]
# Ashby and Lever return no company name; display names for the board IDs above.
COMPANY_NAMES = {"openai": "OpenAI", "posthog": "PostHog", "clickup": "ClickUp", "hex": "Hex", "modal": "Modal",
                 "runway": "Runway", "ramp": "Ramp", "notion": "Notion", "linear": "Linear", "vanta": "Vanta",
                 "replit": "Replit", "supabase": "Supabase", "cohere": "Cohere", "perplexity": "Perplexity",
                 "zapier": "Zapier", "spotify": "Spotify", "palantir": "Palantir", "jumpcloud": "JumpCloud",
                 "outreach": "Outreach", "binance": "Binance"}
REMOTIVE_CATEGORIES = ["software-dev", "devops", "data", "qa", "product", "design"]
WWR_CATEGORIES = ["programming", "devops-sysadmin", "full-stack-programming", "back-end-programming",
                  "front-end-programming", "design", "product"]

# ── Monitoring (per-source request counts; never stores URLs or bodies) ─────
_source_context = local()


def _source_error(exc):
    metrics = getattr(_source_context, "metrics", None)
    if metrics is not None:
        metrics["errors"] += 1


def _source_get(*args, **kwargs):
    metrics = getattr(_source_context, "metrics", None)
    if metrics is not None:
        metrics["requests"] += 1
    kwargs.setdefault("headers", HEADERS)
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


def _parallel(items, fn, workers=8):
    """Run fn over items in threads while counting requests on the caller's source."""
    metrics = getattr(_source_context, "metrics", None)

    def run(item):
        _source_context.metrics = metrics
        try:
            return fn(item)
        except Exception as exc:
            _source_error(exc)
            logger.warning("scraper_board_failed board=%s error_type=%s", item, type(exc).__name__)
            return []
        finally:
            _source_context.metrics = None
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return [job for batch in pool.map(run, items) for job in batch]


# ── Text helpers ─────────────────────────────────────────────────────────────

def _clean(html_text: str, limit=None) -> str:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_text or '', 'html.parser')
    for element in soup(['script', 'style']):
        element.decompose()
    for element in soup.find_all('li'):
        element.insert_before('- ')
    for element in soup.find_all(['p', 'li', 'div', 'h1', 'h2', 'h3', 'h4', 'br']):
        element.insert_after('\n')
    lines = [re.sub(r'[ \t\xa0]+', ' ', line).strip() for line in soup.get_text().splitlines()]
    text = '\n'.join(line for line in lines if line)
    return text[:limit] if limit else text


def _work_type(location: str, title: str, description: str) -> str:
    # The location field is the most reliable signal; the description often
    # mentions several arrangements ("hybrid or remote"), so it comes last.
    for text in (f"{location} {title}".lower(),):
        if any(k in text for k in ["hybrid", "partially remote"]):
            return "hybrid"
        if any(k in text for k in ["remote", "work from home", "anywhere", "worldwide"]):
            return "remote"
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
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(0).strip()
    return None


_CURRENCY = {'USD': '$', 'EUR': '€', 'GBP': '£', 'NGN': '₦', 'CAD': 'C$', 'AUD': 'A$'}


def _money_range(low, high, currency='USD', period=None) -> str | None:
    def num(v):
        try:
            return float(str(v).replace(',', ''))
        except (TypeError, ValueError):
            return 0.0
    low, high = num(low), num(high)
    if not low and not high:
        return None
    symbol = _CURRENCY.get((currency or 'USD').upper(), f"{currency} " if currency else '$')
    fmt = (lambda v: f"{symbol}{v:,.0f}") if (period or '').lower().startswith('hour') or max(low, high) < 1000 \
        else (lambda v: f"{symbol}{v / 1000:,.0f}k")
    text = f"{fmt(low)}–{fmt(high)}" if low and high and low != high else fmt(low or high)
    if (period or '').lower().startswith('hour') or max(low, high) < 1000:
        return f"{text} / hour"
    return f"{text} / year"


def _guess_category(title: str) -> str:
    t = f" {title.lower()} "
    rules = [
        ("DevOps Engineer", ["devops", "cloud", "aws", "azure", "gcp", "infrastructure", " sre", "site reliability",
                             "kubernetes", "platform engineer", "terraform"]),
        ("Cybersecurity", ["security", "cyber", "penetration", " soc ", "infosec"]),
        ("Data Engineer", ["data engineer", "data pipeline", "etl", "analytics engineer", "data platform"]),
        ("Machine Learning Engineer", ["machine learning", " ml ", " ai ", "llm", "data scientist", "research engineer",
                                       "research scientist", "deep learning", "nlp", "computer vision"]),
        ("Mobile Developer", ["mobile", "android", " ios", "flutter", "react native", "swift", "kotlin"]),
        ("QA Engineer", [" qa", "quality assurance", "tester", "sdet", "test automation"]),
        ("Frontend Developer", ["frontend", "front-end", "front end", "react", "vue", "angular", "ui engineer"]),
        ("Fullstack Developer", ["fullstack", "full stack", "full-stack"]),
        ("Backend Engineer", ["backend", "back-end", "back end", "python", "django", "node", "java ", "golang",
                              " go ", "rails", "php", "ruby", "api"]),
        ("Product Manager", ["product manager", "product owner", "technical program manager", "program manager"]),
        ("Designer", ["designer", " ux", " ui ", "user experience"]),
        ("Data Analyst", ["data analyst", "business intelligence", " bi "]),
    ]
    for category, keys in rules:
        if any(k in t for k in keys):
            return category
    return "Software Engineer"


_TECH_INCLUDE = re.compile(
    r"\b(engineer(ing)?|developer|programmer|devops|sre|site reliability|software|front[- ]?end|back[- ]?end|"
    r"full[- ]?stack|data (scientist|engineer|analyst|architect)|analytics engineer|machine learning|\bml\b|\bai\b|"
    r"llm|cloud|platform|infrastructure|security|cyber|penetration|\bqa\b|quality assurance|sdet|test automation|"
    r"mobile|ios|android|architect|sysadmin|system administrator|systems administrator|network|database|dba|"
    r"tech lead|technical lead|cto|product manager|product owner|technical program manager|product designer|"
    r"ux|ui designer|devsecops|blockchain|smart contract|solidity|web3|kubernetes|scientist)\b", re.I)
_TECH_EXCLUDE = re.compile(
    r"\b(sales|account executive|account manager|business development|recruit(er|ing)|talent|marketing|"
    r"customer success|customer support|support specialist|legal|counsel|paralegal|finance|financial|accountant|"
    r"accounting|payroll|people partner|human resources|\bhr\b|nurse|driver|teacher|tutor|content reviewer|"
    r"copywriter|structural|mechanical|civil|chemical|electrical engineer|process engineer|manufacturing|"
    r"field engineer|hardware technician|warehouse|facilities|executive assistant|office manager|optical|"
    r"rf engineer|antenna|analog|pcb|mechatronics)\b", re.I)


def is_tech_role(title: str) -> bool:
    title = title or ''
    return bool(_TECH_INCLUDE.search(title)) and not _TECH_EXCLUDE.search(title)


def dedupe_key(title: str, company: str) -> str:
    norm = lambda v: re.sub(r'[^a-z0-9]+', ' ', (v or '').lower()).strip()  # noqa: E731
    title = re.sub(r'\s*[-–(|,].*$', '', title or '')        # "DevOps Engineer - Remote (EU)" -> "DevOps Engineer"
    return f"{norm(title)}|{norm(company)}"[:300]


def _date(value) -> datetime | None:
    """Accept ISO strings, epoch seconds or epoch milliseconds; return naive UTC."""
    if value in (None, '', 0):
        return None
    try:
        if isinstance(value, (int, float)) or str(value).isdigit():
            number = float(value)
            moment = datetime.fromtimestamp(number / 1000 if number > 1e11 else number, tz=timezone.utc)
        else:
            moment = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if moment.tzinfo:
            moment = moment.astimezone(timezone.utc).replace(tzinfo=None)
        return moment
    except (ValueError, OverflowError, OSError):
        return None


def _employment(value) -> str | None:
    text = ' '.join(value) if isinstance(value, list) else str(value or '')
    t = text.lower().replace('_', ' ').replace('-', ' ')
    for needle, label in (("intern", "Internship"), ("contract", "Contract"), ("freelance", "Contract"),
                          ("part time", "Part-time"), ("parttime", "Part-time"), ("full time", "Full-time"),
                          ("fulltime", "Full-time"), ("permanent", "Full-time"), ("temporary", "Contract")):
        if needle in t:
            return label
    return None


def _https(url: str | None) -> str | None:
    return url if url and url.startswith('https://') and len(url) <= 500 else None


def _job(**fields) -> dict:
    fields['title'] = html.unescape(fields.get('title') or '').strip()
    fields['company'] = html.unescape(fields.get('company') or '').strip()
    fields['location'] = (fields.get('location') or '').strip() or None
    return fields


# ── Employer career boards ───────────────────────────────────────────────────

def _greenhouse_board(company: str) -> list:
    res = _source_get(f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true", timeout=30)
    if res.status_code != 200:
        return []
    jobs = []
    for job in res.json().get('jobs', []):
        if not is_tech_role(job.get('title')):
            continue
        location = (job.get('location') or {}).get('name') or ''
        description = _clean(html.unescape(job.get('content') or ''))
        jobs.append(_job(title=job.get('title'), company=job.get('company_name') or company.title(),
                         location=location, description=description, url=job.get('absolute_url'),
                         source='Greenhouse', published_at=_date(job.get('first_published') or job.get('updated_at')),
                         salary_range=_salary(description)))
        if len(jobs) >= PER_COMPANY_LIMIT:
            break
    return jobs


def _ashby_board(company: str) -> list:
    res = _source_get(f"https://api.ashbyhq.com/posting-api/job-board/{company}?includeCompensation=true", timeout=30)
    if res.status_code != 200:
        return []
    jobs = []
    for job in res.json().get('jobs', []):
        if not job.get('isListed', True) or not is_tech_role(job.get('title')):
            continue
        workplace = (job.get('workplaceType') or '').lower()
        compensation = (job.get('compensation') or {}).get('compensationTierSummary')
        jobs.append(_job(title=job.get('title'), company=COMPANY_NAMES.get(company, company.title()), location=job.get('location'),
                         description=job.get('descriptionPlain') or _clean(job.get('descriptionHtml')),
                         url=job.get('jobUrl'), source='Ashby', published_at=_date(job.get('publishedAt')),
                         employment_type=_employment(job.get('employmentType')),
                         work_type={'remote': 'remote', 'hybrid': 'hybrid', 'onsite': 'onsite'}.get(workplace),
                         salary_range=compensation if compensation and len(compensation) < 80 else None))
        if len(jobs) >= PER_COMPANY_LIMIT:
            break
    return jobs


def _lever_board(company: str) -> list:
    res = _source_get(f"https://api.lever.co/v0/postings/{company}?mode=json", timeout=30)
    if res.status_code != 200 or not isinstance(res.json(), list):
        return []
    jobs = []
    for job in res.json():
        if not is_tech_role(job.get('text')):
            continue
        categories = job.get('categories') or {}
        workplace = (job.get('workplaceType') or '').lower()
        description = '\n'.join(filter(None, [job.get('descriptionPlain') or job.get('openingPlain'),
                                              *[f"{item.get('text')}\n{_clean(item.get('content'))}" for item in job.get('lists') or []],
                                              job.get('additionalPlain')]))
        jobs.append(_job(title=job.get('text'), company=COMPANY_NAMES.get(company, company.title()), location=categories.get('location'),
                         description=description, url=job.get('hostedUrl'), source='Lever',
                         published_at=_date(job.get('createdAt')), employment_type=_employment(categories.get('commitment')),
                         work_type={'remote': 'remote', 'hybrid': 'hybrid', 'on-site': 'onsite', 'onsite': 'onsite'}.get(workplace)))
        if len(jobs) >= PER_COMPANY_LIMIT:
            break
    return jobs


def scrape_greenhouse() -> list:
    return _parallel(GREENHOUSE_BOARDS, _greenhouse_board)


def scrape_ashby() -> list:
    return _parallel(ASHBY_BOARDS, _ashby_board)


def scrape_lever() -> list:
    return _parallel(LEVER_BOARDS, _lever_board)


# ── Remote job boards ────────────────────────────────────────────────────────

def scrape_himalayas() -> list:
    jobs = []
    for offset in (0, 20, 40, 60, 80):
        res = _source_get(f"https://himalayas.app/jobs/api?limit=20&offset={offset}", timeout=20)
        if res.status_code != 200:
            break
        batch = res.json().get('jobs', [])
        for job in batch:
            if not is_tech_role(job.get('title')):
                continue
            regions = job.get('locationRestrictions') or []
            jobs.append(_job(title=job.get('title'), company=(job.get('companyName') or '').title(),
                             location='Remote · ' + ', '.join(regions[:3]) if regions else 'Remote · Worldwide',
                             description=_clean(job.get('description')), url=job.get('applicationLink') or job.get('guid'),
                             source='Himalayas', published_at=_date(job.get('pubDate')), work_type='remote',
                             employment_type=_employment(job.get('employmentType')),
                             company_logo=_https(job.get('companyLogo')),
                             salary_range=_money_range(job.get('minSalary'), job.get('maxSalary'), job.get('currency'),
                                                       job.get('salaryPeriod'))))
        if len(batch) < 20:
            break
    return jobs


def scrape_remotive(category: str = "software-dev") -> list:
    """Remotive public API. Accepts a Remotive category (or a role name, kept for callers)."""
    category = category if category in REMOTIVE_CATEGORIES else "software-dev"
    res = _source_get(f"https://remotive.com/api/remote-jobs?category={category}&limit=100", timeout=20)
    if res.status_code != 200:
        return []
    jobs = []
    for job in res.json().get('jobs', []):
        if not is_tech_role(job.get('title')):
            continue
        jobs.append(_job(title=job.get('title'), company=job.get('company_name'),
                         location='Remote · ' + (job.get('candidate_required_location') or 'Worldwide'),
                         description=_clean(job.get('description')), url=job.get('url'), source='Remotive',
                         published_at=_date(job.get('publication_date')), work_type='remote',
                         employment_type=_employment(job.get('job_type')), company_logo=_https(job.get('company_logo')),
                         salary_range=(job.get('salary') or None) and job['salary'][:60]))
    return jobs


def scrape_remotive_all() -> list:
    return [job for category in REMOTIVE_CATEGORIES for job in scrape_remotive(category)]


def scrape_weworkremotely() -> list:
    jobs = []
    for category in WWR_CATEGORIES:
        res = _source_get(f"https://weworkremotely.com/categories/remote-{category}-jobs.rss", timeout=20)
        if res.status_code != 200:
            continue
        for item in ET.fromstring(res.content).iter('item'):
            raw_title = (item.findtext('title') or '').strip()
            company, _, title = raw_title.partition(':')
            title, company = (title or raw_title).strip(), company.strip() if title else ''
            if not is_tech_role(title):
                continue
            jobs.append(_job(title=title, company=company, location='Remote · ' + (item.findtext('region') or 'Worldwide'),
                             description=_clean(item.findtext('description')), url=(item.findtext('link') or '').strip(),
                             source='We Work Remotely', published_at=_date_rfc822(item.findtext('pubDate')),
                             work_type='remote', employment_type=_employment(item.findtext('type'))))
    return jobs


def _date_rfc822(value) -> datetime | None:
    from email.utils import parsedate_to_datetime
    try:
        moment = parsedate_to_datetime(value)
        return moment.astimezone(timezone.utc).replace(tzinfo=None) if moment.tzinfo else moment
    except (TypeError, ValueError):
        return None


def scrape_remoteok() -> list:
    res = _source_get("https://remoteok.com/api", timeout=20)
    if res.status_code != 200:
        return []
    jobs = []
    for job in res.json()[1:]:            # first element is a legal notice
        if not isinstance(job, dict) or not is_tech_role(job.get('position')):
            continue
        jobs.append(_job(title=job.get('position'), company=job.get('company'),
                         location='Remote · ' + (job.get('location') or 'Worldwide'),
                         description=_clean(job.get('description')), url=job.get('url') or job.get('apply_url'),
                         source='RemoteOK', published_at=_date(job.get('epoch') or job.get('date')), work_type='remote',
                         company_logo=_https(job.get('company_logo') or job.get('logo')),
                         salary_range=_money_range(job.get('salary_min'), job.get('salary_max'))))
    return jobs


def scrape_jobicy() -> list:
    res = _source_get("https://jobicy.com/api/v2/remote-jobs?count=100", timeout=20)
    if res.status_code != 200:
        return []
    jobs = []
    for job in res.json().get('jobs', []):
        if not is_tech_role(job.get('jobTitle')):
            continue
        jobs.append(_job(title=html.unescape(job.get('jobTitle') or ''), company=job.get('companyName'),
                         location='Remote · ' + (job.get('jobGeo') or 'Worldwide'),
                         description=_clean(job.get('jobDescription')), url=job.get('url'), source='Jobicy',
                         published_at=_date(job.get('pubDate')), work_type='remote',
                         employment_type=_employment(job.get('jobType')), company_logo=_https(job.get('companyLogo')),
                         salary_range=_money_range(job.get('annualSalaryMin'), job.get('annualSalaryMax'),
                                                   job.get('salaryCurrency'))))
    return jobs


def scrape_working_nomads() -> list:
    res = _source_get("https://www.workingnomads.com/api/exposed_jobs/", timeout=20)
    if res.status_code != 200:
        return []
    jobs = []
    for job in res.json():
        if not is_tech_role(job.get('title')):
            continue
        jobs.append(_job(title=job.get('title'), company=job.get('company_name'),
                         location='Remote · ' + (job.get('location') or 'Worldwide'),
                         description=_clean(job.get('description')), url=job.get('url'), source='Working Nomads',
                         published_at=_date(job.get('pub_date')), work_type='remote'))
    return jobs


def scrape_arbeitnow() -> list:
    jobs = []
    for page in (1, 2):
        res = _source_get(f"https://www.arbeitnow.com/api/job-board-api?page={page}", timeout=20)
        if res.status_code != 200:
            break
        for job in res.json().get('data', []):
            if not is_tech_role(job.get('title')):
                continue
            remote = bool(job.get('remote'))
            jobs.append(_job(title=job.get('title'), company=(job.get('company_name') or '').title(),
                             location=('Remote · ' if remote else '') + (job.get('location') or 'Germany'),
                             description=_clean(html.unescape(job.get('description') or '')), url=job.get('url'),
                             source='Arbeitnow', published_at=_date(job.get('created_at')),
                             work_type='remote' if remote else None, employment_type=_employment(job.get('job_types'))))
    return jobs


def scrape_adzuna() -> list:
    app_id, app_key = os.getenv('ADZUNA_APP_ID', ''), os.getenv('ADZUNA_APP_KEY', '')
    if not app_id or not app_key:
        return []
    jobs = []
    for country in ('gb', 'us', 'za', 'ca'):
        res = _source_get(f"https://api.adzuna.com/v1/api/jobs/{country}/search/1", timeout=20,
                          params={'app_id': app_id, 'app_key': app_key, 'results_per_page': 50,
                                  'what': 'software engineer developer devops data', 'max_days_old': MAX_AGE_DAYS,
                                  'content-type': 'application/json'})
        if res.status_code != 200:
            continue
        for job in res.json().get('results', []):
            if not is_tech_role(job.get('title')):
                continue
            jobs.append(_job(title=_clean(job.get('title')), company=(job.get('company') or {}).get('display_name'),
                             location=(job.get('location') or {}).get('display_name'),
                             description=_clean(job.get('description')), url=job.get('redirect_url'), source='Adzuna',
                             published_at=_date(job.get('created')),
                             employment_type=_employment(job.get('contract_time')),
                             salary_range=_money_range(job.get('salary_min'), job.get('salary_max'),
                                                       {'gb': 'GBP', 'us': 'USD', 'za': 'ZAR', 'ca': 'CAD'}[country])))
    return jobs


# Order matters: when the same role appears on several boards, the first wins,
# so employers' own boards come before aggregators.
SOURCES = [
    ("Greenhouse", scrape_greenhouse),
    ("Ashby", scrape_ashby),
    ("Lever", scrape_lever),
    ("Himalayas", scrape_himalayas),
    ("Remotive", scrape_remotive_all),
    ("We Work Remotely", scrape_weworkremotely),
    ("RemoteOK", scrape_remoteok),
    ("Jobicy", scrape_jobicy),
    ("Working Nomads", scrape_working_nomads),
    ("Arbeitnow", scrape_arbeitnow),
    ("Adzuna", scrape_adzuna),
]


# ── Persistence ──────────────────────────────────────────────────────────────

def _prepare(jd: dict) -> dict:
    from backend.app.utils.skill_terms import find_terms
    description = jd.get('description') or ''
    jd.setdefault('category', _guess_category(jd.get('title', '')))
    jd['work_type'] = jd.get('work_type') or _work_type(jd.get('location') or '', jd.get('title', ''), description)
    jd['dedupe_key'] = dedupe_key(jd.get('title'), jd.get('company'))
    jd['skills'] = find_terms(f"{jd.get('title', '')}\n{description}")[:25]
    if not jd.get('salary_range'):
        jd['salary_range'] = _salary(description)
    return jd


def save_jobs_to_db(jobs: list, db: Session, save_stats=None) -> int:
    """Insert new listings, refresh ones already stored. Returns the number inserted."""
    saved = 0
    now = datetime.utcnow()
    save_stats = save_stats if save_stats is not None else {"db_errors": 0}
    save_stats.setdefault("duplicates", 0)
    fields = ("title", "company", "location", "description", "salary_range", "category", "employment_type",
              "company_logo", "skills", "dedupe_key", "published_at", "work_type")
    for jd in jobs:
        try:
            if not jd.get("url") or not jd.get("title"):
                save_stats["db_errors"] += 1
                continue
            jd = _prepare(dict(jd))
            inserted = False
            with db.begin_nested():   # a malformed row must not roll back earlier rows
                existing = db.query(Job).filter(Job.url == jd["url"]).first()
                if existing is None and jd.get("dedupe_key"):
                    twin = (db.query(Job).filter(Job.dedupe_key == jd["dedupe_key"], Job.is_active == True)  # noqa: E712
                            .first())
                    if twin is not None:          # same role from another board: keep the first listing
                        if not twin.posted_by_hr:
                            twin.last_checked_at = now
                            twin.scraped_at = now
                        save_stats["duplicates"] += 1
                        continue
                if existing:
                    if existing.posted_by_hr:     # employer-managed vacancies are never overwritten by a feed
                        continue
                    for field in fields:
                        if jd.get(field) is not None:
                            setattr(existing, field, jd[field])
                    existing.last_checked_at = now
                    existing.scraped_at = now
                    existing.is_active = True
                else:
                    db.add(Job(url=jd["url"], source=jd.get("source", "Unknown"), scraped_at=now, last_checked_at=now,
                               first_seen_at=now, is_active=True, **{f: jd.get(f) for f in fields}))
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


def expire_stale_jobs(db: Session, now: datetime | None = None) -> dict:
    """Close scraped listings that are too old or no longer at their source;
    delete long-closed ones nobody applied to. Employer jobs are untouched."""
    from sqlalchemy import func, or_
    now = now or datetime.utcnow()
    scraped = db.query(Job).filter(Job.posted_by_hr.isnot(True), Job.is_active == True)  # noqa: E712
    too_old = func.coalesce(Job.published_at, Job.first_seen_at) < now - timedelta(days=MAX_AGE_DAYS)
    unseen = Job.last_checked_at < now - timedelta(days=UNSEEN_DAYS)
    closed = scraped.filter(or_(too_old, unseen)).update({Job.is_active: False}, synchronize_session=False)
    applied = db.query(Application.job_id).distinct()
    purged = (db.query(Job).filter(Job.posted_by_hr.isnot(True), Job.is_active == False,  # noqa: E712
                                   func.coalesce(Job.last_checked_at, Job.scraped_at) < now - timedelta(days=PURGE_AFTER_DAYS),
                                   ~Job.id.in_(applied))
              .delete(synchronize_session=False))
    db.commit()
    return {"closed": closed, "purged": purged}


def clear_scraped_jobs(db: Session) -> dict:
    """Owner action: remove every scraped listing. Listings someone applied to are
    closed instead of deleted so their application history stays intact."""
    applied = db.query(Application.job_id).distinct()
    base = db.query(Job).filter(Job.posted_by_hr.isnot(True))
    closed = base.filter(Job.id.in_(applied), Job.is_active == True).update(  # noqa: E712
        {Job.is_active: False}, synchronize_session=False)
    deleted = base.filter(~Job.id.in_(applied)).delete(synchronize_session=False)
    db.commit()
    return {"deleted": deleted, "closed": closed,
            "kept_employer_jobs": db.query(Job).filter(Job.posted_by_hr.is_(True)).count()}


# ── Orchestration ────────────────────────────────────────────────────────────

def _keep(jobs: list, cutoff: datetime) -> list:
    """Tech roles with a URL, posted within MAX_AGE_DAYS (undated postings are kept)."""
    return [j for j in jobs if j.get('url') and j.get('title') and is_tech_role(j['title'])
            and (j.get('published_at') is None or j['published_at'] >= cutoff)]


def _run_sources_concurrent(source_fns: list, max_workers: int = 6, source_results=None) -> list:
    """Run every source; return kept jobs in SOURCES priority order."""
    cutoff = datetime.utcnow() - timedelta(days=MAX_AGE_DAYS)
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_observe_source, name, fn): name for name, fn in source_fns}
        for future in as_completed(futures):
            name = futures[future]
            try:
                raw, result = future.result()
            except Exception as e:
                logger.warning("scraper_source_failed name=%s error_type=%s", name, type(e).__name__)
                raw, result = [], {"name": name, "status": "failed", "job_count": 0}
            kept = _keep(raw, cutoff)
            result.update(fetched=len(raw), job_count=len(kept))
            results[name] = kept
            if source_results is not None:
                source_results.append(result)
            logger.info("scraper_source name=%s fetched=%s kept=%s", name, len(raw), len(kept))
    ordered, seen = [], set()
    for name, _ in source_fns:
        for job in results.get(name, []):
            key = dedupe_key(job.get('title'), job.get('company'))
            if key in seen:
                continue
            seen.add(key)
            ordered.append(job)
    return ordered


def scrape_global_jobs() -> dict:
    from backend.app.models.automation import ScrapeRun
    from backend.app.services.job_automation import run_tick
    db = SessionLocal()
    source_results = []
    save_stats = {"db_errors": 0, "duplicates": 0}
    fatal_error = False
    total_scraped = total_saved = 0
    expired = {"closed": 0, "purged": 0}
    run = ScrapeRun(id=uuid.uuid4().hex, started_at=datetime.utcnow(), status="running", summary={})
    try:
        db.add(run)
        db.commit()   # a terminated process leaves a visible running heartbeat
    except Exception:
        db.close()
        raise
    try:
        jobs = _run_sources_concurrent(SOURCES, source_results=source_results)
        total_scraped = sum(r.get("fetched", r.get("job_count", 0)) for r in source_results)
        total_saved = save_jobs_to_db(jobs, db, save_stats)
        if any(r["status"] in ("success", "partial") for r in source_results):
            expired = expire_stale_jobs(db)   # only after a run that actually reached its sources
    except Exception as e:
        fatal_error = True
        db.rollback()
        logger.error("scraper_run_failed error_type=%s", type(e).__name__)

    summary = {
        "total_scraped": total_scraped,
        "total_saved": total_saved,
        "timestamp": datetime.utcnow().isoformat(),
        "run_id": run.id,
        "failed_sources": sum(result["status"] == "failed" for result in source_results),
        "partial_sources": sum(result["status"] == "partial" for result in source_results),
        "source_results": sorted(source_results, key=lambda result: result["name"]),
        "expired": expired,
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
    logger.info("scraper_done status=%s saved=%s", summary["status"], total_saved)
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(scrape_global_jobs())
