import importlib.util
import json
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from backend.app.models.application import Application
from backend.app.models.automation import AutomationEvent, ScrapeRun
from backend.app.models.job import Job
from backend.app.models.user import User
from backend.app.models.resume import Resume
from backend.app.services import job_automation as service
from backend.app.utils import global_scraper as scraper
from backend.test.test_platform_quality import db, client, headers  # noqa: F401

NOW = datetime(2026, 10, 10, 12, 0)
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def transport(monkeypatch):
    monkeypatch.setattr(service.settings, "N8N_EVENTS_WEBHOOK_URL", "https://n8n.example.com/webhook/jobs")
    monkeypatch.setattr(service.settings, "N8N_WEBHOOK_SECRET", "private-test-secret")
    calls = []
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(status_code=200, json=lambda: {"accepted": True, "provider_message_id": "test-email-id"})
    monkeypatch.setattr(service.httpx, "post", post)
    return calls


def owner(db):
    return db.get(User, 1)


def candidate(db):
    user = db.get(User, 2)
    user.career_track = "DevOps Engineer"
    user.country = "Nigeria"
    user.job_alert_work_type = "remote"
    user.job_alerts_enabled = True
    user.job_alerts_enabled_at = NOW - timedelta(hours=1)
    db.commit()
    return user


def job(**fields):
    data = dict(title="DevOps Engineer", company="Employer", category="DevOps Engineer",
                location="Worldwide", work_type="remote", is_active=True,
                first_seen_at=NOW-timedelta(minutes=10), scraped_at=NOW,
                url="https://example.com/apply", posted_by_hr=False)
    return Job(**{**data, **fields})


def test_digests_include_new_internal_and_external_jobs_once_per_day(db):
    user = candidate(db)
    external = job()
    internal = job(url=None, posted_by_hr=True, hr_user_id=3)
    refreshed = job(first_seen_at=NOW-timedelta(days=2), scraped_at=NOW)
    restricted = job(location="Remote — United States only")
    wrong_role = job(title="React Developer", category="Frontend Developer")
    legacy = job(first_seen_at=None)
    db.add_all([external, internal, refreshed, restricted, wrong_role, legacy]); db.commit()
    # Existing rows migrated in-place have no first_seen_at; new ORM rows get
    # the insertion default even when constructed with None.
    legacy.first_seen_at = None; db.commit()
    assert service.queue_job_digests(db, NOW) == 1
    db.commit()
    event = db.query(AutomationEvent).first()
    assert set(event.payload["job_ids"]) == {internal.id, external.id}
    assert "Apply on Baalebos" in event.payload["text"]
    assert "Complete the employer's application form" in event.payload["text"]
    assert service.queue_job_digests(db, NOW+timedelta(minutes=30)) == 0
    later = job(first_seen_at=NOW+timedelta(minutes=1))
    db.add(later); db.commit()
    assert service.queue_job_digests(db, NOW+timedelta(days=1)) == 1
    next_event = db.query(AutomationEvent).order_by(AutomationEvent.created_at.desc()).first()
    assert next_event.payload["job_ids"] == [later.id]
    assert event.payload["to_email"] == user.email


@pytest.mark.parametrize("change", ["opt_out", "unverified", "not_available", "closed", "email_changed", "preferences_changed", "stale"])
def test_prepared_digest_rechecks_consent_and_job_state(db, transport, change):
    user = candidate(db); vacancy = job()
    db.add(vacancy); db.commit()
    service.queue_job_digests(db, NOW); db.commit()
    if change == "opt_out": user.job_alerts_enabled = False
    if change == "unverified": user.is_verified = False
    if change == "not_available": user.available_for_work = False
    if change == "closed": vacancy.is_active = False
    if change == "email_changed": user.email = "new@example.com"
    if change == "preferences_changed": user.country = "Ghana"; vacancy.location = "Nigeria"
    if change == "stale": vacancy.scraped_at = NOW-timedelta(days=4)
    db.commit()
    assert service.dispatch_pending(db, now=NOW)["cancelled"] == 1
    assert transport == []


def test_location_and_role_matching_uses_whole_words(db):
    user = candidate(db)
    assert not service.matches_preferences(job(location="Remote"), user)
    assert service.matches_preferences(job(location="Nigeria"), user)
    assert not service.matches_preferences(job(location="Worldwide except Nigeria"), user)
    assert not service.matches_preferences(job(work_type="onsite"), user)
    user.country = "Niger"
    assert not service.matches_preferences(job(location="Nigeria"), user)
    user.country = ""; user.career_track = "Java Developer"
    assert not service.matches_preferences(job(title="JavaScript Developer", category="Frontend Developer"), user)


