# Crédito a Privados — Diseño de flujo en el POS

> Documento de diseño. No implementado aún. Retomar lunes.
> Fecha: 2026-06-19 · v0.23.0

---

## Estado actual (lo que ya existe)

### Modelo de datos ✅

```
credit_contracts                 credit_contract_vehicles        credit_contract_products
├─ contract_id (PK)              ├─ contract_vehicle_id (PK)      ├─ contract_product_id (PK)
├─ contract_code (unique)        ├─ contract_id (FK)              ├─ contract_id (FK)
├─ person_id (FK)                ├─ vehicle_id (FK)               ├─ product_id (FK)
├─ contract_date                 ├─ date_from / date_to           └─ amount (Decimal)
├─ cupo (Decimal, monto total)   └─ is_active
├─ contract_type
│   ├─ INDEFINIDO    → rotativo: solo PENDING_INVOICE consume cupo
│   └─ NO_INDEFINIDO → plazo fijo: todos los no cancelados consumen
├─ sercop_type
│   └─ INFIMA_CUANTIA | ADJUDICACION | CONTRATACION_DIRECTA | NO_DEFINIDO
├─ notes
└─ is_active
```

### Lógica de negocio ✅ (`pos_backend/app/services/credit_service.py`)

| Función | Qué hace |
|---------|----------|
| `find_active_contract_for_vehicle(vehicle_id)` | JOIN con vehicles, filtra por fechas y active |
| `get_contract_product_amount(contract_id, product_id)` | Monto asignado a ese producto |
| `calcular_cupo_disponible(contract)` | INDEFINIDO: cupo − Σ(PENDING_INVOICE). NO_INDEFINIDO: cupo − Σ(todos no cancelados) |
| `validate_credit_dispatch(vehicle_id, product_id, amount)` | 3 checks: vehículo con contrato, producto asignado, monto ≤ cupo |

### Endpoints ✅

| Endpoint | Método | Descripción |
|----------|:------:|-------------|
| `/api/pos/credit-contracts` | GET | Lista contratos activos con vehículos, productos y cupo disponible |
| `/api/pos/credit-contracts/{id}` | GET | Detalle de un contrato |
| `/api/pos/credit-contracts/{id}/available` | GET | Solo cupo disponible en tiempo real |
| `/api/pos/credit-contracts` | POST | Crear contrato |
| `/api/pos/credit-contracts/{id}` | PUT | Editar cupo, tipo, sercop, notas, activo |
| `/api/pos/dispatches/{id}/invoice` | POST | Marcar despacho como INVOICED |

### Backend dispatch ✅

`POST /api/pos/dispatches` ya acepta `dispatch_type_code="CREDIT"` y `credit_contract_id`.
Busca contrato por placa automáticamente si no se pasa `credit_contract_id`.
Asigna `credit_status = "PENDING_INVOICE"`.

---

## Gaps identificados

| # | Gap | Ubicación |
|---|-----|-----------|
| 1 | **Sin selector de crédito en SaleWizard** — el despachador no puede elegir "Crédito" | `SaleWizard.svelte` |
| 2 | **`vehicle_id=0` hardcodeado** en validación de crédito (línea 143) | `dispatches.py` |
| 3 | **Collect bloquea `amount=0`** para todos los despachos, incluyendo crédito | `dispatches.py:collect_dispatch` |
| 4 | **`credit_contract_products.amount` no se descuenta** — solo se valida cupo total | `credit_service.py` |
| 5 | **Cupo disponible no se muestra** en el wizard de venta | `SaleWizard.svelte` |
| 6 | **Sin UI de facturación** — el endpoint `/invoice` existe pero no tiene pantalla | Admin / POS |
| 7 | **`sercop_type` no se usa en lógica** — preparado para sector público | `credit_service.py` |

---

## Flujo propuesto (Crédito a Privados)

