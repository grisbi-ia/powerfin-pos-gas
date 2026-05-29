#!/usr/bin/env python3.11
"""
reiniciar_bomba.py — Reinicializar Transaction Engine de dispensadores Wayne

 USO:
   python3.11 docs/scripts_fusion_bridge/reiniciar_bomba.py --pump 1
   python3.11 docs/scripts_fusion_bridge/reiniciar_bomba.py --pump 1,3,5
   python3.11 docs/scripts_fusion_bridge/reiniciar_bomba.py --all
   python3.11 docs/scripts_fusion_bridge/reiniciar_bomba.py --all --dry-run

 PROPÓSITO:
   Forzar que el Transaction Engine de cada bomba se reinicialice y cargue
   la configuración más reciente desde la base de datos del Synergy.
   Necesario después de cambios en la GUI del Fusion (ATO, Retries, precios, etc.).

 SECUENCIA POR BOMBA:
   1. REQ_PUMP_STOP_ID_00N  → detener (PA=1: pausar si está despachando)
   2. Esperar 5 segundos
   3. REQ_PUMP_CLEAR_STOP_ID_00N → liberar
   4. REQ_PUMP_OPEN_ID_00N  → reabrir → Transaction Engine se reinicializa
   5. Esperar status → verificar que quede en IDLE
"""

import socket
import time
import sys
import argparse

# ─── CONFIGURACIÓN ───────────────────────────────────────────
FUSION_IP   = "192.168.1.20"
FUSION_PORT = 3011
TIMEOUT     = 5
# ─────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def build_msg(event_type, params=""):
    body = f"2||POST|{event_type}|||{params}|^"
    return f"{len(body):05d}|5|{body}"


def build_subscribe(event):
    body = f"2||SUBSCRIBE|{event}||||^"
    return f"{len(body):05d}|5|{body}"


def recv_all(sock, timeout=3):
    """Recibe todos los datos disponibles en el buffer."""
    data = b""
    sock.settimeout(timeout)
    try:
        while True:
            chunk = sock.recv(8192)
            if not chunk:
                break
            data += chunk
    except socket.timeout:
        pass
    return data.decode('ascii', errors='replace')


def parse_messages(raw):
    """Separa mensajes terminados en ^ y extrae ST y event_type."""
    results = []
    for m in raw.split('^'):
        m = m.strip()
        if not m:
            continue
        parts = m.split('|')
        event = parts[5] if len(parts) > 5 else ""
        params = {}
        for p in parts[8:]:
            if '=' in p:
                k, v = p.split('=', 1)
                params[k] = v
        results.append({'event': event, 'st': params.get('ST', '?')})
    return results


