#!/usr/bin/env python3
"""
PowerFin Server Simulator — REST API mock for multi-device testing.

Exposes the same /api/pos/* endpoints that PowerFin ERP will provide.
Persists state to a JSON file so it survives server restarts and is shared
across all connected POS devices (tablets, phones).

Usage:
    python3 tools/powerfin_server.py [--port PORT] [--host HOST]

Endpoints:
    POST   /api/pos/auth/login
    GET    /api/pos/config
    GET    /api/pos/customers?q=
    POST   /api/pos/customers
    GET    /api/pos/prices?customerId=&gradeId=
    POST   /api/pos/shifts/open
    GET    /api/pos/shifts/current
    POST   /api/pos/shifts/{id}/close
    POST   /api/pos/dispatches
    GET    /api/pos/shifts/{id}/dispatches
    POST   /api/pos/dispatches/{id}/complete
    POST   /api/pos/dispatches/{id}/collect
    POST   /api/pos/dispatches/{id}/cancel
"""

import json
import time
import uuid
import argparse
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone


# ═══════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(SCRIPT_DIR, "powerfin_state.json")
DEFAULT_PORT = 8080
DEFAULT_HOST = "0.0.0.0"


# ═══════════════════════════════════════════════════════════════
# Mock data (same as pos/src/lib/api/powerfin.mock.ts)
# ═══════════════════════════════════════════════════════════════

MOCK_USERS = {
    "carlos": {"pin": "1234", "user_id": 3, "name": "Carlos Sarmiento", "role": "DISPATCHER"},
    "maria":  {"pin": "1234", "user_id": 4, "name": "María Fernanda López", "role": "DISPATCHER"},
    "pedro":  {"pin": "1234", "user_id": 5, "name": "Pedro Ramírez", "role": "DISPATCHER"},
}

MOCK_CONFIG = {
    "location": {
        "location_id": 1,
        "name": "NEOPAUTE",
        "address": "Av. Principal 123, Cuenca"
    },
    "dispensers": [
        {
            "dispenser_id": 1,
            "fusion_pump_id": 1,
            "name": "Surtidor 1",
            "sides": {
                "A": [
                    {"hose_id": 1, "fusion_hose_id": 1, "grade_id": "SUPER", "grade_name": "Gasolina Super"},
                    {"hose_id": 2, "fusion_hose_id": 2, "grade_id": "EXTRA", "grade_name": "Gasolina Extra"},
                    {"hose_id": 3, "fusion_hose_id": 3, "grade_id": "DIESEL", "grade_name": "Diesel"},
                    {"hose_id": 4, "fusion_hose_id": 4, "grade_id": "SUPER", "grade_name": "Gasolina Super"}
                ],
                "B": [
                    {"hose_id": 5, "fusion_hose_id": 5, "grade_id": "SUPER", "grade_name": "Gasolina Super"},
                    {"hose_id": 6, "fusion_hose_id": 6, "grade_id": "EXTRA", "grade_name": "Gasolina Extra"},
                    {"hose_id": 7, "fusion_hose_id": 7, "grade_id": "DIESEL", "grade_name": "Diesel"},
                    {"hose_id": 8, "fusion_hose_id": 8, "grade_id": "SUPER", "grade_name": "Gasolina Super"}
                ]
            }
        },
        {
            "dispenser_id": 2,
            "fusion_pump_id": 2,
            "name": "Surtidor 2",
            "sides": {
                "A": [
                    {"hose_id": 9, "fusion_hose_id": 1, "grade_id": "SUPER", "grade_name": "Gasolina Super"},
                    {"hose_id": 10, "fusion_hose_id": 2, "grade_id": "EXTRA", "grade_name": "Gasolina Extra"},
                    {"hose_id": 11, "fusion_hose_id": 3, "grade_id": "DIESEL", "grade_name": "Diesel"},
                    {"hose_id": 12, "fusion_hose_id": 4, "grade_id": "SUPER", "grade_name": "Gasolina Super"}
                ],
                "B": [
                    {"hose_id": 13, "fusion_hose_id": 5, "grade_id": "SUPER", "grade_name": "Gasolina Super"},
                    {"hose_id": 14, "fusion_hose_id": 6, "grade_id": "EXTRA", "grade_name": "Gasolina Extra"},
                    {"hose_id": 15, "fusion_hose_id": 7, "grade_id": "DIESEL", "grade_name": "Diesel"},
                    {"hose_id": 16, "fusion_hose_id": 8, "grade_id": "SUPER", "grade_name": "Gasolina Super"}
                ]
            }
        },
        {
            "dispenser_id": 3,
            "fusion_pump_id": 3,
            "name": "Surtidor 3",
            "sides": {
                "A": [
                    {"hose_id": 17, "fusion_hose_id": 1, "grade_id": "SUPER", "grade_name": "Gasolina Super"},
                    {"hose_id": 18, "fusion_hose_id": 2, "grade_id": "DIESEL", "grade_name": "Diesel"}
                ],
                "B": [
                    {"hose_id": 19, "fusion_hose_id": 3, "grade_id": "EXTRA", "grade_name": "Gasolina Extra"},
                    {"hose_id": 20, "fusion_hose_id": 4, "grade_id": "SUPER", "grade_name": "Gasolina Super"}
                ]
            }
        },
        {
            "dispenser_id": 4,
            "fusion_pump_id": 4,
            "name": "Surtidor 4",
            "sides": {
                "A": [
                    {"hose_id": 21, "fusion_hose_id": 1, "grade_id": "SUPER", "grade_name": "Gasolina Super"},
                    {"hose_id": 22, "fusion_hose_id": 2, "grade_id": "DIESEL", "grade_name": "Diesel"}
                ],
                "B": [
                    {"hose_id": 23, "fusion_hose_id": 3, "grade_id": "EXTRA", "grade_name": "Gasolina Extra"},
                    {"hose_id": 24, "fusion_hose_id": 4, "grade_id": "SUPER", "grade_name": "Gasolina Super"}
                ]
            }
        }
    ],
    "grades": [
        {"grade_id": "SUPER", "name": "Gasolina Super", "unit": "litros"},
        {"grade_id": "EXTRA", "name": "Gasolina Extra", "unit": "litros"},
        {"grade_id": "DIESEL", "name": "Diesel", "unit": "litros"}
    ],
    "price_lists": [
        {"code": "STANDARD", "name": "Precio Normal"},
        {"code": "VIP", "name": "Cliente VIP"}
    ],
    "payment_methods": [
        {"code": "EFECTIVO", "name": "Efectivo", "requires_reference": False},
        {"code": "TARJETA", "name": "Tarjeta Crédito/Débito", "requires_reference": True},
        {"code": "QR", "name": "QR / Transferencia", "requires_reference": False},
        {"code": "CREDITO", "name": "Crédito", "requires_reference": False},
        {"code": "DEUNA", "name": "DeUna", "requires_reference": True},
        {"code": "JEPFAST", "name": "JepFast", "requires_reference": True},
        {"code": "SIPY", "name": "Sipy", "requires_reference": True}
    ],
    "polling": {
        "interval_ms": 2000,
        "enabled": True
    }
}

