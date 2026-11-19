# Production hardening rollout

Covers the AI Resume Refiner, ingestion hardening, auth/RBAC, data-layer
scaling and the audit/privacy/observability work. Deploy in this order.

## 0. Before deploying (people, not code)

1. **Rotate every credential that was ever committed.** `terraform/main.tf`
   held a database password default and the launch template a production
   `SECRET_KEY`; `backend/job_hunter.db`, `terraform/tfplan` and the
   `terraform.tfstate.*.backup` files are still in Git history. Rotate the
   RDS master password, `SECRET_KEY`, mail password, AI and Stripe keys.
   Rotating `SECRET_KEY` also invalidates every old session.
2. **Decide on purging history** (`git filter-repo` + force push). Rotation is
   what removes the risk; purging stops further copies.
3. **Refresh-cookie site:** the dashboard (`www.baalebo.xyz`) calls the API
   cross-site. A `SameSite=Strict` cookie is only sent if the API is on the
   same site, e.g. `api.baalebo.xyz` (Railway custom domain + DNS CNAME). Until
   then set `REFRESH_COOKIE_SAMESITE=none` (sent cross-site, still
   `Secure; HttpOnly`) or users are signed out every 15 minutes.

## 1. Environment variables (Railway: API and worker)

| Variable | Value | Notes |
| --- | --- | --- |
| `SECRET_KEY` | new random 64+ chars | rotated |
| `ADMIN_EMAIL` | the owner's verified email | read once by the RBAC migration to grant `super_admin` |
| `TRUSTED_PROXY_CIDRS` | Railway/ALB proxy ranges | only these peers' `X-Forwarded-For` is honoured; default = private ranges |
| `REFRESH_COOKIE_SAMESITE` | `strict` (same site) or `none` | see 0.3 |
| `CRON_SECRET` | random | callers must send `X-Cron-Secret`; `?secret=` no longer works |
| `RESUME_S3_BUCKET`, `RESUME_S3_KMS_KEY_ID`, `AWS_REGION` (+ credentials) | from `terraform output` | omit to keep PDFs in Postgres |
| `RESUME_PROCESSING_MODE` | `sync` (default) or `async` | `async` requires the Celery worker service |
| `DATABASE_READ_URL`, `DATABASE_READ_POOLER=pgbouncer` | optional | read replica for read-only GETs |
| `METRICS_TOKEN` | random | bearer token for Prometheus scrapes of `/metrics` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` (+ `OTEL_EXPORTER_OTLP_HEADERS`) | optional | ADOT/CloudWatch, Datadog Agent or Grafana Alloy |
| `ALERT_P95_MS`, `ALERT_UNAUTHORIZED_PER_5M`, `ALERT_5XX_PER_5M` | 350 / 25 / 10 | dashboard alert thresholds |
| `AUDIT_RETENTION_DAYS`, `RESUME_RETENTION_DAYS` | 400 / 0 | 0 keeps resumes until the user deletes them |

## 2. Schema

`railway.toml` runs `python -m backend.scripts.migrate` as the pre-deploy
command. It detects a legacy database (created by the removed startup DDL,
no `alembic_version`), stamps the old baseline and upgrades; fresh databases
get the full schema. Indexes are built `CONCURRENTLY`. Take a backup first.
Verified against PostgreSQL 16 for fresh, legacy and already-stamped databases.

## 3. Deploy API, worker and dashboard together

The dashboard now relies on `/auth/refresh`, JSON password-reset bodies and
the governance API. Everyone is signed out once (legacy 30-day tokens are
rejected). Users with legacy password hashes are upgraded on next sign-in.

## 4. After deploy

1. Sign in as the owner and open **Security & governance**; assign other roles.
2. If S3 is configured: `python -m backend.scripts.migrate_resume_blobs` until
   it reports `remaining=0`; then a follow-up migration can drop `resumes.content`.
3. Point Prometheus at `/metrics` with `Authorization: Bearer $METRICS_TOKEN`.
4. Optionally switch `RESUME_PROCESSING_MODE=async` once the worker is healthy.
5. Terraform (EC2/RDS stack): `terraform -chdir=terraform/bootstrap apply`, then
   `terraform -chdir=terraform init -backend-config=backend.hcl -migrate-state`.
   `manage_master_user_password` rotates the RDS password into Secrets Manager.
