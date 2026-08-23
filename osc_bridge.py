#!/usr/bin/env python3
"""
OSC Bridge for TotalMixFX (RME Babyface Pro)
Confirmed TotalMixFX OSC address map (from live capture):
  /1/volume1-8      Input channel faders      (float 0.0-1.0)
  /2/volume1-8      Playback channel faders   (float 0.0-1.0)
  /3/volume1-8      Output channel faders     (float 0.0-1.0)
  /1/mastervolume   Main output volume        (float 0.0-1.0)
  /1/mute1-8        Input mutes               (float 0.0 or 1.0)
  /2/mute1-8        Playback mutes
  /3/mute1-8        Output mutes

LEVEL METERS NOTE:
  TotalMixFX only broadcasts level data for Hardware Inputs (bank 1) via OSC.
  Software Playback (bank 2) and Hardware Outputs (bank 3) levels are NOT sent.
  We read playback/output levels from Windows WASAPI via pycaw instead.

TotalMixFX setup:
  Options → Settings → Remote Controller
  Port Incoming: 7001   (TotalMix listens — we send here)
  Port Outgoing: 9001   (TotalMix sends  — we listen here)
  Remote IP:     127.0.0.1
  OSC:           enabled
"""

import json
import re
import socket
import struct
import threading
import time
import http.server

# Optional: pycaw for Windows WASAPI audio level metering
# (used to read Software Playback / Hardware Output levels TotalMixFX doesn't send via OSC)
try:
    import comtypes
    from ctypes import POINTER, cast
    from comtypes import CLSCTX_ALL, GUID
    from pycaw.pycaw import IAudioMeterInformation
    # CLSID_MMDeviceEnumerator — defined inline; not exported by all pycaw versions
    _CLSID_MMDeviceEnumerator = GUID('{BCDE0395-E52F-467C-8E3D-C4579291692E}')
    PYCAW_AVAILABLE = True
    print("pycaw available — WASAPI meters enabled")
except ImportError as _pycaw_err:
    PYCAW_AVAILABLE = False
    print(f"pycaw not found — install with: pip install pycaw  (Software Playback VU meters disabled)")

# ── CONFIG ─────────────────────────────────────────────────
TOTALMIX_HOST   = "127.0.0.1"
TOTALMIX_PORT   = 7001
OSC_LISTEN_PORT = 9001
HTTP_PORT       = 8081

# ── STATE ──────────────────────────────────────────────────
# Babyface Pro channel counts (as shown in TotalMixFX):
#   Inputs:   8 (AN1, AN2, Instr3, Instr4, AS1/2, ADAT3/4, ADAT5/6, ADAT7/8)
#   Playback: 6 (AN1/2, PH3/4, AS1/2, ADAT3/4, ADAT5/6, ADAT7/8)
#   Outputs:  6 (AN1/2, AS1/2, ADAT3/4, ADAT5/6, ADAT7/8, Main)
def _ch(n): return [{"fader": 0.75, "mute": False, "level": 0.0, "peak": 0.0} for _ in range(n)]
state = {
    "inputs":   _ch(8),
    "playback": _ch(6),
    "outputs":  _ch(6),
    "main_out": 0.75,
    "connected": False,
}
state_lock  = threading.Lock()
last_osc_rx = 0.0

# ── RAW OSC HELPERS ────────────────────────────────────────
def osc_pad(s: bytes) -> bytes:
    r = len(s) % 4
    return s + b'\x00' * (4 - r if r else 0)

def osc_encode_string(s: str) -> bytes:
    return osc_pad(s.encode('ascii') + b'\x00')

def osc_decode_string(data: bytes, offset: int):
    end = data.index(b'\x00', offset)
    s   = data[offset:end].decode('ascii', errors='replace')
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
    """Parse raw OSC bytes → list of (address, args) tuples."""
    try:
        if data[:8] == b'#bundle\x00':
            results = []
            offset  = 16  # skip #bundle + timetag
            while offset < len(data) - 4:
                size = struct.unpack('>I', data[offset:offset+4])[0]
                offset += 4
                if size > 0:
                    sub = parse_osc_message(data[offset:offset+size])
                    if sub:
                        results.extend(sub)
                offset += size
            return results

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
            else:
                offset += 4  # skip unknown types
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
    row = {"input": 1, "playback": 2, "output": 3}.get(bank, 2)
    # Park OSC client on the correct row before sending fader value
    bus_addr = {"input": "/1/busInput", "playback": "/1/busPlayback", "output": "/1/busOutput"}.get(bank)
    if bus_addr:
        osc_send(bus_addr, 1.0)
    osc_send(f"/1/volume{channel + 1}", float(value))

