"""
Two-way OSC test for TotalMixFX.
Run with: python osc_test.py
This sends a /refresh command TO TotalMixFX and listens for any response.
"""
import socket
import struct
import threading
import time

SEND_PORT = 7001   # TotalMixFX listens here
RECV_PORT = 9001   # TotalMixFX sends here

def osc_string(s):
    s = s.encode() + b'\x00'
    while len(s) % 4: s += b'\x00'
    return s

def make_osc(addr, *args):
    msg = osc_string(addr)
    if args:
        type_tag = ',' + ''.join('f' if isinstance(a, float) else 'i' for a in args)
        msg += osc_string(type_tag)
        for a in args:
            msg += struct.pack('>f', float(a))
    else:
        msg += osc_string(',')
    return msg

def listen():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", RECV_PORT))
    sock.settimeout(1.0)
    print(f"Listening on port {RECV_PORT} for TotalMixFX responses...\n")
    while True:
        try:
            data, addr = sock.recvfrom(4096)
            print(f"✅ GOT RESPONSE from {addr}: {len(data)} bytes: {data[:40]}")
        except socket.timeout:
            pass

def send():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    msgs = [
        make_osc("/refresh", 1.0),
        make_osc("/1/fader1"),
        make_osc("/2/fader1"),
        make_osc("/3/fader1"),
    ]
    time.sleep(0.5)
    for msg in msgs:
        sock.sendto(msg, ("127.0.0.1", SEND_PORT))
        print(f"📤 Sent {len(msg)} bytes to port {SEND_PORT}")
        time.sleep(0.3)

threading.Thread(target=listen, daemon=True).start()
send()

print("\nWaiting 5 seconds for TotalMixFX to respond...")
print("Also try moving a fader inside TotalMixFX now.\n")
time.sleep(5)
print("Done. If no ✅ lines appeared, TotalMixFX is not sending OSC feedback.")
print("Check: Options → Settings → Remote Controller → is OSC selected (not MIDI)?")
