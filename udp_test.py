"""
UDP listener — run this to see if TotalMixFX is sending ANYTHING on port 9001.
Run with: python udp_test.py
Then move faders in TotalMixFX and watch for output.
"""
import socket

PORT = 9001
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", PORT))
print(f"Listening for UDP on port {PORT}... Move a fader in TotalMixFX.")
print("Press Ctrl+C to stop.\n")

while True:
    data, addr = sock.recvfrom(4096)
    print(f"Received {len(data)} bytes from {addr}: {data.hex()}")
