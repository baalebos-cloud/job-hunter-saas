import io
import re
import json
import pdfplumber
from docx import Document
from openai import OpenAI
from backend.app.core.config import settings


# ─── Text Extraction ──────────────────────────────────────────────────────────

def extract_text(file_content: bytes, filename: str) -> str:
    ext  = filename.split('.')[-1].lower()
    text = ""
    try:
        if ext == "pdf":
            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                for page in pdf.pages:
                    text += (page.extract_text() or "") + " "
        elif ext in ["docx", "doc"]:
            doc = Document(io.BytesIO(file_content))
            for para in doc.paragraphs:
                text += para.text + " "
    except Exception as e:
        print(f"[ATS] Extraction Error: {e}")
    return text.strip()


# ─── ATS Scoring ─────────────────────────────────────────────────────────────

def analyze_detailed_ats(file_content: bytes, filename: str, job_description: str) -> dict:
    resume_text = extract_text(file_content, filename)

    if not resume_text:
        return _error_response("Could not extract text from resume. Please use a text-based PDF or DOCX.")

    if not settings.GROQ_API_KEY:
        return _simulated_response()

    client = OpenAI(
        api_key=settings.GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1",
    )

    prompt = f"""You are a Senior ATS (Applicant Tracking System) expert and technical recruiter.
Analyze this resume against the job description and score it accurately.

JOB DESCRIPTION:
{job_description[:2500]}

RESUME:
{resume_text[:3500]}

Score the resume on these criteria:
1. Keyword match — how many job description keywords appear in the resume
2. Action verbs — strong verbs like "Architected", "Deployed", "Automated", "Reduced"
3. Quantified achievements — metrics like percentages, numbers, time saved
4. Job title alignment — does the resume title match the job title
5. Skills coverage — technical skills required vs present

Return ONLY valid JSON:
{{
    "overall_score": 78,
    "keywords_matched": 14,
    "keywords_missing": 6,
    "total_keywords": 20,
    "missing_list": ["Terraform", "Kubernetes", "AWS RDS", "CI/CD", "Helm"],
    "breakdown": {{
        "action_verbs": {{"score": 80, "count": 8}},
        "technical_skills": {{"score": 65, "count": 12}},
        "soft_skills": {{"score": 70, "count": 5}}
    }},
    "suggestions": [
        "Add Terraform and Kubernetes to your skills section",
        "Quantify your DevOps achievements with specific metrics",
        "Mirror the job title in your resume headline"
    ]
}}

Rules:
- overall_score must be a number 0-100
- missing_list must be actual missing keywords from the job description (short terms only)
- Return ONLY the JSON, no markdown, no explanation"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are an ATS analysis expert. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.2,
        )

        raw = response.choices[0].message.content.strip()
        raw = re.sub(r'^```json\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'^```\s*',     '', raw, flags=re.MULTILINE)
        raw = re.sub(r'\s*```$',     '', raw, flags=re.MULTILINE)

        result = json.loads(raw)

        return {
            "overall_score":    float(result.get("overall_score", 0)),
            "keywords_matched": int(result.get("keywords_matched", 0)),
            "keywords_missing": int(result.get("keywords_missing", 0)),
            "total_keywords":   int(result.get("total_keywords", 0)),
            "missing_list":     result.get("missing_list", []),
            "breakdown":        result.get("breakdown", {
                "action_verbs":    {"score": 0, "count": 0},
                "technical_skills":{"score": 0, "count": 0},
                "soft_skills":     {"score": 0, "count": 0},
            }),
            "suggestions": result.get("suggestions", []),
        }

    except json.JSONDecodeError as e:
        print(f"[ATS] JSON parse error: {e} | Raw: {raw[:200]}")
        return _error_response("AI returned invalid response. Please try again.")
    except Exception as e:
        print(f"[ATS] Groq error: {e}")
        return _error_response(str(e))


# ─── AI Resume Rewriter ───────────────────────────────────────────────────────

def rewrite_resume_for_job(
    resume_text: str,
    job_description: str,
    job_title: str,
    missing_keywords: list,
    context_phrases: list = None,
) -> dict:
    """
    Rewrites the resume to achieve 96%+ ATS score for the target job.
    Returns a structured dict ready for pdf_generator.generate_optimized_resume().
    """
    if not settings.GROQ_API_KEY:
        return _fallback_structured_resume(resume_text, job_title, missing_keywords)

    client = OpenAI(
        api_key=settings.GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1",
    )

    missing_str = ", ".join(missing_keywords[:20]) if missing_keywords else "none"

    prompt = f"""You are a world-class ATS resume optimization expert. Your goal is to rewrite this resume to score 96%+ on ATS systems for the target job.

