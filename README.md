# job-hunter-saas

**AI-powered job hunting platform** — ATS resume optimization, live job aggregation, and AI interview assistant built with FastAPI, React/Vite, and LLM APIs.

---

## What it does

Most resumes fail ATS screening before a human ever reads them. job-hunter-saas solves this end-to-end:

1. **Upload your CV** (PDF or DOCX) + paste a job description
2. **AI scores your resume** against the JD — keyword gaps, action verbs, quantified achievements
3. **LLM rewrites your resume** targeting 96%+ ATS score for that specific role
4. **Download an ATS-optimized PDF** — single column, Helvetica, no tables or graphics
5. **Browse live job listings** aggregated from 9 global sources in real time

---

## Tech Stack

### Backend
- **Python3** — FastAPI, Pydantic, SQLAlchemy
- **LLM** — Groq API (`llama-3.3-70b-versatile`) via OpenAI-compatible client
- **Document processing** — pdfplumber (PDF), python-docx (DOCX)
- **PDF generation** — ReportLab (ATS-compliant single-column layout)
- **Database** — SQLAlchemy ORM + SQLite (dev) / PostgreSQL (prod)
- **Job scraping** — requests, feedparser, XML parsing across 9 sources

### Frontend
- **React + Vite** — TypeScript
- **Styling** — Tailwind CSS
- **State** — React hooks

### Infrastructure
- **Docker** — containerized backend and frontend
- **GitHub Actions** — CI/CD pipeline (lint, test, build, deploy)
- **AWS** — EC2, S3, RDS deployment target

---

## Architecture

```
frontend/          # React/Vite TypeScript UI
backend/
  app/
    api/           # FastAPI route handlers
    models/        # SQLAlchemy ORM models
    utils/
      ats_engine.py      # Text extraction + LLM ATS scoring + AI resume rewrite
      optimizer.py       # Pipeline orchestrator — wires ats_engine → pdf_generator
      pdf_generator.py   # ATS-compliant PDF rendering (ReportLab)
      global_scraper.py  # Multi-source job aggregation (9 sources)
    core/
      config.py          # Settings — GROQ_API_KEY, DATABASE_URL, etc.
    database.py          # SQLAlchemy session management
```

---

## Key Engineering Decisions

### LLM Inference Pipeline
The AI rewrite pipeline (`optimizer.py → ats_engine.py → pdf_generator.py`) follows a strict 3-stage flow:

1. `extract_text()` — converts uploaded file bytes to plain text
2. `analyze_detailed_ats()` — scores resume against JD, returns missing keywords
3. `rewrite_resume_for_job()` — AI rewrites resume, returns structured JSON dict

The structured dict flows directly to `generate_optimized_resume()` which renders the PDF. If any stage fails, the pipeline falls back gracefully — never crashing, always returning a usable result.

### ATS-Compliant PDF Design
ReportLab is used instead of HTML-to-PDF conversion because ATS parsers fail on:
- Multi-column layouts (columns parsed left-to-right as garbled text)
- Tables (cells parsed out of order)
- Images, text boxes, or non-standard fonts

Every PDF output uses: single column, Helvetica, plain hyphen bullets, full-width section dividers, consistent left margin.

### Job Aggregation
`global_scraper.py` hits 9 sources concurrently using `ThreadPoolExecutor` — Remotive, Jobicy, Arbeitnow, WeWorkRemotely, Greenhouse, Lever, The Muse, Adzuna, and Stack Overflow Jobs (deprecated — removed). Deduplication by URL before DB insert.

---

## Known Bugs Fixed

### Bug: Silent ImportError in optimizer.py → blank PDF output
**Root cause:** `optimizer.py` imported non-existent function names from `ats_engine.py`:
```python
# BUGGY — these functions do not exist
from backend.app.utils.ats_engine import analyze_resume, rewrite_resume

# FIXED — correct names
from backend.app.utils.ats_engine import analyze_detailed_ats, rewrite_resume_for_job
```
The `ImportError` was silently caught, causing `structured=None` to flow to `pdf_generator`, which rendered a PDF containing only `"Candidate"` as the name with all sections empty.

**Fix:** Corrected import names + added `_validate_structured()` post-AI validation to enforce all required fields are populated from raw resume text if AI returns empty arrays.

### Bug: `save_jobs_to_db()` — `if True:` always commits
```python
# BUGGY
if True:
    db.commit()

# FIXED
if saved > 0:
    try:
        db.commit()
    except Exception as e:
        db.rollback()
```

### Bug: AI model drops education and certifications arrays
**Fix:** Pre-extraction injection into prompt + `_enforce_education_and_certs()` post-AI enforcement — parses raw resume text directly if AI returns `[]`.

---

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker (optional)

### Environment Variables
```bash
# backend/.env
GROQ_API_KEY=your_groq_api_key   # Free at console.groq.com
DATABASE_URL=sqlite:///./jobs.db
```

### Run with Docker
```bash
docker-compose up --build
```

### Run locally
```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

### Run tests
```bash
cd backend
pytest tests/ -v
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/resume/analyze` | Upload CV + JD → ATS score + missing keywords |
| POST | `/api/resume/optimize` | Upload CV + JD → AI-rewritten ATS-optimized PDF |
| GET | `/api/jobs` | Browse aggregated job listings |
| GET | `/api/jobs/scrape` | Trigger fresh job scrape (all 9 sources) |

---

## Job Sources

| Source | Coverage |
|--------|----------|
| Remotive | Global remote |
| Jobicy | Global remote |
| Arbeitnow | Europe + global |
| WeWorkRemotely | USA + global |
| Greenhouse | Top tech companies |
| Lever | Startups |
| The Muse | USA companies |
| Adzuna | 10 countries incl. Nigeria, South Africa |
| Micro1 | Global remote |

---

## Author

**Oluwadare Tobi Jayeola** — DevOps Engineer & Software Engineer
- GitHub: [github.com/baalebos-cloud](https://github.com/baalebos-cloud)
- LinkedIn: [linkedin.com/in/oluwadare-jayeola-6874591b4](https://linkedin.com/in/oluwadare-jayeola-6874591b4)
- Email: jayeolaoluwadamilare@gmail.com

---

## License

MIT
