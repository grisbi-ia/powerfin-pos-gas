# NEXT_SESSION.md — Powerfin POS

## Estado actual (2026-06-15)

### ✅ Fases completadas

| Fase | Tag | Descripción |
|------|-----|-------------|
| 1 | `v0.1.0` | FusionBridge TCP connection |
| 2 | — | APIs PowerFin documentadas (21 endpoints) |
| 3 | `v0.2.0` | Powerfin POS base — login, surtidores |
| 4 | `v0.3.0` | Flujo de venta completo |
| 5 | `v0.5.0` | Impresión térmica — ESC/POS, config multi-isla, templates editables |
| 6 | `v0.6.0` | Módulo de caja + refactor turnos + historial + usuarios en línea |
| 7 | `v0.7.0` | Validación hardware real — Wayne Synergy |
| 7.1 | `v0.7.1` | Bugfix: match IDs dispensador/manguera, flujo de cobro |
| 7.2 | `v0.8.0` | Sincronización multi-dispositivo + cancelación manual |
| 7.3 | `v0.8.1` | Fix customer_name cross-device |
| 7.4 | `v0.8.2` | Cambio de facturación post-despacho |
| 7.5 | `v0.8.3` | Eliminación Consumidor Final + offline detection + fixes |
| 8 | `v0.9.0` | POS Backend — FastAPI + PostgreSQL (26 tablas, 38 endpoints, 71 tests) |
| 9a | `v0.10.0` | Phase 9 — dispenser mapping, dispatch_details, multi-device sync, collect flow |
| 9b | `v0.11.0` | Phase 9 — price lists (VIP/EMPLOYEE), wizard reorder, emission points, schema simplification |
| 9c | `v0.12.0` | Phase 9 — cuadre de caja, transfers, lookup, billing preferencial, auto-save, validación, registro |
| 10a | `v0.13.0` | Phase 10 — Edge cases: cancel/stop mid-flow, phone-off resilience, completeDispatch en FusionBridge |
| 10b | `v0.14.0` | Phase 10 — Impresión: ticket completo, clave de acceso SRI, Font B, datos desde BD |
| 10c | `v0.15.0` | Phase 10 — Correcciones: subtotal/IVA, código aleatorio, espacio corte, saldos negativos, comprobantes caja |
| 10d | `v0.16.0` | Phase 10 — Key49: facturación electrónica SRI, fire-and-forget, polling, reintentos |
| 10e | `v0.16.1` | Phase 10 — Correcciones: zona horaria, clave Key49, IPs impresora, subtotal→total, reimpresión |
| 10f | `v0.17.0` | Phase 10 — Cierre de turno completo: cuadre, surplus/shortage, depósito, template impresión |
| 10g | `v0.18.0` | Phase 10 — RecoveryService: reconexión FusionBridge durante despacho activo |
| **11** | **v0.19.0** | **Phase 11 — UX, refactors, bugfixes: dashboard visual, IDs vs strings, SRI column, búsqueda por nombre, placas predefinidas** |

### 📊 Tests

```bash
FusionBridge — 67 tests    ./mvnw test    # BUILD SUCCESS
POS Backend  — 92 tests    pytest          # 92 passed
Powerfin POS — 0 errors    npm run check   # svelte-check OK
Total: 159 tests pasando
```

---

## Logros de la sesión (2026-06-15) — v0.19.0

### 62. Dashboard UX ✅

- **Lado 1A/1B**: etiquetas con `dispenserId` en vez de "A"/"B" genérico
- **Colores por lado**: Lado A → azul sutil (`bg-blue-50/20`), Lado B → ámbar (`bg-amber-50/20`)
- **Sin productos**: removidos los tags de `gradeName` en tarjetas de dispensadores
- **Sin "Vender →"**: removido texto decorativo redundante
- **Turno al inicio**: card de turno movida arriba de los dispensadores

### 63. Eliminación `dispensers.fusion_pump_id` ✅

Columna obsoleta y peligrosa como fallback. Solo `hoses.fusion_pump_id` es el real.
- DB: `ALTER TABLE dispensers DROP COLUMN fusion_pump_id`
- Backend: removido de modelo, schema, API
- Frontend: fallbacks `?? dispCfg?.fusion_pump_id ?? dispenserId` reemplazados por error visible

### 64. Bugfix — cuadre de caja con formas de pago no-efectivo ✅

`sales_cash` sumaba `Dispatch.total` de TODOS los COLLECTED sin filtrar por forma de pago.
Una venta con tarjeta aparecía como efectivo Y en non_cash_sales (duplicada).
Fix: filtra por `DispatchPayment.payment_method_id == 1` (efectivo estándar).

