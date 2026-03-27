from typing import Dict
import re

from backend.app.database import SessionLocal
from backend.app.models.application import Application

# Sample keyword lists per category (can be expanded)
CATEGORY_KEYWORDS = {
    "action_verbs": ["developed", "implemented", "designed", "optimized", "managed", "led"],
    "certifications": ["AWS Certified", "PMP", "CCNA", "CISSP", "Scrum Master"],
    "education": ["B.Sc", "M.Sc", "Bachelor", "Master", "PhD"],
    "soft_skills": ["communication", "leadership", "teamwork", "problem solving", "adaptability"],
    "technical": ["Python", "SQL", "Docker", "Kubernetes", "Terraform", "React", "Flask"]
}


def extract_keywords(text: str, keywords: list) -> list:
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def analyze_resume(file_content: bytes, filename: str, job_description: str, track: str, user, user_email: str) -> Dict:
    """
    Analyze a resume against a job description and tech track.
    Returns ATS score, suggestions, highlights and also saves the result in DB.
    """

    db = SessionLocal()

    text = file_content.decode("utf-8", errors="ignore")

    # Track-specific technical keywords
    try:
        from backend.app.routes.resume import TECH_TRACKS
        track_keywords = CATEGORY_KEYWORDS["technical"]
        if track in TECH_TRACKS:
            track_keywords = list(set(track_keywords + TECH_TRACKS[track]))
    except Exception:
        track_keywords = CATEGORY_KEYWORDS["technical"]

    # Extract per category
    highlights = {
        "action_verbs": extract_keywords(text, CATEGORY_KEYWORDS["action_verbs"]),
        "certifications": extract_keywords(text, CATEGORY_KEYWORDS["certifications"]),
        "education": extract_keywords(text, CATEGORY_KEYWORDS["education"]),
        "soft_skills": extract_keywords(text, CATEGORY_KEYWORDS["soft_skills"]),
        "technical": extract_keywords(text, track_keywords)
    }

    # Simple ATS scoring
    job_keywords = re.findall(r"\b\w+\b", job_description.lower())
    matched_keywords = [kw for kw in job_keywords if kw in text.lower()]
    ats_score = round((len(matched_keywords) / max(len(job_keywords), 1)) * 100, 2)

    # Suggestions
    suggestions = [
        f"Consider adding more {cat.replace('_', ' ')}."
        for cat, items in highlights.items() if not items
    ]

    # SAVE RESULT TO DATABASE
    application = Application(
        user_email=user_email,
        job_title=track,
        company="ATS Resume Analysis",
        status="processed",
        ats_score=ats_score,
        improvements=str(suggestions)
    )

    db.add(application)
    db.commit()
    db.close()

    return {
        "ats_score": ats_score,
        "highlights": highlights,
        "improvement_suggestions": suggestions
    }


def generate_cover_letter(highlights: dict, job_description: str, track: str, user=None) -> str:
    full_name = getattr(user, "full_name", "Candidate") if user else "Candidate"

    return f"""
Dear Hiring Manager,

I am excited to apply for the {track.title()} position. My experience includes {', '.join(highlights.get('action_verbs', ['relevant projects']))}
and skills in {', '.join(highlights.get('technical', ['the required technologies']))}.
I hold certifications in {', '.join(highlights.get('certifications', ['relevant certifications']))} and have a strong background in {', '.join(highlights.get('education', ['my field']))}.

I am confident that my soft skills such as {', '.join(highlights.get('soft_skills', ['teamwork and adaptability']))} make me a great fit for your team.

Looking forward to contributing to your organization's success.

Best regards,
{full_name}
""".strip()


def generate_hr_message(highlights: dict, job_description: str, track: str, user=None) -> str:
    full_name = getattr(user, "full_name", "Candidate") if user else "Candidate"

    return f"Candidate {full_name} applied for {track.title()} track. Key highlights: {highlights}"
