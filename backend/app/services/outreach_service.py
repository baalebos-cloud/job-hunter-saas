import os
import requests
from bs4 import BeautifulSoup
from openai import OpenAI


def fetch_job_description(job_url: str) -> str:
    response = requests.get(job_url, timeout=10)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    desc = soup.find("div", class_="description")
    return desc.get_text(separator="\n").strip() if desc else ""


def generate_message(job_url: str, candidate_name: str, resume_text: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return "AI outreach unavailable: no API key configured."

    job_description = fetch_job_description(job_url)

    prompt = f"""
    You are a professional recruiter assistant.
    Create a personalized, concise, friendly outreach message to a recruiter
    based on the following job description and candidate resume.

    Candidate Name: {candidate_name}

    Job Description:
    {job_description}

    Candidate Resume:
    {resume_text}

    The message should:
    - Be no longer than 150 words
    - Highlight the candidate's key skills relevant to the job
    - Show enthusiasm for the role
    - Be suitable for LinkedIn InMail or email
    """

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return response.choices[0].message.content
