#!/bin/sh
# Render prometheus.yml from the environment, then start Prometheus.
#   API_TARGET     host:port of the backend (e.g. backend.railway.internal:8080)
#   API_SCHEME     http (private network) or https (public URL); default http
#   METRICS_TOKEN  same value as the backend's METRICS_TOKEN
set -eu
: "${API_TARGET:?Set API_TARGET to the backend host:port}"
: "${METRICS_TOKEN:?Set METRICS_TOKEN to the backend METRICS_TOKEN}"
API_SCHEME="${API_SCHEME:-http}"
printf '%s' "$METRICS_TOKEN" > /etc/prometheus/metrics_token
sed -e "s|\${API_TARGET}|${API_TARGET}|g" -e "s|\${API_SCHEME}|${API_SCHEME}|g" \
    /etc/prometheus/prometheus.yml.tmpl > /etc/prometheus/prometheus.yml
exec /bin/prometheus --config.file=/etc/prometheus/prometheus.yml \
  --storage.tsdb.path=/prometheus --storage.tsdb.retention.time="${RETENTION:-15d}" \
  --web.listen-address=":${PORT:-9090}" "$@"
