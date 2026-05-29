#!/usr/bin/env python3.11
"""
diagnostico_preset.py — Verificar parámetros de motor de transacción por bomba

 OBJETIVO: Monitorear Retries, Process zero sale, Authorization Timeout
           de cada Pump Transaction Engine mientras ajustas la consola Wayne.

 USO:     python3.11 docs/scripts_fusion_bridge/diagnostico_preset.py
          Ejecútalo tantas veces como necesites mientras ajustas la consola.

 PROBLEMA: REQ_PUMP_PRESET falla con SSF_TRANS_ERR_PRESET_EMPTY porque
           los parámetros del motor de transacción están en -1 (no inicializados)
           en cada bomba, a pesar de que ForecourtManager sí tiene ATO=180.
"""

import socket
import time
import sys

# ─── CONFIGURACIÓN ───────────────────────────────────────────
FUSION_IP   = "192.168.1.20"
FUSION_PORT = 3011
TIMEOUT     = 4
# ─────────────────────────────────────────────────────────────

# Colores ANSI para terminal
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def build_msg(event_type, params="", destination="", origin=""):
    body = f"2||POST|{event_type}|{destination}|{origin}|{params}|^"
    return f"{len(body):05d}|5|{body}"


def build_subscribe(event):
    body = f"2||SUBSCRIBE|{event}||||^"
    return f"{len(body):05d}|5|{body}"


def build_echo():
    return "00012|5|2||ECHO||||^"


def recv_all(sock, timeout=2):
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


def parse_response(raw):
    """Separa múltiples mensajes (terminados en ^) y extrae parámetros."""
    mensajes = []
    for m in raw.split('^'):
        m = m.strip()
        if not m:
            continue
        parts = m.split('|')
        params = {}
        event_type = ""
        for i, p in enumerate(parts):
            if i == 5:
                event_type = p
            if i >= 8 and '=' in p:
                k, v = p.split('=', 1)
                params[k] = v
        mensajes.append({
            'raw': m,
            'event': event_type,
            'params': params
        })
    return mensajes


def check_ok(valor):
    """Evalúa si un parámetro tiene un valor razonable."""
    if valor is None:
        return f"{YELLOW}⚠️  sin datos{RESET}"
    if valor == 'OK':
        return f"{GREEN}✅ OK (preset funciona){RESET}"
    try:
        n = int(valor)
        if n == -1:
            return f"{RED}❌ -1 (NO INICIALIZADO){RESET}"
        if n == 0 and str(valor) == "0":
            return f"{YELLOW}⚠️  0 (podría ser problemático){RESET}"
        if n > 0:
            return f"{GREEN}✅ {n}{RESET}"
        return f"{RED}❌ {valor}{RESET}"
    except (ValueError, TypeError):
        return f"{RED}❌ {valor}{RESET}"


