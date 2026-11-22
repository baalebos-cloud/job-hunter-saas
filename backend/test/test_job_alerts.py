"""Job alert emails: match %, ranking, frequency, direct email delivery, one-click unsubscribe."""
import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from backend.app.models.automation import AutomationEvent
from backend.app.models.job import Job
from backend.app.models.resume import Resume
from backend.app.models.user import OtherSkill, User
from backend.app.routes.job_board import user_skills
from backend.app.services import job_alerts
from backend.app.services import job_automation as service
from backend.test.test_platform_quality import client, db, headers  # noqa: F401

NOW = datetime(2026, 11, 23, 9, 0)          # a Monday


@pytest.fixture(autouse=True)
def email_only(monkeypatch):
    """No n8n: alerts go straight to Resend."""
    monkeypatch.setattr(service.settings, "N8N_EVENTS_WEBHOOK_URL", "")
    monkeypatch.setattr(service.settings, "N8N_WEBHOOK_SECRET", "")
    monkeypatch.setattr(service.settings, "RESEND_API_KEY", "re_test_key")
    monkeypatch.setattr(service.settings, "API_PUBLIC_URL", "https://api.baalebo.example")
    sent = []

    def post(url, **kwargs):
        sent.append((url, kwargs))
        return SimpleNamespace(status_code=200, json=lambda: {"id": "email-1"})
    monkeypatch.setattr("backend.app.utils.email.httpx.post", post)
    return sent


def seeker(db, **prefs):
    user = db.get(User, 2)
    user.full_name = "Ada <Obi>"
    user.career_track, user.country, user.job_alert_work_type = "DevOps Engineer", "Nigeria", "remote"
    user.job_alerts_enabled, user.job_alerts_enabled_at = True, NOW - timedelta(days=1)
    for key, value in prefs.items():
        setattr(user, key, value)
    db.add_all([OtherSkill(user_id=user.id, name=n) for n in ("Kubernetes", "Terraform", "AWS", "Docker")])
    db.commit()
    return user


def job(title="DevOps Engineer", skills=None, **fields):
    data = dict(company="Contoso", category="DevOps Engineer", location="Worldwide", work_type="remote",
                is_active=True, first_seen_at=NOW - timedelta(hours=2), scraped_at=NOW, url="https://example.com/j",
                skills=skills if skills is not None else ["Kubernetes", "Terraform", "AWS", "Helm"])
    return Job(title=title, **{**data, **fields})


def digest(db):
    return db.query(AutomationEvent).filter_by(event_type="jobs.matched").order_by(AutomationEvent.created_at.desc()).first()


def test_digest_ranks_by_match_and_explains_every_percentage(db):
    seeker(db)
    strong = job("Senior DevOps Engineer", ["Kubernetes", "Terraform", "AWS", "Docker"], dedupe_key="a")      # 100%
    medium = job("DevOps Engineer <script>", ["Kubernetes", "Go", "Rust", "Helm"], company="Fabrikam", dedupe_key="b")  # 25%
    unscored = job("DevOps Engineer II", ["Kubernetes"], company="Northwind", dedupe_key="c")                 # too few skills
    twin = job("Senior DevOps Engineer", ["Kubernetes", "Terraform", "AWS", "Docker"], dedupe_key="a")       # same role
    db.add_all([strong, medium, unscored, twin]); db.commit()
    assert service.queue_job_digests(db, NOW) == 1
    event = digest(db).payload
    first = event["job_ids"][0]
    assert first in (strong.id, twin.id) and event["job_ids"][1:] == [medium.id, unscored.id]   # best first, unscored last
    assert not {strong.id, twin.id} <= set(event["job_ids"])                                    # one role listed once
    assert event["scores"] == {str(first): 100, str(medium.id): 25, str(unscored.id): None}
    assert event["subject"] == "3 new jobs match your profile (best 100%)"
    html = event["html"]
    assert "100% match" in html and "25% match" in html and "Match not available" in html
    assert "You have 4 of its 4 listed skills" in html and "Missing: Go, Rust, Helm" in html
    assert "<script>" not in html and "&lt;script&gt;" in html and "Ada &lt;Obi&gt;" not in html   # escaped; first name only
    assert "Hi Ada" in html
    assert "Apply on Baalebos" in event["text"] or "Complete the employer's application form" in event["text"]


