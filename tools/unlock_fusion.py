#!/usr/bin/env python3
"""
Desbloquear una venta en el Wayne Synergy.

Uso: python3 tools/unlock_fusion.py [lock_id]

Default: desbloquea OV-20260529155627-072 (venta anterior)
"""

import socket
import sys
import time

FUSION_IP = "192.168.1.20"
FUSION_PORT = 3011

def build_msg(event_type, params="", dest="", origin=""):
    body = f"2||POST|{event_type}|{dest}|{origin}|{params}|^"
    return f"{len(body):05d}|5|{body}".encode('ascii')

def main():
    lock_id = sys.argv[1] if len(sys.argv) > 1 else "OV-20260529155627-072"
    # Sale ID 6 from the log: "Sale 6 now locked by ID [OV-20260529155627-072]"
    sale_id = "6"

    print(f"🔌 Conectando a {FUSION_IP}:{FUSION_PORT}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(8)
    sock.connect((FUSION_IP, FUSION_PORT))
    print("✓ Conectado\n")

    # ECHO
    sock.sendall(b"00012|5|2||ECHO||||^")
    time.sleep(0.3)

    # UNLOCK
    params = f"SA={sale_id}|LID={lock_id}"
    msg = build_msg("REQ_PAYMENT_TRANSACTION_UNLOCK", params)
    print(f"🔓 Enviando UNLOCK: SA={sale_id} LID={lock_id}")
    print(f"→ {msg.decode()}")
    sock.sendall(msg)
    time.sleep(1)

    # Read response
    buffer = b""
    sock.settimeout(2)
    while True:
        try:
            data = sock.recv(4096)
            if not data:
                break
            buffer += data
        except socket.timeout:
            break
    sock.close()

    content = buffer.decode('ascii', errors='replace')
    messages = [m.strip() for m in content.split('^') if m.strip()]

    print("\nRespuestas:")
    for msg in messages:
        if 'ECHO' in msg:
            print(f"  📡 ECHO: OK")
        elif 'RES_PAYMENT_TRANSACTION_UNLOCK' in msg:
            print(f"  ✅ UNLOCK: {msg[:120]}")
        elif 'EVT_PAYMENT_TRANSACTION_LOCK' in msg:
            print(f"  🔒 LOCK event: {msg[:120]}")
        elif 'EVT_PUMP_STATUS_CHANGE' in msg:
            for part in msg.split('|'):
                if part.startswith('ST=') or part.startswith('SU='):
                    print(f"  🟢 {part}")
        else:
            print(f"  · {msg[:100]}")

if __name__ == "__main__":
    main()