### 65. ID-based comparisons — inmune a cambios de código ✅

- `DispatchType`: `code == "CREDIT"` → `dispatch_type_id == 2`
- `PaymentMethod`: `_sri_payment_code(code)` → columna `sri_code` en BD
- Todas las comparaciones por código reemplazadas por IDs

### 66. Columna `payment_methods.sri_code` ✅

Nueva columna `VARCHAR(3)` con el código SRI de cada forma de pago.
Eliminado el diccionario hardcodeado de `key49_service.py`.
Agregar una nueva forma de pago = solo INSERT en BD, cero cambios de código.

### 67. Template impresión — movimientos de caja ✅

Agregado `TRANSACCION: {{movement_id}}` y `TURNO: {{shift_id}}` al template.
Backend `create_transfer` devuelve `sender_movement_id`.

### 68. Template impresión — factura de despacho ✅

Agregado `TURNO: {{shift_id}}  CAJERO: {{cashier_name}}` al template.
Backend `_build_receipt_data` + `get_shift_dispatches` incluyen `cashier_name` desde Shift→User.

### 69. Bugfix — TRANSFER_IN visual en historial ✅

Transferencia recibida se mostraba en rojo y negativo (como egreso).
Fix: agregado `TRANSFER_IN` a condiciones de color verde y signo `+`.
Agregado ícono 📥 y label "Transferencia recibida".

### 70. Placas predefinidas para venta sin vehículo ✅

- DB: `vehicles.allow_container_sale BOOLEAN DEFAULT false`
- API: `GET /api/pos/vehicles/predefined`
- UI: dropdown en `PlateInput.svelte` con placas autorizadas
- Al seleccionar una placa del dropdown, busca el vehículo normalmente

### 71. Búsqueda de cliente por nombre ✅

- Nuevo tab "Por Nombre" en paso `idLookup` del `SaleWizard`
- Usa `searchCustomers(query)` — solo BD local, sin APIs externas
- Muestra resultados como lista, al seleccionar va directo a billing

### Archivos modificados (esta sesión)

```
FusionBridge (2):
  ReceiptBuilder.java           ← +movementId, +shiftId en CashMovementData
                                  +shiftId, +cashierName en FuelReceiptData
  TemplateRenderer.java         ← +placeholders en cash y fuel templates

Backend (11):
  models/dispenser.py           ← -fusion_pump_id
  models/payment.py             ← +sri_code
  models/person.py              ← +allow_container_sale
  schemas/__init__.py           ← -fusion_pump_id, +sri_code, +sender_movement_id,
                                  +PredefinedVehicleResponse
  api/cash.py                   ← +sender_movement_id en create_transfer
  api/config.py                 ← +sri_code en PaymentMethodResponse
  api/dispatches.py             ← dispatch_type_id==2, +cashier_name/shiftId en receipt,
                                  +cashier_name en get_shift_dispatches
  api/shifts.py                 ← payment_method_id==1, +select_from
  api/vehicles.py               ← +GET /vehicles/predefined
  services/key49_service.py     ← eliminado PAYMENT_METHOD_SRI, usa sri_code de BD
  tests/conftest.py             ← -fusion_pump_id, +sri_code
  seed_data.py                  ← +sri_code

POS (13):
  types.ts                      ← -fusion_pump_id/fusionPumpId, +sri_code,
                                  +sender_movement_id, +cashier_name, +PredefinedVehicle
  bridge-client.ts              ← eliminados fallbacks dispenser-level
  bridge.mock.ts                ← -fusionPumpId, +sri_code mock
  powerfin.ts                   ← +getPredefinedVehicles
  powerfin.mock.ts              ← +getPredefinedVehicles, +sender_movement_id, +cashier_name
  DispenserCard.svelte          ← UX: labels, colors, sin productos, sin "Vender →"
  PlateInput.svelte             ← +dropdown placas predefinidas
  SaleWizard.svelte             ← +name search tab, +shiftId/cashierName en print
  +page.svelte                  ← error visible en cancel/stop, turno arriba
  history/+page.svelte          ← TRANSFER_IN fix, turno card, movement/shift en print,
                                  fuel receipt shiftId/cashierName
  cash/movement/+page.svelte    ← +movementId/shiftId en print
  cash/transfer/+page.svelte    ← +movementId/shiftId en print

Docs (2):
  DEPLOY.md                     ← NUEVO: guía rápida de deploy a producción
  INSTALL.md                    ← IPs actualizadas a 192.168.1.25
```

---

## Pendiente para próxima sesión

### 🟡 Backlog

