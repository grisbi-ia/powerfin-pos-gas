#!/usr/bin/env python3.11
"""
actualizar_precio.py — Cambiar precio de combustible en Wayne Synergy

 USO:
   python3.11 docs/scripts_fusion_bridge/actualizar_precio.py 3.103
   python3.11 docs/scripts_fusion_bridge/actualizar_precio.py 3.103 --grade 3 --level 1
   python3.11 docs/scripts_fusion_bridge/actualizar_precio.py --show   (solo mostrar)

 El comando Fusion usado:
   REQ_PRICES_SET_NEW_PRICE_CHANGE|Price Change Add In||
     QTY=1|G01NR=3|G01LV=1|G01PR=3.103|^
"""

import socket
import time
import sys
import argparse

FUSION_IP   = "192.168.1.20"
FUSION_PORT = 3011

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def build_msg(event_type, params="", destination=""):
    body = f"2||POST|{event_type}|{destination}||{params}|^"
    return f"{len(body):05d}|5|{body}"


def query_grades(sock):
    """Consulta y muestra la config actual de combustibles."""
    msg = build_msg("REQ_FCRT_GRADES_CONFIG")
    sock.sendall(msg.encode('ascii'))
    time.sleep(2)
    sock.settimeout(3)
    try:
        resp = sock.recv(8192).decode('ascii', errors='replace')
    except socket.timeout:
        resp = ""
    return parse_grades(resp)


def parse_grades(raw):
    """Extrae información de grados de la respuesta."""
    grades = []
    for m in raw.split('^'):
        m = m.strip()
        if not m:
            continue
        parts = m.split('|')
        params = {}
        for p in parts:
            if '=' in p:
                k, v = p.split('=', 1)
                params[k] = v

        num_grades = int(params.get('GRADES', 0))
        for i in range(1, num_grades + 1):
            prefix = f"G{i:03d}"
            desc = params.get(f"{prefix}DES", "?")
            gnr  = params.get(f"{prefix}GNR", "?")
            gid  = params.get(f"{prefix}GID", "?")
            unit = params.get(f"{prefix}UM", "?")
            lvs  = int(params.get(f"{prefix}LVS", 0))
            prices = {}
            for lv in range(1, lvs + 1):
                prices[lv] = params.get(f"{prefix}L{lv:02d}", "?")

            grades.append({
                'index': i,
                'description': desc,
                'grade_number': gnr,
                'grade_id': gid,
                'unit': unit,
                'levels': prices
            })

    return grades


def show_grades(grades):
    """Muestra los grados en formato tabla."""
    print(f"\n{BOLD}{'─'*60}{RESET}")
    print(f"{BOLD}  📋 COMBUSTIBLES CONFIGURADOS{RESET}")
    print(f"{BOLD}{'─'*60}{RESET}\n")
    print(f"  {'#':<4} {'GNR':<6} {'ID':<6} {'DESCRIPCIÓN':<14} {'UNIDAD':<22} {'NIVELES':<10}")
    print(f"  {'─'*4:<4} {'─'*6:<6} {'─'*6:<6} {'─'*14:<14} {'─'*22:<22} {'─'*10:<10}")
    for g in grades:
        unit_display = g['unit'].replace('SSF_TRANS_GRADE_UNIT_', '').replace('_ABBR', '')
        levels_str = ", ".join(f"L{lv}={p}" for lv, p in g['levels'].items())
        print(f"  {g['index']:<4} {g['grade_number']:<6} {g['grade_id']:<6} "
              f"{g['description']:<14} {unit_display:<22} {levels_str}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Actualizar precio de combustible en Wayne Synergy",
        epilog="Ejemplo: python3.11 actualizar_precio.py 3.103"
    )
    parser.add_argument("price", nargs="?", type=float,
                        help="Nuevo precio (ej: 3.103)")
    parser.add_argument("--grade", type=int, default=3,
                        help="Grade Number (default: 3 = DIESEL)")
    parser.add_argument("--level", type=int, default=1,
                        help="Price Level (default: 1)")
    parser.add_argument("--show", action="store_true",
                        help="Solo mostrar precios actuales, no cambiar")
    args = parser.parse_args()

    if not args.show and args.price is None:
        parser.error("Debes especificar un precio o usar --show")

    # ── Conectar ─────────────────────────────────────────
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)

    try:
        sock.connect((FUSION_IP, FUSION_PORT))
    except Exception as e:
        print(f"{RED}❌ Error conectando: {e}{RESET}")
        sys.exit(1)

    # ── Mostrar estado actual ─────────────────────────────
    grades = query_grades(sock)
    if grades:
        show_grades(grades)
    else:
        print(f"{YELLOW}⚠️  No se pudo obtener configuración de combustibles{RESET}")

    if args.show:
        sock.close()
        return

    # ── Confirmar cambio ──────────────────────────────────
    grade_nr = args.grade
    level    = args.level
    new_price = args.price

    # Buscar el grado por GNR
    target = None
    for g in grades:
        if g['grade_number'] == str(grade_nr):
            target = g
            break

    if target:
        old_price = target['levels'].get(level, '?')
        desc = target['description']
        print(f"{BOLD}  🔄 Cambio a realizar:{RESET}")
        print(f"     Combustible: {desc} (GNR={grade_nr})")
        print(f"     Nivel:       {level}")
        print(f"     Precio:      {RED}{old_price}{RESET} → {GREEN}{new_price}{RESET}")
    else:
        print(f"     Combustible GNR={grade_nr}, Nivel={level}")
        print(f"     Precio:      → {GREEN}{new_price}{RESET}")

    # ── Enviar cambio ─────────────────────────────────────
    params = (
        f"QTY=1|"
        f"G01NR={grade_nr}|"
        f"G01LV={level}|"
        f"G01PR={new_price:.3f}"
    )
    msg = build_msg("REQ_PRICES_SET_NEW_PRICE_CHANGE", params, "Price Change Add In")
    print(f"\n  → Enviando: {msg}")
    sock.sendall(msg.encode('ascii'))
    time.sleep(3)

    try:
        resp = sock.recv(8192).decode('ascii', errors='replace')
        print(f"  ← Respuesta: {resp[:300]}")
        if 'OK' in resp or 'APPLIED' in resp:
            print(f"\n  {GREEN}✅ Precio actualizado correctamente{RESET}")
        elif 'ERROR' in resp:
            print(f"\n  {RED}❌ Error al actualizar precio{RESET}")
        else:
            print(f"\n  {YELLOW}⚠️  Verificar en la consola{RESET}")
    except socket.timeout:
        print(f"  ← (timeout — el cambio puede haberse aplicado igual)")
        print(f"\n  {YELLOW}⚠️  Verifica en la consola o vuelve a consultar{RESET}")

    # ── Verificar ─────────────────────────────────────────
    print(f"\n{BOLD}  🔍 Verificando cambio...{RESET}")
    time.sleep(2)
    grades_after = query_grades(sock)
    if grades_after:
        for g in grades_after:
            if g['grade_number'] == str(grade_nr):
                new_val = g['levels'].get(level, '?')
                if new_val == f"{new_price:.3f}":
                    print(f"  {GREEN}✅ Confirmado: {g['description']} L{level} = {new_val}{RESET}")
                else:
                    print(f"  {YELLOW}⚠️  No coincide: esperado {new_price:.3f}, actual {new_val}{RESET}")
                    print(f"  {YELLOW}   Puede requerir aplicar cambio (consola) o reinicializar disp.{RESET}")

    sock.close()
    print()


if __name__ == "__main__":
    main()
