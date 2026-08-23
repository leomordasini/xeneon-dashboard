#!/usr/bin/env python3
"""
Raw OSC dump — prints EVERY packet received on port 9001 in human-readable form.
Run this while playing audio in TotalMixFX to discover the meter OSC format.
"""
import socket, struct, sys

PORT = 9001

def decode_string(data, offset):
    end = data.index(b'\x00', offset)
    s = data[offset:end].decode('ascii', errors='replace')
    padded = end + 1
    r = padded % 4
    if r: padded += (4 - r)
    return s, padded

def parse_and_print(data, indent=0):
    prefix = "  " * indent
    try:
        if data[:8] == b'#bundle\x00':
            print(f"{prefix}[BUNDLE]")
            offset = 16
            count = 0
            while offset < len(data) - 4:
                size = struct.unpack('>I', data[offset:offset+4])[0]
                offset += 4
                if size > 0:
                    parse_and_print(data[offset:offset+size], indent+1)
                    count += 1
                offset += size
            return

        addr, offset = decode_string(data, 0)
        if offset >= len(data):
            print(f"{prefix}{addr}  (no args)")
            return

        type_tag, offset = decode_string(data, offset)
        args = []
        for t in type_tag[1:]:
            if t == 'f':
                v = struct.unpack('>f', data[offset:offset+4])[0]
                args.append(f"{v:.4f}")
                offset += 4
            elif t == 'i':
                v = struct.unpack('>i', data[offset:offset+4])[0]
                args.append(f"int:{v}")
                offset += 4
            elif t == 's':
                s, offset = decode_string(data, offset)
                args.append(f'"{s}"')
            elif t == 'b':
                # blob: 4-byte length then data
                blen = struct.unpack('>I', data[offset:offset+4])[0]
                offset += 4
                blob = data[offset:offset+blen]
                # Try to decode as array of floats
                n_floats = blen // 4
                floats = struct.unpack(f'>{n_floats}f', blob[:n_floats*4])
                args.append(f"blob({blen}b → {n_floats} floats: {[round(x,3) for x in floats[:8]]}{'...' if n_floats>8 else ''})")
                pad = blen + (4 - blen%4 if blen%4 else 0)
                offset += pad
            else:
                args.append(f"?{t}")
                offset += 4

        print(f"{prefix}{addr}  [{type_tag}]  {', '.join(args)}")

    except Exception as e:
        print(f"{prefix}[PARSE ERROR: {e}]  raw={data[:32].hex()}")

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("0.0.0.0", PORT))
print(f"Listening on UDP port {PORT} — play audio in TotalMixFX now...\n")

seen_addresses = set()

while True:
    data, addr = sock.recvfrom(65535)
    # Only print new address types to avoid spam — show first occurrence + blob content changes
    try:
        if data[:8] == b'#bundle\x00':
            # For bundles, extract first message address quickly
            offset = 16
            if offset < len(data) - 4:
                size = struct.unpack('>I', data[offset:offset+4])[0]
                offset += 4
                first_addr, _ = decode_string(data[offset:offset+size], 0)
            else:
                first_addr = "bundle"
        else:
            first_addr, _ = decode_string(data, 0)

        if first_addr not in seen_addresses:
            seen_addresses.add(first_addr)
            print(f"=== NEW ADDRESS: {first_addr} ===")
            parse_and_print(data)
            print()
        elif 'meter' in first_addr.lower() or 'level' in first_addr.lower():
            parse_and_print(data)
            print()
    except Exception as e:
        print(f"[TOP ERROR: {e}]")
