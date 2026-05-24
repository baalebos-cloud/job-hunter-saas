"""
Expert-Grade ATS Engine — AI-Powered Resume Optimization
Produces compelling, metrics-driven resumes that impress both ATS systems AND human recruiters.
"""

import io
import re
import json
import pdfplumber
from docx import Document
from openai import OpenAI
from backend.app.core.config import settings


# ─── Text Extraction ──────────────────────────────────────────────────────────

def extract_text(file_content: bytes, filename: str) -> str:
    ext = filename.split('.')[-1].lower()
    text = ""
    try:
        if ext == "pdf":
            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                for page in pdf.pages:
                    text += (page.extract_text() or "") + " "
        elif ext in ["docx", "doc"]:
            doc = Document(io.BytesIO(file_content))
            for para in doc.paragraphs:
                text += para.text + " "
    except Exception as e:
        print(f"[ATS] Extraction Error: {e}")
    return text.strip()


# ─── ATS Scoring ─────────────────────────────────────────────────────────────

def analyze_detailed_ats(file_content: bytes, filename: str, job_description: str) -> dict:
    resume_text = extract_text(file_content, filename)

    if not resume_text:
        return _error_response("Could not extract text from resume. Please use a text-based PDF or DOCX.")

    if not settings.GROQ_API_KEY:
        return _simulated_response()

    client = OpenAI(
        api_key=settings.GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1",
    )

    prompt = f"""You are a Senior ATS (Applicant Tracking System) expert and technical recruiter with 15+ years of experience.
Analyze this resume against the job description and score it accurately.

JOB DESCRIPTION:
{job_description[:2500]}

RESUME:
{resume_text[:3500]}

Score the resume on these criteria:
1. Keyword match — how many job description keywords appear in the resume
2. Action verbs — strong verbs like "Architected", "Deployed", "Automated", "Reduced", "Spearheaded"
3. Quantified achievements — metrics like percentages, numbers, dollar amounts, time saved
4. Job title alignment — does the resume title/summary match the target job title
5. Skills coverage — technical skills required vs present

Return ONLY valid JSON:
{{
    "overall_score": 78,
    "keywords_matched": 14,
    "keywords_missing": 6,
    "total_keywords": 20,
    "missing_list": ["Terraform", "Kubernetes", "AWS RDS", "CI/CD", "Helm"],
    "breakdown": {{
        "action_verbs": {{"score": 80, "count": 8}},
        "technical_skills": {{"score": 65, "count": 12}},
        "soft_skills": {{"score": 70, "count": 5}}
    }},
    "suggestions": [
        "Add Terraform and Kubernetes to your skills section",
        "Quantify your DevOps achievements with specific metrics",
        "Mirror the job title in your resume headline"
    ]
}}

Rules:
- overall_score must be a number 0-100
- missing_list must be actual missing keywords from the job description (short terms only, max 2-3 words each)
- Return ONLY the JSON, no markdown, no explanation"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are an ATS analysis expert. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.2,
        )

        raw = response.choices[0].message.content.strip()
        raw = re.sub(r'^```json\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'^```\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)

        result = json.loads(raw)

        return {
            "overall_score": float(result.get("overall_score", 0)),
            "keywords_matched": int(result.get("keywords_matched", 0)),
            "keywords_missing": int(result.get("keywords_missing", 0)),
            "total_keywords": int(result.get("total_keywords", 0)),
            "missing_list": result.get("missing_list", []),
            "breakdown": result.get("breakdown", {
                "action_verbs": {"score": 0, "count": 0},
                "technical_skills": {"score": 0, "count": 0},
                "soft_skills": {"score": 0, "count": 0},
            }),
            "suggestions": result.get("suggestions", []),
        }

    except json.JSONDecodeError as e:
        print(f"[ATS] JSON parse error: {e} | Raw: {raw[:200]}")
        return _error_response("AI returned invalid response. Please try again.")
    except Exception as e:
        print(f"[ATS] Groq error: {e}")
        return _error_response(str(e))


# ─── AI Resume Rewriter ───────────────────────────────────────────────────────

def rewrite_resume_for_job(
    resume_text: str,
    job_description: str,
    job_title: str,
    missing_keywords: list,
    context_phrases: list = None,
) -> dict:
    """
    Rewrites the resume to achieve 96%+ ATS score AND impress human recruiters.
    Returns a structured dict ready for pdf_generator.generate_optimized_resume().
    """
    if not settings.GROQ_API_KEY:
        return _fallback_structured_resume(resume_text, job_title, missing_keywords)

    client = OpenAI(
        api_key=settings.GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1",
    )

    missing_str = ", ".join(missing_keywords[:20]) if missing_keywords else "none identified"
    context_str = "; ".join(context_phrases[:5]) if context_phrases else ""

    prompt = f"""You are an ELITE resume writer who has helped 10,000+ candidates land jobs at Google, Amazon, Meta, and top startups. Your resumes achieve 96%+ ATS scores AND impress human recruiters in 6 seconds.

