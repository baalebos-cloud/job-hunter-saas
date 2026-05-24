"""
Resume Enhancement Engine — Optimizes resumes to match job descriptions
Preserves the user's original content while improving phrasing and adding keywords.
"""

import io
import re
import json
import pdfplumber
from docx import Document
from openai import OpenAI
from backend.app.core.config import settings


# ─── Text Extraction ──────────────────────────────────────────────────────────

def extract_text(file_content: bytes, filename: str) -> str:
    ext = filename.split('.')[-1].lower()
    text = ""
    try:
        if ext == "pdf":
            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                for page in pdf.pages:
                    text += (page.extract_text() or "") + "\n"
        elif ext in ["docx", "doc"]:
            doc = Document(io.BytesIO(file_content))
            for para in doc.paragraphs:
                text += para.text + "\n"
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

    prompt = f"""You are an ATS (Applicant Tracking System) expert. Analyze this resume against the job description.

JOB DESCRIPTION:
{job_description[:2500]}

RESUME:
{resume_text[:3500]}

Score the resume and identify missing keywords that should be added.

Return ONLY valid JSON:
{{
    "overall_score": 75,
    "keywords_matched": 12,
    "keywords_missing": 8,
    "total_keywords": 20,
    "missing_list": ["keyword1", "keyword2", "keyword3"],
    "breakdown": {{
        "action_verbs": {{"score": 70, "count": 6}},
        "technical_skills": {{"score": 65, "count": 10}},
        "soft_skills": {{"score": 60, "count": 4}}
    }},
    "suggestions": [
        "Add more quantified achievements",
        "Include specific technologies from job description"
    ]
}}

Rules:
- missing_list should contain short keyword phrases (1-3 words) from the job description not in the resume
- Return ONLY JSON, no markdown"""

    raw = ""
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are an ATS expert. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.2,
        )

        raw = response.choices[0].message.content.strip()
        raw = re.sub(r'^```json\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'^```\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)

        result = json.loads(raw)

        return {
            "overall_score": float(result.get("overall_score", 0)),
            "keywords_matched": int(result.get("keywords_matched", 0)),
            "keywords_missing": int(result.get("keywords_missing", 0)),
            "total_keywords": int(result.get("total_keywords", 0)),
            "missing_list": result.get("missing_list", []),
            "breakdown": result.get("breakdown", {
                "action_verbs": {"score": 0, "count": 0},
                "technical_skills": {"score": 0, "count": 0},
                "soft_skills": {"score": 0, "count": 0},
            }),
            "suggestions": result.get("suggestions", []),
        }

    except json.JSONDecodeError as e:
        print(f"[ATS] JSON parse error: {e} | Raw: {raw[:200]}")
        return _error_response("AI returned invalid response. Please try again.")
    except Exception as e:
        print(f"[ATS] Groq error: {e}")
        return _error_response(str(e))


# ─── Resume Enhancement (NOT Rewrite) ─────────────────────────────────────────

def rewrite_resume_for_job(
    resume_text: str,
    job_description: str,
    job_title: str,
    missing_keywords: list | None,
    context_phrases: list | None = None,
) -> dict:
    """
    ENHANCES the user's resume to better match the job description.
    
    This function PRESERVES:
    - All original facts (companies, dates, schools, degrees)
    - The user's real experience and achievements
    - Education and certifications exactly as provided
    
    This function IMPROVES:
    - Bullet point phrasing (adds action verbs, metrics)
    - Keyword optimization (adds missing job description keywords)
    - Summary alignment with target role
    """
    if not settings.GROQ_API_KEY:
        return _fallback_structured_resume(resume_text, job_title, missing_keywords)

    client = OpenAI(
        api_key=settings.GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1",
    )

    missing_str = ", ".join((missing_keywords or [])[:15]) or "none identified"

    prompt = f"""You are a professional resume editor. Your job is to ENHANCE this resume to better match the job description while PRESERVING all the candidate's real information.

TARGET ROLE: {job_title}

JOB DESCRIPTION (extract keywords to incorporate):
{job_description[:2500]}

KEYWORDS TO ADD NATURALLY: {missing_str}

CANDIDATE'S ORIGINAL RESUME:
{resume_text[:6000]}

═══════════════════════════════════════════════════════════════════════════════
CRITICAL RULES — YOU MUST FOLLOW ALL:
═══════════════════════════════════════════════════════════════════════════════

✅ PRESERVE EXACTLY (do not change):
   - Person's name exactly as written
   - All contact information (email, phone, LinkedIn, location)
   - Company names exactly as written
   - Job titles exactly as written  
   - Employment dates exactly as written
   - School/university names exactly as written
   - Degree names exactly as written
   - Graduation years exactly as written
   - All certifications exactly as written

✅ ENHANCE (improve phrasing only):
   - Make bullet points stronger by adding action verbs at the start
   - Add metrics/numbers where the original implies them (e.g., "managed team" → "Led team of X")
   - Incorporate missing keywords naturally into bullets and skills
   - Improve the summary to highlight relevant experience for this role

❌ NEVER DO:
   - Do not invent companies, jobs, or achievements
   - Do not change dates or durations
   - Do not add degrees or schools the person didn't attend
   - Do not add certifications the person doesn't have
   - Do not fabricate metrics — only add if implied by original

ENHANCEMENT EXAMPLES:
Original: "Worked on backend systems"
Enhanced: "Developed and maintained backend systems using Python and PostgreSQL"

Original: "Managed cloud infrastructure"
Enhanced: "Managed AWS cloud infrastructure including EC2, S3, and RDS services"

Original: "Led a team"
Enhanced: "Led cross-functional engineering team delivering features on schedule"

Return ONLY valid JSON with this exact structure:

{{
  "name": "Candidate's exact name from resume",
  "contact": "email  |  phone  |  location  |  linkedin (exactly as in original)",
  "summary": "2-3 sentence summary highlighting experience relevant to {job_title}",
  "experience": [
    {{
      "title": "Exact job title from original",
      "company": "Exact company name from original",
      "dates": "Exact dates from original",
      "location": "Exact location from original",
      "bullets": [
        "Enhanced bullet with action verb and relevant keywords",
        "Enhanced bullet preserving original achievement",
        "Enhanced bullet with metrics if implied in original"
      ]
    }}
  ],
  "skills": ["Original skills", "Plus missing keywords", "From job description"],
  "education": [
    {{
      "degree": "Exact degree from original",
      "school": "Exact school from original", 
      "year": "Exact year from original"
    }}
  ],
  "certifications": ["Exact certifications from original"]
}}"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You enhance resumes while strictly preserving all original facts. Never invent or fabricate information. Return only valid JSON."
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=4096,
            temperature=0.2,  # Low temperature = more faithful to original
        )

        raw = response.choices[0].message.content.strip()

        # Clean markdown wrappers
        raw = re.sub(r'^```json\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'^```\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)

        result = json.loads(raw)

        # Ensure all required fields exist
        if not result.get("name"):
            result["name"] = "Candidate"
        if not result.get("experience"):
            result["experience"] = []
        if not result.get("skills"):
            result["skills"] = missing_keywords[:20] if missing_keywords else []
        if not result.get("education"):
            result["education"] = []
        if not result.get("certifications"):
            result["certifications"] = []

        return result

    except json.JSONDecodeError as e:
        print(f"[Resume Enhance] JSON parse error: {e}")
        return _fallback_structured_resume(resume_text, job_title, missing_keywords)

    except Exception as e:
        print(f"[Resume Enhance] Error: {e}")
        return _fallback_structured_resume(resume_text, job_title, missing_keywords)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _simulated_response() -> dict:
    return {
        "overall_score": 45.0,
        "keywords_matched": 5,
        "keywords_missing": 8,
        "total_keywords": 13,
        "missing_list": ["Add GROQ_API_KEY for real analysis — free at console.groq.com"],
        "breakdown": {
            "action_verbs": {"score": 50, "count": 4},
            "technical_skills": {"score": 40, "count": 3},
            "soft_skills": {"score": 45, "count": 2},
        },
        "suggestions": ["Add GROQ_API_KEY to enable AI-powered resume enhancement"],
    }


def _error_response(message: str) -> dict:
    return {
        "overall_score": 0,
        "keywords_matched": 0,
        "keywords_missing": 0,
        "total_keywords": 0,
        "missing_list": [],
        "breakdown": {
            "action_verbs": {"score": 0, "count": 0},
            "technical_skills": {"score": 0, "count": 0},
            "soft_skills": {"score": 0, "count": 0},
        },
        "suggestions": [],
        "error": message,
    }


def _fallback_structured_resume(
    resume_text: str,
    job_title: str,
    missing_keywords: list | None,
) -> dict:
    """
    Fallback parser when AI is unavailable.
    Extracts sections from raw resume text using regex.
    """
    lines = [l.strip() for l in (resume_text or "").split("\n") if l.strip()]

    # ── Name (first non-contact line)
    name = "Candidate"
    for line in lines:
        if len(line) < 60 and not any(c in line.lower() for c in ["@", "http", "+", "linkedin", "|", "phone", "email"]):
            name = line
            break

    # ── Contact info
    contact_parts = []
    for line in lines[:10]:
        if any(k in line.lower() for k in ["@", "linkedin", "github"]):
            contact_parts.append(line)
        elif re.search(r'\+?\d[\d\s\-\(\)]{7,}', line):
            contact_parts.append(line)
    contact = "  |  ".join(dict.fromkeys(contact_parts))

    # ── Section detection
    SECTION_MAP = {
        "summary": r'^(professional\s+summary|summary|objective|profile|about)',
        "experience": r'^((work\s+)?experience|professional\s+experience|employment|work\s+history)',
        "skills": r'^((technical\s+)?skills|core\s+(skills|competencies)|technologies|expertise)',
        "education": r'^education',
        "certifications": r'^(certifications?|licenses?|credentials)',
        "projects": r'^(projects|portfolio)',
    }

    sections = {k: [] for k in SECTION_MAP}
    current_sec = None

    for line in lines:
        matched = False
        for sec, pattern in SECTION_MAP.items():
            if re.match(pattern, line, re.I) and len(line) < 50:
                current_sec = sec
                matched = True
                break
        if not matched and current_sec:
            sections[current_sec].append(line)

    # ── Summary
    summary = " ".join(sections["summary"]).strip()
    if not summary:
        summary = f"Experienced professional seeking {job_title} role."

    # ── Experience
    exp_lines = sections["experience"]
    job_entries = []
    current_job = None
    bullets = []

    for line in exp_lines:
        is_bullet = line.startswith(("•", "-", "*", "–", "▸", "●"))
        is_date = bool(re.search(r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|20\d{2}|19\d{2}|present)\b', line, re.I))
        
        if not is_bullet and len(line) < 100 and not is_date and line[0:1].isupper():
            if current_job and bullets:
                current_job["bullets"] = bullets[:]
                job_entries.append(current_job)
            current_job = {"title": line, "company": "", "dates": "", "location": "", "bullets": []}
            bullets = []
        elif is_date and current_job:
            current_job["dates"] = line
        elif current_job and not current_job.get("company") and not is_bullet and not is_date:
            current_job["company"] = line
        elif is_bullet or (len(line) > 30 and current_job):
            clean = line.lstrip("•-*–▸● ").strip()
            if clean and len(clean) > 10:
                bullets.append(clean)

    if current_job:
        current_job["bullets"] = bullets[:]
        job_entries.append(current_job)

    if not job_entries:
        job_entries = [{"title": job_title, "company": "", "dates": "", "location": "", "bullets": ["Professional experience in the field."]}]

    # ── Skills
    skills = []
    for line in sections["skills"]:
        for part in re.split(r"[,|·•\t]", line):
            clean = part.strip().lstrip("-*• ")
            if clean and 2 < len(clean) < 50:
                skills.append(clean)

    # Add missing keywords
    existing_lower = {s.lower() for s in skills}
    for kw in (missing_keywords or []):
        if kw and kw.lower() not in existing_lower and not kw.startswith("Add GROQ"):
            skills.append(kw)
            existing_lower.add(kw.lower())

    # ── Education
    education = []
    current_edu = {}
    for line in sections["education"]:
        if re.search(r'\b(bachelor|master|bsc|msc|b\.?s\.?|m\.?s\.?|phd|diploma|associate|degree)\b', line, re.I):
            if current_edu and current_edu.get("degree"):
                education.append(current_edu)
            current_edu = {"degree": line, "school": "", "year": ""}
        elif current_edu and not current_edu.get("school"):
            if not re.search(r'\b(19|20)\d{2}\b', line):
                current_edu["school"] = line
        year_match = re.search(r'\b(19|20)\d{2}\b', line)
        if year_match and current_edu:
            current_edu["year"] = year_match.group()
    
    if current_edu and current_edu.get("degree"):
        education.append(current_edu)

    # ── Certifications
    certifications = []
    for line in sections["certifications"]:
        clean = line.lstrip("•-*– ").strip()
        if clean and len(clean) > 3:
            certifications.append(clean)

    return {
        "name": name,
        "contact": contact,
        "summary": summary,
        "experience": job_entries,
        "skills": skills[:35],
        "education": education,
        "certifications": certifications,
        "projects": [],
    }