def test_employer_post_is_matched_and_application_immediately_notifies_job_owner(client, db, transport):
    user = candidate(db)
    user.job_alerts_enabled_at = datetime.utcnow()-timedelta(seconds=1); db.commit()
    posted = client.post("/api/v1/hr/jobs",headers=headers("hr@example.com"),json={
        "title":"DevOps Engineer","company":"Employer","location":"Worldwide",
        "description":"DevOps experience required","category":"DevOps Engineer","work_type":"remote",
    })
    assert posted.status_code == 200
    vacancy = db.get(Job,posted.json()["job_id"])
    assert vacancy.first_seen_at is not None and vacancy.posted_by_hr and not vacancy.url
    assert service.queue_job_digests(db,datetime.utcnow()+timedelta(seconds=1)) == 1
    db.add(Resume(owner_id=2,filename="optimized_internal.pdf",content=b"%PDF",analysis_data={"job_description":vacancy.description}))
    db.commit()
    response = client.post(f"/api/v1/jobs/{vacancy.id}/apply",headers=headers(),json={"resume_id":"internal"})
    assert response.status_code == 200 and response.json()["status"] == "submitted_internal"
    assert len(transport) == 1
    payload = transport[0][1]["json"]
    assert payload["event_type"] == "application.created" and payload["to_email"] == "hr@example.com"
    assert "candidate@example.com" not in json.dumps(payload) and "resume" not in json.dumps(payload)
    db.expire_all()
    event = db.get(AutomationEvent,f"baalebos-application-{response.json()['application_id']}")
    assert event.status == "sent"
    assert db.query(AutomationEvent).filter_by(event_type="jobs.matched").first().status == "pending"


def test_revoked_employer_cancels_pending_application_alert(client, db, monkeypatch, transport):
    monkeypatch.setattr("backend.app.routes.jobs.dispatch_pending", lambda **kwargs: None)
    vacancy = job(posted_by_hr=True,url=None,description="DevOps required",hr_user_id=3)
    db.add(vacancy); db.flush()
    db.add(Resume(owner_id=2,filename="optimized_revoked.pdf",content=b"%PDF",analysis_data={"job_description":vacancy.description}))
    db.commit()
    response = client.post(f"/api/v1/jobs/{vacancy.id}/apply",headers=headers(),json={"resume_id":"revoked"})
    assert response.status_code == 200
    db.get(User,3).hr_approved = False; db.commit()
    result = service.dispatch_pending(db,now=datetime.utcnow()+timedelta(seconds=1))
    assert result["cancelled"] == 1 and transport == []


def test_retry_survives_new_session_preserves_payload_and_redacts_errors(db, monkeypatch, caplog):
    service.enqueue(db, "baalebos-retry-test", "admin.summary", owner(db), {"subject": "Summary", "text": "No private applicant data"}, NOW)
    db.commit()
    calls = []
    def timeout(url, **kwargs):
        calls.append(kwargs["json"])
        raise TimeoutError("private-test-secret recipient@example.com private-provider-body")
    monkeypatch.setattr(service.httpx, "post", timeout)
    assert service.dispatch_pending(db, now=NOW)["retrying"] == 1
    assert "private-test-secret" not in caplog.text
    assert "recipient@example.com" not in caplog.text
    new_session = sessionmaker(bind=db.bind)()
    event = new_session.get(AutomationEvent, "baalebos-retry-test")
    assert event.attempts == 1 and event.status == "pending"
    assert event.first_attempt_at == NOW
    def accepted(url, **kwargs):
        calls.append(kwargs["json"])
        return SimpleNamespace(status_code=200, json=lambda: {"accepted": True, "provider_message_id": "email-id"})
    monkeypatch.setattr(service.httpx, "post", accepted)
    assert service.dispatch_pending(new_session, now=NOW+timedelta(minutes=3))["accepted"] == 1
    assert calls[0] == calls[1]
    assert service.dispatch_pending(new_session, now=NOW+timedelta(days=1))["accepted"] == 0
    new_session.close()