MOCK_CUSTOMERS = [
    {
        "customer_id": "0912345678", "id_type": "CED", "id_number": "0912345678",
        "name": "Juan Carlos Pérez", "email": "jperez@email.com", "phone": "0991234567",
        "price_list": "VIP", "price_list_name": "Cliente VIP",
        "credit_active": False, "credit_balance": 0,
        "plates": ["ABC1234"]
    },
    {
        "customer_id": "1790012345001", "id_type": "RUC", "id_number": "1790012345001",
        "name": "Transportes Andinos S.A.", "email": "trans@andinos.com", "phone": "022345678",
        "price_list": "STANDARD", "price_list_name": "Precio Normal",
        "credit_active": True, "credit_balance": 500,
        "plates": ["XYZ5678", "XYZ5679"]
    },
    {
        "customer_id": "1001234567001", "id_type": "RUC", "id_number": "1001234567001",
        "name": "María Fernanda López", "email": "mflopez@email.com", "phone": "0987654321",
        "price_list": "STANDARD", "price_list_name": "Precio Normal",
        "credit_active": False, "credit_balance": 0,
        "plates": []
    }
]

MOCK_VEHICLES = {
    "ABC1234": {
        "plate": "ABC1234", "vehicle_found": True, "incomplete_fields": [],
        "owner": {
            "customer_id": "0912345678", "id_type": "CED", "id_number": "0912345678",
            "name": "Juan Carlos Pérez", "email": "jperez@email.com", "phone": "0991234567"
        },
        "price_list": "VIP", "price_list_name": "Cliente VIP"
    },
    "XYZ5678": {
        "plate": "XYZ5678", "vehicle_found": True, "incomplete_fields": ["email"],
        "owner": {
            "customer_id": "1790012345001", "id_type": "RUC", "id_number": "1790012345001",
            "name": "Transportes Andinos S.A.", "email": None, "phone": "022345678"
        },
        "price_list": "STANDARD", "price_list_name": "Precio Normal"
    }
}

