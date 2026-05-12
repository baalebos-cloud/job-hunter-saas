import re
import random
import logging

logger = logging.getLogger(__name__)

# ── Action verb pool ──────────────────────────────────────────────────────────
ACTION_VERBS = [
    "Spearheaded", "Optimized", "Architected", "Engineered", "Automated",
    "Implemented", "Designed", "Deployed", "Configured", "Integrated",
    "Orchestrated", "Streamlined", "Developed", "Managed", "Reduced",
    "Established", "Monitored", "Built", "Delivered", "Improved",
]

# ── Bullet templates per skill category ──────────────────────────────────────
TEMPLATES = {
    "cloud": [
        "{verb} {skill} cloud infrastructure, improving system reliability by 30% and reducing downtime.",
        "Designed and deployed {skill}-based environments across dev, staging, and production.",
        "Migrated legacy workloads to {skill}, achieving cost savings of 20% through right-sizing.",
        "Configured {skill} networking, IAM policies, and security groups for multi-tier architectures.",
    ],
    "cicd": [
        "{verb} {skill} pipelines reducing average deployment time by 40%.",
        "Integrated {skill} into the CI/CD workflow enabling automated testing and zero-downtime releases.",
        "Built {skill} automation scripts that eliminated manual deployment steps across all environments.",
        "Configured {skill} to trigger automated builds, tests, and container pushes on every commit.",
    ],
    "container": [
        "{verb} {skill} to containerize and orchestrate microservices, improving portability and scalability.",
        "Managed {skill} deployments with rolling updates and auto-scaling policies for high availability.",
        "Configured {skill} networking, persistent volumes, and RBAC for production workloads.",
        "Led migration from monolithic deployment to {skill}-based architecture with zero downtime.",
    ],
    "monitoring": [
        "{verb} {skill} dashboards and alerting, reducing MTTR by 40% through automated incident triage.",
        "Implemented {skill} for centralized log aggregation and real-time system health monitoring.",
        "Configured {skill} alerts and escalation policies reducing false positives by 35%.",
        "Built {skill} observability stack covering metrics, logs, and traces across all services.",
    ],
    "iac": [
        "{verb} {skill} modules for repeatable, version-controlled infrastructure provisioning.",
        "Standardized infrastructure deployment using {skill}, eliminating configuration drift.",
        "Wrote {skill} code to provision multi-region cloud environments with consistent security baselines.",
        "Implemented {skill} state management and remote backends for team-wide infrastructure collaboration.",
    ],
    "scripting": [
        "{verb} {skill} automation scripts reducing manual operational tasks by 60%.",
        "Developed {skill} tooling for system configuration, deployment workflows, and data processing.",
        "Built {skill} CLI utilities enabling the team to self-serve infrastructure operations.",
        "Wrote {skill} integration scripts connecting internal services and third-party APIs.",
    ],
    "security": [
        "{verb} {skill} security controls improving compliance posture and reducing vulnerability exposure.",
        "Implemented {skill} policies following least-privilege principles across all environments.",
        "Conducted {skill} assessments identifying and remediating critical vulnerabilities.",
        "Configured {skill} to enforce encryption, access logging, and anomaly detection.",
    ],
    "default": [
        "{verb} {skill} to improve system reliability and operational efficiency.",
        "Integrated {skill} into existing workflows, reducing manual effort and error rates.",
        "Led implementation of {skill} best practices across the engineering team.",
        "Delivered {skill} solutions that improved performance and scalability by 25%.",
    ],
}