def main():
    print(f"\n{CYAN}{BOLD}{'='*65}{RESET}")
    print(f"{CYAN}{BOLD}  🔬 DIAGNÓSTICO PRESET — Motor de Transacción por Bomba{RESET}")
    print(f"{CYAN}{BOLD}  Wayne Synergy {FUSION_IP}:{FUSION_PORT}{RESET}")
    print(f"{CYAN}{BOLD}{'='*65}{RESET}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(TIMEOUT)

    try:
        sock.connect((FUSION_IP, FUSION_PORT))
        print(f"\n  {GREEN}✅ Conectado al Synergy{RESET}")

    except ConnectionRefusedError:
        print(f"\n  {RED}❌ Conexión rechazada — ¿Synergy encendido? ¿Puerto 3011 abierto?{RESET}")
        sys.exit(1)
    except socket.timeout:
        print(f"\n  {RED}❌ Timeout — Synergy no responde en {FUSION_IP}:{FUSION_PORT}{RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"\n  {RED}❌ Error: {e}{RESET}")
        sys.exit(1)

    # ── 1. ECHO ──────────────────────────────────────────────
    sock.sendall(build_echo().encode('ascii'))
    time.sleep(0.5)
    echo_resp = recv_all(sock, 1)

    # ── 2. CONFIGURACIÓN DE BOMBAS (detallada) ────────────────
    print(f"\n{BOLD}{'─'*65}{RESET}")
    print(f"{BOLD}  📋 CONFIGURACIÓN DE SURTIDORES (REQ_FCRT_PUMPS_CONFIG){RESET}")
    print(f"{BOLD}{'─'*65}{RESET}")

    msg = build_msg("REQ_FCRT_PUMPS_CONFIG", "PC=POWERFIN|MID=001")
    sock.sendall(msg.encode('ascii'))
    time.sleep(2)
    pump_config_raw = recv_all(sock, 3)
    config_msgs = parse_response(pump_config_raw)

    num_pumps = 0
    for m in config_msgs:
        if 'PUMPS' in m['params']:
            num_pumps = int(m['params']['PUMPS'])
        # Mostrar TODOS los parámetros que empiezan con P*
        pump_params = {k: v for k, v in m['params'].items() if k.startswith('P')}
        general_params = {k: v for k, v in m['params'].items()
                         if not k.startswith('P') and k != 'PUMPS'}

    # Mostrar config general del forecourt
    if config_msgs:
        for m in config_msgs:
            params = m['params']
            ato_global = params.get('ATO', '?')
            print(f"\n  {BOLD}ForecourtManager Global:{RESET}")
            print(f"    Authorization Timeout (ATO): {check_ok(ato_global)}")
            retries_global = params.get('RETRIES', params.get('RT', '?'))
            if retries_global != '?':
                print(f"    Retries Global             : {check_ok(retries_global)}")
            # Mostrar info de bombas
            pumps = params.get('PUMPS', '?')
            print(f"    Surtidores configurados    : {pumps}")
            # Mostrar más parámetros relevantes
            for k, v in sorted(params.items()):
                if k in ('ATO', 'PUMPS', 'RETRIES', 'RT', 'SNR', 'SNA', 'MUA', 'MUD'):
                    continue
                if k.startswith('P'):
                    print(f"    {k:<28} : {v}")

    # ── 3. ESTADO ACTUAL DE SURTIDORES ────────────────────────
    print(f"\n{BOLD}{'─'*65}{RESET}")
    print(f"{BOLD}  🚦 ESTADO ACTUAL DE SURTIDORES (REQ_PUMP_STATUS_ID_000){RESET}")
    print(f"{BOLD}{'─'*65}{RESET}")

    msg = build_msg("REQ_PUMP_STATUS_ID_000")
    sock.sendall(msg.encode('ascii'))
    time.sleep(2)
    status_raw = recv_all(sock, 3)
    status_msgs = parse_response(status_raw)

    pump_states = {}
    for m in status_msgs:
        if 'EVT_PUMP_STATUS_CHANGE' in m['event']:
            pump_id = m['event'].split('_')[-1]
            pump_states[pump_id] = {
                'ST': m['params'].get('ST', '?'),
                'SU': m['params'].get('SU', '-'),
                'HO': m['params'].get('HO', '?'),
                'HN': m['params'].get('HN', '?'),
                'PR': m['params'].get('PR', '0'),
                'GR': m['params'].get('GR', '?'),
            }

    if pump_states:
        print(f"\n  {'SURTIDOR':<10} {'ESTADO':<15} {'SUB-ESTADO':<15} {'HOSES':<8} {'GRADE':<8}")
        print(f"  {'─'*10:<10} {'─'*15:<15} {'─'*15:<15} {'─'*8:<8} {'─'*8:<8}")
        for pid in sorted(pump_states.keys()):
            ps = pump_states[pid]
            st_color = GREEN if ps['ST'] == 'IDLE' else (YELLOW if ps['ST'] in ('CALLING', 'AUTHORIZED', 'FUELLING') else RED)
            print(f"  {pid:<10} {st_color}{ps['ST']:<15}{RESET} {ps['SU']:<15} {ps['HN']:<8} {ps['GR']:<8}")
    else:
        print(f"  {YELLOW}⚠️  No se recibió estado de surtidores{RESET}")

    # ── 4. PRUEBA PRESET (intencional) ────────────────────────
    print(f"\n{BOLD}{'─'*65}{RESET}")
    print(f"{BOLD}  🧪 PRUEBA DE PRESET — Motor de Transacción por Bomba{RESET}")
    print(f"{BOLD}{'─'*65}{RESET}")
    print(f"\n  {YELLOW}Enviando REQ_PUMP_PRESET para ver los parámetros internos...{RESET}")

    # Determinar cuántas bombas hay
    if num_pumps == 0:
        # Intentar deducir de pump_states
        num_pumps = len(pump_states)
    if num_pumps == 0:
        num_pumps = 2  # sabemos que hay 2

    preset_results = {}

    for pump_num in range(1, num_pumps + 1):
        pump_id = f"00{pump_num}" if pump_num < 10 else f"0{pump_num}"
        print(f"\n  {BOLD}Pump {pump_num} (ID={pump_id}):{RESET}")

        # Suscribirse a eventos de esta bomba
        sub = build_subscribe(f"EVT_PUMP_STATUS_CHANGE_ID_{pump_id}")
        sock.sendall(sub.encode('ascii'))
        time.sleep(0.3)

        # Intentar un preset pequeño ($1.00) para disparar diagnóstico
        preset = build_msg(
            f"REQ_PUMP_PRESET_ID_{pump_id}",
            "TY=MONEY|VA=1.00|HO=1|LV=1|FTS=YES|PAY_IN=DIAGNOSTICO=POWERFIN"
        )
        sock.sendall(preset.encode('ascii'))
        time.sleep(3)
        resp = recv_all(sock, 5)
        msgs = parse_response(resp)

        # Analizar respuesta
        found_error = False
        for m in msgs:
            params = m['params']
            evt = m['event']

            # Mostrar cambio de estado
            if 'EVT_PUMP_STATUS_CHANGE' in evt:
                st = params.get('ST', '?')
                su = params.get('SU', '?')
                color = GREEN if st == 'AUTHORIZED' else (RED if st == 'ERROR' else YELLOW)
                print(f"    Estado → {color}{st}{RESET} / {su}")

            # Buscar parámetros internos
            retries      = params.get('Retries', params.get('RETRIES', None))
            zero_sale    = params.get('Process zero sale', params.get('ZERO_SALE', None))
            auth_timeout = params.get('Authorization Timeout', params.get('AUTH_TIMEOUT', None))

            # También buscar en otros campos
            for k, v in params.items():
                kl = k.lower()
                if 'retry' in kl and retries is None:
                    retries = v
                if 'zero' in kl and zero_sale is None:
                    zero_sale = v
                if 'timeout' in kl and auth_timeout is None:
                    auth_timeout = v
                if 'auth' in kl and 'time' in kl and auth_timeout is None:
                    auth_timeout = v

            if retries is not None or zero_sale is not None or auth_timeout is not None:
                found_error = True
                preset_results[pump_num] = {
                    'retries': retries,
                    'zero_sale': zero_sale,
                    'auth_timeout': auth_timeout
                }

        if not found_error:
            # Mostrar respuesta cruda por si los parámetros vienen en otro formato
            raw_lines = [m['raw'] for m in msgs if m['raw']]
            if raw_lines:
                print(f"    Respuesta cruda:")
                for line in raw_lines:
                    print(f"      {line[:200]}...")
            # Verificar si el preset fue exitoso (sin error)
            success = any('AUTHORIZED' in m.get('event', '') or
                         m['params'].get('ST') == 'AUTHORIZED'
                         for m in msgs)
            if success:
                print(f"    {GREEN}✅ ¡PRESET ACEPTADO! La bomba {pump_num} ya funciona.{RESET}")
                preset_results[pump_num] = {
                    'retries': 'OK',
                    'zero_sale': 'OK',
                    'auth_timeout': 'OK'
                }
                # Limpiar el preset
                clear = build_msg(f"REQ_PUMP_CLEAR_PRESET_ID_{pump_id}")
                sock.sendall(clear.encode('ascii'))
                time.sleep(1)
                recv_all(sock, 1)
            else:
                print(f"    {YELLOW}⚠️  No se encontraron parámetros internos en la respuesta.{RESET}")
                print(f"    {YELLOW}   Posiblemente el error viene en otro formato.{RESET}")
                print(f"    {YELLOW}   Revisa la consola Fusion para ver logs de debug.{RESET}")
                if raw_lines:
                    # Buscar SSF_TRANS_ERR
                    for line in raw_lines:
                        if 'ERR' in line or 'ERROR' in line:
                            print(f"    {RED}   ERROR DETECTADO: {line[:300]}{RESET}")

    # ── 5. RESUMEN FINAL ──────────────────────────────────────
    print(f"\n{BOLD}{'='*65}{RESET}")
    print(f"{BOLD}  📊 RESUMEN — Parámetros del Motor de Transacción{RESET}")
    print(f"{BOLD}{'='*65}{RESET}")

    if preset_results:
        print(f"\n  {'BOMBA':<8} {'RETRIES':<24} {'ZERO SALE':<26} {'AUTH TIMEOUT':<26} {'ESTADO':<20}")
        print(f"  {'─'*8:<8} {'─'*24:<24} {'─'*26:<26} {'─'*26:<26} {'─'*20:<20}")
        for pnum in sorted(preset_results.keys()):
            r = preset_results[pnum]
            retries_str      = check_ok(r.get('retries', '?'))
            zero_sale_str    = check_ok(r.get('zero_sale', '?'))
            auth_timeout_str = check_ok(r.get('auth_timeout', '?'))

            all_ok = (
                r.get('retries') == 'OK' or
                all(
                    v not in ('-1', None) and v != '-1'
                    for v in [r.get('retries'), r.get('zero_sale'), r.get('auth_timeout')]
                )
            )
            estado = f"{GREEN}✅ LISTO{RESET}" if all_ok else f"{RED}❌ PENDIENTE{RESET}"
            print(f"  Pump {pnum}:  {retries_str}   {zero_sale_str}   {auth_timeout_str}   => {estado}")
    else:
        print(f"\n  {RED}❌ No se pudo obtener información de ninguna bomba.{RESET}")
        print(f"  {YELLOW}   ¿Están los surtidores en IDLE?{RESET}")
        print(f"  {YELLOW}   ¿Están abiertos? (usa REQ_PUMP_OPEN si están CLOSED){RESET}")

    print(f"\n  {CYAN}💡 Consejo:{RESET}")
    print(f"  {CYAN}   Los valores deben ser: Retries=4, Zero Sale=NO/0, Auth Timeout=180{RESET}")
    print(f"  {CYAN}   Si aparecen en -1, ajusta la configuración de cada bomba{RESET}")
    print(f"  {CYAN}   en la consola Wayne (Pump → Transaction Engine).{RESET}")
    print(f"  {CYAN}   Vuelve a ejecutar este script para verificar cambios.{RESET}")
    print()

    # ── 6. LIMPIEZA ───────────────────────────────────────────
    # Cancelar cualquier preset residual — solo si está en IDLE+PRESET
    # (si ya está en IDLE limpio, CLEAR_PRESET dará error inofensivo)
    for pump_num in range(1, num_pumps + 1):
        pump_id = f"00{pump_num}" if pump_num < 10 else f"0{pump_num}"
        clear = build_msg(f"REQ_PUMP_CLEAR_PRESET_ID_{pump_id}")
        sock.sendall(clear.encode('ascii'))
        time.sleep(0.3)
    recv_all(sock, 0.5)

    sock.close()
    print(f"  🔌 Conexión cerrada.\n")


if __name__ == "__main__":
    main()
