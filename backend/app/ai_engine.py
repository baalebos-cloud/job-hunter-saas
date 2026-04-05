import httpx
import os
import json

# Fetching the key from the environment variable injected by GitHub/Docker
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

async def get_resume_match_score(resume_markdown: str, job_description: str):
    if not OPENROUTER_API_KEY:
        return {"error": "API Key missing", "match_score": 0}

    prompt = f"""
    Compare this Resume to the Job Description. 
    Resume: {resume_markdown[:4000]} 
    JD: {job_description[:2000]}
    
    Return a JSON object: 
    {{"match_score": int, "pros": [], "cons": [], "summary": ""}}
    """

    payload = {
        "model": "google/gemini-2.0-flash-001", # High speed, low cost for 2026
        "messages": [{"role": "user", "content": prompt}],
        "response_format": { "type": "json_object" }
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(OPENROUTER_URL, headers=headers, json=payload, timeout=20.0)
            # Parse the text response into a Python dictionary
            result = response.json()
            # OpenRouter returns nested content in 'choices'
            ai_content = result['choices'][0]['message']['content']
            return json.loads(ai_content)
        except Exception as e:
            return {"error": str(e), "match_score": 0}