def send_mute(bank, channel, muted):
    # Park OSC client on the correct row first (each client has its own bank state)
    bus_addr = {"input": "/1/busInput", "playback": "/1/busPlayback", "output": "/1/busOutput"}.get(bank)
    if bus_addr:
        osc_send(bus_addr, 1.0)
    # Send mute value: 1.0 = muted, 0.0 = unmuted — confirmed from live TotalMixFX feedback
    osc_send(f"/1/mute/1/{channel + 1}", 1.0 if muted else 0.0)

def send_main(value):
    osc_send("/1/mastervolume", float(value))

def refresh_state():
    osc_send("/refresh", 1.0)

# ── OSC RECEIVE ───────────────────────────────────────────
def handle_message(addr: str, args: list):
    global last_osc_rx
    last_osc_rx = time.time()

    # Only log addresses we care about to keep output clean
    if any(k in addr for k in ['volume', 'mute', 'master']):
        print(f"OSC RECV: {addr} {args}")

    # Skip if no numeric arg
    if not args or not isinstance(args[0], (int, float)):
        return

    val = float(args[0])

    # Level meters: /1/levelNLeft and /1/levelNRight (bank 1=inputs only for now)
    # Take max of L/R as the display level for each channel strip
    m = re.match(r'^/(\d+)/level(\d+)(Left|Right)$', addr)
    if m:
        row  = int(m.group(1))
        ch   = int(m.group(2)) - 1
        bank_key = {1: "inputs", 2: "playback", 3: "outputs"}.get(row)
        if bank_key and 0 <= ch < len(state[bank_key]):
            with state_lock:
                state["connected"] = True
                cur = state[bank_key][ch]["level"]
                state[bank_key][ch]["level"] = max(cur, val)
                if val > state[bank_key][ch]["peak"]:
                    state[bank_key][ch]["peak"] = val
        return

    # Log anything else we don't recognise (to discover new address formats)
    if not any(k in addr for k in ['volume', 'mute', 'master']):
        print(f"OSC UNKNOWN: {addr} {args[:1] if args else []}")
        return

    # Master volume
    if addr == "/1/mastervolume":
        with state_lock:
            state["main_out"]  = val
            state["connected"] = True
        return

    # Channel faders: /1/volume1 /2/volume3 /3/volume5 etc.
    # Channel mutes:  /1/mute/1/1 /2/mute/1/3 etc.
    parts = addr.strip("/").split("/")

    # Mute format: /row/mute/1/ch → parts = [row, 'mute', '1', ch]
    if len(parts) == 4 and parts[1] == "mute":
        try:
            row      = int(parts[0])
            ch       = int(parts[3]) - 1
            bank_key = {1: "inputs", 2: "playback", 3: "outputs"}.get(row)
            if bank_key and 0 <= ch < 8:
                with state_lock:
                    state["connected"]          = True
                    state[bank_key][ch]["mute"] = bool(val)
        except ValueError:
            pass
        return

    # Level meters: /1/meter1 /2/meter2 etc.
    if len(parts) == 2 and parts[1].startswith("meter"):
        try:
            row      = int(parts[0])
            ch       = int(parts[1][len("meter"):]) - 1
            bank_key = {1: "inputs", 2: "playback", 3: "outputs"}.get(row)
            if bank_key and 0 <= ch < len(state[bank_key]):
                with state_lock:
                    state["connected"]              = True
                    state[bank_key][ch]["level"]    = val
                    if val > state[bank_key][ch]["peak"]:
                        state[bank_key][ch]["peak"] = val
        except (ValueError, IndexError):
            pass
        return

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

    if rest.startswith("volume"):
        ch_str = rest[len("volume"):]
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


