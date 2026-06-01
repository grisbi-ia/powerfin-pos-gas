# Contrato API — Entre los tres sistemas

## Principio

```
Powerfin POS  ──────────────────────►  PowerFin ERP
          login, clientes, precios,
          crear despacho, cobros,
          abrir/cerrar turno, cambio facturación

Powerfin POS  ──────────────────────►  FusionBridge
          autorizar despacho, cancelar,
          consultar política de impresión,
          solicitar impresión de ticket,
          payment lock/clear/unlock

FusionBridge ───────────────────►  Powerfin POS (SSE)
             eventos en tiempo real:
             PUMP_STATUS_CHANGE, NEW_TRANSACTION,
             DELIVERY_PROGRESS, SALE_CLEARED,
             TRANSACTION_LOCK, FUSION_STATUS

Powerfin POS ←── PowerFin ERP ──→  Powerfin POS
          reconciliación cada 3s vía GET /shifts/{id}/dispatches
          PowerFin es source of truth único
```

---

## 0. Arquitectura de sincronización multi-dispositivo

**Problema:** Múltiples tablets/celulares comparten los mismos surtidores.
Una venta autorizada en el dispositivo A debe reflejarse en el dispositivo B.

**Solución — 4 capas:**

| Capa | Mecanismo | Latencia |
|------|-----------|----------|
| 1 — SSE | `NEW_TRANSACTION` → `completeOrder()` en todos los clientes conectados | <1s |
| 2 — Polling | `GET /api/dispensers` cada 2s → actualiza estados de mangueras | 2s |
| 3 — Reconciliación | `GET /api/pos/shifts/{id}/dispatches` cada 3s → `pendingOrders.reconcile()` | 3s |
| 4 — Verificación bajo demanda | Al hacer clic en un lado: `pollDispensers()` + `reconcileWithPowerFin()` | ~300ms |

**Source of truth:** PowerFin ERP (`powerfin_state.json` en modo mock).
`localStorage` en el navegador es solo caché volátil. La reconciliación lo sobreescribe.

**Gate de seguridad:** Al tocar un lado del surtidor, el POS consulta el estado real
a FusionBridge y reconcilia con PowerFin antes de permitir navegar al flujo de venta.
Si el hose está ocupado o tiene una orden pendiente de cobro, se bloquea la navegación.

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
        "location_name": "NEOGAS"
    }
}
// Response 401 → credenciales inválidas
```

---

### GET /api/pos/config

Configuración inicial al arrancar la app. Incluye el layout físico de cada surtidor
(lados y mangueras) según la instalación real de la gasolinera, formas de pago, y
configuración de polling.

```json
// Response 200
{
  "location": {
    "location_id": 1,
    "name": "NEOGAS",
    "address": "Av. Principal 123, Cuenca"
  },
  "dispensers": [
    {
      "dispenser_id": 1,
      "fusion_pump_id": 1,
      "name": "Surtidor DIESEL",
      "printer_island": 1,
      "sides": {
        "A": [
          {
            "hose_id": 1,
            "fusion_pump_id": 1,
            "fusion_hose_id": 1,
            "grade_id": "DIESEL",
            "grade_name": "Diesel"
          }
        ],
        "B": [
          {
            "hose_id": 2,
            "fusion_pump_id": 2,
            "fusion_hose_id": 1,
            "grade_id": "DIESEL",
            "grade_name": "Diesel"
          }
        ]
      }
    }
  ],
  "grades": [
    { "grade_id": "DIESEL", "name": "Diesel", "unit": "GALONES" }
  ],
  "price_lists": [
    { "code": "STANDARD", "name": "Precio Normal" },
    { "code": "VIP", "name": "Cliente VIP" }
  ],
  "payment_methods": [
    { "code": "EFECTIVO", "name": "Efectivo", "requires_reference": false },
    { "code": "TARJETA", "name": "Tarjeta Crédito/Débito", "requires_reference": true },
    { "code": "QR", "name": "QR / Transferencia", "requires_reference": false },
    { "code": "CREDITO", "name": "Crédito", "requires_reference": false },
    { "code": "DEUNA", "name": "DeUna", "requires_reference": true },
    { "code": "JEPFAST", "name": "JepFast", "requires_reference": true },
    { "code": "SIPY", "name": "Sipy", "requires_reference": true }
  ],
  "polling": {
    "interval_ms": 2000,
    "enabled": true
  }
}
```

**Nota:** El mapeo `fusion_pump_id` + `fusion_hose_id` → `hose_id` → `side` → `grade_id`
viene de PowerFin. Cada gasolinera tiene su propio layout físico. El POS no asume nada.
Un mismo `dispenser_id` (armario) puede abarcar múltiples `fusion_pump_id` (lados).

---

### GET /api/pos/vehicles?plate={plate}

Búsqueda por placa del vehículo. Devuelve datos del vehículo + propietario para facturación.

```json
// Request: GET /api/pos/vehicles?plate=ABC1234