PRICES = {
    "VIP": 1.100,
    "STANDARD": 1.500
}


# ═══════════════════════════════════════════════════════════════
# State management (persisted to JSON file)
# ═══════════════════════════════════════════════════════════════

def load_state():
    """Load server state from JSON file. Returns fresh state if file missing."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"shifts": [], "orders": [], "order_seq": 0}


def save_state(state):
    """Persist server state to JSON file atomically."""
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)


def find_shift(state, shift_id):
    return next((s for s in state["shifts"] if s["shift_id"] == shift_id), None)


# ═══════════════════════════════════════════════════════════════
# HTTP Request Handler
# ═══════════════════════════════════════════════════════════════

class PowerFinHandler(BaseHTTPRequestHandler):

    state = None          # set by server after load_state()
    server_started = None

    def log_message(self, format, *args):
        print(f"  [{datetime.now().strftime('%H:%M:%S')}] {args[0]}")

    # ── CORS & helpers ──────────────────────────────────────────

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _json_reply(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _error(self, msg, status=400):
        self._json_reply({"error": msg}, status)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        content_type = self.headers.get("Content-Type", "")
        if "application/json" in content_type:
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError):
                return {}
        return {}

    def _path_parts(self):
        parsed = urlparse(self.path)
        return parsed.path.rstrip("/").split("/"), parse_qs(parsed.query)

    # ── Routing ──────────────────────────────────────────────────

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        parts, qs = self._path_parts()
        # /api/pos/config
        if parts == ["", "api", "pos", "config"]:
            return self._json_reply(MOCK_CONFIG)

        # /api/pos/vehicles?plate=ABC1234
        if parts == ["", "api", "pos", "vehicles"]:
            plate = qs.get("plate", [""])[0].upper().replace(" ", "").replace("-", "")
            vehicle = MOCK_VEHICLES.get(plate)
            if vehicle:
                return self._json_reply(vehicle)
            return self._json_reply({
                "plate": plate, "vehicle_found": False, "incomplete_fields": [],
                "owner": None, "price_list": "STANDARD", "price_list_name": "Precio Normal"
            })

        # /api/pos/customers?q=...
        if parts == ["", "api", "pos", "customers"]:
            query = qs.get("q", [""])[0].lower()
            results = [c for c in MOCK_CUSTOMERS if
                       query in c["name"].lower() or
                       query in c["id_number"] or
                       any(query in p.lower() for p in c["plates"])]
            return self._json_reply(results)

        # /api/pos/prices?customerId=&gradeId=
        if parts == ["", "api", "pos", "prices"]:
            customer_id = qs.get("customerId", [""])[0]
            grade_id = qs.get("gradeId", ["SUPER"])[0]
            grade_name = next((g["name"] for g in MOCK_CONFIG["grades"] if g["grade_id"] == grade_id), grade_id)
            customer = next((c for c in MOCK_CUSTOMERS if c["customer_id"] == customer_id), None)
            price_list = customer["price_list"] if customer else "STANDARD"
            price = PRICES.get(price_list, 1.500)
            return self._json_reply({
                "grade_id": grade_id, "grade_name": grade_name,
                "unit_price": price, "price_list": price_list, "currency": "USD"
            })

        # /api/pos/shifts/current
        if parts == ["", "api", "pos", "shifts", "current"]:
            open_shift = next((s for s in self.state["shifts"] if s["status"] == "OPEN"), None)
            return self._json_reply(open_shift)

        # /api/pos/shifts/{id}/dispatches
        if len(parts) == 6 and parts[0:4] == ["", "api", "pos", "shifts"] and parts[5] == "dispatches":
            try:
                shift_id = int(parts[4])
            except ValueError:
                return self._error("Invalid shift_id", 400)
            orders = [o for o in self.state["orders"] if o["shift_id"] == shift_id]
            return self._json_reply(orders)

        return self._error("Not found", 404)

    def do_POST(self):
        parts, qs = self._path_parts()
        body = self._read_body()

        # ── Auth ──────────────────────────────────────────────────
        # POST /api/pos/auth/login
        if parts == ["", "api", "pos", "auth", "login"]:
            username = body.get("username", "").lower()
            pin = body.get("pin", "")
            user = MOCK_USERS.get(username)
            if user and user["pin"] == pin:
                token = str(uuid.uuid4())
                return self._json_reply({
                    "access_token": token,
                    "expires_in": 28800,
                    "user": {
                        "user_id": user["user_id"],
                        "name": user["name"],
                        "role": user["role"],
                        "location_id": 1,
                        "location_name": "NEOPAUTE"
                    }
                })
            return self._error("Credenciales inválidas", 401)

        # ── Customers ─────────────────────────────────────────────
        # POST /api/pos/customers
        if parts == ["", "api", "pos", "customers"]:
            new_cust = {
                "customer_id": body["id_number"],
                "id_type": body["id_type"],
                "id_number": body["id_number"],
                "name": body["name"],
                "email": body.get("email"),
                "phone": None,
                "price_list": "STANDARD",
                "price_list_name": "Precio Normal",
                "credit_active": False,
                "credit_balance": 0,
                "plates": [body.get("plate", "")]
            }
            MOCK_CUSTOMERS.append(new_cust)
            plate = body.get("plate", "").upper().replace(" ", "")
            if plate:
                MOCK_VEHICLES[plate] = {
                    "plate": plate, "vehicle_found": True, "incomplete_fields": [],
                    "owner": {
                        "customer_id": new_cust["customer_id"], "id_type": new_cust["id_type"],
                        "id_number": new_cust["id_number"], "name": new_cust["name"],
                        "email": new_cust["email"], "phone": new_cust["phone"]
                    },
                    "price_list": "STANDARD", "price_list_name": "Precio Normal"
                }
            return self._json_reply({"customer_id": body["id_number"], "price_list": "STANDARD"}, 201)

        # ── Vehicles ──────────────────────────────────────────────
        # POST /api/pos/vehicles/lookup  (Plate search)
        if parts == ["", "api", "pos", "vehicles", "lookup"]:
            plate = body.get("plate", "").upper().replace(" ", "").replace("-", "")
            vehicle = MOCK_VEHICLES.get(plate)
            if vehicle:
                return self._json_reply(vehicle)
            return self._json_reply({
                "plate": plate, "vehicle_found": False, "incomplete_fields": [],
                "owner": None, "price_list": "STANDARD", "price_list_name": "Precio Normal"
            })

        # ── Shifts ────────────────────────────────────────────────
        # POST /api/pos/shifts/open
        if parts == ["", "api", "pos", "shifts", "open"]:
            # Close any existing open shift first
            for s in self.state["shifts"]:
                if s["status"] == "OPEN":
                    s["status"] = "CLOSED"
            user = MOCK_USERS["carlos"]  # default; in real life from token
            shift_id = max([s["shift_id"] for s in self.state["shifts"]], default=44) + 1
            shift = {
                "shift_id": shift_id,
                "user_id": body.get("user_id", user["user_id"]),
                "user_name": body.get("user_name", user["name"]),
                "opened_at": datetime.now(timezone.utc).isoformat(),
                "accounting_date": datetime.now().strftime("%Y-%m-%d"),
                "status": "OPEN",
                "opening_cash": body.get("opening_cash", 0)
            }
            self.state["shifts"].append(shift)
            save_state(self.state)
            return self._json_reply(shift, 201)

        # POST /api/pos/shifts/{id}/close
        if len(parts) == 6 and parts[0:4] == ["", "api", "pos", "shifts"] and parts[5] == "close":
            try:
                shift_id = int(parts[4])
            except ValueError:
                return self._error("Invalid shift_id", 400)
            shift = find_shift(self.state, shift_id)
            if not shift:
                return self._error("Turno no encontrado", 404)
            shift["status"] = "CLOSED"
            shift["closed_at"] = datetime.now(timezone.utc).isoformat()
            shift["closing_cash"] = body.get("closing_cash", 0)
            save_state(self.state)
            return self._json_reply({
                "shift_id": shift_id,
                "closed_at": shift["closed_at"],
                "opening_cash": shift["opening_cash"],
                "closing_cash": body.get("closing_cash", 0),
                "expected_cash": body.get("expected_cash", body.get("closing_cash", 0)),
                "difference": body.get("difference", 0),
                "total_sales": 0,
                "total_volume": 0,
                "dispatch_count": 0
            })

        # ── Dispatches ────────────────────────────────────────────
        # POST /api/pos/dispatches  (Create order)
        if parts == ["", "api", "pos", "dispatches"]:
            self.state["order_seq"] += 1
            seq = str(self.state["order_seq"]).zfill(3)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            order_id = f"OV-{timestamp}-{seq}"

            # Find active shift
            active_shift = next((s for s in self.state["shifts"] if s["status"] == "OPEN"), None)
            shift_id = active_shift["shift_id"] if active_shift else 0
            authorized_by = active_shift["user_name"] if active_shift else ""

            order = {
                "order_id": order_id,
                "dispenser_id": body.get("dispenser_id", 1),
                "hose_id": body.get("hose_id", 1),
                "side": body.get("side", "A"),
                "grade": "SUPER",
                "preset_type": body.get("preset_type", "MONEY"),
                "preset_value": body.get("preset_value", "0"),
                "unit_price": body.get("unit_price", 1.500),
                "payment_method": body.get("payment_method", "EFECTIVO"),
                "customer_id": body.get("customer_id"),
                "customer_name": body.get("customer_name"),
                "plate": body.get("plate"),
                "status": "AUTHORIZED",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "shift_id": shift_id,
                "authorized_by": authorized_by,
                "final_amount": None,
                "final_volume": None,
                "invoice_number": None
            }
            self.state["orders"].append(order)
            save_state(self.state)
            return self._json_reply({"order_id": order_id, "status": "PENDING"}, 201)

        # POST /api/pos/dispatches/{id}/complete
        if len(parts) == 6 and parts[0:4] == ["", "api", "pos", "dispatches"] and parts[5] == "complete":
            order_id = parts[4]
            order = next((o for o in self.state["orders"] if o["order_id"] == order_id), None)
            if order:
                order["status"] = "COMPLETED"
                order["final_amount"] = float(body.get("amount", 0))
                order["final_volume"] = str(body.get("volume", "0"))
                order["invoice_number"] = body.get("invoice_number")
                save_state(self.state)
            return self._json_reply({"status": "ok"})

        # POST /api/pos/dispatches/{id}/collect
        if len(parts) == 6 and parts[0:4] == ["", "api", "pos", "dispatches"] and parts[5] == "collect":
            order_id = parts[4]
            order = next((o for o in self.state["orders"] if o["order_id"] == order_id), None)
            if not order:
                return self._error("Orden no encontrada", 404)
            order["status"] = "COLLECTED"
            collected_shift = body.get("collected_by_shift_id", 0)
            if collected_shift:
                order["shift_id"] = collected_shift
            save_state(self.state)
            return self._json_reply({
                "order_id": order_id,
                "status": "COLLECTED",
                "collected_by_shift_id": collected_shift,
                "collected_by_name": order.get("authorized_by", ""),
                "payment_method": body.get("payment_method", "EFECTIVO"),
                "collected_amount": body.get("collected_amount", 0),
                "change_amount": body.get("change_amount", 0)
            })

        # POST /api/pos/dispatches/{id}/cancel
        if len(parts) == 6 and parts[0:4] == ["", "api", "pos", "dispatches"] and parts[5] == "cancel":
            order_id = parts[4]
            order = next((o for o in self.state["orders"] if o["order_id"] == order_id), None)
            if order:
                order["status"] = "CANCELLED"
                save_state(self.state)
            return self._json_reply({"status": "ok"})

        return self._error("Not found", 404)


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="PowerFin Server Simulator")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"HTTP port (default: {DEFAULT_PORT})")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Bind address (default: {DEFAULT_HOST})")
    args = parser.parse_args()

    # Load state from disk
    state = load_state()
    print(f"📂 State loaded: {len(state['orders'])} orders, {len(state['shifts'])} shifts")

    PowerFinHandler.state = state
    PowerFinHandler.server_started = datetime.now()

    server = HTTPServer((args.host, args.port), PowerFinHandler)
    print(f"\n🔌 PowerFin Server Simulator")
    print(f"   Listening on http://{args.host}:{args.port}")
    print(f"   State file: {STATE_FILE}")
    print(f"   Users: carlos/1234, maria/1234, pedro/1234")
    print(f"   Endpoints:")
    print(f"     GET  /api/pos/config")
    print(f"     GET  /api/pos/customers?q=")
    print(f"     GET  /api/pos/prices?customerId=&gradeId=")
    print(f"     GET  /api/pos/shifts/current")
    print(f"     GET  /api/pos/shifts/{{id}}/dispatches")
    print(f"     POST /api/pos/auth/login")
    print(f"     POST /api/pos/customers")
    print(f"     POST /api/pos/shifts/open")
    print(f"     POST /api/pos/shifts/{{id}}/close")
    print(f"     POST /api/pos/dispatches")
    print(f"     POST /api/pos/dispatches/{{id}}/complete")
    print(f"     POST /api/pos/dispatches/{{id}}/collect")
    print(f"     POST /api/pos/dispatches/{{id}}/cancel")
    print(f"     POST /api/pos/vehicles/lookup")
    print(f"\n   Press Ctrl+C to stop\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹  Shutting down...")
        save_state(state)
        server.shutdown()


if __name__ == "__main__":
    main()
