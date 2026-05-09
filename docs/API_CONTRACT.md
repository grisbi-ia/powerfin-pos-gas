# Contrato API — Entre los tres sistemas

## Principio

```
Powerfin POS  ──────────────────────►  PowerFin ERP
          login, clientes, precios,
          crear despacho, cobros,
          abrir/cerrar turno

Powerfin POS  ──────────────────────►  FusionBridge
          autorizar despacho,
          consultar política de impresión,
          solicitar impresión de ticket

FusionBridge ───────────────────►  PowerFin ERP
             despacho completado

FusionBridge ───────────────────►  Powerfin POS (SSE)
             eventos en tiempo real
```

---

## 1. APIs de PowerFin ERP para el Powerfin POS

Todos los endpoints requieren: `Authorization: Bearer {jwt_token}`

### POST /api/pos/auth/login

```json
// Request
{ "username": "carlos", "pin": "1234" }

// Response 200
{
    "access_token": "eyJ...",
    "expires_in":   28800,
    "user": {
        "user_id":       3,
        "name":          "Carlos Sarmiento",
        "role":          "DISPATCHER",
        "location_id":   1,
        "location_name": "NEOPAUTE"
    }
}
// Response 401 → credenciales inválidas
```

---

### GET /api/pos/config

Configuración inicial al arrancar la app.

```json
// Response 200
{
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
      "hoses": [
        {
          "hose_id": 1,
          "fusion_hose_id": 1,
          "grade_id": "SUPER",
          "grade_name": "Gasolina Super"
        },
        {
          "hose_id": 2,
          "fusion_hose_id": 2,
          "grade_id": "SUPER",
          "grade_name": "Gasolina Super"
        }
      ]
    }
  ],
  "grades": [
    { "grade_id": "SUPER", "name": "Gasolina Super", "unit": "litros" }
  ],
  "price_lists": [
    { "code": "STANDARD", "name": "Precio Normal" },
    { "code": "VIP", "name": "Cliente VIP" }
  ]
}
```

---

### GET /api/pos/customers?q={query}

Búsqueda por placa, cédula, RUC o nombre.

```json
// Response 200
{
  "customer_id": "0912345678",
  "id_type": "CED",
  "id_number": "0912345678",
  "name": "Juan Carlos Pérez",
  "email": "jperez@email.com",
  "phone": "0991234567",
  "price_list": "VIP",
  "price_list_name": "Cliente VIP",
  "credit_active": false,
  "credit_balance": 0.0,
  "plates": ["ABC-1234"]
}
// Response 404 → no encontrado
```

---

### POST /api/pos/customers

```json
// Request
{
    "id_type":   "CED",
    "id_number": "0912345678",
    "name":      "Juan Pérez",
    "email":     "jperez@email.com",
    "phone":     "0991234567",
    "plate":     "ABC-1234"
}
// Response 201
{ "customer_id": "0912345678", "price_list": "STANDARD" }
```

---

### GET /api/pos/prices?customerId={id}&gradeId={grade}

```json
// Response 200
{
  "grade_id": "SUPER",
  "grade_name": "Gasolina Super",
  "unit_price": 1.1,
  "price_list": "VIP",
  "currency": "USD"
}
```

---

### POST /api/pos/shifts/open

```json
// Request
{
    "dispenser_ids": [1, 2],
    "opening_cash":  0.00,
    "notes":         ""
}
// Response 201
{
    "shift_id":        45,
    "user_id":         3,
    "user_name":       "Carlos Sarmiento",
    "opened_at":       "2024-04-21T06:03:00",
    "accounting_date": "2024-04-21",
    "status":          "OPEN",
    "opening_cash":    0.00,
    "dispenser_ids":   [1, 2]
}
```

---

### GET /api/pos/shifts/current

```
Response 200 → objeto Shift del usuario autenticado
Response 404 → no hay turno activo
```

---

### POST /api/pos/shifts/{shiftId}/close

```json
// Request
{ "closing_cash": 890.50, "notes": "" }

// Response 200
{
    "shift_id":       45,
    "closed_at":      "2024-04-21T14:08:00",
    "opening_cash":   0.00,
    "closing_cash":   890.50,
    "expected_cash":  890.50,
    "difference":     0.00,
    "total_sales":    47,
    "total_volume":   1234.567,
    "total_amount":   1481.48,
    "by_grade": [
        { "grade": "SUPER", "volume": 1234.567, "amount": 1481.48 }
    ],
    "by_payment": [
        { "method": "CASH",  "amount": 890.50 },
        { "method": "CARD",  "amount": 450.00 },
        { "method": "QR",    "amount": 140.98 }
    ]
}
```