// Response 200 — vehículo y dueño encontrados
{
  "plate": "ABC1234",
  "vehicle_found": true,
  "incomplete_fields": [],
  "owner": {
    "customer_id": "0912345678",
    "id_type": "CED",
    "id_number": "0912345678",
    "name": "Juan Carlos Pérez",
    "email": "jperez@email.com",
    "phone": "0991234567"
  },
  "price_list": "STANDARD",
  "price_list_name": "Precio Normal"
}

// Response 200 — datos incompletos (falta email)
{
  "plate": "ABC1234",
  "vehicle_found": true,
  "incomplete_fields": ["email"],
  "owner": { ... },
  "price_list": "STANDARD",
  "price_list_name": "Precio Normal"
}

// Response 200 — vehículo no encontrado
{
  "plate": "ZZZ9999",
  "vehicle_found": false,
  "incomplete_fields": [],
  "owner": null,
  "price_list": "STANDARD",
  "price_list_name": "Precio Normal"
}
```

---

### GET /api/pos/customers/by-id?id_type={CED|RUC}&id_number={id}

Busca datos de un cliente por identificación (cédula o RUC).

```json
// Request: GET /api/pos/customers/by-id?id_type=CED&id_number=0912345678

// Response 200
{
  "customer_id": "0912345678",
  "id_type": "CED",
  "id_number": "0912345678",
  "name": "Juan Carlos Pérez",
  "email": "jperez@email.com",
  "phone": "0991234567",
  "price_list": "STANDARD",
  "price_list_name": "Precio Normal"
}