def test_active_lease_prevents_second_dispatcher_sending_same_event(db, monkeypatch):
    service.enqueue(db, "baalebos-claim-test", "admin.summary", owner(db), {"subject": "Summary", "text": "Text"}, NOW)
    db.commit(); calls = []
    def post(url, **kwargs):
        calls.append(kwargs)
        other = sessionmaker(bind=db.bind)()
        try: assert service.dispatch_pending(other, now=NOW)["accepted"] == 0
        finally: other.close()
        return SimpleNamespace(status_code=200, json=lambda: {"accepted": True, "provider_message_id": "email-id"})
    monkeypatch.setattr(service.httpx, "post", post)
    assert service.dispatch_pending(db, now=NOW)["accepted"] == 1
    assert len(calls) == 1


def test_expired_lease_recovered_and_24h_duplicate_risk_is_stopped(db, transport):
    service.enqueue(db, "baalebos-recover-test", "admin.summary", owner(db), {"subject": "Summary", "text": "Text"}, NOW)
    event = db.get(AutomationEvent, "baalebos-recover-test")
    event.status = "processing"; event.locked_until = NOW-timedelta(minutes=1)
    event.first_attempt_at = NOW-timedelta(minutes=10); event.attempts = 1
    db.commit()
    assert service.dispatch_pending(db, now=NOW)["accepted"] == 1
    service.enqueue(db, "baalebos-expired-test", "admin.summary", owner(db), {"subject": "Summary", "text": "Text"}, NOW)
    expired = db.get(AutomationEvent, "baalebos-expired-test")
    expired.first_attempt_at = NOW-timedelta(hours=25); expired.attempts = 1
    db.commit()
    assert service.dispatch_pending(db, now=NOW)["failed"] == 1
    assert len(transport) == 1
    assert expired.last_error == "retry_window_exhausted"


@pytest.mark.parametrize("ack", [{"accepted":True}, {"accepted":False,"provider_message_id":"id"}, {"accepted":True,"provider_message_id":1}])
def test_workflow_success_without_provider_acceptance_is_not_sent(db, monkeypatch, ack):
    service.enqueue(db, "baalebos-ack-test", "admin.summary", owner(db), {"subject": "Summary", "text": "Text"}, NOW)
    db.commit()
    monkeypatch.setattr(service.httpx, "post", lambda *args, **kwargs: SimpleNamespace(status_code=200,json=lambda:ack))
    assert service.dispatch_pending(db, now=NOW)["retrying"] == 1
    assert db.get(AutomationEvent, "baalebos-ack-test").status == "pending"


def test_unconfigured_automation_keeps_event_pending_without_spending_attempt(db, monkeypatch, transport):
    service.enqueue(db, "baalebos-disabled-test", "admin.summary", owner(db), {"subject": "Summary", "text": "Text"}, NOW)
    db.commit()
    monkeypatch.setattr(service.settings, "N8N_EVENTS_WEBHOOK_URL", "")
    service.dispatch_pending(db, now=NOW)
    assert db.get(AutomationEvent, "baalebos-disabled-test").attempts == 0
    assert transport == []


def test_missed_scrape_and_completed_day_summary_are_deduplicated(db):
    service.queue_admin_reports(db, NOW); db.commit()
    assert db.query(AutomationEvent).filter_by(event_type="scraper.stale").count() == 0
    for hours in (9, 10):
        service.queue_admin_reports(db, NOW+timedelta(hours=hours)); db.commit()
    assert db.query(AutomationEvent).filter_by(event_type="scraper.stale").count() == 1
    assert db.query(AutomationEvent).filter_by(event_type="admin.summary").count() == 1
    summary = db.query(AutomationEvent).filter_by(event_type="admin.summary").first()
    assert summary.payload["to_email"] == owner(db).email
    assert "employer receipt not verified" in summary.payload["text"]


def test_admin_summary_counts_internal_jobs_and_external_handoffs(db):
    yesterday = NOW-timedelta(days=1)
    internal = job(posted_by_hr=True,url=None,first_seen_at=yesterday)
    external = job(first_seen_at=yesterday)
    db.add_all([internal, external]); db.flush()
    db.add_all([Application(job_id=internal.id,user_id=2,submission_method="baalebos",status="submitted_internal",created_at=yesterday),
                Application(job_id=external.id,user_id=2,submission_method="external_handoff",status="submitted_external",created_at=yesterday)])
    db.commit()
    service.queue_admin_reports(db, NOW)
    report = db.query(AutomationEvent).filter_by(event_type="admin.summary").first().payload["text"]
    assert "New employer-posted listings: 1" in report
    assert "New external listings: 1" in report
    assert "Internal applications received: 1" in report
    assert "External application handoffs: 1" in report


