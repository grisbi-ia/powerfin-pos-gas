#!/usr/bin/env python3
"""
Test: Enviar REQ_PAYMENT_TRANSACTION_LOCK directo al Synergy
para ver qué estado/evento responde.

Uso: python3 tools/test_lock.py [sale_id]
Default sale_id = 5 (última venta del test anterior)
"""

import socket
import sys
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
    sale_id = sys.argv[1] if len(sys.argv) > 1 else "5"
    lock_id = f"TEST-{sale_id}"

    print(f"🔌 Conectando a {FUSION_IP}:{FUSION_PORT}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    sock.connect((FUSION_IP, FUSION_PORT))
    print("✓ Conectado\n")

    # 1. ECHO
    print("→ ECHO")
    sock.sendall(b"00012|5|2||ECHO||||^")
    time.sleep(0.5)

    # 2. Subscribe to ALL events (so we see everything)
    print("→ SUBSCRIBE|ALL")
    sock.sendall(build_subscribe("ALL"))
    time.sleep(0.5)

    # 3. Request pump status to see current state
    print("→ REQ_PUMP_STATUS_ID_000")
    sock.sendall(build_msg("REQ_PUMP_STATUS_ID_000"))
    time.sleep(1)

    # 4. Send LOCK for the sale
    print(f"\n🔒 Enviando LOCK: SA={sale_id} LID={lock_id}")
    params = f"SA={sale_id}|LID={lock_id}|TMO=30"
    msg = build_msg("REQ_PAYMENT_TRANSACTION_LOCK", params)
    print(f"→ {msg.decode()}")
    sock.sendall(msg)
    print("⏳ Esperando respuestas (10s)...\n")

    # 5. Read all responses
    buffer = b""
    start = time.time()
    while time.time() - start < 10:
        try:
            sock.settimeout(2)
            data = sock.recv(4096)
            if not data:
                break
            buffer += data
        except socket.timeout:
            break

    # 6. Parse and display
    sock.close()

    content = buffer.decode('ascii', errors='replace')
    messages = content.split('^')
    
    print("=" * 60)
    print("RESPUESTAS DEL SYNERGY:")
    print("=" * 60)
    
    pump_statuses = []
    lock_events = []
    others = []
    
    for msg in messages:
        msg = msg.strip()
        if not msg:
            continue
        
        if 'ECHO' in msg:
            print(f"  📡 ECHO: {msg[:80]}...")
        elif 'EVT_PUMP_STATUS_CHANGE' in msg:
            # Extract key params
            st = ""
            su = ""
            pay_al = ""
            for part in msg.split('|'):
                if part.startswith('ST='): st = part
                elif part.startswith('SU='): su = part
                elif part.startswith('PAY_AL='): pay_al = part
            
            pump_statuses.append((st, su, pay_al))
            print(f"  🟢 STATUS: {st} | {su} | {pay_al}")
            if len(pump_statuses) <= 3:
                print(f"     Full: {msg[:200]}")
        elif 'EVT_PAYMENT' in msg:
            lock_events.append(msg)
            print(f"  🔒 PAYMENT: {msg[:200]}")
        elif 'RES_' in msg:
            print(f"  ✅ RESPONSE: {msg[:200]}")
        else:
            others.append(msg)
    
    if others:
        print(f"\n  Otros ({len(others)}):")
        for o in others:
            print(f"     {o[:150]}")

    print(f"\n{'=' * 60}")
    print("RESUMEN:")
    print(f"  Status changes: {len(pump_statuses)}")
    print(f"  Payment events: {len(lock_events)}")
    print(f"  Total messages: {len(messages)}")
    
    if pump_statuses:
        print("\n  Último estado de la bomba:")
        last_st, last_su, last_payal = pump_statuses[-1]
        print(f"    {last_st}")
        print(f"    {last_su}")
        print(f"    {last_payal}")

if __name__ == "__main__":
    main()
