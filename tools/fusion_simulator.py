#!/usr/bin/env python3
"""
FusionBridge Simulator — Wayne Fusion/Synergy emulator for testing.

Listens on TCP port 3012 (default) and speaks the Fusion Native Protocol.
Simulates dispenser states, fueling progress, and payment handshake.

Usage:
    python3 fusion_simulator.py [--port PORT] [--pumps N]

Protocol: <len>|<crypt>|<version>|<user_id>|<msg_type>|<event>|<dest>|<origin>|<params>|^
"""

import socket
import threading
import time
import argparse
import random
from dataclasses import dataclass, field
from typing import Optional


# ── Configuration ─────────────────────────────────────────────

DEFAULT_PORT = 3012
DEFAULT_PUMPS = 2          # Number of simulated dispensers
HOSES_PER_PUMP = 4         # Hoses per pump (2 per side)
FUELING_DURATION = 20.0    # Seconds to simulate fueling
PROGRESS_INTERVAL = 1.5    # Seconds between progress updates
ECHO_INTERVAL = 120        # Client should ECHO every N seconds


# ── Dispenser/Hose State ─────────────────────────────────────

@dataclass
class HoseState:
    pump_id: int
    hose_num: int
    status: str = "IDLE"            # IDLE | AUTHORIZED | STARTING | FUELLING | PAUSED
    sub_status: str = ""
    preset_type: str = ""            # MONEY | VOLUME
    preset_value: float = 0.0
    unit_price: float = 0.0
    grade: int = 0
    pay_in: str = ""                 # OV=xxx~CLI=xxx~...
    pay_type: str = ""
    sale_id: int = 0
    volume_delivered: float = 0.0
    amount_delivered: float = 0.0
    lock_id: str = ""
    locked: bool = False

    def reset(self):
        self.status = "IDLE"
        self.sub_status = ""
        self.preset_type = ""
        self.preset_value = 0.0
        self.unit_price = 0.0
        self.pay_in = ""
        self.pay_type = ""
        self.volume_delivered = 0.0
        self.amount_delivered = 0.0
        self.locked = False
        self.lock_id = ""