def _categorize(skill: str) -> str:
    s = skill.lower()
    if any(k in s for k in ["aws", "gcp", "azure", "cloud", "ec2", "s3", "vpc", "rds", "lambda"]):
        return "cloud"
    if any(k in s for k in ["ci/cd", "jenkins", "github action", "gitlab", "circleci", "pipeline"]):
        return "cicd"
    if any(k in s for k in ["docker", "kubernetes", "k8s", "container", "ecs", "eks", "helm"]):
        return "container"
    if any(k in s for k in ["prometheus", "grafana", "elk", "datadog", "cloudwatch", "monitor", "observ"]):
        return "monitoring"
    if any(k in s for k in ["terraform", "cloudformation", "ansible", "pulumi", "iac"]):
        return "iac"
    if any(k in s for k in ["python", "bash", "script", "golang", "node", "java", "ruby"]):
        return "scripting"
    if any(k in s for k in ["iam", "security", "waf", "acl", "hardening", "vault", "secret"]):
        return "security"
    return "default"


# ── Public API ────────────────────────────────────────────────────────────────

def generate_resume_fix(missing_keywords: list, job_title: str) -> list:
    """
    Generate professional bullet point suggestions for missing skills.
    Returns list of {"skill": str, "bullet_point": str}.
    """
    suggestions = []
    for skill in (missing_keywords or []):
        if not skill or not skill.strip():
            continue
        verb      = random.choice(ACTION_VERBS)
        category  = _categorize(skill)
        templates = TEMPLATES.get(category, TEMPLATES["default"])
        bullet    = random.choice(templates).format(verb=verb, skill=skill)
        suggestions.append({
            "skill":        skill.strip(),
            "bullet_point": bullet,
        })
    return suggestions


def build_optimized_resume(
    file_content: bytes,
    filename: str,
    job_description: str,
    job_title: str,
) -> dict:
    """
    Full optimization pipeline — call this from your route handler.

    Steps:
      1. Extract text from uploaded file (PDF or DOCX)
      2. Score resume against JD using analyze_detailed_ats()
      3. Rewrite resume using rewrite_resume_for_job()
      4. Validate and fill any missing structured fields
      5. Return everything pdf_generator needs

    Args:
        file_content:    Raw bytes of the uploaded resume file
        filename:        Original filename e.g. "resume.pdf" or "cv.docx"
        job_description: Full job description text
        job_title:       Target job title e.g. "DevOps Engineer"

    Returns:
        {
            "ats_score":   float,     # 0-100
            "structured":  dict,      # pass directly to generate_optimized_resume()
            "suggestions": list,      # bullet suggestions for missing skills
            "missing":     list,      # list of missing keyword strings
            "resume_text": str,       # extracted plain text (useful for logging)
        }
    """
    # ── Import with correct function names from ats_engine.py ─────────────────
    # FIX 1: Original optimizer imported non-existent names:
    #   analyze_resume()   → correct name is analyze_detailed_ats()
    #   rewrite_resume()   → correct name is rewrite_resume_for_job()
    try:
        from backend.app.utils.ats_engine import (
            extract_text,           # extract raw text from PDF/DOCX bytes
            analyze_detailed_ats,   # score resume against JD
            rewrite_resume_for_job, # AI rewrite returning structured dict
        )
    except ImportError as e:
        logger.error(f"[Optimizer] Import failed: {e}")
        return _emergency_fallback(b"", filename, job_title, [], 0.0)

    # ── Step 1: Extract text ──────────────────────────────────────────────────
    resume_text = ""
    try:
        resume_text = extract_text(file_content, filename)
    except Exception as e:
        logger.error(f"[Optimizer] Text extraction failed: {e}")

    if not resume_text.strip():
        return {
            "ats_score":   0.0,
            "structured":  _safe_fallback_structured(resume_text, job_title, []),
            "suggestions": [],
            "missing":     [],
            "resume_text": "",
            "error":       "Could not extract text from resume file.",
        }

    # ── Step 2: ATS Analysis ──────────────────────────────────────────────────
    analysis = {}
    try:
        # analyze_detailed_ats takes (file_content, filename, job_description)
        analysis = analyze_detailed_ats(file_content, filename, job_description)
    except Exception as e:
        logger.error(f"[Optimizer] ATS analysis failed: {e}")

    ats_score = float(analysis.get("overall_score", 0.0))

    # Filter out placeholder messages injected when API key is missing
    missing_keywords = [
        k for k in (analysis.get("missing_list") or [])
        if k and isinstance(k, str)
        and not k.startswith("Add GROQ")
        and not k.startswith("Sign up")
        and len(k) < 80
    ]

    # ── Step 3: AI Resume Rewrite ─────────────────────────────────────────────
    # rewrite_resume_for_job takes (resume_text, job_description, job_title, missing_keywords)
    # Note: it takes resume_text (str), NOT file_content (bytes)
    structured = None
    try:
        structured = rewrite_resume_for_job(
            resume_text,
            job_description,
            job_title,
            missing_keywords,
        )
    except Exception as e:
        logger.error(f"[Optimizer] AI rewrite failed: {e}")

    # ── Step 4: Validate and fill missing fields ──────────────────────────────
    structured = _validate_structured(structured, resume_text, job_title, missing_keywords)

    # ── Step 5: Generate bullet suggestions ───────────────────────────────────
    suggestions = generate_resume_fix(missing_keywords, job_title)

    return {
        "ats_score":   ats_score,
        "structured":  structured,
        "suggestions": suggestions,
        "missing":     missing_keywords,
        "resume_text": resume_text,
    }


