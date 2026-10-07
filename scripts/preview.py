#!/usr/bin/env python3
"""Loopback-only UI fixture, using the installed host React without copying it."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import argparse
import json
import sys
sys.dont_write_bytecode = True
from mod import Archive, ROOT, NEW, ASAR

HOST_FILES = {'app-shared-122c56612a72.js','rolldown-runtime-2d059c5e81f4.js',
              'codex-usage-speed.mjs','codex-usage-bar.mjs','codex-usage-metrics.mjs',
              'codex-usage-diff-slot.mjs','codex-usage-native-fixed.mjs'}
HOST_ARCHIVE = NEW / ASAR
WINDOWS = False

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        path = self.path.split('?', 1)[0]
        try:
            if path in ['/', '/tests/fixture.html']:
                html = (ROOT / 'tests/fixture.html').read_text(encoding='utf-8')
                if WINDOWS:
                    html = html.replace('cfn as loadReact, eln as loadJSX, Zcn as loadDOM, Qcn as loadPortal',
                                        'ggn as loadReact, npn as loadJSX, $fn as loadDOM, epn as loadPortal')
                    html = html.replace('app-shared-122c56612a72.js', 'app-shared-40678a67f0e3.js')
                data = html.encode('utf-8'); mime = 'text/html'
            elif path.startswith('/__host/') and path.rsplit('/',1)[1] in HOST_FILES:
                data = Archive(HOST_ARCHIVE).read('webview/assets/' + path.rsplit('/',1)[1]); mime = 'text/javascript'
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--windows', action='store_true', help='Use the latest verified local Windows build')
    args = parser.parse_args()
    if args.windows:
        WINDOWS = True
        build = Path(json.loads((ROOT / '.local-windows/latest.json').read_text(encoding='utf-8'))['build'])
        HOST_ARCHIVE = build / 'app/resources/app.asar'
        HOST_FILES.add('app-shared-40678a67f0e3.js')
        for name in ['responsive', 'native-layout']:
            HOST_FILES.add('codex-usage-' + name + '.mjs')
    server = HTTPServer(('127.0.0.1', 0), Handler)
    print(f'http://127.0.0.1:{server.server_port}', flush=True)
    server.serve_forever()
