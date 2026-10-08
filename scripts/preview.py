#!/usr/bin/env python3
"""Loopback-only UI fixture, using the installed host React without copying it."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import sys
sys.dont_write_bytecode = True
from mod import Archive, ROOT, NEW, ASAR

HOST_FILES = {'app-shared-122c56612a72.js','rolldown-runtime-2d059c5e81f4.js',
              'codex-usage-speed.mjs','codex-usage-bar.mjs','codex-usage-metrics.mjs',
              'codex-usage-diff-slot.mjs','codex-usage-native-fixed.mjs'}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        path = self.path.split('?', 1)[0]
        try:
            if path in ['/', '/tests/fixture.html']:
                data = (ROOT / 'tests/fixture.html').read_bytes(); mime = 'text/html'
            elif path.startswith('/__host/') and path.rsplit('/',1)[1] in HOST_FILES:
                data = Archive(NEW / ASAR).read('webview/assets/' + path.rsplit('/',1)[1]); mime = 'text/javascript'
            elif path in ['/src/bar.mjs','/src/metrics.mjs','/src/speed.mjs','/src/diff-slot.mjs','/src/native-fixed.mjs','/src/native-layout.mjs','/src/responsive.mjs']:
                data = (ROOT / path.lstrip('/')).read_bytes(); mime = 'text/javascript'
            else:
                self.send_error(404); return
            self.send_response(200)
            self.send_header('Content-Type', mime + '; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers(); self.wfile.write(data)
        except Exception:
            self.send_error(500)

if __name__ == '__main__':
    server = HTTPServer(('127.0.0.1', 0), Handler)
    print(f'http://127.0.0.1:{server.server_port}', flush=True)
    server.serve_forever()
