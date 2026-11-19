"""Prometheus metrics and cross-replica observability windows.

``/metrics`` exposes per-process Prometheus series (scraped per replica).
``record_request`` additionally keeps one-minute buckets in the shared store
(Redis) so the governance dashboard can alert on fleet-wide p95 latency and
401/403 spikes without a Prometheus server.
"""
from __future__ import annotations

import math
import time

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from prometheus_client.core import GaugeMetricFamily

REGISTRY = CollectorRegistry(auto_describe=True)

HTTP_REQUESTS = Counter('http_requests_total', 'HTTP requests', ['method', 'route', 'status'], registry=REGISTRY)
HTTP_LATENCY = Histogram('http_request_duration_seconds', 'Request latency', ['method', 'route'], registry=REGISTRY,
                         buckets=(0.025, 0.05, 0.1, 0.2, 0.35, 0.5, 0.75, 1, 2, 5, 10, 30, 60))
UNAUTHORIZED_ATTEMPTS = Counter('unauthorized_attempts_total', '401/403 responses by reason', ['status', 'reason'], registry=REGISTRY)
SANITIZATION_BLOCKS = Counter('sanitization_blocks_total', 'Markup/PDF-injection tokens removed from untrusted text', registry=REGISTRY)
OCR_FALLBACKS = Counter('ocr_fallback_total', 'OCR fallback attempts by outcome', ['outcome'], registry=REGISTRY)
PDF_SINGLE_PAGE_PASS = Counter('pdf_single_page_pass_total', 'One-page resume exports by layout profile', ['layout', 'condensed'], registry=REGISTRY)
RATE_LIMITED = Counter('rate_limited_total', 'Requests rejected by rate limiting', ['route'], registry=REGISTRY)


class _PoolCollector:
    """DB read/write pool saturation, sampled at scrape time."""

    def collect(self):
        gauge = GaugeMetricFamily('db_pool_connections', 'SQLAlchemy pool connections', labels=['engine', 'state'])
        saturation = GaugeMetricFamily('db_pool_saturation_ratio', 'checked_out / (size + max overflow)', labels=['engine'])
        try:
            from backend.app.database import pool_status
            for name, stats in pool_status().items():
                gauge.add_metric([name, 'checked_out'], stats['checked_out'])
                gauge.add_metric([name, 'size'], stats['size'])
                capacity = max(stats['size'] + max(stats.get('overflow', 0), 0), 1)
                saturation.add_metric([name], stats['checked_out'] / capacity)
        except Exception:
            pass
        yield gauge
        yield saturation


REGISTRY.register(_PoolCollector())


def render() -> bytes:
    return generate_latest(REGISTRY)


# ── Fleet-wide windows (shared store) ────────────────────────────────────────
WINDOW_TTL = 2 * 3600


def _minute(ts: float | None = None) -> int:
    return int((ts or time.time()) // 60)


def record_request(route: str, status: int, latency_ms: float):
    from backend.app.core.kv_store import safe_call
    minute = _minute()
    try:
        safe_call('incr', f'obs:{minute}:total', 1, WINDOW_TTL)
        if status in (401, 403):
            safe_call('incr', f'obs:{minute}:s{status}', 1, WINDOW_TTL)
        if status >= 500:
            safe_call('incr', f'obs:{minute}:s5xx', 1, WINDOW_TTL)
        safe_call('push_sample', f'obs:{minute}:lat', round(latency_ms, 2), 2000, WINDOW_TTL)
    except Exception:
        pass


def percentile(values, pct: float):
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(pct / 100 * len(ordered)) - 1)
    return ordered[index]


def window_summary(minutes: int = 5) -> dict:
    from backend.app.core.kv_store import safe_call
    now = _minute()
    total = s401 = s403 = s5xx = 0
    latencies, series = [], []
    for minute in range(now - minutes + 1, now + 1):
        get = lambda suffix: int(safe_call('get', f'obs:{minute}:{suffix}', default=0) or 0)
        bucket = {'minute': minute * 60, 'total': get('total'), 's401': get('s401'), 's403': get('s403'), 's5xx': get('s5xx')}
        lat = safe_call('samples', f'obs:{minute}:lat', default=[]) or []
        bucket['p95_ms'] = percentile(lat, 95)
        series.append(bucket)
        total += bucket['total']; s401 += bucket['s401']; s403 += bucket['s403']; s5xx += bucket['s5xx']
        latencies.extend(lat)
    return {'window_minutes': minutes, 'requests': total, 'unauthorized_401': s401, 'forbidden_403': s403,
            'server_errors': s5xx, 'p95_ms': percentile(latencies, 95), 'p50_ms': percentile(latencies, 50),
            'series': series}