TARGET ROLE: {job_title}

JOB DESCRIPTION (extract EVERY keyword and requirement):
{job_description[:3500]}

CANDIDATE'S ORIGINAL RESUME (preserve ALL facts, improve presentation):
{resume_text[:5500]}

MISSING KEYWORDS TO WEAVE IN: {missing_str}
{f"CONTEXT TO INCORPORATE: {context_str}" if context_str else ""}

═══════════════════════════════════════════════════════════════════════════════
YOUR MISSION: Transform this resume into a POWERFUL document that:
1. Passes ALL ATS filters with 96%+ keyword match
2. Makes recruiters say "WOW, we need to interview this person" in 6 seconds
3. Tells a compelling career story with IMPACT and RESULTS
═══════════════════════════════════════════════════════════════════════════════

ELITE RESUME RULES (follow ALL):

📌 PROFESSIONAL SUMMARY (3 powerful sentences):
   - Sentence 1: "[Job Title] with [X] years driving [key outcome] at [company type]"
   - Sentence 2: "Delivered [biggest quantified achievement] resulting in [business impact]"
   - Sentence 3: "Expert in [top 3-4 skills from JD] seeking to [value proposition for this role]"

📌 EXPERIENCE BULLETS (5-7 per role, each MUST follow this formula):
   [POWER VERB] + [specific what you did] + [quantified result] + [business impact]
   
   EXCELLENT: "Architected CI/CD pipeline reducing deployment time from 4 hours to 12 minutes, enabling 15x faster feature releases"
   EXCELLENT: "Spearheaded migration of 50+ microservices to Kubernetes, achieving 99.99% uptime and $2.4M annual cost savings"
   EXCELLENT: "Led cross-functional team of 8 engineers to deliver real-time analytics platform processing 10M events/day"
   
   BAD: "Worked on CI/CD pipelines" (no metrics, no impact)
   BAD: "Responsible for cloud infrastructure" (passive, no results)
   
   POWER VERBS to use: Architected, Engineered, Spearheaded, Drove, Delivered, Reduced, Increased, Automated, Transformed, Led, Optimized, Scaled, Built, Designed, Implemented, Orchestrated, Pioneered, Accelerated

📌 METRICS (every bullet needs at least ONE):
   - Percentages: "reduced by 40%", "improved by 3x", "increased 150%"
   - Numbers: "team of 8", "12 microservices", "$2M pipeline", "50+ services"
   - Time: "in 3 months", "from 4 hours to 12 minutes", "within 6 weeks"
   - Scale: "serving 2M users", "processing 50K requests/sec", "10M daily events"

📌 SKILLS (comprehensive, from job description):
   - Include EVERY skill mentioned in the job description
   - Add the missing keywords naturally
   - Keep each skill 1-3 words (no sentences)
   - Order by relevance to the job

📌 STRICT RULES:
   - NEVER fabricate companies, degrees, dates, or certifications
   - PRESERVE all existing metrics from the original (never replace "reduced 47%" with "reduced significantly")
   - Contact info: preserve EXACT email, phone, LinkedIn from original
   - Dates: normalize to "Month YYYY – Month YYYY" or "Month YYYY – Present"

