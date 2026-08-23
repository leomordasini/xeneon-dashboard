#!/usr/bin/env python3
"""
OSC Bridge for TotalMixFX (RME Babyface Pro)
- HTTP on localhost:8081  ← dashboard talks here
- OSC out → TotalMixFX on port 7001
- OSC in  ← TotalMixFX on port 9001

TotalMixFX setup:
  Options → Settings → OSC Remote Controller
  Enable: checked
  Incoming port: 7001   (TotalMix listens — we send here)
  Outgoing port: 9001   (TotalMix sends  — we listen here)
  Remote IP: 127.0.0.1

Install: pip install python-osc
"""

import json
import threading
import time
import http.server
from pythonosc import udp_client, dispatcher, osc_server

# ── CONFIG ─────────────────────────────────────────────────
TOTALMIX_HOST   = "127.0.0.1"
TOTALMIX_PORT   = 7001
OSC_LISTEN_PORT = 9001
HTTP_PORT       = 8081

# ── STATE ──────────────────────────────────────────────────
state = {
    "inputs":   [{"fader": 0.75, "mute": False} for _ in range(8)],
    "playback": [{"fader": 0.75, "mute": False} for _ in range(8)],
    "outputs":  [{"fader": 0.75, "mute": False} for _ in range(8)],
    "main_out": 0.75,
    "connected": False,
}
state_lock   = threading.Lock()
last_osc_rx  = 0.0   # timestamp of last received OSC message

# ── OSC CLIENT ─────────────────────────────────────────────
osc_client = udp_client.SimpleUDPClient(TOTALMIX_HOST, TOTALMIX_PORT)

def send_fader(bank, channel, value):
    # TotalMixFX OSC rows: 1=inputs, 2=playback, 3=outputs
    row = {"input": 1, "playback": 2, "output": 3}.get(bank, 2)
    addr = f"/{row}/fader{channel + 1}"
    print(f"OSC SEND: {addr} = {value:.3f}")
    osc_client.send_message(addr, float(value))

def send_mute(bank, channel, muted):
    row  = {"input": 1, "playback": 2, "output": 3}.get(bank, 2)
    addr = f"/{row}/mute{channel + 1}"
    print(f"OSC SEND: {addr} = {1.0 if muted else 0.0}")
    osc_client.send_message(addr, 1.0 if muted else 0.0)

def send_main(value):
    osc_client.send_message("/1/mainVolume", float(value))

def refresh_state():
    try:
        osc_client.send_message("/refresh", 1.0)
    except Exception:
        pass

# ── OSC LISTENER ───────────────────────────────────────────
# Use a default handler to catch ALL incoming OSC messages —
# python-osc wildcards are unreliable; this approach catches everything.

def handle_any(addr, *args):
    global last_osc_rx
    last_osc_rx = time.time()

    print(f"OSC RECV: {addr} {args}")

    try:
        val = float(args[0]) if args else 0.0
    except (TypeError, ValueError):
        return

    # Parse address: /row/typeN  e.g. /1/fader3 /3/mute2
    parts = addr.strip("/").split("/")
    if len(parts) != 2:
        return

    row_str, rest = parts
    try:
        row = int(row_str)
    except ValueError:
        return

    bank_key = {1: "inputs", 2: "playback", 3: "outputs"}.get(row)
    if not bank_key:
        return

    if rest.startswith("fader"):
        ch_str = rest[len("fader"):]
    elif rest.startswith("mute"):
        ch_str = rest[len("mute"):]
    else:
        return

    try:
        ch = int(ch_str) - 1
    except ValueError:
        return

    if not (0 <= ch < 8):
        return

    with state_lock:
        state["connected"] = True
        if rest.startswith("fader"):
            state[bank_key][ch]["fader"] = val
        elif rest.startswith("mute"):
            state[bank_key][ch]["mute"] = bool(val)

    # Handle main volume separately
    if addr == "/1/mainVolume":
        with state_lock:
            state["main_out"] = val


def osc_listener_thread():
    disp = dispatcher.Dispatcher()
    disp.set_default_handler(handle_any)
    try:
        srv = osc_server.ThreadingOSCUDPServer(("0.0.0.0", OSC_LISTEN_PORT), disp)
        print(f"OSC listener ready on port {OSC_LISTEN_PORT}")
        srv.serve_forever()
    except Exception as e:
        print(f"OSC listener error: {e}")


def watchdog_thread():
    """Mark disconnected if no OSC message received in 10 seconds."""
    global last_osc_rx
    while True:
        time.sleep(3)
        with state_lock:
            if last_osc_rx > 0 and (time.time() - last_osc_rx) > 10:
                state["connected"] = False
            elif last_osc_rx == 0:
                state["connected"] = False


# ── HTTP SERVER ─────────────────────────────────────────────
class MixerHandler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path.startswith("/mixer/state"):
            refresh_state()
            time.sleep(0.08)
            with state_lock:
                data = json.dumps(state).encode()
            self._json(200, data)
        else:
            self._json(404, b'{"error":"not found"}')

    def do_POST(self):
        length  = int(self.headers.get("Content-Length", 0))
        body    = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(body)
        except Exception:
            self._json(400, b'{"error":"bad json"}')
            return

        action = payload.get("action")
        bank   = payload.get("bank", "playback")
        ch     = int(payload.get("channel", 0))

        if action == "fader":
            val = float(payload.get("value", 0.75))
            send_fader(bank, ch, val)
            bk = {"input":"inputs","playback":"playback","output":"outputs"}.get(bank,"playback")
            with state_lock:
                if 0 <= ch < 8:
                    state[bk][ch]["fader"] = val
            self._json(200, b'{"ok":true}')

        elif action == "mute":
            muted = bool(payload.get("muted", False))
            send_mute(bank, ch, muted)
            bk = {"input":"inputs","playback":"playback","output":"outputs"}.get(bank,"playback")
            with state_lock:
                if 0 <= ch < 8:
                    state[bk][ch]["mute"] = muted
            self._json(200, b'{"ok":true}')

        elif action == "main":
            val = float(payload.get("value", 0.75))
            send_main(val)
            with state_lock:
                state["main_out"] = val
            self._json(200, b'{"ok":true}')

        elif action == "refresh":
            refresh_state()
            self._json(200, b'{"ok":true}')

        else:
            self._json(400, b'{"error":"unknown action"}')

    def _json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    threading.Thread(target=osc_listener_thread, daemon=True).start()
    threading.Thread(target=watchdog_thread,     daemon=True).start()

    time.sleep(0.5)
    refresh_state()

    print(f"OSC Bridge HTTP ready on port {HTTP_PORT}")
    http.server.HTTPServer(("127.0.0.1", HTTP_PORT), MixerHandler).serve_forever()