```
Paso 1 — Placa (lookup normal)
  Despachador ingresa placa → Buscar → VehicleResponse
  + llamada extra: GET /credit-contracts/{id}/available
  → guardamos credit_contract_id y cupo_disponible

Paso 2 — Billing (modificado)
  Si el vehículo tiene contrato activo:
  ┌─────────────────────────────────────────┐
  │  💳 Crédito disponible: $4,250.00       │
  │  Forma de pago:                         │
  │  [ 🪙 Efectivo ]    [ 💳 Crédito ]     │
  └─────────────────────────────────────────┘
  Por defecto: Efectivo (flujo normal).

Paso 3 — Producto (igual, validación extra en backend)
  El backend valida que el producto esté en credit_contract_products.

Paso 4 — Monto (modificado)
  Si modo crédito:
  ┌─────────────────────────────────────────┐
  │  Cupo disponible: $4,250.00             │
  │  [$5] [$10] [$20] [$50] [$100]         │
  │  [__________] monto manual              │
  │  ⚠️ Bloquear si monto > cupo           │
  └─────────────────────────────────────────┘

Paso 5 — Autorizar (modificado)
  POST /dispatches con:
    dispatch_type_code = "CREDIT"
    credit_contract_id = <id del contrato>
    payment_method_id  = 3  (CREDITO)

Paso 6 — Fueling (sin cambios)

Paso 7 — Confirmar (modificado)
  Modo crédito:
  ┌─────────────────────────────────────────┐
  │  Despacho a crédito: $18.62             │
  │  Cliente: Juan Pérez                    │
  │  [Confirmar despacho a crédito]         │
  └─────────────────────────────────────────┘
  POST /collect con:
    payment_method_id = 3 (CREDITO)
    collected_amount  = 0
```

---

## Cambios por archivo (cuando se implemente)

### Backend

| Archivo | Cambio | Prioridad |
|---------|--------|:---------:|
| `dispatches.py:~143` | Arreglar `validate_credit_dispatch(db, 0, ...)` → pasar `vehicle_id` real | 🔴 |
| `dispatches.py:collect_dispatch` | Permitir `effective_amount=0` cuando `dispatch.credit_contract_id IS NOT NULL` | 🔴 |
| `credit_service.py` | Agregar validación: `amount ≤ product_amount` por producto (no solo cupo total) | 🟠 |
| `vehicles.py` (opcional) | Endpoint ligero: `GET /vehicles/{id}/credit` → `{credit_available, contract_id}` | 🟡 |

### Frontend

| Archivo | Cambio | Prioridad |
|---------|--------|:---------:|
| `SaleWizard.svelte` | Agregar estado `paymentMode: 'cash' \| 'credit'` | 🔴 |
| `SaleWizard.svelte` | Botones Efectivo / Crédito en paso `billing` | 🔴 |
| `SaleWizard.svelte` | Mostrar `cupo_disponible` en paso `presetValue` | 🔴 |
| `SaleWizard.svelte` | Validar `presetValue ≤ cupo` en frontend | 🟠 |
| `SaleWizard.svelte` | Modo crédito en paso cobro: sin input de efectivo, solo confirmación | 🔴 |
| `powerfin.ts` | `createDispatch` → agregar `dispatch_type_code` y `credit_contract_id` | 🔴 |
| `powerfin.ts` | Nueva función: `getCreditAvailable(vehicleId)` → llama al endpoint existente | 🟡 |
| `types.ts` | `CreateDispatchRequest` → agregar campos opcionales | 🔴 |

---

## Lo que NO cambia

- Wayne / FusionBridge — despacha combustible igual
- Impresión de ticket — solo cambia "Efectivo" → "Crédito" en el método de pago
- Facturación SRI (Key49) — fire-and-forget, mismo flujo
- Cierre de turno — despachos a crédito no son efectivo, no afectan cuadre de caja
- `POST /{order_id}/invoice` — ya existe, se usa desde el admin para facturar

---

## Pendiente para fase posterior (Crédito Sector Público)

- Control de consumo mensual por producto
- Validaciones según `sercop_type`
- Reportes de consumo por período
- Límites por partida presupuestaria
