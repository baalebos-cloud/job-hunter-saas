import openai
import requests
from bs4 import BeautifulSoup

openai.api_key = "YOUR_OPENAI_API_KEY"  # secure via env vars

def fetch_job_description(job_url: str):
    """
    Fetch the job description text from the job URL
    """
    response = requests.get(job_url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    # RemoteOK: main description is usually inside div with class "description"
    desc = soup.find("div", class_="description")
    return desc.get_text(separator="\n").strip() if desc else ""

def generate_message(job_url: str, candidate_name: str, resume_text: str):
    """
    Generate a personalized outreach message for the recruiter
    """
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

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )

    return response.choices[0].message.content