def reiniciar_bomba(sock, pump_num, dry_run=False):
    """Ejecuta la secuencia STOP → CLEAR_STOP → OPEN para una bomba."""
    pump_id = f"{pump_num:03d}"

    if dry_run:
        print(f"  {CYAN}[DRY RUN] Se enviaría secuencia a bomba {pump_num}{RESET}")
        return True

    # Suscribirse a eventos de esta bomba
    sub = build_subscribe(f"EVT_PUMP_STATUS_CHANGE_ID_{pump_id}")
    sock.sendall(sub.encode('ascii'))
    time.sleep(0.3)
    recv_all(sock, 0.3)

    # ── 1. STOP ──────────────────────────────────────────────
    stop_msg = build_msg(f"REQ_PUMP_STOP_ID_{pump_id}", "PA=1")
    sock.sendall(stop_msg.encode('ascii'))
    print(f"    → STOP enviado")
    time.sleep(2)
    resp_stop = recv_all(sock, 3)
    msgs_stop = parse_messages(resp_stop)
    for m in msgs_stop:
        if 'STATUS_CHANGE' in m['event']:
            print(f"    ← Estado post-STOP: {m['st']}")

    # ── 2. Esperar ───────────────────────────────────────────
    print(f"    ⏳ Esperando 5s...")
    time.sleep(5)

    # ── 3. CLEAR STOP ────────────────────────────────────────
    clear_msg = build_msg(f"REQ_PUMP_CLEAR_STOP_ID_{pump_id}")
    sock.sendall(clear_msg.encode('ascii'))
    print(f"    → CLEAR_STOP enviado")
    time.sleep(1)
    recv_all(sock, 1)

    # ── 4. OPEN ──────────────────────────────────────────────
    open_msg = build_msg(f"REQ_PUMP_OPEN_ID_{pump_id}")
    sock.sendall(open_msg.encode('ascii'))
    print(f"    → OPEN enviado")
    time.sleep(3)
    resp_open = recv_all(sock, 5)
    msgs_open = parse_messages(resp_open)

    final_state = "?"
    for m in msgs_open:
        if 'STATUS_CHANGE' in m['event']:
            final_state = m['st']
            print(f"    ← Estado post-OPEN: {final_state}")

    # ── 5. Verificar ─────────────────────────────────────────
    # Consultar estado actual
    status_msg = build_msg(f"REQ_PUMP_STATUS_ID_{pump_id}")
    sock.sendall(status_msg.encode('ascii'))
    time.sleep(2)
    resp_status = recv_all(sock, 3)
    msgs_status = parse_messages(resp_status)

    for m in msgs_status:
        if 'STATUS_CHANGE' in m['event']:
            final_state = m['st']

    if final_state in ('IDLE', 'CLOSED'):
        print(f"    {GREEN}✅ Bomba {pump_num}: {final_state} (reinicializada){RESET}")
        return True
    elif final_state == 'ERROR':
        print(f"    {YELLOW}⚠️  Bomba {pump_num}: ERROR — posiblemente sin dispensador físico conectado{RESET}")
        print(f"    {YELLOW}   Esto es normal si el dispensador está apagado.{RESET}")
        print(f"    {YELLOW}   Al encenderlo, pasará a IDLE y cargará la nueva configuración.{RESET}")
        return True  # ERROR es esperado sin hardware
    else:
        print(f"    {RED}❌ Bomba {pump_num}: {final_state} — no se pudo verificar{RESET}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Reinicializar Transaction Engine de dispensadores Wayne Synergy"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pump", type=str,
                       help="Número de bomba (ej: 1) o bombas separadas por coma (ej: 1,2,3)")
    group.add_argument("--all", action="store_true",
                       help="Reinicializar todas las bombas (1-6)")
    parser.add_argument("--max-pumps", type=int, default=6,
                       help="Número máximo de bombas con --all (default: 6)")
    parser.add_argument("--dry-run", action="store_true",
                       help="Mostrar qué se haría sin ejecutar")
    args = parser.parse_args()

    # ── Determinar lista de bombas ───────────────────────────
    if args.pump:
        try:
            pumps = [int(p.strip()) for p in args.pump.split(',')]
        except ValueError:
            print(f"{RED}❌ Error: --pump debe ser número(s) (ej: 1 o 1,2,3){RESET}")
            sys.exit(1)
    else:
        pumps = list(range(1, args.max_pumps + 1))

    # Validar
    for p in pumps:
        if p < 1 or p > 99:
            print(f"{RED}❌ Error: número de bomba inválido: {p}{RESET}")
            sys.exit(1)

    # ── Cabecera ─────────────────────────────────────────────
    print(f"\n{CYAN}{BOLD}{'='*60}{RESET}")
    print(f"{CYAN}{BOLD}  🔄 REINICIALIZAR BOMBAS — Wayne Synergy{RESET}")
    print(f"{CYAN}{BOLD}  {FUSION_IP}:{FUSION_PORT}{RESET}")
    print(f"{CYAN}{BOLD}{'='*60}{RESET}")
    print(f"\n  Bombas a reinicializar: {', '.join(str(p) for p in pumps)}")
    if args.dry_run:
        print(f"  {YELLOW}  MODO: DRY RUN (no se ejecutará nada){RESET}")
    print()

    # ── Conectar ─────────────────────────────────────────────
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(TIMEOUT)

    try:
        sock.connect((FUSION_IP, FUSION_PORT))
        print(f"  {GREEN}✅ Conectado al Synergy{RESET}\n")
    except ConnectionRefusedError:
        print(f"  {RED}❌ Conexión rechazada — ¿Synergy encendido?{RESET}\n")
        sys.exit(1)
    except socket.timeout:
        print(f"  {RED}❌ Timeout — Synergy no responde{RESET}\n")
        sys.exit(1)
    except Exception as e:
        print(f"  {RED}❌ Error: {e}{RESET}\n")
        sys.exit(1)

    # ── Procesar bombas una por una ──────────────────────────
    results = {}
    total = len(pumps)

    for i, pump_num in enumerate(pumps, 1):
        print(f"{BOLD}  [{i}/{total}] Bomba {pump_num}:{RESET}")
        ok = reiniciar_bomba(sock, pump_num, dry_run=args.dry_run)
        results[pump_num] = ok
        if i < total:
            print(f"    ─────────────────────────────────────")
        print()

    # ── Resumen ──────────────────────────────────────────────
    print(f"{BOLD}{'─'*60}{RESET}")
    print(f"{BOLD}  📊 RESUMEN{RESET}")
    print(f"{BOLD}{'─'*60}{RESET}\n")

    ok_count = sum(1 for v in results.values() if v)
    fail_count = sum(1 for v in results.values() if not v)

    for pump_num in pumps:
        ok = results.get(pump_num, False)
        icon = f"{GREEN}✅{RESET}" if ok else f"{RED}❌{RESET}"
        estado = "OK" if ok else "FALLÓ"
        print(f"  {icon} Bomba {pump_num}: {estado}")

    print(f"\n  {GREEN}{ok_count} exitosa(s){RESET}", end="")
    if fail_count > 0:
        print(f"  {RED}{fail_count} fallida(s){RESET}")
    else:
        print()

    # ── Recordatorio ─────────────────────────────────────────
    if not args.dry_run and ok_count > 0:
        print(f"\n  {CYAN}💡 Ejecuta el diagnóstico para verificar:{RESET}")
        print(f"  {CYAN}   python3.11 docs/scripts_fusion_bridge/diagnostico_preset.py{RESET}")

    sock.close()
    print(f"\n  🔌 Conexión cerrada.\n")

    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