TARGET JOB TITLE: {job_title}

JOB DESCRIPTION (read carefully — extract ALL keywords):
{job_description[:3000]}

ORIGINAL RESUME (preserve ALL facts — only improve phrasing):
{resume_text[:5000]}

MISSING KEYWORDS TO ADD: {missing_str}

ATS OPTIMIZATION RULES (follow all of these):
1. TITLE MATCH: The summary must open with the exact job title from the job description
2. KEYWORD DENSITY: Every keyword from the job description must appear at least once
3. ACTION VERBS: Every bullet must start with a strong past-tense action verb
4. QUANTIFY EVERYTHING: Every bullet must include at least one metric (%, time, count)
5. SKILLS COMPLETENESS: Include EVERY skill from original PLUS all missing keywords
6. NO FABRICATION: Do not invent companies, degrees, or certifications not in the original
7. SUMMARY: 3 sentences — job title + years + top skills | biggest achievement | value to role
8. BULLETS: 5-7 bullets per job, each starting with action verb + achievement + metric
9. CONTACT: Preserve exact email, phone, location, LinkedIn from original

Return ONLY valid JSON — no markdown, no explanation:
{{
  "name": "FULL NAME IN CAPS",
  "contact": "email | phone | location | LinkedIn URL",
  "summary": "3-sentence ATS-optimized summary with exact job title",
  "experience": [
    {{
      "title": "exact job title from resume",
      "company": "exact company name",
      "dates": "exact dates",
      "location": "city, country or Remote",
      "bullets": [
        "Action verb + specific achievement + quantified metric",
        "Action verb + specific achievement + quantified metric"
      ]
    }}
  ],
  "skills": ["every skill term — short, no sentences"],
  "education": [
    {{"degree": "exact degree", "school": "exact school", "year": "year"}}
  ],
  "certifications": ["every certification from original resume"]
}}"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are an ATS resume optimization expert. Always respond with valid JSON only. Never fabricate experience."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=4096,
            temperature=0.2,
        )
        raw    = response.choices[0].message.content.strip()
        raw    = re.sub(r'^```json\s*', '', raw, flags=re.MULTILINE)
        raw    = re.sub(r'^```\s*',     '', raw, flags=re.MULTILINE)
        raw    = re.sub(r'\s*```$',     '', raw, flags=re.MULTILINE)
        result = json.loads(raw)
        return result
    except Exception as e:
        print(f"[Resume Rewrite] Error: {e}")
        return _fallback_structured_resume(resume_text, job_title, missing_keywords)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _simulated_response() -> dict:
    return {
        "overall_score":    45.0,
        "keywords_matched": 5,
        "keywords_missing": 8,
        "total_keywords":   13,
        "missing_list":     ["Add GROQ_API_KEY to .env for real AI analysis — free at console.groq.com"],
        "breakdown": {
            "action_verbs":     {"score": 50, "count": 4},
            "technical_skills": {"score": 40, "count": 3},
            "soft_skills":      {"score": 45, "count": 2},
        },
        "suggestions": ["Sign up free at console.groq.com and add your GROQ_API_KEY to .env to enable real AI analysis"],
    }


def _error_response(message: str) -> dict:
    return {
        "overall_score":    0,
        "keywords_matched": 0,
        "keywords_missing": 0,
        "total_keywords":   0,
        "missing_list":     [],
        "breakdown": {
            "action_verbs":     {"score": 0, "count": 0},
            "technical_skills": {"score": 0, "count": 0},
            "soft_skills":      {"score": 0, "count": 0},
        },
        "suggestions": [],
        "error": message,
    }