def wasapi_meter_thread():
    """
    Poll Windows WASAPI peak levels for Software Playback and Hardware Output channels.
    TotalMixFX does NOT send these via OSC — only Hardware Inputs (bank 1) are broadcast.
    Runs at 20fps (50ms). Requires pycaw (for IAudioMeterInformation).
    Maps: default render device peak → playback[0] (AN 1/2) and outputs[0] (AN 1/2)
    """
    if not PYCAW_AVAILABLE:
        return

    comtypes.CoInitialize()

    # Define IMMDevice/IMMDeviceEnumerator inline — avoids pycaw version export differences
    from comtypes import GUID, COMMETHOD, HRESULT, IUnknown
    from ctypes import POINTER, c_uint

    class IMMDevice(IUnknown):
        _iid_ = GUID('{D666063F-1587-4E43-81F1-B948E807363F}')
        _methods_ = [
            # Only define Activate (first method) — it's all we need
            COMMETHOD([], HRESULT, 'Activate',
                      (['in'],  GUID,                      'iid'),
                      (['in'],  c_uint,                    'dwClsCtx'),
                      (['in'],  POINTER(c_uint),           'pActivationParams'),
                      (['out'], POINTER(POINTER(IUnknown)),'ppInterface')),
        ]

    class IMMDeviceEnumeratorLocal(IUnknown):
        _iid_ = GUID('{A95664D2-9614-4F35-A746-DE8DB63617E6}')
        _methods_ = [
            # EnumAudioEndpoints must be listed first (vtable slot 3) even though unused
            COMMETHOD([], HRESULT, 'EnumAudioEndpoints',
                      (['in'],  c_uint,                    'dataFlow'),
                      (['in'],  c_uint,                    'dwStateMask'),
                      (['out'], POINTER(POINTER(IUnknown)),'ppDevices')),
            # GetDefaultAudioEndpoint (vtable slot 4)
            COMMETHOD([], HRESULT, 'GetDefaultAudioEndpoint',
                      (['in'],  c_uint,                    'dataFlow'),
                      (['in'],  c_uint,                    'role'),
                      (['out'], POINTER(POINTER(IMMDevice)),'ppEndpoint')),
        ]

    meter = None

    while True:
        try:
            if meter is None:
                enumerator = comtypes.CoCreateInstance(
                    _CLSID_MMDeviceEnumerator,
                    IMMDeviceEnumeratorLocal,
                    CLSCTX_ALL
                )
                # comtypes returns ['out'] params as Python return values — don't pass them manually
                device = enumerator.GetDefaultAudioEndpoint(0, 0)  # eRender=0, eConsole=0
                iunk   = device.Activate(IAudioMeterInformation._iid_, CLSCTX_ALL, None)
                meter  = iunk.QueryInterface(IAudioMeterInformation)

            peak = meter.GetPeakValue()
            # debug print removed — confirmed working

            with state_lock:
                state["playback"][0]["level"] = peak
                if peak > state["playback"][0]["peak"]:
                    state["playback"][0]["peak"] = peak
                state["outputs"][0]["level"] = peak
                if peak > state["outputs"][0]["peak"]:
                    state["outputs"][0]["peak"] = peak

        except Exception as e:
            meter = None
            print(f"WASAPI meter error: {e}")

        time.sleep(0.05)  # 50ms = 20fps


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
                for addr, args in parsed:
                    handle_message(addr, args)
        except Exception as e:
            print(f"OSC recv error: {e}")


def watchdog_thread():
    while True:
        time.sleep(0.1)
        with state_lock:
            if last_osc_rx == 0 or (time.time() - last_osc_rx) > 15:
                state["connected"] = False
            # Decay peaks slowly (drop 2% every 100ms = ~5 seconds full decay)
            for bank_key in ("inputs", "playback", "outputs"):
                for ch in state[bank_key]:
                    if ch["peak"] > 0:
                        ch["peak"]  = max(0.0, ch["peak"]  - 0.02)
                    if ch["level"] > 0:
                        ch["level"] = max(0.0, ch["level"] - 0.01)  # slow decay — WASAPI refreshes at 20fps


# ── HTTP SERVER ─────────────────────────────────────────────
class MixerHandler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path.startswith("/mixer/state"):
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
                if 0 <= ch < len(state[bk]):
                    state[bk][ch]["fader"] = val
            self._json(200, b'{"ok":true}')

        elif action == "mute":
            muted = bool(payload.get("muted", False))
            send_mute(bank, ch, muted)
            bk = {"input":"inputs","playback":"playback","output":"outputs"}.get(bank,"playback")
            with state_lock:
                if 0 <= ch < len(state[bk]):
                    state[bk][ch]["mute"] = muted
            self._json(200, b'{"ok":true}')

        elif action == "main":
            val = float(payload.get("value", 0.75))
            send_main(val)
            with state_lock:
                state["main_out"] = val
            self._json(200, b'{"ok":true}')

        elif action == "osc_raw":
            addr = payload.get("addr", "")
            val  = payload.get("value", 1.0)
            if addr:
                if val == -1:
                    # Send bare OSC message with no args (toggle format)
                    msg = make_osc_message(addr)
                    _send_sock.sendto(msg, (TOTALMIX_HOST, TOTALMIX_PORT))
                    print(f"OSC SEND (no-arg): {addr}")
                else:
                    osc_send(addr, float(val))
                self._json(200, b'{"ok":true}')
            else:
                self._json(400, b'{"error":"no addr"}')

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
    threading.Thread(target=wasapi_meter_thread, daemon=True).start()
    time.sleep(0.5)
    refresh_state()
    print(f"OSC Bridge HTTP ready on port {HTTP_PORT}")
    http.server.HTTPServer(("127.0.0.1", HTTP_PORT), MixerHandler).serve_forever()
