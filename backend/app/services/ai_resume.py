import os
from openai import OpenAI


def tailor_resume(job_description: str, resume: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return "AI tailoring unavailable: no API key configured."

    client = OpenAI(api_key=api_key)
    prompt = f"""Customize this resume for the job.\n\nJob:\n{job_description}\n\nResume:\n{resume}"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content
