"""Job board API: search, filters, employer jobs first, and a resume match score.

GET /api/v1/jobs/board works signed out; with a bearer token each job also
gets a match percentage against the user's latest resume and profile skills.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.app.database import get_read_db
from backend.app.models.job import Job

router = APIRouter(tags=["Jobs"])

CATEGORY_GROUPS = {
    "engineering": ["Software Engineer", "Backend Engineer", "Frontend Developer", "Fullstack Developer"],
    "devops": ["DevOps Engineer"],
    "data": ["Data Engineer", "Machine Learning Engineer", "Data Analyst", "AI Engineer", "Data Scientist"],
    "security": ["Cybersecurity"],
    "mobile": ["Mobile Developer"],
    "qa": ["QA Engineer"],
    "product": ["Product Manager", "Designer"],
}
REGIONS = {
    "worldwide": ["worldwide", "anywhere", "global"],
    "africa": ["africa", "nigeria", "lagos", "kenya", "ghana", "south africa", "emea"],
    "europe": ["europe", "emea", "eu ", "germany", "netherlands", "france", "spain", "ireland", "poland", "portugal",
               "berlin", "amsterdam", "cet"],
    "uk": ["uk", "united kingdom", "london", "england"],
    "us": ["us", "usa", "united states", "america", "new york", "san francisco", "remote - us"],
    "canada": ["canada", "toronto", "vancouver"],
    "asia": ["asia", "apac", "india", "singapore", "japan", "philippines"],
}


def optional_user(request: Request, db: Session):
    """The signed-in user, or None (the board is public)."""
    header = request.headers.get('authorization', '')
    if not header.lower().startswith('bearer '):
        return None
    from backend.app.dependencies.auth import get_current_user
    try:
        return get_current_user(request, header.split(' ', 1)[1].strip(), db)
    except Exception:
        return None


def user_skills(db: Session, user) -> set[str]:
    """Canonical skills from the user's latest resume and profile."""
    from backend.app.models.resume import Resume
    from backend.app.models.user import CertifiedSkill, OtherSkill
    from backend.app.utils.skill_terms import find_terms
    if user is None:
        return set()
    text = []
    latest = (db.query(Resume).filter(Resume.owner_id == user.id)
              .order_by(Resume.created_at.desc(), Resume.id.desc()).first())
    if latest is not None:
        text.append(latest.parsed_data or '')
        if latest.analysis_data:
            text.append(json.dumps(latest.analysis_data)[:60000])
    text += [s.name for s in db.query(CertifiedSkill).filter(CertifiedSkill.user_id == user.id)]
    text += [s.name for s in db.query(OtherSkill).filter(OtherSkill.user_id == user.id)]
    return set(find_terms('\n'.join(text)))


def job_skills(job) -> list[str]:
    if job.skills is not None:
        return list(job.skills)
    from backend.app.utils.skill_terms import find_terms
    return find_terms(f"{job.title or ''}\n{job.description or ''}")[:25]


def match(job_skill_list: list[str], mine: set[str]) -> dict | None:
    if not mine or len(job_skill_list) < 3:
        return None
    matched = [s for s in job_skill_list if s in mine]
    return {'score': round(100 * len(matched) / len(job_skill_list)), 'matched': matched,
            'missing': [s for s in job_skill_list if s not in mine][:6]}


def _posted(job):
    return job.published_at or job.first_seen_at or job.scraped_at


def _serialize(job, mine: set[str], detail: bool = False) -> dict:
    skills = job_skills(job)
    posted = _posted(job)
    item = {
        'id': job.id, 'title': job.title, 'company': job.company or 'Company not provided', 'location': job.location,
        'work_type': job.work_type if job.work_type in ('remote', 'hybrid', 'onsite') else None,
        'employment_type': job.employment_type, 'salary_range': job.salary_range, 'category': job.category,
        'source': 'Baalebos' if job.posted_by_hr else job.source, 'url': job.url,
        'is_employer': bool(job.posted_by_hr), 'company_logo': job.company_logo,
        'posted_at': posted.isoformat() + 'Z' if posted else None, 'skills': skills[:8], 'match': match(skills, mine),
        'summary': re.sub(r'\s+', ' ', (job.description or ''))[:220],
    }
    if detail:
        item['description'] = job.description
    return item


