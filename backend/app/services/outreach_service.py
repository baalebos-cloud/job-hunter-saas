import logging
import re
from openai import OpenAI
from backend.app.core.config import settings

logger = logging.getLogger(__name__)


def generate_message(
    job_title: str,
    company: str,
    job_description: str,
    candidate_name: str,
    resume_text: str,
) -> str:
    """
    Generates a tailored HR outreach message using Groq (free).
    Uses the job description already stored in the DB — no URL scraping needed.
    """
    if not settings.GROQ_API_KEY:
        return _fallback_message(candidate_name, job_title, company)

    client = OpenAI(
        api_key=settings.GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1",
    )

    prompt = f"""You are a professional career coach helping a job seeker write an outreach message to a recruiter or hiring manager.

JOB TITLE: {job_title}
COMPANY: {company}

JOB DESCRIPTION (first 1500 chars):
{job_description[:1500]}

CANDIDATE NAME: {candidate_name}

CANDIDATE RESUME (first 2000 chars):
{resume_text[:2000]}

Write a personalized, professional outreach message that:
1. Opens with a specific reference to the role and company (not generic)
2. Highlights 2-3 of the candidate's most relevant skills/achievements that match the job
3. Shows genuine enthusiasm for the specific company/role
4. Ends with a clear, polite call to action
5. Is between 100-150 words
6. Is suitable for LinkedIn InMail or email
7. Does NOT start with "I hope this message finds you well" or similar clichés

Return ONLY the message text. No subject line. No labels. No explanation."""

    try:
        response = client.chat.completions.create(
            # The configured Groq model (llama-3.3-70b-versatile was retired by Groq on 16 Aug 2026).
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are an expert career coach. Write professional, personalized outreach messages."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            **_length_options(settings.GROQ_MODEL),
        )
        message = (response.choices[0].message.content or '').strip()
        if not message:
            raise ValueError('empty outreach message')
        # Clean any markdown that slipped through
        message = re.sub(r'\*\*|__', '', message)
        return message
    except Exception as e:
        # Type only: provider errors can echo the resume text.
        logger.warning('outreach_generation_failed error_type=%s', type(e).__name__)
        return _fallback_message(candidate_name, job_title, company)


def _length_options(model: str) -> dict:
    """GPT-OSS models reason before answering and the budget covers both, so keep
    reasoning low and leave room for the ~150-word message."""
    if model.startswith('openai/gpt-oss'):
        return {'extra_body': {'reasoning_effort': 'low', 'max_completion_tokens': 1200}}
    return {'max_tokens': 300}


def _fallback_message(candidate_name: str, job_title: str, company: str) -> str:
    return (
        f"Hi,\n\n"
        f"My name is {candidate_name} and I came across the {job_title} opening at {company}. "
        f"I believe my background aligns well with what you're looking for and I'd love the opportunity "
        f"to discuss how I can contribute to your team.\n\n"
        f"I'd welcome the chance to connect at your convenience.\n\n"
        f"Best regards,\n{candidate_name}"
    )