// Response 404 → no encontrado
```

---

### GET /api/pos/customers?q={query}

Búsqueda general por placa, cédula, RUC o nombre.

```json
// Response 200 — array
[{
  "customer_id": "0912345678",
  "id_type": "CED",
  "id_number": "0912345678",
  "name": "Juan Carlos Pérez",
  "email": "jperez@email.com",
  "phone": "0991234567",
  "price_list": "STANDARD",
  "price_list_name": "Precio Normal",
  "credit_active": false,
  "credit_balance": 0.0,
  "plates": ["ABC1234"]
}]
// Response 404 → no encontrado
```

---

### POST /api/pos/customers

Registra nuevo cliente y vehículo cuando `GET /api/pos/vehicles` devuelve `vehicle_found: false`.

```json
// Request
{
    "id_type":   "CED",
    "id_number": "0912345678",
    "name":      "Juan Pérez",
    "email":     "jperez@email.com",
    "plate":     "ABC1234"
}
// Response 201
{ "customer_id": "0912345678", "price_list": "STANDARD" }
```

---

### GET /api/pos/prices?customerId={id}&gradeId={grade}

```json
// Response 200
{
  "grade_id": "DIESEL",
  "grade_name": "Diesel",
  "unit_price": 3.103,
  "price_list": "STANDARD",
  "currency": "USD"
}
```

---

### POST /api/pos/shifts/open

Cada usuario abre su turno con su caja independiente. **No se asignan dispensadores:**
cualquier despachador puede vender en cualquier surtidor.

```json
// Request
{
    "opening_cash": 0.00,
    "notes": "",
    "user_name": "Carlos Sarmiento"
}
// Response 201
{
    "shift_id":        45,
    "user_id":         3,
    "user_name":       "Carlos Sarmiento",
    "opened_at":       "2026-06-01T09:00:00",
    "accounting_date": "2026-06-01",
    "status":          "OPEN",
    "opening_cash":    0.00
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
    "closed_at":      "2026-06-01T14:00:00",
    "opening_cash":   0.00,
    "closing_cash":   890.50,
    "expected_cash":  890.50,
    "difference":     0.00,
    "total_sales":    12,
    "total_volume":   487.5,
    "dispatch_count": 45
}
```

---

### POST /api/pos/dispatches

Crea el registro de la orden en PowerFin. **No toca el hardware.**
El hardware se activa en el paso siguiente con FusionBridge.

```json
// Request
{
    "dispenser_id":   1,
    "hose_id":        1,
    "side":           "A",
    "preset_type":    "MONEY",
    "preset_value":   "20.00",
    "unit_price":     3.103,
    "payment_method": "EFECTIVO",
    "customer_id":    "0912345678",
    "customer_name":  "Juan Carlos Pérez",
    "plate":          "ABC1234",
    "authorized_by":  "Carlos Sarmiento"
}
// Response 201
{
    "order_id": "OV-20260601-090000-001",
    "status":   "AUTHORIZED"
}
```

**Campos nuevos (v0.8.x):**
- `customer_name`: nombre del cliente para mostrar en otros dispositivos en reconciliación
- `authorized_by`: quién autorizó la venta (para validar botón Cancelar y auditoría)

---

### POST /api/pos/dispatches/{orderId}/complete

Recibe la señal de que el despacho terminó (desde el SSE `NEW_TRANSACTION`).
PowerFin actualiza el status a COMPLETED.
**IDEMPOTENTE:** si ya fue procesada, retorna ok sin duplicar.

```json
// Request
{
    "order_id":         "OV-20260601-090000-001",
    "fusion_sale_id":   "185",
    "volume":           "6.442",
    "amount":           "20.00",
    "unit_price":       "3.103",
    "payment_method":   "EFECTIVO",
    "completed_at":     "2026-06-01T09:05:00Z"
}
// Response 200
{ "status": "ok" }
```

---

### POST /api/pos/dispatches/{orderId}/cancel

```json
// Response 200
{ "status": "CANCELLED" }
```

---

### POST /api/pos/dispatches/{orderId}/collect

Registra el cobro de una orden completada. Marca status = COLLECTED.

```json
// Request
{
    "collected_by_shift_id": 45,
    "payment_method":        "EFECTIVO",
    "collected_amount":      20.00,
    "change_amount":         0.00,
    "reference_code":        null
}
// Response 200
{
    "order_id":               "OV-20260601-090000-001",
    "status":                 "COLLECTED",
    "collected_by_shift_id":  45,
    "collected_by_name":     "Carlos Sarmiento",
    "payment_method":         "EFECTIVO",
    "collected_amount":       20.00,
    "change_amount":          0.00
}
```

---

### POST /api/pos/dispatches/{orderId}/billing

Cambia el destinatario de facturación después del despacho pero antes del cobro.
La placa del vehículo **no cambia** (se capturó al inicio de la venta).

```json
// Request
{
    "customer_id":   "1790012345001",
    "customer_name": "Transportes Andinos S.A."
}
// Response 200
{ "status": "ok" }

