#!/usr/bin/env python3
"""
OSC Bridge for TotalMixFX (RME Babyface Pro)
- Listens for HTTP requests from the mixer dashboard
- Translates them to OSC messages sent to TotalMixFX
- Reads OSC responses from TotalMixFX and caches state
- Runs on localhost:8081

TotalMixFX OSC config:
  Remote Controller → Enable OSC
  Incoming port: 7001  (TotalMix listens here — we send TO this)
  Outgoing port: 9001  (TotalMix sends FROM here — we listen HERE)

Install: pip install python-osc
"""

import json
import threading
import time
import http.server
from http import HTTPStatus
from pythonosc import udp_client, dispatcher, osc_server

# ── CONFIG ─────────────────────────────────────────────────
TOTALMIX_HOST = "127.0.0.1"
TOTALMIX_PORT = 7001   # TotalMix listens on this port (we send to it)
OSC_LISTEN_PORT = 9001  # TotalMix sends to this port (we listen here)
HTTP_PORT = 8081

# ── STATE ──────────────────────────────────────────────────
# Mixer state cache — updated whenever TotalMix sends OSC feedback
state = {
    "inputs":  [{"fader": 0.75, "mute": False, "label": f"Input {i+1}"} for i in range(8)],
    "playback": [{"fader": 0.75, "mute": False, "label": f"PB {i+1}"}   for i in range(8)],
    "outputs": [{"fader": 0.75, "mute": False, "label": f"Out {i+1}"}   for i in range(8)],
    "main_out": 0.75,
    "connected": False,
}
state_lock = threading.Lock()

# ── OSC CLIENT (send to TotalMix) ──────────────────────────
osc_client = udp_client.SimpleUDPClient(TOTALMIX_HOST, TOTALMIX_PORT)

def send_fader(bank, channel, value):
    """Send fader value. bank: 'input'|'playback'|'output', channel: 0-indexed, value: 0.0-1.0"""
    addr_map = {"input": "/1/fader", "playback": "/2/fader", "output": "/3/fader"}
    base = addr_map.get(bank, "/2/fader")
    # TotalMixFX OSC fader addresses: /1/fader1 through /1/fader8
    addr = f"{base}{channel + 1}"
    osc_client.send_message(addr, float(value))

def send_mute(bank, channel, muted):
    addr_map = {"input": "/1/mute", "playback": "/2/mute", "output": "/3/mute"}
    base = addr_map.get(bank, "/2/mute")
    addr = f"{base}{channel + 1}"
    osc_client.send_message(addr, 1.0 if muted else 0.0)

def send_main(value):
    osc_client.send_message("/1/mainVolume", float(value))

def refresh_state():
    """Ask TotalMix to send back all current values"""
    try:
        osc_client.send_message("/refresh", 1.0)
    except Exception:
        pass

# ── OSC SERVER (receive from TotalMix) ─────────────────────
def handle_fader(addr, *args):
    # addr like /1/fader3, /2/fader5, /3/fader2
    with state_lock:
        state["connected"] = True
        val = float(args[0]) if args else 0.75
        parts = addr.strip("/").split("/")
        if len(parts) == 2:
            bank_num = parts[0]
            chan_str = parts[1].replace("fader", "")
            try:
                ch = int(chan_str) - 1
                if bank_num == "1" and 0 <= ch < 8:
                    state["inputs"][ch]["fader"] = val
                elif bank_num == "2" and 0 <= ch < 8:
                    state["playback"][ch]["fader"] = val
                elif bank_num == "3" and 0 <= ch < 8:
                    state["outputs"][ch]["fader"] = val
            except ValueError:
                pass

def handle_mute(addr, *args):
    with state_lock:
        val = bool(args[0]) if args else False
        parts = addr.strip("/").split("/")
        if len(parts) == 2:
            bank_num = parts[0]
            chan_str = parts[1].replace("mute", "")
            try:
                ch = int(chan_str) - 1
                if bank_num == "1" and 0 <= ch < 8:
                    state["inputs"][ch]["mute"] = val
                elif bank_num == "2" and 0 <= ch < 8:
                    state["playback"][ch]["mute"] = val
                elif bank_num == "3" and 0 <= ch < 8:
                    state["outputs"][ch]["mute"] = val
            except ValueError:
                pass

def handle_main(addr, *args):
    with state_lock:
        state["main_out"] = float(args[0]) if args else 0.75
        state["connected"] = True

def start_osc_listener():
    disp = dispatcher.Dispatcher()
    disp.map("/1/fader*", handle_fader)
    disp.map("/2/fader*", handle_fader)
    disp.map("/3/fader*", handle_fader)
    disp.map("/1/mute*", handle_mute)
    disp.map("/2/mute*", handle_mute)
    disp.map("/3/mute*", handle_mute)
    disp.map("/1/mainVolume", handle_main)
    try:
        server = osc_server.ThreadingOSCUDPServer(("0.0.0.0", OSC_LISTEN_PORT), disp)
        with state_lock:
            state["connected"] = True
        server.serve_forever()
    except Exception as e:
        print(f"OSC listener error: {e}")

# ── HTTP SERVER ─────────────────────────────────────────────
class MixerHandler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/mixer/state":
            refresh_state()
            time.sleep(0.05)  # brief wait for OSC feedback
            with state_lock:
                data = json.dumps(state).encode()
            self._json(200, data)
        else:
            self._json(404, b'{"error":"not found"}')

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(body)
        except Exception:
            self._json(400, b'{"error":"bad json"}')
            return

        action = payload.get("action")
        bank   = payload.get("bank", "playback")  # input | playback | output
        ch     = int(payload.get("channel", 0))

        if action == "fader":
            val = float(payload.get("value", 0.75))
            send_fader(bank, ch, val)
            with state_lock:
                bank_key = {"input": "inputs", "playback": "playback", "output": "outputs"}.get(bank, "playback")
                if 0 <= ch < 8:
                    state[bank_key][ch]["fader"] = val
            self._json(200, b'{"ok":true}')

        elif action == "mute":
            muted = bool(payload.get("muted", False))
            send_mute(bank, ch, muted)
            with state_lock:
                bank_key = {"input": "inputs", "playback": "playback", "output": "outputs"}.get(bank, "playback")
                if 0 <= ch < 8:
                    state[bank_key][ch]["mute"] = muted
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
    # Start OSC listener in background thread
    osc_thread = threading.Thread(target=start_osc_listener, daemon=True)
    osc_thread.start()

    # Request initial state from TotalMix
    time.sleep(0.5)
    refresh_state()

    print(f"OSC Bridge running — HTTP:{HTTP_PORT} | OSC→TotalMix:{TOTALMIX_PORT} | OSC←TotalMix:{OSC_LISTEN_PORT}")
    http.server.HTTPServer(("127.0.0.1", HTTP_PORT), MixerHandler).serve_forever()
