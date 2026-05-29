import socket
import time

FUSION_IP   = "192.168.1.20"
FUSION_PORT = 3011

def build_msg(event_type, params="", destination="", origin=""):
    body = f"2||POST|{event_type}|{destination}|{origin}|{params}|^"
    return f"{len(body):05d}|5|{body}"

def build_subscribe(event):
    body = f"2||SUBSCRIBE|{event}||||^"
    return f"{len(body):05d}|5|{body}"

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(5)
sock.connect((FUSION_IP, FUSION_PORT))
print(f"✅ Conectado a {FUSION_IP}:{FUSION_PORT}\n")

# 1. Suscribirse a cambios de estado del surtidor 1
sub = build_subscribe("EVT_PUMP_STATUS_CHANGE_ID_001")
sock.sendall(sub.encode('ascii'))
print(f"→ Suscrito a eventos del surtidor 1")
time.sleep(1)

# 2. Abrir el surtidor (pasar de CLOSED a activo)
msg = build_msg("REQ_PUMP_OPEN_ID_001")
sock.sendall(msg.encode('ascii'))
print(f"→ Abriendo surtidor 1: {msg}")
time.sleep(2)

try:
    resp = sock.recv(4096).decode('ascii', errors='replace')
    print(f"← Estado tras OPEN: {resp}")
except socket.timeout:
    print("← (sin respuesta al OPEN)")

# 3. Solicitar estado actual
msg2 = build_msg("REQ_PUMP_STATUS_ID_001")
sock.sendall(msg2.encode('ascii'))
print(f"\n→ Consultando estado: {msg2}")
time.sleep(2)

try:
    resp2 = sock.recv(4096).decode('ascii', errors='replace')
    print(f"← Estado actual: {resp2}")
    
    if "ST=IDLE" in resp2:
        print("\n🎉 ¡SURTIDOR EN IDLE! Listo para recibir autorizaciones")
        
        # 4. Intentar una pre-autorización de $5.00 en pistola 1
        print("\n→ Enviando preset de $5.00 en pistola 1...")
        preset = build_msg(
            "REQ_PUMP_PRESET_ID_001",
            "TY=MONEY|VA=5.00|HO=1|PAY_IN=TEST=POWERFIN"
        )
        sock.sendall(preset.encode('ascii'))
        time.sleep(3)
        resp3 = sock.recv(4096).decode('ascii', errors='replace')
        print(f"← Respuesta preset: {resp3}")
        
    elif "ST=ERROR" in resp2:
        print("\n⚠️  Surtidor en ERROR — esperado sin hardware físico conectado")
        print("    Cuando conectes el dispensador real pasará a IDLE automáticamente")
        
    elif "ST=CLOSED" in resp2:
        print("\n⚠️  Surtidor sigue CLOSED — puede necesitar reinicio del Fusion")
        
except socket.timeout:
    print("← (sin respuesta)")

sock.close()
print("\n🔌 Conexión cerrada")
