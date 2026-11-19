"""Observability and governance API for the compliance dashboard."""
import csv
import io
import json
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from backend.app.database import get_read_db
from backend.app.dependencies.roles import require_permission
from backend.app.models.audit import AuditLog

router = APIRouter(tags=["Governance"])

P95_ALERT_MS = float(os.getenv("ALERT_P95_MS", "350"))
UNAUTHORIZED_ALERT = int(os.getenv("ALERT_UNAUTHORIZED_PER_5M", "25"))
ERROR_ALERT = int(os.getenv("ALERT_5XX_PER_5M", "10"))


def build_alerts(summary: dict) -> list[dict]:
    alerts = []
    if summary.get("p95_ms") is not None and summary["p95_ms"] > P95_ALERT_MS:
        alerts.append({"severity": "warning", "kind": "latency",
                       "message": f"p95 latency {summary['p95_ms']:.0f} ms exceeds {P95_ALERT_MS:.0f} ms"})
    denied = summary.get("unauthorized_401", 0) + summary.get("forbidden_403", 0)
    if denied >= UNAUTHORIZED_ALERT:
        alerts.append({"severity": "critical", "kind": "unauthorized_probe",
                       "message": f"{denied} unauthorized/forbidden responses in {summary['window_minutes']} minutes"})
    if summary.get("server_errors", 0) >= ERROR_ALERT:
        alerts.append({"severity": "critical", "kind": "errors",
                       "message": f"{summary['server_errors']} server errors in {summary['window_minutes']} minutes"})
    return alerts


@router.get("/summary")
def live_summary(minutes: int = Query(5, ge=1, le=60), _=Depends(require_permission("metrics:read"))):
    from backend.app.core.metrics import window_summary
    summary = window_summary(minutes)
    summary["alerts"] = build_alerts(summary)
    summary["thresholds"] = {"p95_ms": P95_ALERT_MS, "unauthorized": UNAUTHORIZED_ALERT, "server_errors": ERROR_ALERT}
    return summary


@router.get("/audit")
def audit_trail(db: Session = Depends(get_read_db), _=Depends(require_permission("audit:read")),
                action: str = "", outcome: str = "", limit: int = Query(100, ge=1, le=500),
                before_id: int | None = None):
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    if outcome:
        query = query.filter(AuditLog.outcome == outcome)
    if before_id:
        query = query.filter(AuditLog.id < before_id)
    rows = query.order_by(AuditLog.id.desc()).limit(limit).all()
    return [{"id": r.id, "ts": r.ts.isoformat() + "Z", "trace_id": r.trace_id, "kind": r.kind, "action": r.action,
             "actor": r.actor_display, "actor_role": r.actor_role, "method": r.method, "route": r.route,
             "status": r.status, "latency_ms": r.latency_ms, "outcome": r.outcome, "ip": r.ip_masked,
             "details": r.details} for r in rows]


def weekly_report_data(db: Session, end: datetime | None = None) -> dict:
    end = end or datetime.utcnow()
    start = end - timedelta(days=7)
    window = db.query(AuditLog).filter(AuditLog.ts >= start, AuditLog.ts < end)
    requests = window.filter(AuditLog.kind == "request")
    by_outcome = dict(requests.with_entities(AuditLog.outcome, func.count()).group_by(AuditLog.outcome).all())
    daily = requests.with_entities(func.date(AuditLog.ts), func.count(),
                                   func.sum(case((AuditLog.status.in_([401, 403]), 1), else_=0)),
                                   func.sum(case((AuditLog.status >= 500, 1), else_=0))) \
        .group_by(func.date(AuditLog.ts)).order_by(func.date(AuditLog.ts)).all()
    latencies = [v for (v,) in requests.with_entities(AuditLog.latency_ms).filter(AuditLog.latency_ms.isnot(None))
                 .order_by(AuditLog.id.desc()).limit(50000)]
    from backend.app.core.metrics import percentile
    top_routes = requests.with_entities(AuditLog.method, AuditLog.route, func.count().label("n"), func.avg(AuditLog.latency_ms)) \
        .group_by(AuditLog.method, AuditLog.route).order_by(func.count().desc()).limit(10).all()
    denied_routes = requests.filter(AuditLog.status.in_([401, 403])).with_entities(AuditLog.route, func.count()) \
        .group_by(AuditLog.route).order_by(func.count().desc()).limit(10).all()
    events = window.filter(AuditLog.kind == "event").with_entities(AuditLog.action, func.count()) \
        .group_by(AuditLog.action).order_by(AuditLog.action).all()
    return {
        "period": {"start": start.isoformat() + "Z", "end": end.isoformat() + "Z"},
        "totals": {"requests": sum(by_outcome.values()), **{k or "unknown": v for k, v in by_outcome.items()}},
        "latency_ms": {"p50": percentile(latencies, 50), "p95": percentile(latencies, 95), "p99": percentile(latencies, 99)},
        "daily": [{"date": str(d), "requests": n, "denied": int(den or 0), "errors": int(err or 0)} for d, n, den, err in daily],
        "top_routes": [{"method": m, "route": r, "requests": n, "avg_latency_ms": round(a or 0, 1)} for m, r, n, a in top_routes],
        "denied_routes": [{"route": r, "count": n} for r, n in denied_routes],
        "governance_events": [{"action": a, "count": n} for a, n in events],
    }


