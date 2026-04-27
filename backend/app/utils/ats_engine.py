import io
import pdfplumber
from docx import Document
import json
import os
import openai
from backend.app.core.config import settings

# Keep your extraction logic – it's clean and works well!
def extract_text(file_content, filename):
    file_ext = filename.split('.')[-1].lower()
    text = ""
    try:
        if file_ext == "pdf":
            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                for page in pdf.pages:
                    text += (page.extract_text() or "") + " "
        elif file_ext in ["docx", "doc"]:
            doc = Document(io.BytesIO(file_content))
            for para in doc.paragraphs:
                text += para.text + " "
    except Exception as e:
        print(f"Extraction Error: {e}")
    return text.strip()

def analyze_detailed_ats(file_content, filename, job_description):
    """
    The Brain: Uses OpenAI to analyze the resume against the JD.
    """
    resume_text = extract_text(file_content, filename)
    
    # 1. Check if we have an API Key. If not, use a 'Simulated' smart response.
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "your_openai_key_here":
        return {
            "overall_score": 45.0,
            "keywords_matched": 0,
            "keywords_missing": 0,
            "missing_list": ["API Key Missing"],
            "breakdown": {"System": "Please add OPENAI_API_KEY to .env to see real AI analysis."}
        }

    # 2. Construct the "Expert Recruiter" Prompt
    client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    
    prompt = f"""
    You are a Senior Technical Recruiter. Analyze this resume against the Job Description.
    
    JOB DESCRIPTION:
    {job_description}
    
    RESUME TEXT:
    {resume_text[:4000]}
    
    Return a JSON object exactly in this format:
    {{
        "overall_score": 85,
        "keywords_matched": 12,
        "keywords_missing": 4,
        "total_keywords": 16,
        "missing_list": ["Terraform", "Kubernetes", "AWS RDS"],
        "breakdown": {{
            "technical_skills": "Strong in Python and Docker, but lacks IaC experience.",
            "soft_skills": "Good leadership evidence shown in project management.",
            "action_verbs": "Strong use of impact-oriented verbs."
        }},
        "suggestions": ["Add a section for Cloud certifications", "Quantify your DevOps achievements"]
    }}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o", # Using 4o for high-speed, high-quality analysis
            messages=[
                {"role": "system", "content": "You are a helpful assistant that outputs JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={ "type": "json_object" }
        )
        
        # 3. Parse and return the AI's "Deep Thought"
        return json.loads(response.choices[0].message.content)

    except Exception as e:
        print(f"AI Analysis Crash: {e}")
        return {
            "overall_score": 0,
            "error": "The AI engine encountered an error during analysis."
        }
