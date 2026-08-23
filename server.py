#!/usr/bin/env python3
"""
Xeneon Dashboard Server — HTTPS edition
- Serves HTML dashboards as static files over HTTPS
- Proxies /api/* to Home Assistant (handles auth + CORS)
- Generates self-signed cert on first run if cert.pem missing
- Auto-starts on Windows login via Task Scheduler (setup_autostart.bat)
"""

import http.server
import urllib.request
import urllib.error
import ssl
import os
import sys
import subprocess

PORT     = 8080
HA_URL   = "http://192.168.1.30:8123"
HA_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiIyNTkyYmQxODU2N2Q0MjJmOWZkNmRlYTc2MjdmYTUyNyIsImlhdCI6MTc4NzQ1MjgwOSwiZXhwIjoyMTAyODEyODA5fQ.PDfpA3-H5g5v2UHPf6Lhiq5iI5eR5IvINOVgQab-kmI"

HERE = os.path.dirname(os.path.abspath(__file__))
CERT = os.path.join(HERE, "cert.pem")
KEY  = os.path.join(HERE, "key.pem")


class DashboardHandler(http.server.SimpleHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/api/"):
            self._proxy("GET", None)
        else:
            super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else None
            self._proxy("POST", body)
        else:
            self.send_error(405)

    def _proxy(self, method, body):
        url = HA_URL + self.path
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Authorization", f"Bearer {HA_TOKEN}")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = resp.read()
                self.send_response(resp.status)
                self.send_header("Content-Type", "application/json")
                self._cors()
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            data = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self._cors()
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_error(502, str(e))

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def log_message(self, format, *args):
        pass  # Silent


def ensure_cert():
    if os.path.exists(CERT) and os.path.exists(KEY):
        return True
    print("No certificate found. Run generate_cert.py first.")
    print("  python generate_cert.py")
    return False


if __name__ == "__main__":
    os.chdir(HERE)

    if not ensure_cert():
        sys.exit(1)

    # Set up SSL context
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(CERT, KEY)

    server = http.server.HTTPServer(("0.0.0.0", PORT), DashboardHandler)
    server.socket = context.wrap_socket(server.socket, server_side=True)

    print(f"Xeneon Dashboard → https://192.168.1.148:{PORT}/lights.html")
    server.serve_forever()
