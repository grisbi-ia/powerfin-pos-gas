import socket
import time

# ─── CONFIGURACIÓN ───────────────────────────────────────────
FUSION_IP   = "192.168.1.20"   # ← cambia por la IP real del Synergy
FUSION_PORT = 3011
TIMEOUT     = 5
# ─────────────────────────────────────────────────────────────

def test_fusion():
    print(f"\n🔌 Conectando a Wayne Fusion {FUSION_IP}:{FUSION_PORT}...")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(TIMEOUT)

    try:
        sock.connect((FUSION_IP, FUSION_PORT))
        print("✅ Conexión TCP establecida\n")

        # ── TEST 1: ECHO ──────────────────────────────────────
        echo_msg = "00012|5|2||ECHO||||^"
        sock.sendall(echo_msg.encode('ascii'))
        print(f"→ Enviado ECHO : {echo_msg}")

        time.sleep(1)
        resp = sock.recv(1024).decode('ascii', errors='replace')
        print(f"← Respuesta    : {resp}")

        if "ECHO" in resp:
            print("✅ ECHO OK — Fusion está viva!\n")
        else:
            print("⚠️  Respuesta inesperada al ECHO\n")

        # ── TEST 2: Estado de todos los surtidores ────────────
        status_msg = "00035|5|2||POST|REQ_PUMP_STATUS_ID_000||||^"
        sock.sendall(status_msg.encode('ascii'))
        print(f"→ Enviado REQ status surtidores: {status_msg}")

        time.sleep(1)
        resp2 = sock.recv(4096).decode('ascii', errors='replace')
        print(f"← Respuesta:\n{resp2}")

        if "EVT_PUMP_STATUS_CHANGE" in resp2:
            print("✅ Surtidores respondieron correctamente")
        else:
            print("⚠️  No se recibió estado de surtidores")

    except ConnectionRefusedError:
        print(f"❌ Conexión rechazada — verifica IP y que el puerto 3011 esté abierto")
    except socket.timeout:
        print(f"❌ Timeout — el equipo no respondió en {TIMEOUT}s")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        sock.close()
        print("\n🔌 Conexión cerrada")

if __name__ == "__main__":
    test_fusion()