def test_minimum_match_filters_out_weak_and_unscored_jobs(db):
    seeker(db, job_alert_min_match=70)
    db.add_all([job("DevOps Engineer", ["Kubernetes", "Terraform", "AWS", "Go"], dedupe_key="a"),            # 75%
                job("DevOps Engineer", ["Kubernetes", "Go", "Rust"], company="Fabrikam", dedupe_key="b"),  # 33%
                job("DevOps Engineer", ["Kubernetes"], company="Northwind", dedupe_key="c")])              # unscored
    db.commit()
    service.queue_job_digests(db, NOW)
    assert list(digest(db).payload["scores"].values()) == [75]


def test_weekly_frequency_sends_at_most_once_a_week(db):
    seeker(db, job_alert_frequency="weekly", job_alerts_enabled_at=NOW - timedelta(days=8))
    db.add(job(dedupe_key="a")); db.commit()
    assert service.queue_job_digests(db, NOW) == 1
    db.add(job(company="Later", dedupe_key="b", first_seen_at=NOW + timedelta(days=1))); db.commit()
    assert service.queue_job_digests(db, NOW + timedelta(days=3)) == 0           # same ISO week
    assert service.queue_job_digests(db, NOW + timedelta(days=7, hours=1)) == 1  # next week


def test_alert_is_emailed_through_resend_with_unsubscribe_headers(db, email_only):
    user = seeker(db)
    db.add(job(dedupe_key="a")); db.commit()
    result = service.run_tick(db, now=NOW)
    assert result["queued_job_digests"] == 1 and result["accepted"] == 1
    url, request = email_only[0]
    body = request["json"]
    assert url == "https://api.resend.com/emails" and body["to"] == [user.email]
    assert request["headers"]["Idempotency-Key"].startswith("baalebos-job-digest-")
    assert body["text"] and body["html"].startswith("<!DOCTYPE html>")
    assert body["headers"]["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert "https://api.baalebo.example/api/v1/alerts/unsubscribe?t=" in body["headers"]["List-Unsubscribe"]
    assert digest(db).status == "sent"


def test_one_click_unsubscribe_link(client, db):
    user = seeker(db)
    token = job_alerts.unsubscribe_token(user)
    assert client.post("/api/v1/alerts/unsubscribe", json={"token": token[:-2] + "xx"}).status_code == 400
    assert client.post("/api/v1/alerts/unsubscribe", params={"t": token}).json() == {"unsubscribed": True}  # RFC 8058
    db.refresh(user)
    assert user.job_alerts_enabled is False
    user.job_alerts_enabled, user.email = True, "changed@example.com"; db.commit()
    assert client.post("/api/v1/alerts/unsubscribe", json={"token": token}).status_code == 400   # old address's link
    assert client.post("/api/v1/alerts/unsubscribe", json={"token": job_alerts.unsubscribe_token(user)}).status_code == 200


def test_match_never_credits_skills_taken_from_the_job_description(db):
    user = seeker(db)
    db.add(Resume(owner_id=user.id, filename="optimized_x.pdf", status="completed",
                  parsed_data=json.dumps({"skills": {"Cloud": ["Python"]}}),
                  analysis_data={"job_description": "Need Rust and Haskell", "missing_list": ["Rust", "Haskell"],
                                 "requirements": [{"phrase": "Rust", "matched": False}],
                                 "confirmed_keywords": ["Ansible"]}))
    db.commit()
    mine = user_skills(db, user)
    assert {"Python", "Ansible", "Kubernetes"} <= mine and not {"Rust", "Haskell"} & mine


def test_alert_preferences_and_scheduler_secret(client, db, monkeypatch):
    seeker(db)
    ok = client.patch("/api/v1/profile/me", headers=headers(), json={"job_alert_frequency": "weekly", "job_alert_min_match": 50})
    assert ok.status_code == 200 and ok.json()["job_alert_frequency"] == "weekly" and ok.json()["job_alert_min_match"] == 50
    assert client.patch("/api/v1/profile/me", headers=headers(), json={"job_alert_min_match": 40}).status_code == 422
    assert client.patch("/api/v1/profile/me", headers=headers(), json={"job_alert_frequency": None}).status_code == 422
    monkeypatch.setattr(service.settings, "CRON_SECRET", "cron-test-secret")
    assert client.post("/api/v1/automation/tick", headers={"X-Cron-Secret": "wrong"}).status_code == 403
    assert client.post("/api/v1/automation/tick", headers={"X-Cron-Secret": "cron-test-secret"}).status_code == 200
