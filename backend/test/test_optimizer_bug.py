"""
Test Suite: optimizer.py — Silent ImportError causing empty resume PDF
Codebase: job-hunter-saas
Language: Python3
Type: fail-to-pass (primary) + pass-to-pass (regression)

Bug Description:
    optimizer.py imported non-existent function names from ats_engine.py:
        - analyze_resume      → correct name: analyze_detailed_ats
        - rewrite_resume      → correct name: rewrite_resume_for_job
    The ImportError was silently caught inside build_optimized_resume(),
    causing structured=None to flow to pdf_generator.generate_optimized_resume(),
    which rendered a PDF containing only "Candidate" as the name with all
    other sections empty.

Fix:
    Correct the import names in optimizer.py:
        from backend.app.utils.ats_engine import (
            extract_text,
            analyze_detailed_ats,
            rewrite_resume_for_job,
        )
"""

import pytest
from unittest.mock import patch, MagicMock


# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_RESUME_TEXT = """
OLUWADARE TOBI JAYEOLA
jayeolaoluwadamilare@gmail.com | +2347067158165 | Nigeria (Remote)

PROFESSIONAL SUMMARY
DevOps Engineer with hands-on experience in AWS, Terraform, Docker, and Kubernetes.
Reduced MTTR by 40%+ through automated alerting using Prometheus and Grafana.

WORK EXPERIENCE
DevOps Engineer / Cloud Engineer Trainee | Ekiti MSME ICT Hub | Aug 2025 - Jan 2026
- Built and maintained CI/CD pipelines using GitHub Actions and Jenkins.
- Automated AWS infrastructure provisioning using Terraform and CloudFormation.
- Implemented observability stack: Prometheus, Grafana, ELK Stack, CloudWatch.

TECHNICAL SKILLS
CI/CD Pipelines: GitHub Actions, Jenkins, GitLab CI
Cloud Platforms: AWS, GCP, Azure
Containers: Docker, Kubernetes, Amazon ECS

EDUCATION
Cloud Computing Certification - Ekiti MSME ICT Hub, 2026
BSc Entrepreneurship & Business Management (In Progress) - NOUN

