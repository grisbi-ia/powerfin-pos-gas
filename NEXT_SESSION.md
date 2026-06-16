# NEXT_SESSION.md — Powerfin POS

## Estado actual (2026-06-16)

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
| 11b | `v0.19.1` | Bugfix: recovery despacho AUTHORIZED cuando PAY_IN no eco-devuelto (phone-off) |
| 11c | `v0.19.2` | Bugfix: doble autorización mismo dispensador → 409 Conflict en create_dispatch |
| 11d | `v0.19.3` | Bugfix: preset_value persistido en BD + bloqueo cobro $0.00 (cross-page race condition) |

### 📊 Tests

```bash
FusionBridge — 67 tests    /opt/maven/bin/mvn test    # BUILD SUCCESS
POS Backend  — 93 tests    pytest                     # 93 passed
Powerfin POS — 0 errors    npm run check              # svelte-check OK
Total: 160 tests pasando
```

---

## Logros de la sesión (2026-06-16) — v0.19.1, v0.19.2, v0.19.3

### 72. Recovery despacho AUTHORIZED cuando PAY_IN no eco-devuelto ✅ — v0.19.1

**Problema**: Celular apagado durante despacho → Wayne envía NEW_TRANSACTION pero
si PAY_IN no trae OV, `completeDispatchOnBackend` nunca se llama → dispatch
queda AUTHORIZED para siempre (irrecuperable).

**Solución — defensa en 3 capas**:
- **Backend**: Nuevo endpoint `POST /api/pos/dispatches/complete-by-pump` (sin auth).
  Encuentra dispatch AUTHORIZED por `fusion_pump_id` + `fusion_hose_number`.
- **FusionBridge**: `handleNewTransaction()` con fallback: si `orderId` es null,
  llama `completeDispatchByPumpOnBackend()` con pump+hose.
- **POS Frontend**: `DispenserCard` y `+page.svelte` detectan `FUELLING+IDLE`
  (no solo `COMPLETED+IDLE`) como cobro pendiente.

### 73. Doble autorización mismo dispensador → 409 Conflict ✅ — v0.19.2

**Problema**: Dos despachadores abren wizard para mismo dispensador. A autoriza
primero. B pulsa AUTORIZAR después → crea segundo despacho + envía CLEAR_STOP
+ PRESET que interfiere con A → despacho de A queda CANCELADO.

**Solución**:
- **Backend `create_dispatch`**: `pg_advisory_xact_lock(hose_id)` + check de
  despacho activo (`AUTHORIZED`/`COMPLETED`) → 409 Conflict.
- **Frontend `SaleWizard`**: Extrae `detail` del error 409, muestra mensaje claro.
- **Test**: `test_create_dispatch_conflict_same_hose` (93 tests total).

### 74. preset_value persistido + bloqueo cobro $0.00 ✅ — v0.19.3

**Problema**: Usuario B estaba en otra página (ej. HISTORIAL) mientras A autorizaba
y apagaba celular. Al terminar despacho, B regresa al DASHBOARD → ve COBRAR con
**$0.00**. Si B cobra, se registra cobro en cero (error grave).

Causa raíz: `preset_value` nunca se persistía en BD. `get_active_dispatches`
hardcodeaba `"preset_value": "0"`. Cuando B hace reconcile, `finalAmount=0`
y `presetAmount=0` → `$0.00`.

**Solución**:
- **Modelo `Dispatch`**: Nueva columna `preset_value VARCHAR(20)`.
- **API `create_dispatch`**: Almacena `body.preset_value`.
- **API `get_active_dispatches`**: Devuelve `d.preset_value` real.
- **API `collect_dispatch`**: Bloquea cobro a $0.00 cuando `dispatch.total > 0`.

### Archivos modificados (esta sesión)

```
FusionBridge (1):
  FusionEventHandler.java       ← +completeDispatchByPumpOnBackend (fallback pump+hose)

Backend (3):
  models/dispatch.py            ← +preset_value column
  api/dispatches.py             ← +complete-by-pump endpoint, +409 guard create_dispatch,
                                  +preset_value persist, +$0.00 collect block
  schemas/__init__.py           ← +CompleteByPumpRequest
  tests/test_api_dispatch.py    ← +test_create_dispatch_conflict_same_hose

POS (3):
  DispenserCard.svelte          ← FUELLING+IDLE detectado como cobro pendiente
  +page.svelte                  ← FUELLING+IDLE redirige a collect mode
  powerfin.ts                   ← createDispatch extrae detail del error 409
  SaleWizard.svelte             ← maneja err.status===409 con mensaje claro
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
☐ 4. dispatch.total no debe ser 0 en active dispatches cuando el despacho ya
   está COMPLETED. Revisar si completeDispatchOnBackend está actualizando
   correctamente d.total en todos los casos (incluyendo fallback pump+hose).
```

**SQL para producción (esta sesión):**

```sql
-- v0.19.3: preset_value en dispatches
ALTER TABLE dispatches ADD COLUMN IF NOT EXISTS preset_value VARCHAR(20);

-- v0.19.0 (pendiente de sesión anterior)
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

