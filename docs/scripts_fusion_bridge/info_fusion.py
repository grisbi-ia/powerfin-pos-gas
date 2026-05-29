import socket
import time

FUSION_IP   = "192.168.1.20"
FUSION_PORT = 3011

def build_msg(event_type, params="", destination="", origin=""):
    body = f"2||POST|{event_type}|{destination}|{origin}|{params}|^"
    length = len(body)
    return f"{length:05d}|5|{body}"

def send_and_receive(sock, nombre, msg, timeout=3):
    print(f"\n{'='*60}")
    print(f"→ {nombre}")
    print(f"  Enviado : {msg}")
    sock.sendall(msg.encode('ascii'))
    time.sleep(timeout)
    try:
        resp = sock.recv(8192).decode('ascii', errors='replace')
        # Separar múltiples mensajes por ^
        mensajes = [m.strip() for m in resp.split('^') if m.strip()]
        for m in mensajes:
            print(f"  ← {m}^")
        return resp
    except socket.timeout:
        print(f"  ← (sin respuesta)")
        return ""

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(4)
sock.connect((FUSION_IP, FUSION_PORT))
print(f"✅ Conectado a {FUSION_IP}:{FUSION_PORT}")

comandos = [
    ("Config general del site",
     build_msg("REQ_FCRT_GET_GRAL_CONFIG")),

    ("Surtidores y pistolas configurados",
     build_msg("REQ_FCRT_PUMPS_CONFIG", "PC=POWERFIN|MID=001")),

    ("Combustibles (Grades) configurados",
     build_msg("REQ_FCRT_GRADES_CONFIG")),

    ("Tanques configurados",
     build_msg("REQ_FCRT_TANK_CONFIG")),

    ("Estado actual de surtidores",
     build_msg("REQ_PUMP_STATUS_ID_000")),
]

for nombre, msg in comandos:
    send_and_receive(sock, nombre, msg)

sock.close()
print(f"\n{'='*60}")
print("🔌 Conexión cerrada")
