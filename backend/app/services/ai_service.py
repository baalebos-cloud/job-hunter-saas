import json
import os
import httpx # You might need to add 'httpx' to requirements.txt

class AIService:
    def __init__(self):
        self.model = os.getenv("AI_MODEL", "gpt-4o") # or 'llama3' for Ollama
        self.api_key = os.getenv("OPENAI_API_KEY")

    async def analyze_resume(self, resume_text: str, job_description: str = ""):
        """
        The core engine that performs the ATS scoring and gap analysis.
        """
        prompt = f"""
        Analyze this resume against the following job description.
        Resume: {resume_text[:4000]}
        Job Description: {job_description}
        
        Return ONLY a JSON object with:
        {{
          "ats_score": (0-100),
          "technical_skills": {{"score": 0, "found": [], "missing": []}},
          "suggestions": ["list of 3 improvements"]
        }}
        """

        # --- MOCK MODE (What you see now) ---
        if not self.api_key and self.model != "llama3":
            return {
                "ats_score": 75.0,
                "technical_skills": {"score": 70, "found": ["Python", "Docker"], "missing": ["AWS RDS"]},
                "suggestions": ["Add more Cloud Computing keywords", "Quantify your impact"]
            }

        # --- REAL MODE (OpenAI Example) ---
        # (This is where we add the actual API call logic)
        return {"status": "AI Logic goes here"}

ai_engine = AIService()