---

### POST /api/pos/dispatches

Crea el registro de la orden en PowerFin. **No toca el hardware.**
El hardware se activa en el paso siguiente con FusionBridge.

```json
// Request
{
    "shift_id":       45,
    "dispenser_id":   1,
    "hose_id":        1,
    "grade_id":       "SUPER",
    "customer_id":    "0912345678",
    "plate":          "ABC-1234",
    "price_list":     "VIP",
    "preset_type":    "MONEY",
    "preset_value":   "50.00",
    "unit_price":     1.100,
    "payment_method": "CASH"
}
// Response 201
{
    "dispatch_order_id": "OV-20240421-143022-001",
    "status":            "CREATED"
}
```

---

### POST /api/pos/dispatches/{orderId}/complete

Recibe la señal de FusionBridge de que el despacho terminó.
PowerFin actualiza la venta y emite la factura SRI.
**IDEMPOTENTE:** si ya fue procesada, retorna los datos existentes sin duplicar.

```json
// Request
{
    "fusion_sale_id":   "185",
    "actual_volume":    45.455,
    "actual_amount":    50.00,
    "actual_unit_price": 1.100,
    "change_amount":    0.00,
    "completed_at":     "2024-04-21T14:32:47"
}
// Response 200
{
    "dispatch_order_id": "OV-20240421-143022-001",
    "status":            "INVOICED",
    "invoice_id":        "001-001-000001234",
    "invoice_auth":      "20240421143247...",
    "change_amount":     0.00
}
```

---

### POST /api/pos/dispatches/{orderId}/cancel

```json
// Response 200
{ "status": "CANCELLED" }
```

---

### GET /api/pos/shifts/{shiftId}/dispatches

Historial del turno.

```json
// Response 200
[
  {
    "dispatch_order_id": "OV-20240421-143022-001",
    "customer_name": "Juan Pérez",
    "plate": "ABC-1234",
    "grade": "SUPER",
    "actual_volume": 45.455,
    "actual_amount": 50.0,
    "payment_method": "CASH",
    "status": "INVOICED",
    "completed_at": "2024-04-21T14:32:47"
  }
]
```

---

### POST /api/pos/cash-movements

```json
// Request
{
  "shift_id": 45,
  "type": "IN",
  "amount": 100.0,
  "reason": "Cambio inicial de caja"
}
```

---

## 2. APIs de FusionBridge

### POST /api/dispatch/authorize

```json
// Request
{
    "order_id":        "OV-20240421-143022-001",
    "dispenser_id":    1,
    "hose_id":         1,
    "preset_type":     "MONEY",
    "preset_value":    "50.00",
    "unit_price":      1.100,
    "customer_id":     "0912345678",
    "plate":           "ABC-1234",
    "price_list":      "VIP",
    "payment_method":  "CASH"
}
// Response 200
{
    "status":   "PRESET_SENT",
    "order_id": "OV-20240421-143022-001"
}
// Response 409 → surtidor no disponible
// Response 503 → sin conexión al Synergy
```

---

### POST /api/dispatch/cancel

```json
// Request
{ "dispenser_id": 1, "order_id": "OV-20240421-143022-001" }
// Response 200 → { "status": "CANCELLED" }
```

---

### GET /api/dispensers

```json
// Response 200
{
  "connected": true,
  "dispensers": [
    {
      "dispenser_id": 1,
      "fusion_pump_id": 1,
      "status": "IDLE",
      "sub_status": "",
      "hose": null,
      "last_updated": "2024-04-21T14:30:00Z"
    }
  ]
}
```

---

### GET /api/print/policy

Retorna la política de impresión configurada en el servidor.

```json
// Response 200
{ "policy": "ASK" }
// Valores posibles: "ALWAYS" | "ASK" | "NEVER"
```

---

### POST /api/print

Solicitud de impresión de ticket.

```json
// Request
{
    "type":         "FUEL_RECEIPT",
    "dispenser_id": 1,
    "fuel_data": {
        "location_name":    "GASOLINERA XXX",
        "location_address": "Av. Principal 123, Cuenca",
        "location_ruc":     "0190012345001",
        "date":             "21/04/2024",
        "time":             "14:32:47",
        "dispenser_id":     1,
        "hose_id":          1,
        "grade":            "SUPER",
        "volume":           "45.455",
        "unit_price":       "1.100",
        "amount":           "50.00",
        "payment_method":   "EFECTIVO",
        "customer_name":    "Juan Pérez",
        "plate":            "ABC-1234",
        "invoice_id":       "001-001-000001234",
        "invoice_auth":     "20240421143247..."
    }
}

// Response 200
{ "status": "PRINTED", "printer_ip": "192.168.1.31" }

// Response 503
{ "error": "Printer not reachable: 192.168.1.31" }
```

