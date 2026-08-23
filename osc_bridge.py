#!/usr/bin/env python3
"""
OSC Bridge for TotalMixFX (RME Babyface Pro)
- HTTP on localhost:8081  ← dashboard talks here
- OSC out → TotalMixFX on port 7001
- OSC in  ← TotalMixFX on port 9001 (raw UDP, no library dependency)

TotalMixFX setup:
  Options → Settings → Remote Controller
  Port Incoming: 7001
  Port Outgoing: 9001
  Remote IP:     127.0.0.1
  OSC enabled:   yes
"""

import json
import socket
import struct
import threading
import time
import http.server

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
state_lock  = threading.Lock()
last_osc_rx = 0.0

# ── RAW OSC HELPERS ────────────────────────────────────────
def osc_pad(s: bytes) -> bytes:
    """Pad bytes to next 4-byte boundary."""
    r = len(s) % 4
    return s + b'\x00' * (4 - r if r else 0)

def osc_encode_string(s: str) -> bytes:
    return osc_pad(s.encode('ascii') + b'\x00')

def osc_decode_string(data: bytes, offset: int):
    """Read null-terminated string from data at offset, return (string, new_offset)."""
    end = data.index(b'\x00', offset)
    s   = data[offset:end].decode('ascii', errors='replace')
    # advance to next 4-byte boundary
    padded = end + 1
    r = padded % 4
    if r: padded += (4 - r)
    return s, padded

def make_osc_message(addr: str, *args) -> bytes:
    msg = osc_encode_string(addr)
    if args:
        type_tag = ',' + ''.join('f' for _ in args)
        msg += osc_encode_string(type_tag)
        for a in args:
            msg += struct.pack('>f', float(a))
    else:
        msg += osc_encode_string(',')
    return msg

def parse_osc_message(data: bytes):
    """Parse raw OSC bytes → (address, [float_args]) or None on failure."""
    try:
        if data[:8] == b'#bundle\x00':
            # OSC bundle — iterate sub-messages
            results = []
            offset = 16  # skip #bundle + timetag
            while offset < len(data):
                size = struct.unpack('>I', data[offset:offset+4])[0]
                offset += 4
                sub = parse_osc_message(data[offset:offset+size])
                if sub: results.append(sub)
                offset += size
            return results if results else None

        addr, offset = osc_decode_string(data, 0)
        if offset >= len(data):
            return [(addr, [])]

        type_tag, offset = osc_decode_string(data, offset)
        args = []
        for t in type_tag[1:]:  # skip leading ','
            if t == 'f':
                args.append(struct.unpack('>f', data[offset:offset+4])[0])
                offset += 4
            elif t == 'i':
                args.append(struct.unpack('>i', data[offset:offset+4])[0])
                offset += 4
            elif t == 's':
                s, offset = osc_decode_string(data, offset)
                args.append(s)
        return [(addr, args)]
    except Exception:
        return None

# ── OSC SEND ──────────────────────────────────────────────
_send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def osc_send(addr: str, *args):
    msg = make_osc_message(addr, *args)
    _send_sock.sendto(msg, (TOTALMIX_HOST, TOTALMIX_PORT))
    print(f"OSC SEND: {addr} {args}")

def send_fader(bank, channel, value):
    row  = {"input": 1, "playback": 2, "output": 3}.get(bank, 2)
    osc_send(f"/{row}/fader{channel + 1}", float(value))

def send_mute(bank, channel, muted):
    row  = {"input": 1, "playback": 2, "output": 3}.get(bank, 2)
    osc_send(f"/{row}/mute{channel + 1}", 1.0 if muted else 0.0)

def send_main(value):
    osc_send("/1/mainVolume", float(value))

def refresh_state():
    osc_send("/refresh", 1.0)

# ── OSC RECEIVE (raw UDP) ──────────────────────────────────
def handle_message(addr: str, args: list):
    global last_osc_rx
    last_osc_rx = time.time()
    print(f"OSC RECV: {addr} {args}")

    val = float(args[0]) if args else 0.0

    # /1/mainVolume
    if addr == "/1/mainVolume":
        with state_lock:
            state["main_out"] = val
            state["connected"] = True
        return

    parts = addr.strip("/").split("/")
    if len(parts) != 2:
        with state_lock:
            state["connected"] = True
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
        key    = "fader"
    elif rest.startswith("mute"):
        ch_str = rest[len("mute"):]
        key    = "mute"
    else:
        with state_lock:
            state["connected"] = True
        return

    try:
        ch = int(ch_str) - 1
    except ValueError:
        return

    if not (0 <= ch < 8):
        return

    with state_lock:
        state["connected"] = True
        if key == "fader":
            state[bank_key][ch]["fader"] = val
        else:
            state[bank_key][ch]["mute"] = bool(val)


def osc_listener_thread():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", OSC_LISTEN_PORT))
    print(f"OSC listener ready on UDP port {OSC_LISTEN_PORT}")
    while True:
        try:
            data, _ = sock.recvfrom(65535)
            parsed  = parse_osc_message(data)
            if parsed:
                if isinstance(parsed, list):
                    for addr, args in parsed:
                        handle_message(addr, args)
                else:
                    addr, args = parsed
                    handle_message(addr, args)
        except Exception as e:
            print(f"OSC recv error: {e}")


def watchdog_thread():
    while True:
        time.sleep(5)
        with state_lock:
            if last_osc_rx == 0 or (time.time() - last_osc_rx) > 15:
                state["connected"] = False


# ── HTTP SERVER ─────────────────────────────────────────────
class MixerHandler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path.startswith("/mixer/state"):
            refresh_state()
            time.sleep(0.1)
            with state_lock:
                data = json.dumps(state).encode()
            self._json(200, data)
        else:
            self._json(404, b'{"error":"not found"}')

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length) if length else b"{}"
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