def test_tick_requires_header_secret_and_admin_status_requires_owner(client, db):
    endpoint = "/api/v1/automation/tick"
    assert client.post(endpoint).status_code == 403
    assert client.post(endpoint, headers=headers()).status_code == 403
    assert client.post(endpoint, headers={"X-Baalebos-Webhook-Key":"wrong"}).status_code == 403
    assert client.get("/api/v1/admin/automation", headers=headers()).status_code == 403
    response = client.post(endpoint, headers={"X-Baalebos-Webhook-Key":"private-test-secret"})
    assert response.status_code == 200
    assert "@" not in response.text and "private-test-secret" not in response.text
    status = client.get("/api/v1/admin/automation", headers=headers(owner(db).email))
    assert status.status_code == 200 and status.headers["cache-control"] == "no-store"
    assert "to_email" not in status.text and "private-test-secret" not in status.text


def test_job_alerts_require_explicit_verified_consent_and_can_be_disabled(client, db):
    assert client.get("/api/v1/profile/me", headers=headers()).json()["job_alerts_enabled"] is False
    assert client.patch("/api/v1/profile/me", headers=headers(),json={"job_alerts_enabled":True}).status_code == 422
    db.get(User,2).is_verified = False; db.commit()
    assert client.patch("/api/v1/profile/me", headers=headers(),json={"job_alerts_enabled":True,"career_track":"DevOps Engineer"}).status_code == 422
    db.get(User,2).is_verified = True; db.commit()
    response = client.patch("/api/v1/profile/me", headers=headers(),json={"job_alerts_enabled":True,"career_track":"DevOps Engineer","job_alert_work_type":"remote"})
    assert response.status_code == 200
    assert db.get(User,2).job_alerts_enabled_at is not None
    assert client.patch("/api/v1/profile/me", headers=headers(),json={"job_alert_work_type":"invalid"}).status_code == 422
    assert client.patch("/api/v1/profile/me", headers=headers(),json={"job_alerts_enabled":None}).status_code == 422
    assert client.patch("/api/v1/profile/me", headers=headers(),json={"job_alerts_enabled":False}).json()["job_alerts_enabled"] is False


def test_internal_job_stays_visible_until_closed(client, db):
    internal = job(posted_by_hr=True, url=None,scraped_at=NOW-timedelta(days=30))
    external = job(scraped_at=NOW-timedelta(days=30))
    db.add_all([internal, external]); db.commit()
    listing = client.get("/api/v1/jobs/").json()
    assert internal.id in [entry["id"] for entry in listing]
    assert external.id not in [entry["id"] for entry in listing]
    internal.is_active = False; db.commit()
    assert internal.id not in [entry["id"] for entry in client.get("/api/v1/jobs/").json()]


@pytest.mark.parametrize("outcome,status", [("empty","empty"),("http_failure","failed"),("parse_failure","failed"),("timeout","failed")])
def test_source_monitoring_distinguishes_healthy_empty_from_swallowed_errors(monkeypatch, outcome, status):
    def get(*args, **kwargs):
        if outcome == "timeout": raise TimeoutError("private-url")
        def body():
            if outcome == "parse_failure": raise ValueError("private-body")
            return {"jobs":[]}
        return SimpleNamespace(status_code=429 if outcome == "http_failure" else 200,json=body)
    monkeypatch.setattr(scraper.requests, "get", get)
    jobs, result = scraper._observe_source("Remotive", lambda: scraper.scrape_remotive("DevOps Engineer"))
    assert jobs == [] and result["status"] == status
    assert "private" not in json.dumps(result)


def test_saver_keeps_valid_rows_when_one_row_is_invalid_and_preserves_first_seen(db):
    base = dict(title="DevOps Engineer",company="Employer",location="Worldwide",source="Test",category="DevOps Engineer")
    stats = {"db_errors":0}
    assert scraper.save_jobs_to_db([{**base,"url":"https://example.com/1"},
                                    {**base,"location":["invalid"],"url":"https://example.com/bad"},
                                    {**base,"url":"https://example.com/2"}],db,stats) == 2
    assert db.query(Job).count() == 2 and stats["db_errors"] == 1
    first = db.query(Job).filter_by(url="https://example.com/1").first().first_seen_at
    assert scraper.save_jobs_to_db([{**base,"url":"https://example.com/1"}],db) == 0
    assert db.query(Job).filter_by(url="https://example.com/1").first().first_seen_at == first