// Cambiar a Consumidor Final
{
    "customer_name": "Consumidor Final"
}
```

---

### GET /api/pos/shifts/{shiftId}/dispatches

Usado para **reconciliación multi-dispositivo** cada 3 segundos.
Retorna todas las órdenes del turno (no solo las del usuario actual).

```json
// Response 200
[
  {
    "order_id":       "OV-20260601-090000-001",
    "dispenser_id":   1,
    "hose_id":        1,
    "side":           "A",
    "grade":          "DIESEL",
    "preset_type":    "MONEY",
    "preset_value":   "20.00",
    "unit_price":     3.103,
    "payment_method": "EFECTIVO",
    "customer_id":    "0912345678",
    "customer_name":  "Juan Carlos Pérez",
    "plate":          "ABC1234",
    "status":         "COMPLETED",
    "created_at":     "2026-06-01T09:00:00Z",
    "shift_id":       45,
    "authorized_by":  "Carlos Sarmiento",
    "final_amount":   20.00,
    "final_volume":   "6.442",
    "invoice_number": null
  }
]
```

**Estados y su interpretación en reconciliación:**

| Status PowerFin | Status local | Mostrado como |
|----------------|-------------|---------------|
| `PENDING` | — | (ignorado) |
| `AUTHORIZED` | `FUELLING` | "Despachando" |
| `COMPLETED` | `COMPLETED` | "Cobrar" |
| `COLLECTED` | (eliminado) | "Disponible" |
| `CANCELLED` | (eliminado) | "Disponible" |

---

### POST /api/pos/cash-movements

```json
// Request
{
  "shift_id":    45,
  "type":        "INCOME",
  "amount":      100.00,
  "observation": "Cambio inicial de caja"
}
// Response 201
{
  "movement_id":     1,
  "shift_id":        45,
  "type":            "INCOME",
  "amount":          100.00,
  "observation":     "Cambio inicial de caja",
  "created_at":      "2026-06-01T09:00:00Z",
  "running_balance": 100.00
}
```

### GET /api/pos/users/online

```
Response 200 → [{ user_id, name, role, shift_id, sales_count, total_amount }]
```

---

## 2. APIs de FusionBridge

### POST /api/dispatch/authorize

Envía el comando `REQ_PUMP_PRESET` al Fusion. Los campos `dispenser_id` y `hose_id`
deben ser los IDs del Fusion (`fusion_pump_id` y `fusion_hose_id`), no los IDs de PowerFin.

```json
// Request
{
    "order_id":        "OV-20260601-090000-001",
    "dispenser_id":    1,
    "hose_id":         1,
    "side":            "A",
    "preset_type":     "MONEY",
    "preset_value":    "20.00",
    "unit_price":      3.103,
    "customer_id":     "0912345678",
    "plate":           "ABC1234",
    "price_list":      "STANDARD",
    "payment_method":  "EFECTIVO"
}
// Response 200
{
    "status":   "PRESET_SENT",
    "order_id": "OV-20260601-090000-001"
}
// Response 503 → sin conexión al Synergy
```

---

### POST /api/dispatch/cancel

Envía `REQ_PUMP_CLEAR_PRESET` al Fusion. **Importante:** `dispenser_id` debe ser el
`fusion_pump_id` (ID del pump en el Synergy), no el `dispenser_id` de PowerFin (armario).
Para un surtidor con dos lados (Pump 1 + Pump 2), cancelar el lado B requiere `dispenser_id: 2`.

```json
// Request
{ "dispenser_id": 2 }
// Response 200 → { "status": "CANCELLED" }
// Response 503 → sin conexión al Synergy
```

---

### POST /api/dispatch/payment-lock

Bloquea una venta completada para procesar el pago.
Evita que el pump vuelva a IDLE automáticamente.

```json
// Request
{ "sale_id": "185", "lock_id": "185" }
// Response 200
{ "status": "LOCKED", "sale_id": "185", "lock_id": "185" }
```

---

### POST /api/dispatch/payment-clear

Libera la venta después de cobrar. El pump vuelve a IDLE.

```json
// Request
{ "sale_id": "185", "lock_id": "185", "method": "CASH" }
// Response 200
{ "status": "CLEARED", "sale_id": "185" }
```

---

### POST /api/dispatch/payment-unlock

Desbloquea sin limpiar (si el pago se pospone).

```json
// Request
{ "sale_id": "185", "lock_id": "185" }
// Response 200
{ "status": "UNLOCKED", "sale_id": "185" }
```

---

### GET /api/dispensers

Retorna el estado de todos los surtidores. Usado para polling (cada 2s) y
verificación bajo demanda.

```json
// Response 200
{
  "dispensers": [
    { "dispenserId": 1, "status": "IDLE", "subStatus": "",
      "hoseCount": 1, "presetAmount": 0, "grade": "DIESEL",
      "activeHose": 1, "connected": true },
    { "dispenserId": 2, "status": "AUTHORIZED", "subStatus": "MONEY_PRESET",
      "hoseCount": 1, "presetAmount": 20.00, "grade": "DIESEL",
      "activeHose": 1, "connected": true }
  ],
  "fusionConnected": true
}
```

**Nota:** `dispenserId` aquí es el número de pump del Fusion (1, 2, 3...).
El POS lo mapea a la estructura `DispenserState` con lados A/B usando la config de PowerFin.

---

### GET /api/dispensers/{id}

Retorna el estado de un solo pump.

```
GET /api/dispensers/2 → estado del Pump 2 (Lado B del DIESEL)
```

---

### GET /api/print/policy

```json
// Response 200
{ "policy": "ASK" }
// Valores: "ALWAYS" | "ASK" | "NEVER"
```

---

### POST /api/print

```json
// Request
{
    "type":         "FUEL_RECEIPT",
    "island":       1,
    "dispenser_id": 1,
    "fuel_data": {
        "dispenser_id":   1,
        "orderId":       "OV-20260601-090000-001",
        "volume":        "6.442",
        "amount":        "20.00",
        "unitPrice":     "3.103",
        "paymentMethod": "EFECTIVO",
        "grade":         "DIESEL"
    }
}
// Response 200
{ "status": "PRINTED" }
// Response 503
{ "error": "Printer not reachable" }
```

---

### GET /api/events (SSE)

Eventos emitidos en tiempo real. Todos los clientes conectados reciben
los mismos eventos simultáneamente.

```
GET /api/events
Accept: text/event-stream