def _filtered(db, *, q=None, category=None, work_type=None, region=None, posted_within=None,
              employer_only=False, has_salary=False):
    query = db.query(Job).filter(Job.is_active == True)  # noqa: E712
    if q:
        for word in q.split()[:6]:
            term = f"%{word}%"
            query = query.filter(or_(Job.title.ilike(term), Job.company.ilike(term), Job.description.ilike(term)))
    if category in CATEGORY_GROUPS:
        query = query.filter(Job.category.in_(CATEGORY_GROUPS[category]))
    if work_type in ('remote', 'hybrid', 'onsite'):
        query = query.filter(Job.work_type == work_type)
    if region in REGIONS:
        query = query.filter(or_(*[func.lower(func.coalesce(Job.location, '')).like(f"%{word}%")
                                   for word in REGIONS[region]]))
    if posted_within:
        since = datetime.utcnow() - timedelta(days=posted_within)
        query = query.filter(or_(Job.posted_by_hr.is_(True),
                                 func.coalesce(Job.published_at, Job.first_seen_at, Job.scraped_at) >= since))
    if employer_only:
        query = query.filter(Job.posted_by_hr.is_(True))
    if has_salary:
        query = query.filter(Job.salary_range.isnot(None), Job.salary_range != '')
    return query


def _one_per_role(rows):
    """Last line of defence against duplicates: one listing per role per company
    (the first in display order, so an employer's own posting wins)."""
    from backend.app.utils.global_scraper import _keyed, dedupe_key
    seen, kept = set(), []
    for row in rows:
        key = dedupe_key(row.title, row.company)
        if _keyed(key):
            if key in seen:
                continue
            seen.add(key)
        kept.append(row)
    return kept


@router.get("/board")
def job_board(request: Request, q: Optional[str] = None, category: Optional[str] = None,
              work_type: Optional[str] = None, region: Optional[str] = None,
              posted_within: Optional[int] = Query(None, ge=1, le=90), employer_only: bool = False,
              has_salary: bool = False, sort: str = Query("best", pattern="^(best|newest)$"),
              page: int = Query(1, ge=1, le=200), page_size: int = Query(20, ge=1, le=50),
              db: Session = Depends(get_read_db)):
    """Employer jobs on Baalebos first, then by match (signed in) or newest."""
    user = optional_user(request, db)
    mine = user_skills(db, user)
    query = _filtered(db, q=(q or '').strip()[:100], category=category, work_type=work_type, region=region,
                      posted_within=posted_within, employer_only=employer_only, has_salary=has_salary)
    rows = query.with_entities(Job.id, Job.posted_by_hr, Job.skills, Job.title, Job.company, Job.dedupe_key,
                               Job.published_at, Job.first_seen_at, Job.scraped_at).all()

    def score(row):
        if sort != 'best' or not mine:
            return 0
        skills = row.skills if row.skills is not None else []
        result = match(list(skills), mine)
        return result['score'] if result else 0

    def posted(row):
        return (row.published_at or row.first_seen_at or row.scraped_at or datetime.min).timestamp()
    rows.sort(key=lambda r: (bool(r.posted_by_hr), score(r), posted(r)), reverse=True)
    rows = _one_per_role(rows)
    total = len(rows)
    ids = [r.id for r in rows[(page - 1) * page_size: page * page_size]]
    jobs = {j.id: j for j in db.query(Job).filter(Job.id.in_(ids))} if ids else {}
    last = db.query(func.max(Job.scraped_at)).filter(Job.posted_by_hr.isnot(True)).scalar()
    return {'total': total, 'page': page, 'page_size': page_size, 'personalised': bool(mine),
            'updated_at': last.isoformat() + 'Z' if last else None,
            'items': [_serialize(jobs[i], mine) for i in ids if i in jobs]}


@router.get("/board/{job_id}")
def job_board_detail(job_id: int, request: Request, db: Session = Depends(get_read_db)):
    from fastapi import HTTPException
    job = db.query(Job).filter(Job.id == job_id, Job.is_active == True).first()  # noqa: E712
    if not job:
        raise HTTPException(404, "This job is no longer available.")
    return _serialize(job, user_skills(db, optional_user(request, db)), detail=True)
