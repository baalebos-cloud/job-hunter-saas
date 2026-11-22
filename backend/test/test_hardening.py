"""Security hardening: secure-by-default environment, CORS, full route names in audit/metrics."""
import os
import subprocess
import sys

from fastapi.testclient import TestClient
from starlette.requests import Request

from backend.app.main import _route_template, app

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def _probe(environment):
    """Import the app in a fresh interpreter with the given ENVIRONMENT."""
    env = {**os.environ, 'PYTHONPATH': ROOT, 'DATABASE_URL': 'sqlite://', 'SECRET_KEY': 'probe-secret'}
    env.pop('ENVIRONMENT', None)
    if environment is not None:
        env['ENVIRONMENT'] = environment
    code = ("from fastapi.testclient import TestClient\nfrom backend.app import main\n"
            "c = TestClient(main.app, base_url='https://testserver')\n"
            "r = c.get('/health')\n"
            "print(main.IS_DEVELOPMENT, c.get('/docs').status_code, 'Strict-Transport-Security' in r.headers)")
    out = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True, timeout=120, cwd=ROOT)
    assert out.returncode == 0, out.stderr[-2000:]
    return out.stdout.strip().splitlines()[-1]


def test_production_protections_are_on_unless_explicitly_development():
    assert _probe(None) == 'False 404 True'            # variable missing: secure
    assert _probe('Production ') == 'False 404 True'   # case/space tolerant
    assert _probe('typo') == 'False 404 True'          # unknown value: secure
    assert _probe('development') == 'True 200 False'


def test_cors_no_longer_trusts_the_retired_railway_domain():
    origin = 'https://job-hunter-saas-production-bb41.up.railway.app'
    r = TestClient(app).options('/api/v1/auth/me', headers={'Origin': origin, 'Access-Control-Request-Method': 'GET'})
    assert r.headers.get('access-control-allow-origin') != origin


def _request(path, template, params):
    class Route:
        pass
    route = Route()
    route.path = template
    return Request({'type': 'http', 'path': path, 'path_params': params, 'route': route, 'headers': []})


def test_route_template_keeps_the_router_prefix_and_hides_ids():
    assert _route_template(_request('/api/v1/auth/me', '/me', {})) == '/api/v1/auth/me'
    assert _route_template(_request('/api/v1/jobs/board/12', '/board/{job_id}', {'job_id': 12})) == '/api/v1/jobs/board/{job_id}'
    assert _route_template(_request('/api/v1/profile/photo/ab12.webp', '/photo/{token}.webp', {'token': 'ab12'})) \
        == '/api/v1/profile/photo/{token}.webp'
    assert _route_template(_request('/api/v1/x/5', '/x/{n:int}', {'n': 5})) == '/api/v1/x/{n:int}'
    assert _route_template(Request({'type': 'http', 'path': '/nowhere', 'headers': []})) == 'unmatched'