def _fallback_structured_resume(
    resume_text: str,
    job_title: str,
    missing_keywords: list,
) -> dict:
    """
    FIXED: Full section parser replacing the weak original that returned
    education=[], certifications=[], and capped bullets at 8.

    Now extracts all resume sections from raw text using regex.
    Used when GROQ_API_KEY is missing or the AI call fails.
    """
    lines = [l.strip() for l in (resume_text or "").split("\n") if l.strip()]

    # ── Name ─────────────────────────────────────────────────────────────────
    name = "Candidate"
    for line in lines:
        if len(line) < 60 and not any(c in line for c in ["@", "http", "+", "linkedin", "|"]):
            name = line
            break

    # ── Contact — scan first 8 lines for email/phone/LinkedIn ─────────────────
    contact_parts = []
    for line in lines[:8]:
        if any(k in line.lower() for k in ["@", "linkedin", "github", "+"]):
            contact_parts.append(line)
        elif re.search(r'\+?\d[\d\s\-\(\)]{7,}', line):
            contact_parts.append(line)
    contact = "  |  ".join(dict.fromkeys(contact_parts))

    # ── Section parser ────────────────────────────────────────────────────────
    SECTION_MAP = {
        "summary":        r'^(professional\s+summary|summary|objective|profile)',
        "experience":     r'^((work\s+)?experience|professional\s+experience|employment)',
        "skills":         r'^((technical\s+)?skills|core\s+(skills|competencies)|technologies)',
        "education":      r'^education',
        "certifications": r'^certifications?(\s+&\s+training)?',
        "projects":       r'^(selected\s+)?projects',
    }

    sections    = {k: [] for k in SECTION_MAP}
    current_sec = None

    for line in lines:
        matched = False
        for sec, pattern in SECTION_MAP.items():
            if re.match(pattern, line, re.I) and len(line) < 60:
                current_sec = sec
                matched     = True
                break
        if not matched and current_sec:
            sections[current_sec].append(line)

    # ── Summary ───────────────────────────────────────────────────────────────
    summary = " ".join(sections["summary"]).strip() or (
        f"Results-driven {job_title} with hands-on experience in cloud infrastructure, "
        f"CI/CD pipeline engineering, and DevOps automation. Delivered measurable improvements "
        f"including 40%+ reduction in MTTR through observability tooling. "
        f"Seeking to leverage expertise in a high-impact {job_title} role."
    )

    # ── Experience ────────────────────────────────────────────────────────────
    exp_lines   = sections["experience"] + sections["projects"]
    job_entries = []
    current_job = None
    bullets     = []

    for line in exp_lines:
        is_bullet = line.startswith(("•", "-", "*", "–", "▸")) or (
            len(line) > 40 and line[0].islower()
        )
        is_date = bool(re.search(
            r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|20\d{2}|19\d{2})\b',
            line, re.I
        ))
        if not is_bullet and not is_date and len(line) < 80 and line[0].isupper():
            if current_job and bullets:
                current_job["bullets"] = bullets[:]
                job_entries.append(current_job)
            current_job = {"title": line, "company": "", "dates": "", "location": "", "bullets": []}
            bullets     = []
        elif is_date and current_job:
            current_job["dates"] = line
        elif is_bullet or len(line) > 30:
            clean = line.lstrip("•-*–▸ ").strip()
            if clean and len(clean) > 15:
                bullets.append(clean)

    if current_job:
        current_job["bullets"] = bullets[:]
        job_entries.append(current_job)
    elif bullets:
        job_entries = [{"title": job_title, "company": "", "dates": "", "location": "", "bullets": bullets[:15]}]

    if not job_entries:
        job_entries = [{"title": job_title, "company": "", "dates": "", "location": "",
                        "bullets": ["Delivered key projects aligned with engineering and business objectives."]}]

    # ── Skills ────────────────────────────────────────────────────────────────
    skills = []
    for line in sections["skills"]:
        for part in re.split(r"[,|·•\t]", line):
            clean = part.strip().lstrip("-*• ")
            if clean and 2 < len(clean) < 50:
                skills.append(clean)

    existing_lower = {s.lower() for s in skills}
    for kw in (missing_keywords or []):
        if kw and not kw.startswith("Add GROQ") and kw.lower() not in existing_lower:
            skills.append(kw)
            existing_lower.add(kw.lower())

    if not skills:
        skills = missing_keywords[:20] if missing_keywords else ["See resume for full skill set"]

    # ── Education ─────────────────────────────────────────────────────────────
    # FIXED: was always returning []
    education  = []
    current_edu = {}
    for line in sections["education"]:
        if re.search(r'\b(bachelor|master|bsc|msc|b\.sc|m\.sc|phd|diploma|certificate|degree)\b', line, re.I):
            if current_edu:
                education.append(current_edu)
            current_edu = {"degree": line, "school": "", "year": ""}
        elif current_edu and not current_edu.get("school") and not re.search(r'\b20\d{2}\b', line):
            current_edu["school"] = line
        year_m = re.search(r'\b(19|20)\d{2}\b', line)
        if year_m and current_edu:
            current_edu["year"] = year_m.group()
    if current_edu and current_edu.get("degree"):
        education.append(current_edu)

    # ── Certifications ────────────────────────────────────────────────────────
    # FIXED: was always returning []
    certifications = []
    for line in sections["certifications"]:
        clean = line.lstrip("•-*– ").strip()
        if clean and len(clean) > 5:
            certifications.append(clean)

    return {
        "name":           name,
        "contact":        contact,
        "summary":        summary,
        "experience":     job_entries,
        "skills":         skills[:40],
        "education":      education,      # ← was always []
        "certifications": certifications, # ← was always []
    }