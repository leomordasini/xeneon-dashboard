#!/usr/bin/env python3
"""
tunnel.py — Starts cloudflared tunnel, captures the public URL,
writes it to tunnel_url.txt, and keeps running.

Run via Task Scheduler (setup_autostart.bat registers this).
"""

import subprocess
import sys
import os
import re
import time

HERE   = os.path.dirname(os.path.abspath(__file__))
CF     = os.path.join(HERE, "cloudflared.exe")
URLFILE = os.path.join(HERE, "tunnel_url.txt")

if not os.path.exists(CF):
    with open(URLFILE, "w") as f:
        f.write("ERROR: cloudflared.exe not found in " + HERE)
    sys.exit(1)

proc = subprocess.Popen(
    [CF, "tunnel", "--url", "http://localhost:8080"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1
)

url_found = False
for line in proc.stdout:
    if not url_found:
        match = re.search(r'https://[a-z0-9\-]+\.trycloudflare\.com', line)
        if match:
            url = match.group(0)
            url_found = True
            with open(URLFILE, "w") as f:
                f.write(url + "/lights.html\n")
                f.write(url + "\n")

proc.wait()
