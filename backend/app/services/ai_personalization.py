from typing import List, Dict
import re

def extract_skills_and_verbs(resume_text: str) -> Dict[str, List[str]]:
    """
    Extracts action verbs, soft skills, technical skills, certifications, education.
    """
    # Simple placeholders; replace with real NLP or ML later
    action_verbs = re.findall(r"\b(managed|developed|implemented|designed|led|created)\b", resume_text, re.I)
    soft_skills = re.findall(r"\b(communication|teamwork|leadership|problem solving)\b", resume_text, re.I)
    technical_skills = re.findall(r"\b(python|sql|aws|docker|fastapi|react)\b", resume_text, re.I)
    certifications = re.findall(r"\b(AWS Certified|PMP|Scrum Master)\b", resume_text, re.I)
    education = re.findall(r"\b(Bachelor|Master|PhD)\b", resume_text, re.I)

    return {
        "action_verbs": list(set(action_verbs)),
        "soft_skills": list(set(soft_skills)),
        "technical_skills": list(set(technical_skills)),
        "certifications": list(set(certifications)),
        "education": list(set(education)),
    }


def score_resume_against_job(resume_text: str, job_description: str) -> float:
    """
    Returns a simple match score (0-100) based on keyword overlap.
    """
    resume_words = set(resume_text.lower().split())
    job_words = set(job_description.lower().split())
    overlap = resume_words.intersection(job_words)
    score = len(overlap) / max(len(job_words), 1) * 100
    return round(score, 2)
