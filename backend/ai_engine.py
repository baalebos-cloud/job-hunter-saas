import os
from openai import OpenAI
from pypdf import PdfReader
import io

# Initialize client using OpenRouter base URL
client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=os.getenv("OPENROUTER_API_KEY"),
)

async def analyze_resume_stateless(file_bytes: bytes, job_description: str):
    # 1. Read PDF from memory (No Disk Storage)
    reader = PdfReader(io.BytesIO(file_bytes))
    resume_text = ""
    for page in reader.pages:
        resume_text += page.extract_text()

    # 2. Call OpenRouter (Using a cheap/free model like GPT-4o-mini or Gemini Flash)
    response = client.chat.completions.create(
      extra_headers={
        "HTTP-Referer": "https://baalebo.xyz", # Required by OpenRouter
        "X-Title": "Baalebos AI", 
      },
      model="google/gemini-flash-1.5-8b", # Very cheap/professional
      messages=[
        {"role": "system", "content": "You are a professional recruiter. Compare the resume to the job description and return a match score (0-100) and 3 bullet points of feedback. Return ONLY JSON."},
        {"role": "user", "content": f"Job: {job_description}\n\nResume: {resume_text}"}
      ]
    )
    
    # 3. Return the result (Resume text is now deleted from RAM)
    return response.choices[0].message.content