Return ONLY valid JSON — no markdown, no explanation, no ```json wrapper:

{{
  "name": "FULL NAME IN CAPS",
  "contact": "email@domain.com  |  +1-XXX-XXX-XXXX  |  City, Country  |  linkedin.com/in/username",
  "summary": "3-sentence power summary following the formula above — must mention the exact job title",
  "experience": [
    {{
      "title": "Job Title from Original Resume",
      "company": "Company Name",
      "dates": "Month YYYY – Present",
      "location": "City, Country",
      "bullets": [
        "Power verb + specific achievement + metric + business impact",
        "Power verb + specific achievement + metric + business impact",
        "Power verb + specific achievement + metric + business impact",
        "Power verb + specific achievement + metric + business impact",
        "Power verb + specific achievement + metric + business impact"
      ]
    }}
  ],
  "skills": ["Skill1", "Skill2", "Skill3", "...include ALL from JD plus originals"],
  "education": [
    {{"degree": "Degree Name", "school": "University Name", "year": "YYYY"}}
  ],
  "certifications": ["Certification 1", "Certification 2"],
  "projects": [
    {{"name": "Project Name", "description": "1-2 sentence impact description with metrics", "technologies": ["Tech1", "Tech2"]}}
  ]
}}"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are an elite resume writer. Return ONLY valid JSON. Never fabricate experience. Every bullet must have a quantified metric and business impact."
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=4096,
            temperature=0.3,  # Slightly higher for more compelling writing
        )

        raw = response.choices[0].message.content.strip()

        # Clean markdown wrappers
        raw = re.sub(r'^```json\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'^```\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)

        result = json.loads(raw)

        # Validate required fields
        if not result.get("experience"):
            result["experience"] = []
        if not result.get("skills"):
            result["skills"] = missing_keywords[:20] if missing_keywords else []

        return result

    except json.JSONDecodeError as e:
        print(f"[Resume Rewrite] JSON parse error: {e}")
        # Retry once with stricter prompt
        try:
            retry_response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "Return ONLY a JSON object. No text before or after. No markdown."},
                    {"role": "user", "content": f"Convert this resume to JSON format with keys: name, contact, summary, experience (array with title, company, dates, location, bullets), skills (array), education (array with degree, school, year), certifications (array):\n\n{resume_text[:3000]}"}
                ],
                max_tokens=3000,
                temperature=0.1,
            )
            retry_raw = retry_response.choices[0].message.content.strip()
            retry_raw = re.sub(r'^```json\s*', '', retry_raw, flags=re.MULTILINE)
            retry_raw = re.sub(r'^```\s*', '', retry_raw, flags=re.MULTILINE)
            retry_raw = re.sub(r'\s*```$', '', retry_raw, flags=re.MULTILINE)
            return json.loads(retry_raw)
        except:
            return _fallback_structured_resume(resume_text, job_title, missing_keywords)

    except Exception as e:
        print(f"[Resume Rewrite] Error: {e}")
        return _fallback_structured_resume(resume_text, job_title, missing_keywords)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _simulated_response() -> dict:
    return {
        "overall_score": 45.0,
        "keywords_matched": 5,
        "keywords_missing": 8,
        "total_keywords": 13,
        "missing_list": ["Add GROQ_API_KEY to .env for real AI analysis — free at console.groq.com"],
        "breakdown": {
            "action_verbs": {"score": 50, "count": 4},
            "technical_skills": {"score": 40, "count": 3},
            "soft_skills": {"score": 45, "count": 2},
        },
        "suggestions": ["Sign up free at console.groq.com and add your GROQ_API_KEY to .env to enable real AI analysis"],
    }


def _error_response(message: str) -> dict:
    return {
        "overall_score": 0,
        "keywords_matched": 0,
        "keywords_missing": 0,
        "total_keywords": 0,
        "missing_list": [],
        "breakdown": {
            "action_verbs": {"score": 0, "count": 0},
            "technical_skills": {"score": 0, "count": 0},
            "soft_skills": {"score": 0, "count": 0},
        },
        "suggestions": [],
        "error": message,
    }