# ── Structured resume validator ───────────────────────────────────────────────

def _validate_structured(
    s: dict | None,
    resume_text: str,
    job_title: str,
    missing_keywords: list,
) -> dict:
    """
    Ensures every key pdf_generator expects is present and non-empty.
    Fills gaps from raw resume_text rather than leaving sections blank.
    """
    if not s or not isinstance(s, dict):
        s = {}

    if not s.get("name"):
        s["name"] = _extract_name(resume_text)

    if not s.get("contact"):
        s["contact"] = _extract_contact(resume_text)

    if not s.get("summary"):
        s["summary"] = (
            f"Results-driven {job_title} with hands-on experience in cloud infrastructure, "
            f"CI/CD pipeline engineering, and DevOps automation. Delivered measurable improvements "
            f"including 40%+ reduction in MTTR through observability tooling. "
            f"Seeking to leverage expertise in a high-impact {job_title} role."
        )

    if not s.get("experience") or not isinstance(s["experience"], list):
        s["experience"] = _extract_experience(resume_text, job_title)

    # Ensure every job entry has a bullets list
    for job in s["experience"]:
        if not job.get("bullets") or not isinstance(job["bullets"], list):
            job["bullets"] = ["Delivered key projects aligned with engineering and business objectives."]

    if not s.get("skills") or not isinstance(s["skills"], list):
        s["skills"] = _extract_skills(resume_text, missing_keywords)
    else:
        # Inject missing keywords into existing skills list
        existing_lower = {sk.lower() for sk in s["skills"]}
        for kw in missing_keywords:
            if kw and kw.lower() not in existing_lower:
                s["skills"].append(kw)
                existing_lower.add(kw.lower())

    if not s.get("education") or not isinstance(s["education"], list):
        s["education"] = _extract_education(resume_text)

    if not s.get("certifications") or not isinstance(s["certifications"], list):
        s["certifications"] = _extract_certifications(resume_text)

    return s


# ── Text parsers ──────────────────────────────────────────────────────────────

def _extract_name(text: str) -> str:
    for line in (text or "").split("\n"):
        s = line.strip()
        if s and len(s) < 60 and not any(c in s for c in ["@", "http", "+", "linkedin", "|"]):
            return s
    return "Candidate"


def _extract_contact(text: str) -> str:
    contact_parts = []
    for line in (text or "").split("\n")[:10]:
        s = line.strip()
        if not s:
            continue
        if any(k in s.lower() for k in ["@", "linkedin", "github", "+"]):
            contact_parts.append(s)
        elif re.search(r'\+?\d[\d\s\-\(\)]{7,}', s):
            contact_parts.append(s)
    seen   = set()
    unique = []
    for p in contact_parts:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return "  |  ".join(unique[:4])