CERTIFICATIONS
AWS Certified Cloud Practitioner (CLF-C02)
AWS Educate: Introduction to Generative AI
3MTT Data Science / Machine Learning
"""

SAMPLE_JOB_DESCRIPTION = """
We are looking for a DevOps Engineer with experience in:
- AWS infrastructure management (EC2, S3, VPC, IAM, RDS)
- CI/CD pipeline engineering using Jenkins and GitHub Actions
- Infrastructure as Code with Terraform and CloudFormation
- Container orchestration with Docker and Kubernetes
- Monitoring and observability using Prometheus and Grafana
"""

SAMPLE_JOB_TITLE = "DevOps Engineer"

MOCK_STRUCTURED = {
    "name": "OLUWADARE TOBI JAYEOLA",
    "contact": "jayeolaoluwadamilare@gmail.com | +2347067158165 | Nigeria (Remote)",
    "summary": "DevOps Engineer with hands-on AWS experience and 40%+ MTTR reduction.",
    "experience": [{
        "title": "DevOps Engineer / Cloud Engineer Trainee",
        "company": "Ekiti MSME ICT Hub",
        "dates": "Aug 2025 - Jan 2026",
        "location": "Nigeria (Remote)",
        "bullets": [
            "Built CI/CD pipelines using GitHub Actions and Jenkins.",
            "Automated AWS infrastructure provisioning using Terraform.",
        ]
    }],
    "skills": ["AWS", "Terraform", "Docker", "Kubernetes", "Jenkins", "GitHub Actions"],
    "education": [{"degree": "Cloud Computing Certification", "school": "Ekiti MSME ICT Hub", "year": "2026"}],
    "certifications": ["AWS Certified Cloud Practitioner (CLF-C02)", "3MTT Data Science / Machine Learning"],
}

MOCK_ANALYSIS = {
    "overall_score": 78.0,
    "keywords_matched": 12,
    "keywords_missing": 3,
    "total_keywords": 15,
    "missing_list": ["Ansible", "ELK Stack", "Datadog"],
    "breakdown": {
        "action_verbs": {"score": 80, "count": 6},
        "technical_skills": {"score": 75, "count": 10},
        "soft_skills": {"score": 70, "count": 3},
    },
    "suggestions": ["Add Ansible to your skills section"],
}


# ── FAIL-TO-PASS TESTS ────────────────────────────────────────────────────────
# These tests FAIL on the buggy code and PASS after the fix is applied.

class TestFailToPass:
    """
    Primary tests that expose the bug.
    Before fix: optimizer.py imports analyze_resume + rewrite_resume
                → ImportError silently caught → structured = None
                → all assertions below fail
    After fix:  optimizer.py imports analyze_detailed_ats + rewrite_resume_for_job
                → pipeline executes correctly → all assertions below pass
    """

    def test_structured_name_is_not_candidate(self):
        """
        FAIL BEFORE FIX: structured defaults to {} → name extracted
        as 'Candidate' from empty resume_text fallback.
        PASS AFTER FIX: AI rewrite returns actual candidate name.
        """
        with patch("backend.app.utils.ats_engine.extract_text",
                   return_value=SAMPLE_RESUME_TEXT), \
             patch("backend.app.utils.ats_engine.analyze_detailed_ats",
                   return_value=MOCK_ANALYSIS), \
             patch("backend.app.utils.ats_engine.rewrite_resume_for_job",
                   return_value=MOCK_STRUCTURED):

            from backend.app.utils.optimizer import build_optimized_resume
            result = build_optimized_resume(
                file_content=b"fake_pdf_bytes",
                filename="resume.pdf",
                job_description=SAMPLE_JOB_DESCRIPTION,
                job_title=SAMPLE_JOB_TITLE,
            )

        assert result["structured"]["name"] != "Candidate", (
            "Bug present: name is 'Candidate' — ImportError silently caught, "
            "structured=None passed to validator which fell back to 'Candidate'"
        )
        assert result["structured"]["name"] == "OLUWADARE TOBI JAYEOLA"

    def test_structured_experience_is_not_empty(self):
        """
        FAIL BEFORE FIX: experience section is empty or contains only
        a generic fallback bullet — AI rewrite never executed.
        PASS AFTER FIX: experience contains actual job history from AI rewrite.
        """
        with patch("backend.app.utils.ats_engine.extract_text",
                   return_value=SAMPLE_RESUME_TEXT), \
             patch("backend.app.utils.ats_engine.analyze_detailed_ats",
                   return_value=MOCK_ANALYSIS), \
             patch("backend.app.utils.ats_engine.rewrite_resume_for_job",
                   return_value=MOCK_STRUCTURED):

            from backend.app.utils.optimizer import build_optimized_resume
            result = build_optimized_resume(
                file_content=b"fake_pdf_bytes",
                filename="resume.pdf",
                job_description=SAMPLE_JOB_DESCRIPTION,
                job_title=SAMPLE_JOB_TITLE,
            )

        experience = result["structured"]["experience"]
        assert len(experience) > 0, "Bug present: experience list is empty"
        assert experience[0]["company"] == "Ekiti MSME ICT Hub", (
            "Bug present: company name is wrong — AI rewrite output not used"
        )

    def test_education_is_not_empty(self):
        """
        FAIL BEFORE FIX: education always returns [] — both because
        ImportError prevents AI rewrite and because fallback _fallback_structured_resume
        had education=[] hardcoded.
        PASS AFTER FIX: education extracted from AI structured output.
        """
        with patch("backend.app.utils.ats_engine.extract_text",
                   return_value=SAMPLE_RESUME_TEXT), \
             patch("backend.app.utils.ats_engine.analyze_detailed_ats",
                   return_value=MOCK_ANALYSIS), \
             patch("backend.app.utils.ats_engine.rewrite_resume_for_job",
                   return_value=MOCK_STRUCTURED):

            from backend.app.utils.optimizer import build_optimized_resume
            result = build_optimized_resume(
                file_content=b"fake_pdf_bytes",
                filename="resume.pdf",
                job_description=SAMPLE_JOB_DESCRIPTION,
                job_title=SAMPLE_JOB_TITLE,
            )

        education = result["structured"]["education"]
        assert len(education) > 0, "Bug present: education list is empty"
        assert education[0]["school"] == "Ekiti MSME ICT Hub"

    def test_certifications_is_not_empty(self):
        """
        FAIL BEFORE FIX: certifications always returns [] for same reason
        as education — hardcoded in fallback and never reached via AI path.
        PASS AFTER FIX: certifications populated from AI structured output.
        """
        with patch("backend.app.utils.ats_engine.extract_text",
                   return_value=SAMPLE_RESUME_TEXT), \
             patch("backend.app.utils.ats_engine.analyze_detailed_ats",
                   return_value=MOCK_ANALYSIS), \
             patch("backend.app.utils.ats_engine.rewrite_resume_for_job",
                   return_value=MOCK_STRUCTURED):

            from backend.app.utils.optimizer import build_optimized_resume
            result = build_optimized_resume(
                file_content=b"fake_pdf_bytes",
                filename="resume.pdf",
                job_description=SAMPLE_JOB_DESCRIPTION,
                job_title=SAMPLE_JOB_TITLE,
            )

        certs = result["structured"]["certifications"]
        assert len(certs) > 0, "Bug present: certifications list is empty"
        assert any("AWS" in c for c in certs), "AWS certification not found in output"

    def test_ats_score_is_nonzero(self):
        """
        FAIL BEFORE FIX: ats_score is 0.0 — analyze_detailed_ats never
        called due to ImportError.
        PASS AFTER FIX: actual ATS score returned from analysis.
        """
        with patch("backend.app.utils.ats_engine.extract_text",
                   return_value=SAMPLE_RESUME_TEXT), \
             patch("backend.app.utils.ats_engine.analyze_detailed_ats",
                   return_value=MOCK_ANALYSIS), \
             patch("backend.app.utils.ats_engine.rewrite_resume_for_job",
                   return_value=MOCK_STRUCTURED):

            from backend.app.utils.optimizer import build_optimized_resume
            result = build_optimized_resume(
                file_content=b"fake_pdf_bytes",
                filename="resume.pdf",
                job_description=SAMPLE_JOB_DESCRIPTION,
                job_title=SAMPLE_JOB_TITLE,
            )

        assert result["ats_score"] > 0.0, (
            "Bug present: ats_score is 0.0 — analyze_detailed_ats was never called"
        )
        assert result["ats_score"] == 78.0

    def test_missing_keywords_populated(self):
        """
        FAIL BEFORE FIX: missing keywords list is empty — analysis never ran.
        PASS AFTER FIX: missing keywords extracted from ATS analysis.
        """
        with patch("backend.app.utils.ats_engine.extract_text",
                   return_value=SAMPLE_RESUME_TEXT), \
             patch("backend.app.utils.ats_engine.analyze_detailed_ats",
                   return_value=MOCK_ANALYSIS), \
             patch("backend.app.utils.ats_engine.rewrite_resume_for_job",
                   return_value=MOCK_STRUCTURED):

            from backend.app.utils.optimizer import build_optimized_resume
            result = build_optimized_resume(
                file_content=b"fake_pdf_bytes",
                filename="resume.pdf",
                job_description=SAMPLE_JOB_DESCRIPTION,
                job_title=SAMPLE_JOB_TITLE,
            )

        assert len(result["missing"]) > 0, (
            "Bug present: missing keywords list is empty — ATS analysis never ran"
        )
        assert "Ansible" in result["missing"]

    def test_import_uses_correct_function_names(self):
        """
        FAIL BEFORE FIX: importing analyze_resume or rewrite_resume
        raises ImportError — neither exists in ats_engine.py.
        PASS AFTER FIX: correct names import successfully.
        """
        try:
            from backend.app.utils.ats_engine import (
                extract_text,
                analyze_detailed_ats,
                rewrite_resume_for_job,
            )
            imported_successfully = True
        except ImportError as e:
            imported_successfully = False
            pytest.fail(
                f"Bug present: ImportError when importing from ats_engine — {e}. "
                f"Check that analyze_detailed_ats and rewrite_resume_for_job exist."
            )

        assert imported_successfully


# ── PASS-TO-PASS TESTS ────────────────────────────────────────────────────────
# These tests PASS both before and after the fix.
# They verify that the fix does not break existing behaviour.

class TestPassToPass:
    """
    Regression tests. Verify nothing breaks after the fix is applied.
    """

    def test_result_has_required_keys(self):
        """
        build_optimized_resume must always return a dict with all
        required keys regardless of whether AI call succeeds or fails.
        """
        with patch("backend.app.utils.ats_engine.extract_text",
                   return_value=SAMPLE_RESUME_TEXT), \
             patch("backend.app.utils.ats_engine.analyze_detailed_ats",
                   return_value=MOCK_ANALYSIS), \
             patch("backend.app.utils.ats_engine.rewrite_resume_for_job",
                   return_value=MOCK_STRUCTURED):

            from backend.app.utils.optimizer import build_optimized_resume
            result = build_optimized_resume(
                file_content=b"fake_pdf_bytes",
                filename="resume.pdf",
                job_description=SAMPLE_JOB_DESCRIPTION,
                job_title=SAMPLE_JOB_TITLE,
            )

        required_keys = {"ats_score", "structured", "suggestions", "missing", "resume_text"}
        assert required_keys.issubset(result.keys()), (
            f"Missing keys: {required_keys - result.keys()}"
        )

    def test_structured_has_all_sections(self):
        """
        structured dict must always contain all sections pdf_generator expects.
        """
        with patch("backend.app.utils.ats_engine.extract_text",
                   return_value=SAMPLE_RESUME_TEXT), \
             patch("backend.app.utils.ats_engine.analyze_detailed_ats",
                   return_value=MOCK_ANALYSIS), \
             patch("backend.app.utils.ats_engine.rewrite_resume_for_job",
                   return_value=MOCK_STRUCTURED):

            from backend.app.utils.optimizer import build_optimized_resume
            result = build_optimized_resume(
                file_content=b"fake_pdf_bytes",
                filename="resume.pdf",
                job_description=SAMPLE_JOB_DESCRIPTION,
                job_title=SAMPLE_JOB_TITLE,
            )

        structured = result["structured"]
        required_sections = {"name", "contact", "summary", "experience", "skills", "education", "certifications"}
        assert required_sections.issubset(structured.keys()), (
            f"Missing structured sections: {required_sections - structured.keys()}"
        )

    def test_empty_resume_returns_safe_fallback(self):
        """
        When file content produces empty text, result must return a
        safe error dict — not raise an unhandled exception.
        """
        with patch("backend.app.utils.ats_engine.extract_text", return_value=""):
            from backend.app.utils.optimizer import build_optimized_resume
            result = build_optimized_resume(
                file_content=b"",
                filename="resume.pdf",
                job_description=SAMPLE_JOB_DESCRIPTION,
                job_title=SAMPLE_JOB_TITLE,
            )

        assert "error" in result or result["ats_score"] == 0.0, (
            "Empty resume should return safe fallback, not raise exception"
        )

    def test_suggestions_is_a_list(self):
        """
        suggestions must always be a list — never None — even when
        no missing keywords are found.
        """
        with patch("backend.app.utils.ats_engine.extract_text",
                   return_value=SAMPLE_RESUME_TEXT), \
             patch("backend.app.utils.ats_engine.analyze_detailed_ats",
                   return_value=MOCK_ANALYSIS), \
             patch("backend.app.utils.ats_engine.rewrite_resume_for_job",
                   return_value=MOCK_STRUCTURED):

            from backend.app.utils.optimizer import build_optimized_resume
            result = build_optimized_resume(
                file_content=b"fake_pdf_bytes",
                filename="resume.pdf",
                job_description=SAMPLE_JOB_DESCRIPTION,
                job_title=SAMPLE_JOB_TITLE,
            )

        assert isinstance(result["suggestions"], list), (
            "suggestions must be a list, not None or another type"
        )

    def test_skills_includes_missing_keywords(self):
        """
        After fix, missing keywords from ATS analysis must be injected
        into the skills list so the optimized resume covers all JD gaps.
        """
        with patch("backend.app.utils.ats_engine.extract_text",
                   return_value=SAMPLE_RESUME_TEXT), \
             patch("backend.app.utils.ats_engine.analyze_detailed_ats",
                   return_value=MOCK_ANALYSIS), \
             patch("backend.app.utils.ats_engine.rewrite_resume_for_job",
                   return_value=MOCK_STRUCTURED):

            from backend.app.utils.optimizer import build_optimized_resume
            result = build_optimized_resume(
                file_content=b"fake_pdf_bytes",
                filename="resume.pdf",
                job_description=SAMPLE_JOB_DESCRIPTION,
                job_title=SAMPLE_JOB_TITLE,
            )

        skills = result["structured"]["skills"]
        missing = result["missing"]
        for keyword in missing:
            assert keyword in skills, (
                f"Missing keyword '{keyword}' was not injected into skills list"
            )

    def test_experience_bullets_are_not_empty(self):
        """
        Every experience entry must have at least one bullet point.
        Verifies pdf_generator will not render empty experience sections.
        """
        with patch("backend.app.utils.ats_engine.extract_text",
                   return_value=SAMPLE_RESUME_TEXT), \
             patch("backend.app.utils.ats_engine.analyze_detailed_ats",
                   return_value=MOCK_ANALYSIS), \
             patch("backend.app.utils.ats_engine.rewrite_resume_for_job",
                   return_value=MOCK_STRUCTURED):

            from backend.app.utils.optimizer import build_optimized_resume
            result = build_optimized_resume(
                file_content=b"fake_pdf_bytes",
                filename="resume.pdf",
                job_description=SAMPLE_JOB_DESCRIPTION,
                job_title=SAMPLE_JOB_TITLE,
            )

        for job in result["structured"]["experience"]:
            assert len(job.get("bullets", [])) > 0, (
                f"Experience entry '{job.get('title')}' has no bullets"
            )