class FusionSimulator:
    def __init__(self, port: int = DEFAULT_PORT, num_pumps: int = DEFAULT_PUMPS):
        self.port = port
        self.num_pumps = num_pumps
        self.sale_counter = 100
        self.clients: list[socket.socket] = []
        self.running = True

        # State: one pump with multiple hoses
        self.pumps: dict[int, dict[int, HoseState]] = {}
        for p in range(1, num_pumps + 1):
            self.pumps[p] = {}
            for h in range(1, HOSES_PER_PUMP + 1):
                grade = (h % 3) + 1 if h % 3 != 0 else 3  # 1=SUPER, 2=EXTRA, 3=DIESEL
                self.pumps[p][h] = HoseState(pump_id=p, hose_num=h, grade=grade)

        self.lock = threading.Lock()

    # ── Message Builder ───────────────────────────────────────

    def build_msg(self, event: str, params: str = "", destination: str = "",
                  origin: str = "", user_id: str = "GUEST") -> str:
        body = f"2||POST|{event}|{destination}|{origin}|{params}|^"
        full = f"{len(body):05d}|5|{body}"
        return full

    def build_echo_response(self, client_addr: str) -> str:
        body = f"2||ECHO||{client_addr}||^"
        return f"{len(body):05d}|5|{body}"

    def build_status_event(self, pump_id: int, hose_num: int, status: str,
                           sub_status: str = "", preset: float = 0.0,
                           hose_count: int = HOSES_PER_PUMP) -> str:
        event = f"EVT_PUMP_STATUS_CHANGE_ID_{pump_id:03d}"
        params = f"ST={status}|SU={sub_status}|HO={hose_num}|PR={preset:.2f}|HN={hose_count}"
        return self.build_msg(event, params)

    def build_new_transaction(self, pump_id: int, hose: HoseState) -> str:
        event = "EVT_PUMP_NEW_TRANSACTION"
        now = time.localtime()
        date_str = time.strftime("%Y%m%d", now)
        time_str = time.strftime("%H%M%S", now)
        params = (
            f"SA={hose.sale_id}|PM={pump_id}|HO={hose.hose_num}|GR={hose.grade}|"
            f"VO={hose.volume_delivered:.3f}|AM={hose.amount_delivered:.2f}|"
            f"PU={hose.unit_price:.3f}|PR={hose.preset_value:.2f}|"
            f"TY=1|DA={date_str}|TI={time_str}|"
            f"PAY_TY={hose.pay_type}|PAY_IN={hose.pay_in}"
        )
        return self.build_msg(event, params)

    def build_delivery_progress(self, pump_id: int, hose: HoseState) -> str:
        event = f"EVT_PUMP_DELIVERY_PROGRESS_ID_{pump_id:03d}"
        params = (
            f"AM={hose.amount_delivered:.2f}|VO={hose.volume_delivered:.3f}|"
            f"PU={hose.unit_price:.3f}|HO={hose.hose_num}"
        )
        return self.build_msg(event, params)

    # ── Message Parser ────────────────────────────────────────

    def parse(self, raw: str) -> dict:
        raw = raw.strip()
        if raw.endswith("^"):
            raw = raw[:-1]
        parts = raw.split("|")
        if len(parts) < 5:
            return {}
        result = {
            "len": parts[0], "crypt": parts[1], "version": parts[2],
            "user_id": parts[3], "msg_type": parts[4],
            "event": parts[5] if len(parts) > 5 else "",
            "destination": parts[6] if len(parts) > 6 else "",
            "origin": parts[7] if len(parts) > 7 else "",
            "params": {}
        }
        for p in parts[8:]:
            if "=" in p:
                k, v = p.split("=", 1)
                result["params"][k] = v
        return result

    # ── Simulated Fueling Thread ───────────────────────────────

    def simulate_fueling(self, pump_id: int, hose_num: int, client_sock: socket.socket):
        """Run fueling simulation in a background thread."""
        with self.lock:
            hose = self.pumps.get(pump_id, {}).get(hose_num)
            if not hose or hose.status != "AUTHORIZED":
                return

            hose.status = "STARTING"
            hose.sub_status = ""
            status_event = self.build_status_event(pump_id, hose_num, "STARTING", "", hose.preset_value)
            client_sock.sendall(status_event.encode("ascii"))

        time.sleep(1.0)

        # Calculate target: if MONEY preset, dispense ~85% of preset value
        # If VOLUME, dispense full volume
        if hose.preset_type == "MONEY":
            target_amount = hose.preset_value * random.uniform(0.75, 0.95)
            target_volume = target_amount / hose.unit_price if hose.unit_price > 0 else target_amount / 1.5
        else:
            target_volume = hose.preset_value
            target_amount = target_volume * hose.unit_price if hose.unit_price > 0 else target_volume * 1.5

        # Simulate progress updates
        steps = int(FUELING_DURATION / PROGRESS_INTERVAL)
        for i in range(1, steps + 1):
            time.sleep(PROGRESS_INTERVAL)
            progress = i / steps
            with self.lock:
                hose.status = "FUELLING"
                hose.volume_delivered = target_volume * progress
                hose.amount_delivered = target_amount * progress

                # Send status + progress
                status_event = self.build_status_event(pump_id, hose_num, "FUELLING", "", hose.preset_value)
                progress_event = self.build_delivery_progress(pump_id, hose)

            client_sock.sendall(status_event.encode("ascii"))
            client_sock.sendall(progress_event.encode("ascii"))

        # Final
        with self.lock:
            hose.volume_delivered = target_volume
            hose.amount_delivered = target_amount
            hose.status = "IDLE"
            hose.sub_status = ""
            hose.sale_id = self.sale_counter
            self.sale_counter += 1

            idle_event = self.build_status_event(pump_id, hose_num, "IDLE")
            tx_event = self.build_new_transaction(pump_id, hose)

        client_sock.sendall(idle_event.encode("ascii"))
        client_sock.sendall(tx_event.encode("ascii"))

    # ── Command Handlers ──────────────────────────────────────

    def handle_echo(self, client_sock: socket.socket, addr: tuple, msg: dict):
        response = self.build_echo_response(f"{addr[0]}:{addr[1]}")
        client_sock.sendall(response.encode("ascii"))

    def handle_pump_status(self, client_sock: socket.socket, msg: dict):
        # REQ_PUMP_STATUS_ID_000 → all pumps; _001 → pump 1
        event = msg.get("event", "")
        pump_str = event.split("_")[-1] if "_" in event else "000"
        pump_id = int(pump_str) if pump_str.isdigit() else 0

        if pump_id == 0:
            # All pumps
            for pid in self.pumps:
                for hnum, hose in self.pumps[pid].items():
                    ev = self.build_status_event(pid, hnum, hose.status, hose.sub_status, hose.preset_value)
                    client_sock.sendall(ev.encode("ascii"))
        else:
            for hnum, hose in self.pumps.get(pump_id, {}).items():
                ev = self.build_status_event(pump_id, hnum, hose.status, hose.sub_status, hose.preset_value)
                client_sock.sendall(ev.encode("ascii"))

    def handle_pump_preset(self, client_sock: socket.socket, msg: dict):
        # REQ_PUMP_PRESET_ID_001
        event = msg.get("event", "")
        pump_str = event.split("_")[-1] if "_" in event else "001"
        pump_id = int(pump_str) if pump_str.isdigit() else 1
        params = msg.get("params", {})

        preset_type = params.get("TY", "MONEY")      # MONEY or VOLUME
        value_str = params.get("VA", "0")
        hose_str = params.get("HO", "1")
        pay_type = params.get("PAY_TY", "")
        pay_in = params.get("PAY_IN", "")
        fts = params.get("FTS", "")

        # Parse hose: could be "1@1.100" or just "1"
        if "@" in hose_str:
            hose_num_str, price_str = hose_str.split("@", 1)
            hose_num = int(hose_num_str) if hose_num_str.isdigit() else 1
            unit_price = float(price_str) if price_str.replace(".", "").isdigit() else 0.0
        else:
            hose_num = int(hose_str) if hose_str.isdigit() else 1
            unit_price = 0.0

        preset_value = float(value_str) if value_str.replace(".", "").isdigit() else 0.0

        with self.lock:
            hose = self.pumps.get(pump_id, {}).get(hose_num)
            if not hose:
                return
            if hose.status != "IDLE" and fts != "YES":
                return  # Hose busy, can't authorize unless FTS=YES

            hose.status = "AUTHORIZED"
            hose.sub_status = "MONEY_PRESET" if preset_type == "MONEY" else "VOLUME_PRESET"
            hose.preset_type = preset_type
            hose.preset_value = preset_value
            hose.unit_price = unit_price if unit_price > 0 else 1.500
            hose.pay_type = pay_type
            hose.pay_in = pay_in
            hose.volume_delivered = 0.0
            hose.amount_delivered = 0.0

            status_event = self.build_status_event(pump_id, hose_num, "AUTHORIZED", hose.sub_status, preset_value)

        client_sock.sendall(status_event.encode("ascii"))

        print(f"  ⛽ PUMP {pump_id} HOSE {hose_num}: AUTHORIZED - {preset_type} ${preset_value:.2f} @ ${hose.unit_price:.3f}")

        # Start simulated fueling in background
        threading.Thread(
            target=self.simulate_fueling,
            args=(pump_id, hose_num, client_sock),
            daemon=True
        ).start()

    def handle_pump_open(self, client_sock: socket.socket, msg: dict):
        event = msg.get("event", "")
        pump_str = event.split("_")[-1] if "_" in event else "000"
        pump_id = int(pump_str) if pump_str.isdigit() else 0

        if pump_id == 0:
            for pid in self.pumps:
                for hose in self.pumps[pid].values():
                    hose.status = "IDLE"
                    ev = self.build_status_event(pid, hose.hose_num, "IDLE")
                    client_sock.sendall(ev.encode("ascii"))
        else:
            for hose in self.pumps.get(pump_id, {}).values():
                hose.status = "IDLE"
                ev = self.build_status_event(pump_id, hose.hose_num, "IDLE")
                client_sock.sendall(ev.encode("ascii"))

    def handle_clear_preset(self, client_sock: socket.socket, msg: dict):
        event = msg.get("event", "")
        pump_str = event.split("_")[-1] if "_" in event else "001"
        pump_id = int(pump_str) if pump_str.isdigit() else 1

        with self.lock:
            for hose in self.pumps.get(pump_id, {}).values():
                if hose.status == "AUTHORIZED":
                    hose.reset()
                    ev = self.build_status_event(pump_id, hose.hose_num, "IDLE")
                    client_sock.sendall(ev.encode("ascii"))
                    print(f"  ⛽ PUMP {pump_id} HOSE {hose.hose_num}: PRESET CANCELLED")

    def handle_transaction_lock(self, client_sock: socket.socket, msg: dict):
        params = msg.get("params", {})
        sale_id = params.get("SA", "")
        lock_id = params.get("LID", "")

        with self.lock:
            for pump in self.pumps.values():
                for hose in pump.values():
                    if str(hose.sale_id) == sale_id:
                        hose.locked = True
                        hose.lock_id = lock_id

        response = self.build_msg("RES_PAYMENT_TRANSACTION_LOCK", f"ST=OK|SA={sale_id}|LID={lock_id}")
        client_sock.sendall(response.encode("ascii"))
        print(f"  🔒 LOCK sale {sale_id} with LID={lock_id}")

    def handle_clear_sale(self, client_sock: socket.socket, msg: dict):
        params = msg.get("params", {})
        sale_id = params.get("SA", "")
        lock_id = params.get("LID", "")

        with self.lock:
            for pump in self.pumps.values():
                for hose in pump.values():
                    if str(hose.sale_id) == sale_id and hose.locked and hose.lock_id == lock_id:
                        hose.locked = False
                        hose.lock_id = ""

        response = self.build_msg("RES_PAYMENT_CLEAR_SALE", f"ST=OK|SA={sale_id}")
        client_sock.sendall(response.encode("ascii"))
        print(f"  💰 CLEAR SALE {sale_id}")

    def handle_transaction_unlock(self, client_sock: socket.socket, msg: dict):
        params = msg.get("params", {})
        sale_id = params.get("SA", "")

        response = self.build_msg("RES_PAYMENT_TRANSACTION_UNLOCK", f"ST=OK|SA={sale_id}")
        client_sock.sendall(response.encode("ascii"))
        print(f"  🔓 UNLOCK sale {sale_id}")

    # ── Client Handler ────────────────────────────────────────

    def handle_client(self, client_sock: socket.socket, addr: tuple):
        print(f"\n⚡ Client connected: {addr[0]}:{addr[1]}")
        self.clients.append(client_sock)
        buffer = ""

        try:
            while self.running:
                data = client_sock.recv(4096)
                if not data:
                    break

                decoded = data.decode("ascii", errors="replace")
                buffer += decoded

                while "^" in buffer:
                    pos = buffer.index("^")
                    raw_msg = buffer[:pos + 1]
                    buffer = buffer[pos + 1:]

                    msg = self.parse(raw_msg)
                    if not msg:
                        continue

                    event = msg.get("event", "")
                    msg_type = msg.get("msg_type", "")
                    params = msg.get("params", {})

                    # Log incoming
                    if msg_type == "ECHO":
                        print(f"  ← ECHO")
                    elif event:
                        pa = params.get("PAY_IN", "")[:60] if params.get("PAY_IN") else ""
                        print(f"  ← {event} {pa}")

                    # Route
                    if msg_type == "ECHO":
                        self.handle_echo(client_sock, addr, msg)
                    elif event.startswith("REQ_PUMP_STATUS"):
                        self.handle_pump_status(client_sock, msg)
                    elif event.startswith("REQ_PUMP_PRESET"):
                        self.handle_pump_preset(client_sock, msg)
                    elif event.startswith("REQ_PUMP_OPEN"):
                        self.handle_pump_open(client_sock, msg)
                    elif event.startswith("REQ_PUMP_CLEAR_PRESET"):
                        self.handle_clear_preset(client_sock, msg)
                    elif event == "REQ_PAYMENT_TRANSACTION_LOCK":
                        self.handle_transaction_lock(client_sock, msg)
                    elif event == "REQ_PAYMENT_CLEAR_SALE":
                        self.handle_clear_sale(client_sock, msg)
                    elif event == "REQ_PAYMENT_TRANSACTION_UNLOCK":
                        self.handle_transaction_unlock(client_sock, msg)
                    elif event.startswith("REQ_GET_FUSION_VERSION"):
                        resp = self.build_msg("RES_GET_FUSION_VERSION", "OS=Linux|HWV=Sim|BIN=Sim-1.0|MAC=00:00:00:00:00:01")
                        client_sock.sendall(resp.encode("ascii"))
                    elif event.startswith("REQ_FCRT"):
                        # Config requests: return minimal config
                        resp = self.build_msg("RES_" + event.replace("REQ_", ""),
                            "PUMPS=" + str(self.num_pumps) + "|P001HOSES=" + str(HOSES_PER_PUMP))
                        client_sock.sendall(resp.encode("ascii"))
                    else:
                        print(f"  ← UNHANDLED: {event}")

        except (ConnectionResetError, BrokenPipeError, OSError):
            pass
        finally:
            print(f"⚡ Client disconnected: {addr[0]}:{addr[1]}")
            if client_sock in self.clients:
                self.clients.remove(client_sock)
            client_sock.close()

    # ── Main Loop ─────────────────────────────────────────────

    def run(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", self.port))
        server.listen(5)
        print(f"""
╔══════════════════════════════════════════════╗
║   ⛽ FusionBridge SIMULATOR                  ║
║                                              ║
║   Listening on 0.0.0.0:{self.port:<5}                ║
║   Simulated pumps: {self.num_pumps:<3}                       ║
║   Hoses per pump:  {HOSES_PER_PUMP:<3}                       ║
║   Fueling duration: {FUELING_DURATION}s                    ║
║                                              ║
║   Connect your FusionBridge to this port     ║
║   to test without real hardware.             ║
╚══════════════════════════════════════════════╝
""")

        print("💡 Quick test: echo '00012|5|2||ECHO||||^' | nc localhost " + str(self.port))

        try:
            while self.running:
                client_sock, addr = server.accept()
                threading.Thread(
                    target=self.handle_client,
                    args=(client_sock, addr),
                    daemon=True
                ).start()
        except KeyboardInterrupt:
            print("\n🛑 Shutting down...")
        finally:
            self.running = False
            server.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FusionBridge Simulator")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"TCP port (default: {DEFAULT_PORT})")
    parser.add_argument("--pumps", type=int, default=DEFAULT_PUMPS, help=f"Number of pumps (default: {DEFAULT_PUMPS})")
    args = parser.parse_args()

    sim = FusionSimulator(port=args.port, num_pumps=args.pumps)
    sim.run()