def render_markdown(data: dict) -> str:
    t, lat = data["totals"], data["latency_ms"]
    fmt = lambda v: "n/a" if v is None else f"{v:.0f} ms"
    lines = [f"# Weekly security & reliability report", "",
             f"Period: {data['period']['start']} to {data['period']['end']}", "",
             "## Summary", "", "| Metric | Value |", "| --- | --- |",
             f"| Requests | {t.get('requests', 0)} |", f"| Denied (401/403) | {t.get('denied', 0)} |",
             f"| Server errors | {t.get('error', 0)} |", f"| p50 / p95 / p99 latency | {fmt(lat['p50'])} / {fmt(lat['p95'])} / {fmt(lat['p99'])} |",
             "", "## Daily", "", "| Date | Requests | Denied | Errors |", "| --- | --- | --- | --- |"]
    lines += [f"| {d['date']} | {d['requests']} | {d['denied']} | {d['errors']} |" for d in data["daily"]]
    lines += ["", "## Busiest routes", "", "| Method | Route | Requests | Avg latency |", "| --- | --- | --- | --- |"]
    lines += [f"| {r['method']} | `{r['route']}` | {r['requests']} | {r['avg_latency_ms']} ms |" for r in data["top_routes"]]
    lines += ["", "## Unauthorized / forbidden by route", ""]
    lines += [f"- `{r['route']}`: {r['count']}" for r in data["denied_routes"]] or ["- none"]
    lines += ["", "## Governance events", ""]
    lines += [f"- {e['action']}: {e['count']}" for e in data["governance_events"]] or ["- none"]
    return "\n".join(lines) + "\n"


def render_csv(data: dict) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["section", "key", "requests", "denied", "errors", "value"])
    for d in data["daily"]:
        writer.writerow(["daily", d["date"], d["requests"], d["denied"], d["errors"], ""])
    for r in data["top_routes"]:
        writer.writerow(["route", f"{r['method']} {r['route']}", r["requests"], "", "", r["avg_latency_ms"]])
    for r in data["denied_routes"]:
        writer.writerow(["denied_route", r["route"], "", r["count"], "", ""])
    for e in data["governance_events"]:
        writer.writerow(["event", e["action"], "", "", "", e["count"]])
    for key, value in data["latency_ms"].items():
        writer.writerow(["latency_ms", key, "", "", "", value])
    return out.getvalue()


@router.get("/reports/weekly")
def weekly_report(format: str = Query("json", pattern="^(json|csv|md)$"), db: Session = Depends(get_read_db),
                  _=Depends(require_permission("reports:read"))):
    data = weekly_report_data(db)
    stamp = datetime.utcnow().strftime("%Y-%m-%d")
    if format == "md":
        body, media = render_markdown(data), "text/markdown; charset=utf-8"
    elif format == "csv":
        body, media = render_csv(data), "text/csv; charset=utf-8"
    else:
        body, media = json.dumps(data, indent=2, default=str), "application/json"
    return Response(body, media_type=media, headers={
        "Content-Disposition": f'attachment; filename="weekly-report-{stamp}.{format}"', "Cache-Control": "private, no-store"})
