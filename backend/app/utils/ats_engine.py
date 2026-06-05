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


# ─── AI Client ────────────────────────────────────────────────────────────────

def get_client():
    """Groq preferred (free + fast), falls back to OpenRouter."""
    if getattr(settings, 'GROQ_API_KEY', None):
        return OpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
        ), "llama3-8b-8192"
    if getattr(settings, 'OPENROUTER_API_KEY', None):
        return OpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
        ), "anthropic/claude-3-haiku"
    return None, None


def _clean_json(raw: str) -> str:
    raw = re.sub(r'^```json\s*', '', raw.strip())
    raw = re.sub(r'^```\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    return raw.strip()


# ─── ATS Scoring ──────────────────────────────────────────────────────────────

def analyze_detailed_ats(file_content: bytes, filename: str, job_description: str) -> dict:
    resume_text = extract_text(file_content, filename)
    if not resume_text:
        return _error_response("Could not extract text. Please use a text-based PDF or DOCX.")

    client, model = get_client()
    if not client:
        return _simulated_response()

    prompt = f"""
You are a Senior Technical Recruiter and ATS expert.
Analyze this resume against the job description below.

JOB DESCRIPTION:
{job_description[:2000]}

RESUME:
{resume_text[:3000]}

Return ONLY valid JSON in this exact format:
{{
    "overall_score": 78,
    "keywords_matched": 14,
    "keywords_missing": 6,
    "total_keywords": 20,
    "missing_list": ["Terraform", "Kubernetes", "CI/CD", "Helm", "Prometheus", "AWS RDS"],
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
Return ONLY the JSON. No markdown. No explanation.
"""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an ATS expert. Respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.3,
        )
        result = json.loads(_clean_json(response.choices[0].message.content))
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
    except Exception as e:
        print(f"[ATS] Error: {e}")
        return _error_response(str(e))


# ─── Resume Data Extraction ───────────────────────────────────────────────────

def extract_resume_data(file_content: bytes, filename: str, job_title: str) -> dict:
    """
    Extracts structured resume data for professional PDF generation.
    Returns name, title, contact, summary, experience, education, skills, certifications.
    """
    resume_text = extract_text(file_content, filename)
    if not resume_text:
        return {}

    client, model = get_client()
    if not client:
        return {}

    prompt = f"""
Extract structured data from this resume. Return ONLY valid JSON, no extra text.

RESUME:
{resume_text[:4000]}

TARGET JOB TITLE: {job_title}

Return this exact JSON structure:
{{
    "name": "Full Name",
    "title": "Current Job Title | Target Role",
    "contact": "Location  |  Phone  |  Email  |  LinkedIn",
    "summary": "Professional summary paragraph",
    "experience": [
        {{
            "role": "Job Title",
            "company": "Company Name",
            "location": "City, Country",
            "dates": "Month Year – Month Year",
            "bullets": [
                "Achievement bullet point with metrics",
                "Another achievement bullet point"
            ]
        }}
    ],
    "education": [
        {{
            "degree": "Degree Name",
            "institution": "Institution Name",
            "year": "Year or In Progress"
        }}
    ],
    "skills": {{
        "Category Name": ["skill1", "skill2", "skill3"]
    }},
    "certifications": [
        "Certification Name 1",
        "Certification Name 2"
    ]
}}

Rules:
- Extract REAL data only, do not invent anything
- Keep bullets concise and achievement-focused
- Return ONLY the JSON, no markdown
"""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You extract structured resume data and return valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000,
            temperature=0.1,
        )
        return json.loads(_clean_json(response.choices[0].message.content))
    except Exception as e:
        print(f"[ATS] Resume extraction error: {e}")
        return {}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _simulated_response() -> dict:
    return {
        "overall_score": 45.0,
        "keywords_matched": 5,
        "keywords_missing": 8,
        "total_keywords": 13,
        "missing_list": ["Add GROQ_API_KEY or OPENROUTER_API_KEY to .env for real analysis"],
        "breakdown": {
            "action_verbs": {"score": 50, "count": 4},
            "technical_skills": {"score": 40, "count": 3},
            "soft_skills": {"score": 45, "count": 2}
        },
        "suggestions": ["Add your Groq or OpenRouter API key to enable real AI analysis"]
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