@pytest.mark.parametrize("failed", [True, False])
def test_scrape_run_persists_outcomes_for_cron_admin_and_worker_entrypoints(db, monkeypatch, failed):
    def source():
        if failed: raise TimeoutError("private-provider-error")
        return []
    names = ["scrape_themuse","scrape_weworkremotely","scrape_greenhouse","scrape_lever","scrape_arbeitnow",
             "scrape_skillsire","scrape_micro1","scrape_amazon_jobs","scrape_remoteok","scrape_jobstash"]
    for name in names: monkeypatch.setattr(scraper,name,source)
    monkeypatch.setattr(scraper,"SEARCH_TERMS",[]); monkeypatch.setattr(scraper,"TECH_ROLES",[])
    monkeypatch.setattr(scraper,"SessionLocal",sessionmaker(bind=db.bind))
    result = scraper.scrape_global_jobs()
    record = db.get(ScrapeRun,result["run_id"])
    assert result["status"] == ("failed" if failed else "empty")
    assert record.status == result["status"] and record.finished_at is not None
    assert len(result["source_results"]) == 10
    assert result["failed_sources"] == (10 if failed else 0)


def test_migration_is_repeatable_and_does_not_alert_on_historical_jobs():
    path = ROOT / "alembic/versions/20261010_job_automation.py"
    spec = importlib.util.spec_from_file_location("job_automation_migration",path)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR)"))
        conn.execute(text("CREATE TABLE jobs (id INTEGER PRIMARY KEY, title VARCHAR)"))
        conn.execute(text("INSERT INTO users VALUES (1,'user@example.com')"))
        conn.execute(text("INSERT INTO jobs VALUES (1,'Existing job')"))
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade(); migration.upgrade()
        assert conn.execute(text("SELECT job_alerts_enabled FROM users")).scalar() == 0
        assert conn.execute(text("SELECT first_seen_at FROM jobs")).scalar() is None
        assert {"automation_events","scrape_runs","automation_state"}.issubset(set(inspect(conn).get_table_names()))
    engine.dispose()


def test_importable_workflow_contract_executes_without_secrets_or_live_email():
    if not shutil.which("node"): pytest.skip("Node required for workflow contract validation")
    workflow = json.loads((ROOT / "workflows/n8n/job-events.json").read_text())
    assert workflow["active"] is False
    nodes = {node["name"]:node for node in workflow["nodes"]}
    assert nodes["Baalebos Webhook"]["parameters"]["authentication"] == "headerAuth"
    assert nodes["Send With Resend"]["parameters"]["headerParameters"]["parameters"][0]["value"] == "={{ $json.idempotency_key }}"
    code = nodes["Prepare Email"]["parameters"]["jsCode"]
    cases = [{"event_id":"baalebos-application-10","application_id":10,"job_title":"DevOps Engineer","employer_email":"hr@example.com"}]
    for event_type in ["jobs.matched","application.created","admin.summary","scraper.warning","scraper.stale"]:
        cases.append({"event_id":"baalebos-test-1","event_type":event_type,"to_email":"user@example.com","subject":"Subject","text":"Message"})
    runner = '''const vm=require('node:vm'); const input=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
for(const body of input.cases){const result=vm.runInNewContext('(function(){'+input.code+'})()',{$input:{first:()=>({json:{body}})}});if(!result[0].json.to)throw Error('No recipient');}
for(const body of [{event_id:'bad'}, {...input.cases[1],event_type:'unsupported'}]){let denied=false;try{vm.runInNewContext('(function(){'+input.code+'})()',{$input:{first:()=>({json:{body}})}});}catch{denied=true;}if(!denied)throw Error('Invalid event accepted');}
process.stdout.write('validated');'''
    result = subprocess.run(["node","-e",runner],input=json.dumps({"code":code,"cases":cases}),text=True,capture_output=True,check=True)
    assert result.stdout == "validated"
    maintenance = json.loads((ROOT / "workflows/n8n/maintenance.json").read_text())
    assert maintenance["active"] is False
    assert maintenance["connections"]["Process Notifications"]["main"][1][0]["node"] == "Report Maintenance Failure"