def _extract_experience(text: str, job_title: str) -> list:
    bullets = []
    section_started = False
    for line in (text or "").split("\n"):
        s = line.strip()
        if not s:
            continue
        if re.match(r'^(work\s+)?experience|professional\s+experience|employment', s, re.I):
            section_started = True
            continue
        if section_started and re.match(
            r'^(education|certifications?|skills|projects|awards|summary)', s, re.I
        ):
            break
        if s.startswith(("•", "-", "*", "–", "▸")) or (section_started and len(s) > 30):
            clean = s.lstrip("•-*–▸ ").strip()
            if clean and len(clean) > 15:
                bullets.append(clean)

    if not bullets:
        for line in (text or "").split("\n"):
            s = line.strip().lstrip("•-*–▸ ")
            if len(s) > 40 and not s.isupper():
                bullets.append(s)

    return [{
        "title":    job_title,
        "company":  "",
        "dates":    "",
        "location": "",
        "bullets":  bullets[:15],
    }]


def _extract_skills(text: str, missing_keywords: list) -> list:
    skills    = []
    in_skills = False
    for line in (text or "").split("\n"):
        s = line.strip()
        if not s:
            continue
        if re.match(r'^(technical\s+)?skills|core\s+(skills|competencies)', s, re.I):
            in_skills = True
            continue
        if in_skills and re.match(
            r'^(experience|education|certifications?|projects|summary)', s, re.I
        ):
            break
        if in_skills:
            parts = re.split(r'[,|·•]', s)
            for p in parts:
                clean = p.strip().lstrip("-* ")
                if clean and 2 < len(clean) < 50:
                    skills.append(clean)

    existing_lower = {sk.lower() for sk in skills}
    for kw in (missing_keywords or []):
        if kw and kw.lower() not in existing_lower:
            skills.append(kw)
            existing_lower.add(kw.lower())

    return skills[:40] if skills else ["See resume for full skill set"]


def _extract_education(text: str) -> list:
    education  = []
    in_edu     = False
    current    = {}
    for line in (text or "").split("\n"):
        s = line.strip()
        if not s:
            continue
        if re.match(r'^education', s, re.I):
            in_edu = True
            continue
        if in_edu and re.match(
            r'^(experience|certifications?|skills|projects|summary)', s, re.I
        ):
            if current:
                education.append(current)
            break
        if in_edu:
            if re.search(r'\b(bachelor|master|bsc|msc|b\.sc|m\.sc|phd|diploma|certificate|degree)\b', s, re.I):
                if current:
                    education.append(current)
                current = {"degree": s, "school": "", "year": ""}
            elif current and not current.get("school"):
                current["school"] = s
            year_m = re.search(r'\b(19|20)\d{2}\b', s)
            if year_m and current:
                current["year"] = year_m.group()

    if current and current.get("degree"):
        education.append(current)
    return education


def _extract_certifications(text: str) -> list:
    certs    = []
    in_certs = False
    for line in (text or "").split("\n"):
        s = line.strip()
        if not s:
            continue
        if re.match(r'^certifications?', s, re.I):
            in_certs = True
            continue
        if in_certs and re.match(
            r'^(experience|education|skills|projects|summary)', s, re.I
        ):
            break
        if in_certs:
            clean = s.lstrip("•-*– ").strip()
            if clean and len(clean) > 5:
                certs.append(clean)
    return certs


def _safe_fallback_structured(text: str, job_title: str, missing: list) -> dict:
    return _validate_structured(None, text, job_title, missing)


def _emergency_fallback(
    file_content: bytes, filename: str, job_title: str, missing: list, score: float
) -> dict:
    return {
        "ats_score":   score,
        "structured":  _safe_fallback_structured("", job_title, missing),
        "suggestions": generate_resume_fix(missing, job_title),
        "missing":     missing,
        "resume_text": "",
        "error":       "Import error — check ats_engine.py is accessible.",
    }