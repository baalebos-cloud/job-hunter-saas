#!/bin/sh
# Worker service — runs a minimal HTTP server for Railway healthcheck
# Analysis runs directly in the API, no Celery/Redis needed
python3 -c "
import http.server, os

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{\"status\":\"worker-standby\"}')
    def log_message(self, *args):
        pass  # suppress logs

port = int(os.environ.get('PORT', 8001))
print(f'Worker standby server on port {port}')
http.server.HTTPServer(('0.0.0.0', port), Handler).serve_forever()
"
