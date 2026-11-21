# Deploying the API on a new Railway account

## 1. Services
Create a project from the GitHub repo and add:

| Service | Needed | Notes |
|---|---|---|
| **API** (this repo) | yes | settings below |
| **PostgreSQL** | yes | Railway template |
| **Redis** | yes | rate limits, sign-in lockouts, job-application queue |
| Worker (Celery) | optional | processes queued job applications; same repo, start command `/app/start-worker.sh` |

Resume processing runs inside the API (`RESUME_PROCESSING_MODE=sync`, the default), so no worker is needed for it.

## 2. API service settings
| Setting | Value |
|---|---|
| Root Directory | `backend` |
| Builder | Dockerfile |
| Dockerfile Path | `Dockerfile` |
| Custom Start Command | `/app/start.sh` |
| **Pre-deploy step** | `python -m backend.scripts.migrate` |
| **Healthcheck Path** | `/health` |
| Restart Policy | On Failure |
| Networking | Generate Domain (the app listens on Railway's `$PORT`) |

With Root Directory `backend`, Railway does not read the repo-root `railway.toml`,
so the pre-deploy step and health check must be set here.

## 3. Variables (API service)
Reference the databases instead of pasting URLs:
`DATABASE_URL=${{Postgres.DATABASE_URL}}` and `REDIS_URL=${{Redis.REDIS_URL}}`.
Then copy the rest from `railway.env.example`. Required:

- `ENVIRONMENT=production`, `PYTHONPATH=/app`, `OUTPUT_DIR=/app/output`
- `FRONTEND_URL=https://baalebo.xyz`
- `SECRET_KEY` (64+ random characters; a new key signs everyone out once)
- `ACCESS_TOKEN_EXPIRE_MINUTES=15` (**must be 1-60**; the old `43200` stops the API starting)
- `REFRESH_COOKIE_SAMESITE=none` (dashboard and API are on different sites)
- `GROQ_API_KEY`
- `RESEND_API_KEY`, `EMAILS_FROM_EMAIL`, `EMAILS_FROM_NAME`, `ADMIN_EMAIL`

Optional: `MAXMIND_LICENSE_KEY`, `METRICS_TOKEN`, `N8N_*`, `ADMIN_2FA_REQUIRED` (default true).

## 4. Point the dashboard at the new API
Vercel → project → Settings → Environment Variables:
`VITE_API_URL=https://<new-api-domain>/api/v1`, then **Redeploy** (Vite reads it at build time).

## 5. Data
**Move the old database (if the old Postgres is still reachable):**
```bash
pg_dump --no-owner --no-acl -Fc "$OLD_DATABASE_PUBLIC_URL" -f baalebos.dump
pg_restore --no-owner --no-acl -d "$NEW_DATABASE_PUBLIC_URL" baalebos.dump
```
Use each database's *public* URL (Postgres service → Connect). Restore into the
**empty** new database **before the first API deploy**; the pre-deploy step then
upgrades the old schema in place (tested against a copy of the 18 Nov schema).

**Fresh start:** the first deploy creates the schema. Sign up with the owner email,
verify it, then run this once inside the running API service
(`railway ssh` with the CLI linked to the project and API service):
```bash
python -m backend.scripts.provision_owner you@example.com
```
`railway run` executes on your own machine, where the private database host does
not resolve, so use `railway ssh`.

## 6. Check
`https://<new-api-domain>/health` returns 200; sign in on the dashboard; open the
Owner console and set up two-step verification (save the recovery codes).