---

### GET /api/events (SSE)

```
GET /api/events
Accept: text/event-stream

// Tipos de eventos emitidos:
data: {"type":"DISPENSER_STATUS","dispenserId":1,"status":"AUTHORIZED","subStatus":"MONEY_PRESET"}
data: {"type":"FUELING_PROGRESS","dispenserId":1,"volume":"23.150","amount":"25.47"}
data: {"type":"SALE_COMPLETED","dispenserId":1,"orderId":"OV-001","volume":"45.455","amount":"50.00"}
data: {"type":"FUSION_DISCONNECTED","connected":false}
data: {"type":"FUSION_CONNECTED","connected":true}
```

---

### GET /health

```json
{
  "status": "UP",
  "fusionConnected": true,
  "fusionIp": "192.168.1.20",
  "powerFinReachable": true,
  "pendingSales": 0,
  "printerPolicy": "ASK",
  "printers": {
    "island1": { "ip": "192.168.1.31", "reachable": true },
    "island2": { "ip": "192.168.1.32", "reachable": true }
  }
}
```

---

## 3. FusionBridge → PowerFin ERP

FusionBridge llama directamente a PowerFin usando API key de sistema.

```
Header: X-Bridge-Key: {api_key}
POST /api/pos/dispatches/{orderId}/complete
(mismo endpoint del Powerfin POS — idempotente)
```

---

## 4. Flujo completo de una venta (secuencia)

```
DESPACHADOR    Powerfin POS          POWERFIN       FUSIONBRIDGE    FUSION/SYNERGY
    │              │                 │                │               │
    │ Busca cliente│                 │                │               │
    ├─────────────►│ GET /customers  │                │               │
    │              ├────────────────►│                │               │
    │              │◄────────────────┤                │               │
    │◄─────────────┤ Juan Pérez VIP  │                │               │
    │              │                 │                │               │
    │ Configura    │                 │                │               │
    │ $50 Efectivo │                 │                │               │
    ├─────────────►│ POST /dispatches│                │               │
    │              ├────────────────►│                │               │
    │              │◄────────────────┤ OV-001         │               │
    │              │                 │                │               │
    │              │ POST /dispatch/authorize          │               │
    │              ├────────────────────────────────► │               │
    │              │                 │                │ REQ_PRESET    │
    │              │                 │                ├──────────────►│
    │              │                 │                │◄──────────────┤
    │              │                 │                │ ST=AUTHORIZED │
    │              │◄────────────────────────────── SSE DISPENSER_STATUS
    │◄─────────────┤ 🟡 Autorizado   │                │               │
    │              │                 │                │               │
    │  [cliente    │                 │                │               │
    │   despacha]  │                 │                │ EVT FUELLING  │
    │              │◄────────────────────────────── SSE FUELING_PROGRESS
    │◄─────────────┤ 🟠 Despachando  │                │               │
    │              │                 │                │               │
    │  [cuelga     │                 │                │               │
    │   pistola]   │                 │                │ EVT_NEW_TX    │
    │              │                 │                ├── Lock ──────►│
    │              │                 │                ├── ClearSale ─►│
    │              │                 │                ├── Unlock ────►│
    │              │                 │                │               │
    │              │                 │ POST /complete │               │
    │              │                 │◄───────────────┤               │
    │              │                 ├── factura SRI  │               │
    │              │◄────────────────────────────── SSE SALE_COMPLETED
    │◄─────────────┤ ✅ $50.00       │                │               │
    │              │   Factura 001.. │                │               │
    │              │                 │                │               │
    │ ¿Ticket?     │                 │                │               │
    ├─────────────►│ POST /print     │                │               │
    │              ├────────────────────────────────► │               │
    │              │                 │                ├──── socket ──►│🖨
    │◄─────────────┤ ✅ Impreso      │                │               │
```

---

## 5. Autenticación entre sistemas

```
Powerfin POS → PowerFin:
  Authorization: Bearer {jwt}   — token del despachador

FusionBridge → PowerFin:
  X-Bridge-Key: {api_key}       — clave de sistema (en variable de entorno)

Powerfin POS → FusionBridge:
  Sin autenticación              — solo accesible en LAN vía Nginx

FusionBridge → Impresoras:
  Sin autenticación              — socket TCP directo en LAN
```
