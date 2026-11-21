# Monitoring: Prometheus + Grafana

The API exposes Prometheus metrics at `/metrics`, protected by a bearer token
(`METRICS_TOKEN`). This folder ships a ready-to-deploy Prometheus (scrape config
plus alert rules) and a Grafana with the datasource and the **Baalebos Overview**
dashboard provisioned.

| Path | What it is |
|---|---|
| `prometheus/prometheus.yml.tmpl` | Scrape config, rendered at start from env vars |
| `prometheus/alerts.yml` | Alert rules (below) |
| `grafana/provisioning/` | Prometheus datasource (`PROMETHEUS_URL`) and dashboard provider |
| `grafana/dashboards/baalebos-overview.json` | Traffic & latency, Security, Platform rows |

## Metrics the API exports

| Metric | Labels | Meaning |
|---|---|---|
| `http_requests_total` | method, route, status | Requests served |
| `http_request_duration_seconds` | method, route | Latency histogram |
| `auth_login_attempts_total` | portal, outcome | Sign-ins: `success`, `failed`, `blocked`, `denied` |
| `security_events_total` | event | Every recorded security event (see Admin → Security) |
| `rate_limited_total` | route | Requests rejected by rate limits |
| `db_pool_saturation_ratio` | engine | Checked-out / (pool size + overflow) |

Metrics are counts only: no IPs, emails or locations ever leave the API through
`/metrics`. Per-person detail lives in the admin Security tab, which is admin-only
and records every view.

## Alerts

| Alert | Fires when |
|---|---|
| `ApiDown` | Scrape fails for 2 min |
| `HighServerErrorRate` | 5xx > 5 % of requests for 10 min |
| `SlowApi` | p95 latency > 2 s for 10 min |
| `SignInFailureSpike` | > 30 failed/blocked sign-ins in 10 min (credential stuffing) |
| `DatabasePoolSaturated` | Pool > 90 % for 5 min |

Alerts are visible in Prometheus (`/alerts`) and Grafana. To get notified, add
an Alertmanager or use Grafana Cloud alerting with your email or Slack.

## Local

Add to `.env`:

```
METRICS_TOKEN=<python3 -c "import secrets; print(secrets.token_urlsafe(32))">
GRAFANA_ADMIN_PASSWORD=<a strong password>
```

```bash
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up --build
```

Prometheus: http://localhost:9090 · Grafana: http://localhost:3001 (user `admin`).

## Production on Railway

1. **Backend service** → Variables: `METRICS_TOKEN=<random 32+ chars>`.
2. **New service → GitHub repo**, root directory `monitoring/prometheus`
   (it builds the Dockerfile there). Variables:
   - `API_TARGET` = `<backend-service>.railway.internal:<backend PORT>` with `API_SCHEME=http`
     (private network, recommended), or `<your-api-domain>:443` with `API_SCHEME=https`
   - `METRICS_TOKEN` = `${{<backend-service>.METRICS_TOKEN}}` (reference variable)
   - optional `RETENTION` (default `15d`)
   - Add a **volume** mounted at `/prometheus` so history survives redeploys.
   - Do **not** give it a public domain; Grafana reaches it privately.
3. **New service**, root directory `monitoring/grafana`. Variables:
   - `PROMETHEUS_URL` = `http://<prometheus-service>.railway.internal:9090`
   - `GF_SECURITY_ADMIN_PASSWORD` = a strong password
   - `GF_SERVER_ROOT_URL` = `https://<grafana-domain>`
   - Add a volume at `/var/lib/grafana`, then generate a public domain on port 3000.
4. **Vercel** (dashboard) → `VITE_GRAFANA_URL=https://<grafana-domain>` and redeploy;
   Admin → Security then shows an "Open Grafana" button.

Railway's private network is IPv6: Prometheus resolves `*.railway.internal`
normally, and the API must listen on `::` or `0.0.0.0` (uvicorn `--host 0.0.0.0`
works on Railway's dual-stack network).

### Alternative: Grafana Cloud (free tier)

Skip both services: in Grafana Cloud add a **Metrics Endpoint** (hosted scrape)
integration pointing at `https://<your-api-domain>/metrics` with bearer token
`METRICS_TOKEN`, then import `grafana/dashboards/baalebos-overview.json` and
choose the Grafana Cloud Prometheus datasource.

## Scaling

The API is stateless, so you can add replicas on Railway. A static target
scrapes one replica per scrape. To scrape every replica, replace
`static_configs` in `prometheus.yml.tmpl` with DNS discovery of the private name
(Railway returns one AAAA record per replica):

```yaml
    dns_sd_configs:
      - names: ["<backend-service>.railway.internal"]
        type: AAAA
        port: <backend PORT>
```

Counters are per process and the dashboard sums them, so totals stay correct as
replicas come and go. The admin Security tab reads the database, so it always
covers every replica.