```
☐ 1. Pago mixto (efectivo + tarjeta)
☐ 2. identity_service.py — mover URL y token a .env o system_config
☐ 3. Roles/permisos — implementar enforcement real:
   · ADMIN: todo
   · SUPERVISOR: ventas, reportes, cierre de turno, SRI retry
   · DISPATCHER: ventas, cierre de turno
```

**SQL para producción (esta sesión):**

```sql
ALTER TABLE dispensers DROP COLUMN IF EXISTS fusion_pump_id;
ALTER TABLE payment_methods ADD COLUMN IF NOT EXISTS sri_code VARCHAR(3) NOT NULL DEFAULT '20';
UPDATE payment_methods SET sri_code = '01' WHERE payment_method_id = 1;
UPDATE payment_methods SET sri_code = '19' WHERE payment_method_id = 4;
ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS allow_container_sale BOOLEAN NOT NULL DEFAULT false;
```

---

## Configuración actual del sitio

| Dato | Valor |
|------|-------|
| Estación | NEOGAS |
| Surtidores | 4: SURT-01 (SUPER+ECO), SURT-02 (ECO), SURT-03 (DIESEL1), SURT-04 (DIESEL2) |
| Puntos emisión | 001-001 a 001-004 (uno por dispensador) |
| Listas precio | STANDARD, VIP, EMPLOYEE, FAMILY |
| ATO | 180s |
| Moneda | DÓLARES ($) |
| Firmware | Rel-5.19.1 |
| Formas de pago | EFECTIVO, TARJETA, QR, CREDITO, DEUNA, JEPFAST, SIPY, YALOBOX |
| Cliente requerido | Sí (cédula o RUC obligatorio — sin Consumidor Final) |

## Base de datos

| Dato | Valor |
|------|-------|
| Host | localhost:5433 |
| Database | powerfin_gas |
| Test DB | powerfin_gas_test |
| User | postgres |
| Password | 1234abcd |

## Cómo arrancar todo

```bash
cd /home/pvalarezo/grisbiapps/powerfin_pos_gas
rm -rf pos/.svelte-kit pos/node_modules/.vite
./start.sh backend  # POS Backend :8080
./start.sh bridge   # FusionBridge :8090
./start.sh pos      # POS :5173
./start.sh stop     # Detener todo
./start.sh status   # Ver estado
```

Abrir: **`http://192.168.1.113:5173`** | Login: `carlos` / `1234` o `maria` / `1234`

---

## Deploy a producción

Ver `docs/DEPLOY.md` para la guía rápida.
Servidor: **192.168.1.25** · Usuario: **app** · OS: Debian 13.

---

## NOTAS

- El dispensador físico requiere **palanca manual** además de levantar la pistola.
- `SUBSCRIBE|ALL` necesario en firmware Rel-5.19.1.
- **NO usar `LID` ni `LM` en PRESET** — firmware Rel-5.19.1 crea locks permanentes.
- **No existe Consumidor Final** — toda venta requiere cliente con cédula o RUC.
- **ATO en 180 segundos** — los presets expiran después de 3 minutos sin levantar pistola.
- **`shift_id` cambia al cobrar**: AUTHORIZED/COMPLETED → shift autorizador; COLLECTED → shift cobrador.
- **Cuadre de caja**: `WHERE shift_id = mi_turno AND status = 'COLLECTED'`.
- **Auto-guardado**: buscar CED/RUC en API externo → se guarda en BD local automáticamente.
- **Facturación preferencial**: `vehicles.billing_person_id` — NULL = usar titular.
- **Validación**: CED = 10 dígitos, RUC = 13 dígitos.
- **Registro nueva persona**: nombre + email requeridos (facturación electrónica).
- **STOP durante FUELLING**: ⏹ → STOP → (2s) → CLEAR_STOP → NEW_TRANSACTION → cobro parcial.
  CLEAR_STOP automático en cada authorize limpia busy buffers residuales.
- **Celular apagado**: FusionBridge completa el dispatch directamente (no depende del POS).
  3 reintentos con 1s backoff. El POS también llama como doble seguro (idempotente).
- **Consola Wayne en oficina** (no en islas) → el POS es la ÚNICA forma de detener un despacho.
- **Modal STOP**: doble barrera anti-bolsillo (CANCELAR grande + Detener pequeño + timeout 8s).
- **Formas de pago**: filtrar por `payment_method_id`, no por `code`. ID 1 = efectivo estándar.
- **Tipos de despacho**: filtrar por `dispatch_type_id`, no por `code`. ID 2 = crédito estándar.
- **SRI codes**: vienen de `payment_methods.sri_code`, no hardcodeados en código.
- **Placas predefinidas**: vehículos con `allow_container_sale=true` aparecen en dropdown del PlateInput.

