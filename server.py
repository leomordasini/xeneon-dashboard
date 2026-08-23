#!/usr/bin/env python3
"""
Xeneon Dashboard Server — HTTP (cloudflared handles HTTPS)
- Serves HTML dashboards as static files
- Proxies /api/*    → Home Assistant at 192.168.1.30:8123
- Proxies /mixer/*  → OSC Bridge at localhost:8081
"""

import http.server
import urllib.request
import urllib.error
import os

PORT     = 8080
HA_URL   = "http://192.168.1.30:8123"
HA_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiIyNTkyYmQxODU2N2Q0MjJmOWZkNmRlYTc2MjdmYTUyNyIsImlhdCI6MTc4NzQ1MjgwOSwiZXhwIjoyMTAyODEyODA5fQ.PDfpA3-H5g5v2UHPf6Lhiq5iI5eR5IvINOVgQab-kmI"
MIXER_URL = "http://127.0.0.1:8081"

HERE = os.path.dirname(os.path.abspath(__file__))


class DashboardHandler(http.server.SimpleHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/api/"):
            self._proxy_to(HA_URL, "GET", None, ha=True)
        elif self.path.startswith("/mixer/"):
            self._proxy_to(MIXER_URL, "GET", None, ha=False)
        else:
            super().do_GET()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else None
        if self.path.startswith("/api/"):
            self._proxy_to(HA_URL, "POST", body, ha=True)
        elif self.path.startswith("/mixer/"):
            self._proxy_to(MIXER_URL, "POST", body, ha=False)
        else:
            self.send_error(405)

    def _proxy_to(self, base_url, method, body, ha=False):
        url = base_url + self.path
        req = urllib.request.Request(url, data=body, method=method)
        if ha:
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
        pass


if __name__ == "__main__":
    os.chdir(HERE)
    server = http.server.HTTPServer(("0.0.0.0", PORT), DashboardHandler)
    server.serve_forever()
