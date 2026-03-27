import io
import pdfplumber
from docx import Document
import re

# Simple Keyword Dictionaries (We can expand these globally)
CATEGORIES = {
    "technical_skills": ["aws", "devops", "ci/cd", "iac", "oracle", "oci", "database", "devsecops", "python", "docker", "kubernetes"],
    "soft_skills": ["leadership", "communication", "problem solving", "teamwork"],
    "action_verbs": ["managed", "developed", "implemented", "optimized", "built"]
}

def extract_text(file_content, filename):
    file_ext = filename.split('.')[-1].lower()
    text = ""
    if file_ext == "pdf":
        with pdfplumber.open(io.BytesIO(file_content)) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + " "
    elif file_ext == "docx":
        doc = Document(io.BytesIO(file_content))
        for para in doc.paragraphs:
            text += para.text + " "
    return text.lower()

def analyze_detailed_ats(file_content, filename, job_description):
    resume_text = extract_text(file_content, filename)
    job_desc = job_description.lower()
    
    # 1. Identify "Target Keywords" from the Job Description
    # In a real app, we'd use NLP to find these. Here we check our dictionary.
    target_keywords = [word for cat in CATEGORIES.values() for word in cat if word in job_desc]
    
    # 2. Check which targets exist in the Resume
    matched = [word for word in target_keywords if word in resume_text]
    missing = [word for word in target_keywords if word not in resume_text]
    
    # 3. Category Breakdown Calculation
    breakdown = {}
    for cat_name, words in CATEGORIES.items():
        cat_targets = [w for w in words if w in job_desc]
        if not cat_targets:
            breakdown[cat_name] = {"score": 100, "count": "0/0"}
            continue
            
        cat_matched = [w for w in cat_targets if w in resume_text]
        score = (len(cat_matched) / len(cat_targets)) * 100
        breakdown[cat_name] = {
            "score": round(score, 2),
            "count": f"{len(cat_matched)}/{len(cat_targets)}"
        }

    # 4. Final Score (Weighted average or simple ratio)
    final_score = (len(matched) / len(target_keywords)) * 100 if target_keywords else 0

    return {
        "overall_score": round(final_score, 2),
        "keywords_matched": len(matched),
        "keywords_missing": len(missing),
        "total_keywords": len(target_keywords),
        "missing_list": missing,
        "breakdown": breakdown
    }
