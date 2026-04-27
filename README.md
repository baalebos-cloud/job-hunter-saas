Job Hunter SaaS (Baalebos Cloud)
A production-ready, cloud-native Job Application Automation Platform. Optimized for resume parsing, ATS scoring, and automated job discovery using an asynchronous distributed architecture.
📌 Overview
Job Hunter SaaS is a full-stack solution designed to modernize the job search. It solves the "black hole" of applications by providing data-driven insights into resume performance and application tracking.
Core Capabilities
 * AI Resume Analysis: Real-time ATS scoring and keyword optimization.
 * Automated Discovery: Distributed scraping and categorization of job listings.
 * Asynchronous Pipelines: Heavy processing (PDF parsing/AI) handled by background workers.
 * DevOps Excellence: Fully automated "Push-to-Deploy" pipeline with container pruning for cost-efficiency.
🧱 System Architecture
The platform utilizes a Decoupled Micro-service Architecture:
 * Frontend: React (Vite) + Tailwind CSS v4 (Native Engine).
 * API Gateway: Nginx acting as a Reverse Proxy.
 * Core API: FastAPI (Asynchronous Python 3.12).
 * Task Orchestration: Redis 7 (Broker) + Celery (Workers).
 * Persistence: PostgreSQL (AWS RDS).
⚙️ Tech Stack
| Layer | Technologies |
|---|---|
| Frontend | React 18, Vite 5, Tailwind CSS v4, Axios, Lucide Icons |
| Backend | FastAPI, SQLAlchemy, Pydantic v2, Python 3.12 |
| Async Processing | Celery, Redis 7 (Message Broker) |
| Cloud & DevOps | Terraform (IaC), AWS EC2, Amazon ECR, GitHub Actions |
| Web Server | Nginx (Reverse Proxy & Static Asset Hosting) |
✨ Key Features
📊 Intelligent Dashboard
 * Live Metrics: Aggregate stats for resumes analyzed, average scores, and tracking status.
 * Application Funnel: Visual breakdown of Pending → Applied → Interview → Offer.
📄 Resume Analyzer
 * Multi-format Support: Upload PDF/DOCX for instant parsing.
 * ATS Engine: AI-driven keyword extraction and improvement suggestions.
⚡ Background Processing
 * Non-blocking UI: Resume analysis is offloaded to Celery workers, allowing the user to continue browsing while the AI processes data in the background.
☁️ Deployment & DevOps (AWS)
The CI/CD Pipeline
 * Continuous Integration: GitHub Actions builds a multi-stage Docker image upon every push to main.
 * Image Registry: Images are versioned and pushed to Amazon ECR.
 * Automated Deployment: GitHub Actions triggers an SSH handshake to the AWS EC2 instance.
 * Resource Management: The deployment script executes docker image prune -a to maintain a lean footprint on 8GB EBS volumes.
Security & Optimization
 * Secret Management: All AWS keys and DB credentials are encrypted via GitHub Secrets.
 * Reverse Proxy: FastAPI is shielded behind Nginx; only ports 80/443 are exposed.
 * Storage: Automated pruning prevents disk-full errors on small cloud instances.
🧪 Local Development
1. Backend & Workers
# Start API
uvicorn app.main:app --reload

# Start Celery Worker
celery -A app.celery_app worker --loglevel=info

2. Frontend (Tailwind v4)
cd job-hunter-dashboard
npm install
npm run dev

📈 Future Roadmap
 * SSL/TLS: Automated certificate renewal via Certbot.
 * K8s Migration: Transitioning from Docker Compose to Kubernetes (EKS) for auto-scaling.
 * WebSockets: Real-time notification updates for background task completion.
👨‍💻 Author

Baalebos Cloud & DevOps Engineer Focused on building high-availability, production-ready systems.
This project is for educational and professional portfolio purposes.
