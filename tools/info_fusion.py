#!/usr/bin/env python3
"""
Consultar estado actual de los dispensadores en el Wayne Synergy.

Uso: python3 tools/info_fusion.py
"""

import socket
import time

FUSION_IP = "192.168.1.20"
FUSION_PORT = 3011

def build_msg(event_type, params="", destination="", origin=""):
    body = f"2||POST|{event_type}|{destination}|{origin}|{params}|^"
    return f"{len(body):05d}|5|{body}".encode('ascii')

def build_subscribe(event_type):
    body = f"2||SUBSCRIBE|{event_type}||||^"
    return f"{len(body):05d}|5|{body}".encode('ascii')

def main():
    print(f"🔌 Conectando a {FUSION_IP}:{FUSION_PORT}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(8)
    sock.connect((FUSION_IP, FUSION_PORT))
    print("✓ Conectado\n")

    # ECHO
    sock.sendall(b"00012|5|2||ECHO||||^")
    time.sleep(0.3)

    # Subscribe ALL
    sock.sendall(build_subscribe("ALL"))
    time.sleep(0.3)

    # Request pump status
    sock.sendall(build_msg("REQ_PUMP_STATUS_ID_000"))
    time.sleep(1.5)

    # Read responses
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

    print("=" * 60)
    print("ESTADO DE DISPENSADORES")
    print("=" * 60)

    for msg in messages:
        if 'EVT_PUMP_STATUS_CHANGE' not in msg:
            continue

        # Extract pump number
        pump = "?"
        for part in msg.split('|'):
            if part.startswith('EVT_PUMP_STATUS_CHANGE_ID_'):
                pump = part.replace('EVT_PUMP_STATUS_CHANGE_ID_', '')
                break

        # Extract params
        params = {}
        for part in msg.split('|'):
            if '=' in part:
                k, v = part.split('=', 1)
                params[k] = v

        st = params.get('ST', '?')
        su = params.get('SU', '')
        pr = params.get('PR', '0')
        hn = params.get('HN', '?')
        pay_al = params.get('PAY_AL', '')

        status_icon = {
            'IDLE': '🟢', 'CALLING': '🔵', 'AUTHORIZED': '🟡',
            'STARTING': '🟠', 'FUELLING': '🟠', 'PAUSED': '🟣',
            'STOPPED': '🔴', 'CLOSED': '⚫', 'ERROR': '🔴'
        }.get(st, '⚪')

        print(f"\n  Bomba {pump}: {status_icon} {st}")
        if su:
            print(f"    Sub-estado: {su}")
        if pr and pr != '0.00':
            print(f"    Preset:     ${pr}")
        if pay_al:
            print(f"    ⚠️  Alarma pago: {pay_al}")
        print(f"    Mangueras:  {hn}")

    print(f"\n{'=' * 60}")
    print(f"Total mensajes: {len(messages)}")

if __name__ == "__main__":
    main()