def _fallback_structured_resume(
    resume_text: str,
    job_title: str,
    missing_keywords: list,
) -> dict:
    """
    Fallback parser when GROQ_API_KEY is missing or the AI call fails.
    Extracts all resume sections from raw text using regex.
    """
    lines = [l.strip() for l in (resume_text or "").split("\n") if l.strip()]

    # ── Name ─────────────────────────────────────────────────────────────────
    name = "Candidate"
    for line in lines:
        if len(line) < 60 and not any(c in line for c in ["@", "http", "+", "linkedin", "|"]):
            name = line
            break

    # ── Contact — scan first 8 lines for email/phone/LinkedIn ─────────────────
    contact_parts = []
    for line in lines[:8]:
        if any(k in line.lower() for k in ["@", "linkedin", "github", "+"]):
            contact_parts.append(line)
        elif re.search(r'\+?\d[\d\s\-\(\)]{7,}', line):
            contact_parts.append(line)
    contact = "  |  ".join(dict.fromkeys(contact_parts))

    # ── Section parser ────────────────────────────────────────────────────────
    SECTION_MAP = {
        "summary": r'^(professional\s+summary|summary|objective|profile)',
        "experience": r'^((work\s+)?experience|professional\s+experience|employment)',
        "skills": r'^((technical\s+)?skills|core\s+(skills|competencies)|technologies)',
        "education": r'^education',
        "certifications": r'^certifications?(\s+&\s+training)?',
        "projects": r'^(selected\s+)?projects',
    }

    sections = {k: [] for k in SECTION_MAP}
    current_sec = None

    for line in lines:
        matched = False
        for sec, pattern in SECTION_MAP.items():
            if re.match(pattern, line, re.I) and len(line) < 60:
                current_sec = sec
                matched = True
                break
        if not matched and current_sec:
            sections[current_sec].append(line)

    # ── Summary ───────────────────────────────────────────────────────────────
    summary = " ".join(sections["summary"]).strip() or (
        f"Results-driven {job_title} with proven expertise in delivering high-impact solutions. "
        f"Track record of driving measurable improvements including enhanced system performance and streamlined operations. "
        f"Seeking to leverage technical skills and leadership experience in a challenging {job_title} role."
    )

    # ── Experience ────────────────────────────────────────────────────────────
    exp_lines = sections["experience"] + sections["projects"]
    job_entries = []
    current_job = None
    bullets = []

    for line in exp_lines:
        is_bullet = line.startswith(("•", "-", "*", "–", "▸")) or (
            len(line) > 40 and line[0].islower()
        )
        is_date = bool(re.search(
            r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|20\d{2}|19\d{2})\b',
            line, re.I
        ))
        if not is_bullet and not is_date and len(line) < 80 and line[0].isupper():
            if current_job and bullets:
                current_job["bullets"] = bullets[:]
                job_entries.append(current_job)
            current_job = {"title": line, "company": "", "dates": "", "location": "", "bullets": []}
            bullets = []
        elif is_date and current_job:
            current_job["dates"] = line
        elif is_bullet or len(line) > 30:
            clean = line.lstrip("•-*–▸ ").strip()
            if clean and len(clean) > 15:
                bullets.append(clean)

    if current_job:
        current_job["bullets"] = bullets[:]
        job_entries.append(current_job)
    elif bullets:
        job_entries = [{"title": job_title, "company": "", "dates": "", "location": "", "bullets": bullets[:15]}]

    if not job_entries:
        job_entries = [{"title": job_title, "company": "", "dates": "", "location": "",
                        "bullets": ["Delivered key projects aligned with engineering and business objectives."]}]

    # ── Skills ────────────────────────────────────────────────────────────────
    skills = []
    for line in sections["skills"]:
        for part in re.split(r"[,|·•\t]", line):
            clean = part.strip().lstrip("-*• ")
            if clean and 2 < len(clean) < 50:
                skills.append(clean)

    existing_lower = {s.lower() for s in skills}
    for kw in (missing_keywords or []):
        if kw and not kw.startswith("Add GROQ") and kw.lower() not in existing_lower:
            skills.append(kw)
            existing_lower.add(kw.lower())

    if not skills:
        skills = missing_keywords[:20] if missing_keywords else ["See resume for full skill set"]

    # ── Education ─────────────────────────────────────────────────────────────
    education = []
    current_edu = {}
    for line in sections["education"]:
        if re.search(r'\b(bachelor|master|bsc|msc|b\.sc|m\.sc|phd|diploma|certificate|degree)\b', line, re.I):
            if current_edu:
                education.append(current_edu)
            current_edu = {"degree": line, "school": "", "year": ""}
        elif current_edu and not current_edu.get("school") and not re.search(r'\b20\d{2}\b', line):
            current_edu["school"] = line
        year_m = re.search(r'\b(19|20)\d{2}\b', line)
        if year_m and current_edu:
            current_edu["year"] = year_m.group()
    if current_edu and current_edu.get("degree"):
        education.append(current_edu)

    # ── Certifications ────────────────────────────────────────────────────────
    certifications = []
    for line in sections["certifications"]:
        clean = line.lstrip("•-*– ").strip()
        if clean and len(clean) > 5:
            certifications.append(clean)

    return {
        "name": name,
        "contact": contact,
        "summary": summary,
        "experience": job_entries,
        "skills": skills[:40],
        "education": education,
        "certifications": certifications,
        "projects": [],
    }