// Eventos:

event: PUMP_STATUS_CHANGE
data: {"dispenserId":2,"status":"AUTHORIZED","subStatus":"MONEY_PRESET","presetAmount":20.00,"activeHose":1}

event: DELIVERY_PROGRESS
data: {"dispenserId":2,"volume":"3.500","amount":"10.86"}

event: NEW_TRANSACTION
data: {"saleId":"185","pumpNumber":2,"hoseId":1,"volume":"6.442","amount":"20.00","unitPrice":"3.103","payIn":"OV=OV-20260601-090000-001~CLI=0912345678~PLC=ABC1234~LISTA=STANDARD","orderId":"OV-20260601-090000-001"}

event: TRANSACTION_LOCK
data: {"saleId":"185","lockId":"185"}

event: SALE_CLEARED
data: {"saleId":"185"}

event: FUSION_STATUS
data: {"connected":true}

event: INIT
data: {"fusionConnected":true}
```

**Uso de NEW_TRANSACTION para multi-dispositivo:**
- `completeOrder(pumpNumber, hoseId, amount, volume)` en todos los clientes
- `completeDispatch(orderId, ...)` → PowerFin (fire-and-forget)
- Reconciliación en otros dispositivos usa el status COMPLETED de PowerFin

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

## 3. Flujo completo de una venta (secuencia)

```
DESPACHADOR    Powerfin POS          POWERFIN       FUSIONBRIDGE    FUSION/SYNERGY
    │              │                 │                │               │
    │ Toca lado A  │                 │                │               │
    ├─────────────►│ Verificación    │                │               │
    │              ├── pollDispensers()               │               │
    │              ├────────────────────────────────► GET /dispensers│
    │              │                 │                │◄── PUMP 1 IDLE│
    │              ├── reconcileWithPowerFin()        │               │
    │              ├────────────────► GET /dispatches │               │
    │              │◄───────────────────────────────────────────────┤
    │◄─────────────┤ ✅ Libre        │                │               │
    │              │                 │                │               │
    │ Busca cliente│                 │                │               │
    ├─────────────►│ GET /vehicles?plate=ABC1234      │               │
    │              ├────────────────►│                │               │
    │              │◄────────────────┤ Juan Pérez     │               │
    │◄─────────────┤                 │                │               │
    │              │                 │                │               │
    │ Config $20   │                 │                │               │
    ├─────────────►│ POST /dispatches│                │               │
    │              ├────────────────►│                │               │
    │              │◄────────────────┤ OV-001         │               │
    │              │                 │                │               │
    │              │ POST /dispatch/authorize          │               │
    │              ├────────────────────────────────► │               │
    │              │                 │                │ REQ_PRESET    │
    │              │                 │                ├──────────────►│
    │              │◄────────────────────────────── SSE PUMP_STATUS   │
    │◄─────────────┤ 🟡 Autorizado   │                │               │
    │              │                 │                │               │
    │  [cliente    │                 │                │               │
    │   despacha]  │                 │                │ EVT FUELLING  │
    │              │◄────────────────────────────── SSE DELIVERY_PROG │
    │◄─────────────┤ 🟠 Despachando  │                │               │
    │              │                 │                │               │
    │  [cuelga     │                 │                │               │
    │   pistola]   │                 │                │ EVT_NEW_TX    │
    │              │◄────────────────────────────── SSE NEW_TRANSACTION
    │              ├── completeOrder() + completeDispatch()           │
    │              ├────────────────►│ POST /complete │               │
    │              │                 │◄── COMPLETED ──┤               │
    │◄─────────────┤ 🟢 Cobrar $20  │                │               │
    │              │                 │                │               │
    │  [otro disp. │                 │                │               │
    │   reconcilia] │                 │                │               │
    │              ├────────────────►│ GET /dispatches│               │
    │              │◄────────────────┤ OV-001 COMPLETED               │
    │◄─────────────┤ 🟢 Cobrar $20  │                │               │
    │              │                 │                │               │
    │ Cobra        │                 │                │               │
    ├─────────────►│ POST /collect   │                │               │
    │              ├────────────────►│                │               │
    │              │◄────────────────┤ COLLECTED      │               │
    │              │                 │                │               │
    │ ¿Ticket?     │                 │                │               │
    ├─────────────►│ POST /print     │                │               │
    │              ├────────────────────────────────► │               │
    │              │                 │                ├── socket ────►│🖨
    │◄─────────────┤ ✅ Impreso      │                │               │
