"""Loopback-only HTTP workbench. Never instantiates cloud clients."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from .engine import analyze, report
from .store import Store

ROOT = Path(__file__).resolve().parent.parent
MAX_BYTES = 5 * 1024 * 1024

def handler(store):
    class Handler(BaseHTTPRequestHandler):
        def respond(self, status, body, kind='application/json'):
            if isinstance(body, (dict, list)):
                body = json.dumps(body).encode()
            elif isinstance(body, str):
                body = body.encode()
            self.send_response(status)
            self.send_header('Content-Type', kind + '; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)
        def do_GET(self):
            path = urlsplit(self.path).path
            if path == '/api/health':
                return self.respond(200, {'status': 'ok', 'mode': 'local', 'engine': 'deterministic', 'cloud_connections': 0})
            if path == '/api/investigations':
                return self.respond(200, [{k: v for k, v in r.items() if k != 'evidence'} for r in store.list()])
            if path.startswith('/api/investigations/'):
                parts = path.split('/')
                result = store.get(parts[3])
                if not result:
                    return self.respond(404, {'error': 'Investigation not found'})
                if len(parts) == 5 and parts[4] == 'report':
                    return self.respond(200, report(result), 'text/markdown')
                if len(parts) == 4:
                    return self.respond(200, result)
                return self.respond(404, {'error': 'Not found'})
            assets = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'application/javascript'), '/style.css': ('style.css', 'text/css')}
            if path in assets:
                name, kind = assets[path]
                return self.respond(200, (ROOT / 'web' / name).read_bytes(), kind)
            return self.respond(404, {'error': 'Not found'})
        def do_POST(self):
            # Same-origin browser writes only; no CORS and no remote binding.
            origin = self.headers.get('Origin')
            if origin and origin not in ('http://127.0.0.1:' + str(self.server.server_port), 'http://localhost:' + str(self.server.server_port)):
                return self.respond(403, {'error': 'Origin rejected'})
            path = urlsplit(self.path).path
            if path not in ('/api/investigations', '/api/scenarios'):
                return self.respond(404, {'error': 'Not found'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if size < 1 or size > MAX_BYTES:
                    return self.respond(413, {'error': 'Body must be between 1 byte and 5 MiB'})
                data = json.loads(self.rfile.read(size))
                if path == '/api/scenarios':
                    if not isinstance(data, dict) or data.get('name') not in ('checkout', 'database', 'iam'):
                        raise ValueError('Unknown scenario')
                    data = json.loads((ROOT / 'fixtures' / (data['name'] + '.json')).read_text())
                result = store.save(analyze(data))
                return self.respond(201, result)
            except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
                return self.respond(400, {'error': str(exc) or 'Invalid evidence'})
    return Handler

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--db', type=Path, default=ROOT / 'data' / 'incidentlab.db')
    args = parser.parse_args()
    args.db.parent.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler(Store(args.db)))
    print('IncidentLab running at http://127.0.0.1:' + str(server.server_port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
