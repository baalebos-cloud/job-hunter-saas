import io
import json
import re
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
                    text += (page.extract_text() or "") + " "
        elif ext in ["docx", "doc"]:
            doc = Document(io.BytesIO(file_content))
            for para in doc.paragraphs:
                text += para.text + " "
    except Exception as e:
        print(f"[ATS] Extraction Error: {e}")
    return text.strip()


# ─── Main Analysis Function ───────────────────────────────────────────────────

def analyze_detailed_ats(file_content: bytes, filename: str, job_description: str) -> dict:
    """
    Uses Groq (free & unlimited) to score a resume against a job description.
    Model: llama-3.3-70b-versatile — fast, free, no credit card required.
    Get your key at: https://console.groq.com
    """
    resume_text = extract_text(file_content, filename)

    if not resume_text:
        return _error_response("Could not extract text from resume. Please use a text-based PDF or DOCX.")

    if not settings.GROQ_API_KEY:
        return _simulated_response()

    # Groq uses the same OpenAI SDK interface — just different base_url
    client = OpenAI(
        api_key=settings.GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1",
    )

    prompt = f"""You are a Senior Technical Recruiter and ATS expert. Analyze the resume against the job description below.

JOB DESCRIPTION:
{job_description[:2000]}

RESUME:
{resume_text[:3000]}

Return ONLY a valid JSON object in exactly this format, no extra text:
{{
    "overall_score": 78,
    "keywords_matched": 14,
    "keywords_missing": 6,
    "total_keywords": 20,
    "missing_list": ["Terraform", "Kubernetes", "AWS RDS", "CI/CD", "Helm", "Prometheus"],
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
- overall_score must be a number between 0 and 100
- missing_list must be an array of strings (the actual missing keywords from the job description)
- breakdown scores must be numbers between 0 and 100
- Return ONLY the JSON, no markdown, no explanation"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # Free on Groq, very fast
            messages=[
                {"role": "system", "content": "You are an ATS analysis expert. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.3,
        )

        raw = response.choices[0].message.content.strip()

        # Strip markdown code blocks if present
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
                "soft_skills": {"score": 0, "count": 0}
            }),
            "suggestions": result.get("suggestions", []),
        }

    except json.JSONDecodeError as e:
        print(f"[ATS] JSON parse error: {e} | Raw: {raw[:200]}")
        return _error_response("AI returned invalid response. Please try again.")
    except Exception as e:
        print(f"[ATS] Groq error: {e}")
        return _error_response(str(e))


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _simulated_response() -> dict:
    """Returned when no GROQ_API_KEY is configured."""
    return {
        "overall_score": 45.0,
        "keywords_matched": 5,
        "keywords_missing": 8,
        "total_keywords": 13,
        "missing_list": ["Add GROQ_API_KEY to .env for real AI analysis — free at console.groq.com"],
        "breakdown": {
            "action_verbs": {"score": 50, "count": 4},
            "technical_skills": {"score": 40, "count": 3},
            "soft_skills": {"score": 45, "count": 2}
        },
        "suggestions": ["Sign up free at console.groq.com and add your GROQ_API_KEY to .env to enable real AI analysis"]
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
            "soft_skills": {"score": 0, "count": 0}
        },
        "suggestions": [],
        "error": message
    }


# ─── AI Resume Rewriter ───────────────────────────────────────────────────────────────

def rewrite_resume_for_job(resume_text: str, job_description: str, job_title: str,
                           missing_keywords: list, context_phrases: list = None) -> dict:
    """
    Uses Groq to fully rewrite the resume tailored to the specific job.
    Returns a structured dict with all resume sections ready for PDF rendering.
    """
    if not settings.GROQ_API_KEY:
        return _fallback_structured_resume(resume_text, job_title, missing_keywords)

    client = OpenAI(
        api_key=settings.GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1",
    )

    missing_str = ", ".join(missing_keywords[:15]) if missing_keywords else "none"
    phrases_str = "; ".join((context_phrases or [])[:5]) if context_phrases else "none"

    prompt = f"""You are an expert resume writer. Rewrite the candidate's resume to be perfectly tailored for the job below.

JOB TITLE: {job_title}

JOB DESCRIPTION:
{job_description[:2000]}

ORIGINAL RESUME (complete — do not skip any section):
{resume_text[:5000]}

SKILL KEYWORDS TO ADD TO SKILLS SECTION: {missing_str}
CONTEXT TO WEAVE INTO BULLET POINTS (do NOT add these as skills): {phrases_str}

CRITICAL INSTRUCTIONS:
1. Extract and preserve ALL sections: name, contact, summary, ALL work experience, ALL skills, ALL education, ALL certifications
2. Do NOT invent or fabricate any experience, company, or qualification
3. Rewrite bullet points with stronger action verbs and quantified achievements
4. Add SKILL KEYWORDS naturally into the skills array (short technical terms only)
5. Weave CONTEXT PHRASES naturally into existing bullet points where truthful
6. Include EVERY skill from the original resume PLUS the skill keywords above
7. Include ALL education entries from the original resume
8. Include ALL certifications from the original resume
9. Skills array must contain ONLY short technical terms (e.g. "Helm", "Kubernetes") NOT sentences

Return ONLY a valid JSON object:
{{
  "name": "exact name from resume",
  "contact": "email | phone | location | linkedin",
  "summary": "2-3 sentence tailored summary mentioning {job_title}",
  "experience": [
    {{
      "title": "exact job title",
      "company": "exact company name",
      "dates": "exact dates",
      "location": "",
      "bullets": ["Strong action verb + achievement + metric"]
    }}
  ],
  "skills": ["only short technical skill terms"],
  "education": [
    {{"degree": "exact degree", "school": "exact school", "year": "year"}}
  ],
  "certifications": ["every certification from original resume"]
}}

Return ONLY the JSON. No markdown. No explanation."""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are an expert resume writer. Extract ALL sections from the resume. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=4000,
            temperature=0.3,
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r'^```json\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'^```\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)
        result = json.loads(raw)
        return result
    except Exception as e:
        print(f"[Resume Rewrite] Error: {e}")
        return _fallback_structured_resume(resume_text, job_title, missing_keywords)


def _fallback_structured_resume(resume_text: str, job_title: str, missing_keywords: list) -> dict:
    """Parse raw resume text into structured sections when AI is unavailable."""
    lines = [l.strip() for l in resume_text.split('\n') if l.strip()]
    name = lines[0] if lines else "Candidate"
    contact = lines[1] if len(lines) > 1 else ""

    # Extract bullets from body
    bullets = [l.lstrip('•-* ') for l in lines[2:] if l.startswith(('•', '-', '*', '–'))]
    non_bullets = [l for l in lines[2:] if not l.startswith(('•', '-', '*', '–'))]

    return {
        "name": name,
        "contact": contact,
        "summary": f"Experienced professional seeking {job_title} role. Skilled in delivering high-impact solutions.",
        "experience": [{"title": job_title, "company": "Previous Employer", "dates": "",
                        "bullets": bullets[:8] or ["Delivered key projects aligned with business objectives."]}],
        "skills": missing_keywords[:12] if missing_keywords else ["See resume for full skill set"],
        "education": [],
        "certifications": []
    }