```

---

## 4. Flujo de cancelación manual

```
DESPACHADOR    Powerfin POS          POWERFIN       FUSIONBRIDGE    FUSION/SYNERGY
    │              │                 │                │               │
    │ Toca Cancelar│                 │                │               │
    ├─────────────►│ Modal confirma  │                │               │
    │◄─────────────┤ "¿Cancelar?"    │                │               │
    │              │                 │                │               │
    │ Confirma     │                 │                │               │
    ├─────────────►│ POST /cancel    │                │               │
    │              ├────────────────────────────────► │               │
    │              │                 │                │ CLEAR_PRESET  │
    │              │                 │                ├──────────────►│
    │              │                 │                │◄── IDLE ──────┤
    │              │                 │                │               │
    │              │ POST /cancel (orderId)           │               │
    │              ├────────────────►│                │               │
    │              │◄────────────────┤ CANCELLED      │               │
    │              │                 │                │               │
    │              │ removeOrder()   │                │               │
    │◄─────────────┤ 🟢 Disponible   │                │               │
```

**Reglas de seguridad:**
- Solo visible en estados AUTHORIZED / CALLING / STARTING (nunca FUELLING)
- Solo para el usuario que autorizó (`authorizedBy === currentUser.name`)
- Confirmación explícita obligatoria antes de ejecutar

---

## 5. Flujo de cambio de facturación (post-despacho)

```
DESPACHADOR    Powerfin POS          POWERFIN
    │              │                 │
    │ Toca Cambiar │                 │
    │ facturación  │                 │
    ├─────────────►│                 │
    │◄─────────────┤ Buscar por cédula/RUC
    │              │                 │
    │ Ingresa ID   │                 │
    ├─────────────►│ GET /customers  │
    │              ├────────────────►│
    │              │◄────────────────┤ Transportes Andinos
    │◄─────────────┤                 │
    │              │                 │
    │              │ POST /billing   │
    │              ├────────────────►│
    │              │◄────────────────┤ OK
    │◄─────────────┤ Cliente: Transportes Andinos S.A.
```

**Reglas:**
- La placa del vehículo NO cambia (viene del inicio de la venta)
- Solo cambia el destinatario de facturación (customer_name, customer_id)
- Disponible en modo cobro, antes de confirmar el pago

---

## 6. Autenticación entre sistemas

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
