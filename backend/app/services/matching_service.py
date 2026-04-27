def compute_match_score(resume_data: dict, job_description: str):
    """
    Basic AI matching logic (can be upgraded later with LLM)
    """

    skills = resume_data.get("technical_skills", [])
    job_text = job_description.lower()

    matched = [skill for skill in skills if skill.lower() in job_text]

    score = (len(matched) / (len(skills) + 1)) * 100

    missing = [skill for skill in skills if skill.lower() not in job_text]

    return {
        "score": round(score, 2),
        "matched_skills": matched,
        "missing_skills": missing
    }
