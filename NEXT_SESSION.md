# NEXT_SESSION.md — Powerfin POS

## Estado actual (2026-06-12)

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
| **10b** | **v0.14.0** | **Phase 10 — Impresión: ticket completo, clave de acceso SRI, Font B, datos desde BD** |
| **10c** | **v0.15.0** | **Phase 10 — Correcciones: subtotal/IVA, código aleatorio, espacio corte, saldos negativos, comprobantes caja** |
| **10d** | **v0.16.0** | **Phase 10 — Key49: facturación electrónica SRI, fire-and-forget, polling, reintentos** |
| **10e** | **v0.16.1** | **Phase 10 — Correcciones: zona horaria, clave Key49, IPs impresora, subtotal→total, reimpresión** |
| **10f** | **v0.17.0** | **Phase 10 — Cierre de turno completo: cuadre, surplus/shortage, depósito, template impresión** |
| **10g** | **—** | **Phase 10 — RecoveryService: reconexión FusionBridge durante despacho activo** |

### 📊 Tests

```bash
FusionBridge — 67 tests    ./mvnw test    # BUILD SUCCESS
POS Backend  — 92 tests    pytest          # 92 passed
Powerfin POS — 0 errors    npm run check   # svelte-check OK
Total: 159 tests pasando
```

---

## Logros de la sesión (2026-06-12) — Reconexión FusionBridge

### 61. RecoveryService — Recuperación de ventas durante caída TCP ✅

**Nuevo archivo:** `fusion-bridge/.../recovery/RecoveryService.java`

**Problema:** Si el TCP entre FusionBridge y Wayne cae mientras un despacho está
en FUELLING y se completa durante la caída, el `EVT_PUMP_NEW_TRANSACTION` se pierde.
Nadie llama a `completeDispatchOnBackend` → el dispatch queda AUTHORIZED en el
backend → auto-cancel a los 5 min → venta perdida.

**Solución:** RecoveryService usa `PAY_AL` (alarma de venta sin cobrar del Wayne)
y `REQ_GET_PUMP_SALES` (consulta de últimas ventas) para recuperar:

```
Reconnect → REQ_PUMP_STATUS_ID_000 → Wayne responde PAY_AL=ON
→ Timer 4s → REQ_GET_PUMP_SALES(PM=N, QT=5)
→ Wayne responde con EVT_PUMP_NEW_TRANSACTION (histórico)
→ FusionEventHandler.handleNewTransaction() (EL MISMO DE SIEMPRE)
→ completeDispatchOnBackend(orderId, amount, volume, unitPrice)
→ Backend: AUTHORIZED → COMPLETED ✅
→ POS reconcileWithPowerFin() (3s) → Pendiente de Cobro visible
```

**Diseño clave:** Reutiliza el handler `handleNewTransaction` existente — no se
duplica lógica de parseo ni de completado. La primera conexión (arranque en frío)
no dispara recovery, solo reconexiones.

**Modificaciones mínimas:**
- `FusionTcpClient.java`: +3 líneas (inyectar RecoveryService, llamar onReconnect)
- `FusionEventHandler.java`: +6 líneas (capturar PAY_AL, constructor param)
- `RecoveryService.java`: NUEVO (~110 líneas)

### Archivos modificados (esta sesión)

```
FusionBridge (3):
  recovery/RecoveryService.java  ← NUEVO: lógica de recuperación post-reconexión
  fusion/FusionTcpClient.java    ← +@Inject RecoveryService, +onReconnect() call
  fusion/FusionEventHandler.java ← +captura PAY_AL, +log WARN para eventos SALE nuevos
```

---

### 48. max_cash_in_hand + alerta en dashboard ✅

`system_config.max_cash_in_hand = 300.00`. Dashboard verifica efectivo cada 30s vía `getShiftCashSummary`.
Si `current_balance > 300` → punto rojo pulsante + texto "⚠️ ALERTA, Límite de dinero en caja excedido".
Solo aviso, no bloquea.

### 49. Módulo Depósito + Caja Fuerte removida ✅

- Nuevo tipo de movimiento: `DEPOSIT` (idéntico a EGRESO, disminuye saldo).
- DB constraint + queries de balance actualizadas.
- POS: botón 🏦 Depósito en módulo Caja.
- Caja Fuerte removida de `get_online_users` y `create_transfer`.
- Transferencia solo entre usuarios reales con turno abierto.

### 50. Cierre de turno sin campo de efectivo ✅

- `CloseShiftRequest`: sin `closing_cash`.
- DB shifts: +`surplus`, +`shortage`.
- Sistema calcula: balance POSITIVO → FALTANTE, balance NEGATIVO → SOBRANTE.
- POS: modal confirmación, sin campo efectivo.
- Botón "🔒 Cerrar Turno" movido del dashboard al módulo Caja.

### 51. Pantalla post-cierre con resumen completo ✅

- Sección 1: 💰 Resumen de Efectivo (apertura, ventas, ingresos, egresos, depósitos, transfers).
- Sección 2: 💳 Otras Formas de Pago (totales por método).
- "Sobrante de Efectivo" / "Faltante de Efectivo" / "Efectivo en CERO".
- Botón 🖨 Imprimir.

### 52. Template impresión cierre de turno ✅

- `SHIFT_CLOSE` type en FusionBridge con `ShiftCloseData`.
- Plantilla completa: empresa, empleado, turno, resumen efectivo (+/-), total ventas.
- 7 puntos separadores al final.

### 53. Validación de saldo negativo eliminada ✅

Egresos, Depósitos y Transferencias ya no validan saldo disponible.
Empleado puede depositar/transferir todo su efectivo físico.
Diferencia se refleja como sobrante/faltante al cerrar.

### 54. TRANSFER_IN como tipo independiente ✅

- Reemplaza `INCOME + related_user_id IS NOT NULL` por `TRANSFER_IN`.
- DB constraint, queries de balance, labels POS actualizados.
- Ícono 📥, label "Transferencia recibida".

### 55. cash_printer_ip en system_config ✅

- `system_config.cash_printer_ip` + `cash_printer_port` independiente de dispensers.
- Expuesto en config API (`$config.cash_printer_ip`).
- Todas las impresiones de caja usan esta IP.

### 56. Módulo Caja — siempre accesible ✅

- Caja accesible sin turno abierto.
- Botones deshabilitados hasta abrir turno.
- Botón "🔓 Abrir Turno" visible cuando no hay turno.
- Dashboard: dispensers visibles pero bloqueados, card "Turno no aperturado".

### 57. Modal de confirmación en movimientos de caja ✅

- Flujo: Formulario → Modal ¿Confirmar? → Registro → Modal ¿Imprimir?
- Aplica a Ingreso, Egreso, Depósito, Transferencia.
- Botones rápidos reemplazan valor (no suman). Etiquetas sin "+".

### 58. Historial: limpieza y reimpresión ✅

- Tarjetas "Total ingresos" / "Total egresos" eliminadas.
- Línea "Saldo: $" eliminada de movimientos de caja.
- Reimpresión en despachos y caja con ícono 🖨.
- `formatCurrency` inmune a strings.

### 59. Plantillas: 7 puntos + puntos suspensivos + MAYÚSCULAS ✅

- Todas las plantillas: 7 `.` al final para evitar corte.
- Cierre de turno: `{{DOT:label:value}}` → "LABEL: ..... $ VALUE".
- Símbolos (+) y (-) en resumen de efectivo.
- Textos fijos en MAYÚSCULAS sin tildes.
- `REIMPRESION` label en tickets reimpresos.
- Auto-redirect 2.5s post-impresión.

### 60. docs/INSTALL.md ✅

Guía completa de instalación para Debian 13, usuario único `app`, sin Docker.
Cubre: PostgreSQL, POS Backend, FusionBridge, Nginx, SSL, firewall, seeds.

### Archivos modificados (esta sesión)

```
FusionBridge (3):
  PrintResource.java           ← SHIFT_CLOSE type, 7 dots test ticket
  ReceiptBuilder.java          ← +ShiftCloseData class
  TemplateRenderer.java        ← renderShiftClose, shiftCloseTemplate, DOT format, TRANSFER_IN label

Backend (7):
  config.py                    ← cash_printer_ip, cash_printer_port
  api/cash.py                  ← DEPOSIT type, TRANSFER_IN, remove balance validation
  api/shifts.py                ← +surplus/shortage, close_shift refactor, sales_cash_count
  api/dispatches.py            ← _build_receipt_data, customer_email
  models/dispatch.py           ← +DEPOSIT, +TRANSFER_IN constraints
  models/shift.py              ← +surplus, +shortage
  schemas/__init__.py          ← CloseShiftResponse refactor, ConfigResponse cash_printer
  tests/test_api_cash.py       ← reescrito: sin validación negativa
  tests/test_api_credit.py     ← test_transfer sin Caja Fuerte
  tests/test_api_dispatch.py   ← test_close_shift surplus/shortage

POS (9):
  +page.svelte                 ← max_cash_in_hand alert, dispensers bloqueados sin turno
  cash/+page.svelte            ← solo botones, Abrir/Cerrar Turno, sin movimientos
  cash/movement/+page.svelte   ← DEPOSIT type, confirm modal, botones reemplazan
  cash/transfer/+page.svelte   ← confirm modal, botones reemplazan, sin Caja Fuerte
  history/+page.svelte         ← reprint cash, sin cards/saldo, TRANSFER_IN label, formatCurrency fix
  users/+page.svelte           ← formatCurrency fix
  shift/close/+page.svelte     ← pantalla completa: resumen efectivo + no-efectivo + print
  SaleWizard.svelte            ← receipt_data from DB, auto-redirect
  bridge.ts                    ← print error logging
  types.ts                     ← DEPOSIT, TRANSFER_IN, CloseShiftResponse, cash_printer
  powerfin.ts                  ← CloseShiftRequest sin closing_cash
  powerfin.mock.ts             ← actualizado para nuevos tipos

Docs (2):
  INSTALL.md                   ← NUEVO: guía instalación Debian 13
  KEY49-INTEGRATION-GUIDE.md   ← actualizado
```

---

## Logros de la sesión (2026-06-10) — v0.16.1

### 41. Zona horaria unificada — ECUADOR_TZ ✅

**Problema:** Mezcla de `datetime.now()` (naive), `datetime.now(timezone.utc)`, y ECUADOR_TZ local.
`.replace(tzinfo=utc)` sobre datetime con offset -05 causaba corte de 24h de facturas Key49
5 horas antes de lo debido.

**Corrección:**
- `config.py`: nueva constante compartida `ECUADOR_TZ = timezone(timedelta(hours=-5))`
- `key49_service.py`: `datetime.now(ECUADOR_TZ)` en sri_authorization_date, cutoff, idempotency key
- `shifts.py`: `datetime.now(ECUADOR_TZ)` en closed_at
- `dispatches.py`: `datetime.now(ECUADOR_TZ)` en completed_at, stale_cutoff, order_id, local_date
- `auth_service.py`: sin cambio (JWT usa UTC por estándar RFC 7519)

### 42. Clave de acceso enviada a Key49 ✅

**Problema:** Key49 generaba su propia clave de acceso, diferente a la impresa en el ticket.

**Corrección:** `_build_invoice_payload()` incluye `"access_key": dispatch.access_key` en el payload.
Key49 respeta la clave enviada y la usa para el SRI → misma clave en ticket y SRI.

### 43. Eliminación de key49_sandbox redundante ✅

`key49_sandbox` en system_config era redundante. El ambiente se determina en un solo lugar:
`company_info.sri_environment` (1=PRUEBAS, 2=PRODUCCION). Eliminado de código y BD.

### 44. Columnas Key49 en BD + system_config ✅

**dispatches:** +5 columnas (key49_invoice_id, key49_access_key, sri_status,
sri_authorization_date, sri_messages).

**system_config:** +3 entradas (key49_api_key, key49_base_url, key49_enabled).
Aplicado en powerfin_gas y powerfin_gas_test.

### 45. final_amount = total (no subtotal) ✅

**Problema:** `get_active_dispatches` y `get_shift_dispatches` devolvían
`final_amount = d.subtotal` ($0.87 sin IVA) en vez de `d.total` ($1.00 con IVA).
El POS mostraba "Cobrar $0.87" y registraba el pago por $0.87 en dispatch_payments.

**Corrección:** Ambos endpoints devuelven `float(d.total or 0)`.

### 46. Eliminación de fallbacks de IPs de impresora ✅

**Problema:** FusionBridge tenía IPs hardcodeadas (192.168.1.31/32) como fallback en
properties, PrinterConfig.java, y múltiples defaults. Errores de conectividad silenciosos.

**Corrección:**
- `PrinterConfig.java`: reducido a solo policy (sin islas, sin IPs, sin JSON file)
- `PrintResource.java`: exige `printerIp` + `printerPort` del POS → error 400 si falta
- `application.properties`: eliminadas island IPs y printer.config.file
- `BridgeHealthResource.java`: sin referencias a islas de impresora
- `AGENTS.md`: IPs reemplazadas por placeholders referenciales

### 47. Corrección de reimpresión de despacho ✅

**Bug 1 — TypeError silencioso:** `subsidy_per_unit` venía como string `'0E+2'`
del backend. `string.toFixed(4)` lanzaba TypeError, tragado por `catch {}` sin log.

**Bug 2 — Config no cargado:** `loadData()` en historial nunca cargaba `$config`.
Si el layout fallaba al cargarlo, `handleReprint` retornaba sin hacer nada.

**Correcciones:**
- Frontend: `Number(val ?? 0).toFixed()` en todos los valores del API (8 ubicaciones)
- Frontend: `console.error('[reprint] ERROR:', err)` en catch del historial
- Frontend: `loadData()` carga config si `!$configStore.loaded`
- Backend: `float()` explícito en subsidy_per_unit, subsidy_amount, price_without_subsidy

### Archivos modificados (esta sesión)

```
FusionBridge (6):
  PrinterConfig.java           ← simplificado: solo policy, sin islas/IPs/JSON
  PrintResource.java           ← error 400 si falta printerIp, sin fallbacks
  BridgeHealthResource.java    ← sin referencias a islas de impresora
  application.properties       ← eliminadas island IPs y printer.config.file
  PrinterConfigTest.java       ← reescrito para nueva API simplificada (7 tests)

Backend (5):
  config.py                    ← +ECUADOR_TZ constante compartida
  services/key49_service.py    ← ECUADOR_TZ, access_key en payload, -sandbox
  api/dispatches.py            ← ECUADOR_TZ, final_amount=total, float() en subsidy
  api/shifts.py                ← ECUADOR_TZ, final_amount=total, float() en subsidy

POS (5):
  bridge.ts                    ← +log datos enviados, +error body en catch
  history/+page.svelte         ← +carga config, +Number().toFixed(), +console.error
  cash/+page.svelte            ← +Number().toFixed()
  SaleWizard.svelte            ← +Number().toFixed()
  AGENTS.md                    ← IPs referenciales, no hardcodeadas
```

---

## Logros de la sesión (2026-06-09) — v0.15.0

### 35. Corrección Subtotal/IVA — desglose correcto ✅

**Problema:** `subtotal == total` ($1.00 ambos). El Wayne devuelve total con IVA incluido,
pero el código lo asignaba como subtotal. Con IVA 15%: subtotal = total / 1.15.

**Corrección en `complete_dispatch`:**
```python
# ✅ CORRECTO
total_dec = amount_dec                          # $1.00 total Wayne (con IVA)
subtotal_dec = total_dec / (1 + tax_rate_dec)   # $1.00 / 1.15 = $0.87
tax_dec = total_dec - subtotal_dec              # $1.00 - $0.87 = $0.13
```

**DB:** `tax_types.rate` 0.1200 → 0.1500, `IVA_12` → `IVA_15`.
**Subsidio:** desactivado — `subsidy_amount = 0` siempre, `price_without_subsidy = base_price`.

### 36. Código numérico aleatorio en clave SRI ✅

**Problema:** `codigo_numerico` usaba el mismo valor del secuencial → "00000019" repetitivo.

**Corrección en `access_key_service.py`:**
```python
if codigo_numerico is None:
    codigo_numerico = random.randint(0, 99999999)  # aleatorio 8 dígitos
```

### 37. Espacio al final de impresión — sin cortar texto ✅

**Problema:** Solo 3 LF antes del corte → "GRACIAS POR SU COMPRA" salía cortado a la mitad.

**Corrección en `TemplateRenderer.java`:** 6 líneas en blanco + punto visible + corte.
`[CUT]` removido de la plantilla default.

### 38. Saldos negativos bloqueados en caja ✅

**Nueva función `_available_cash()`** calcula disponible real:
```
disponible = apertura + ingresos + ventas_cobradas - egresos - transferencias - safe_drops
```

Validaciones agregadas:
- `EXPENSE` → 400 "Saldo insuficiente" si `amount > disponible`
- `TRANSFER_OUT` → misma validación
- `SAFE_DROP` → misma validación
- `INCOME` → sin restricción

**5 tests nuevos** (`test_api_cash.py`): egreso rechazado, egreso permitido, transferencia rechazada,
safe drop rechazado, ingreso siempre permitido.

### 39. Comprobantes de caja — impresión + reimpresión ✅

**FusionBridge:**
- `TemplateRenderer.renderCashMovement()` + plantilla `cashMovementTemplate()`
- `ReceiptBuilder.CashMovementData` + `fromMap()`
- `PrintResource` maneja `type=CASH_MOVEMENT`

**Backend:** `GET /api/pos/cash-movements/{id}` con `user_name` para reimpresión.

**POS:**
- Modal "¿Desea imprimir comprobante?" al crear ingreso/egreso/transferencia
- Botón 🖨 en cada movimiento del listado de caja para reimpresión

**Títulos por tipo:** INGRESO, EGRESO, TRANSFERENCIA, DEPÓSITO.

### Archivos modificados (esta sesión)

```
FusionBridge (3):
  TemplateRenderer.java       ← +renderCashMovement, +movementLabel, +cashMovementTemplate
  ReceiptBuilder.java         ← +CashMovementData class, +buildCashMovementReceipt
  PrintResource.java          ← maneja type=CASH_MOVEMENT

Backend (4):
  services/access_key_service.py  ← random.randint en código numérico
  api/dispatches.py               ← subtotal=total/(1+tax), IVA 15%, subsidy=0
  api/cash.py                     ← +_available_cash(), +GET cash-movements/{id}, validación saldo
  tests/test_api_cash.py          ← NUEVO: 5 tests validación saldo negativo
  tests/test_access_key.py        ← actualizados: validan aleatoriedad

POS (3):
  cash/movement/+page.svelte      ← modal print al crear ingreso/egreso
  cash/transfer/+page.svelte      ← modal print al crear transferencia
  cash/+page.svelte               ← botón 🖨 reimpresión en lista movimientos
```

---

## Logros de la sesión (2026-06-09) — v0.16.0

### 40. Integración Key49 — Facturación electrónica SRI ✅

**DB — 5 columnas nuevas en dispatches:**
- `key49_invoice_id` (UUID de Key49)
- `key49_access_key` (clave SRI oficial de 49 dígitos)
- `sri_status` (PENDING → CREATED → SIGNED → SENT → AUTHORIZED / REJECTED / FAILED)
- `sri_authorization_date` (fecha de autorización SRI)
- `sri_messages` (JSON con errores SRI si rechazado)

**Servicio `key49_service.py` (NUEVO):**
- `emitir_factura()`: POST /v1/invoices → construye payload desde dispatch + person + details
- `_poll_autorizacion()`: polling cada 2s (máx 10 intentos) hasta AUTHORIZED/REJECTED
- `consultar_estado()`: devuelve estado SRI actual
- `retry_pending_invoices()`: reintenta PENDING, ignora >24h (SRI rechaza fecha pasada)

**Arquitectura fire-and-forget:**
- `collect_dispatch` dispara `asyncio.create_task(_key49_background)` con sesión DB independiente
- Si Key49 no responde → `sri_status = PENDING`, venta completada, ticket impreso
- El cliente NUNCA espera por Key49

**Toggle `key49_enabled` en system_config:**
- `true` → envía facturas automáticamente
- `false` → no intenta enviar (testing, emergencias)

**Mappings:**
- `persons.id_type`: CED→05, RUC→04
- `tax_types.rate`: 0%→0, 12%→2, 15%→4
- `payment_methods`: EFECTIVO→01, TARJETA→19, TRANSFERENCIA→20, etc.
- `issue_date`: siempre hoy en zona Ecuador (UTC-5)

**Endpoints nuevos:**
- `GET /api/pos/dispatches/{order_id}/sri-status` — consultar estado SRI
- `POST /api/pos/dispatches/{order_id}/retry-sri` — reintento manual (ADMIN)
- `POST /api/pos/dispatches/retry-pending-invoices` — reintento masivo (ADMIN)

### Archivos modificados (esta sesión)

```
Backend (5):
  models/dispatch.py              ← +5 columnas Key49
  services/key49_service.py       ← NUEVO: emitir, polling, retry, consultar
  api/dispatches.py               ← _key49_background, +3 endpoints SRI
  api/shifts.py                   ← +sri_status, key49_access_key en respuesta
  tests/conftest.py               ← key49 config + IVA_15 seed fix
```

---

## Logros de la sesión (2026-06-08) — v0.14.0

### 34. Impresión — ticket completo con datos desde BD ✅

**DB — 10 columnas nuevas:**
- `company_info`: +6 columnas (city, province, country, fiscal_regime, sri_environment, emission_type)
- `products`: +1 columna (subsidy_per_unit)
- `dispatch_details`: +2 columnas (price_without_subsidy, subsidy_amount)
- `dispatches`: +1 columna (access_key)

**Backend:**
- Config API: LocationResponse extendido, HoseResponse +base_price +subsidy_per_unit
- Config API: printer_policy desde system_config
- create_dispatch: genera access_key (49 dígitos SRI) + guarda base_price y subsidy
- complete_dispatch: calcula subsidy_amount automático
- get_active_dispatches + get_shift_dispatches: customer_id, plate, customer_address,
  customer_phone, price_without_subsidy, subsidy_per_unit, subsidy_amount, access_key
- complete_dispatch sin autenticación (FusionBridge lo llama directo)

**Clave de Acceso SRI (49 dígitos):**
- `app/services/access_key_service.py`: generate_access_key() + módulo 11
- Estructura correcta: Ambiente 1 dígito, Tipo Emisión en posición 48
- 17 tests unitarios

**FusionBridge:**
- TemplateRenderer: +20 placeholders, +5 condicionales anidados, Font B (ESC M 1)
- TemplateRenderer: espaciado mínimo (ESC 3 0), sin líneas en blanco (skipBlankLines)
- ReceiptBuilder.FuelReceiptData: +20 campos
- ReceiptBuilder.fromMap: acepta fuelData (camelCase) + fuel_data (snake_case)
- PrintResource: /stop con CLEAR_STOP diferido, preview mode, acepta printerIp+printerPort
- Template actualizado: formato completo del ticket real
- BOLD con ESC E (independiente de fuente)

**POS:**
- SaleWizard.doPrint: datos completos (location, customer, subsidy, invoice, subtotal/IVA)
- History reprint: mismos datos que venta directa + computed fields (IVA 15%)
- Config types: AppConfig.location extendido, HoseConfig +base_price +subsidy_per_unit
- DispenserConfig: printer_island → printer_ip + printer_port

### 35. Configuración de impresora desde BD ✅

- printer_ip + printer_port desde tabla dispensers (ya no archivo JSON)
- printer_policy desde system_config
- Eliminados archivos: printer-config.json, receipt-template.txt
- Eliminada dependencia PRINTER_CONFIG_FILE de start.sh

### Archivos modificados (esta sesión)

```
FusionBridge (5):
  PrintResource.java          ← +stop CLEAR_STOP, +preview, +printerIp/printerPort
  ReceiptBuilder.java         ← +20 campos FuelReceiptData, fromMap camelCase+sanke_case
  TemplateRenderer.java       ← +20 placeholders, +5 condicionales, Font B, skipBlankLines
  ReceiptBuilderTest.java     ← key actualizado
  ReceiptTemplateTest.java    ← bold command actualizado

Backend (7):
  models/company.py           ← +6 columnas
  models/dispatch.py          ← +3 columnas (price_without_subsidy, subsidy_amount, access_key)
  models/product.py           ← +1 columna (subsidy_per_unit)
  schemas/__init__.py         ← LocationResponse extendido, DispenserConfig printer_ip/port,
                                 HoseResponse +base_price +subsidy_per_unit, ConfigResponse +printer_policy
  api/config.py               ← devuelve location, printer, product fields desde BD
  api/dispatches.py           ← crea access_key, guarda subsidy, auto-cancel, respuestas enriquecidas
  api/shifts.py               ← get_shift_dispatches enriquecido
  services/access_key_service.py  ← NUEVO: generate_access_key() + módulo 11
  tests/test_access_key.py        ← NUEVO: 17 tests

POS (6):
  api/types.ts                ← Location, DispenserConfig, HoseConfig, DispatchOrder extendidos
  api/bridge.ts               ← +stopDispenser(), preview console.log, ESC/POS stripping
  components/SaleWizard.svelte← doPrint completo, loadPrintPolicy desde BD
  routes/(pos)/history/+page.svelte ← reprint con datos completos
  api/powerfin.mock.ts        ← printer_island → printer_ip+printer_port
  start.sh                    ← sin PRINTER_CONFIG_FILE
```

---

## Logros de la sesión (2026-06-08) — v0.13.0

### 32. Edge cases — Gaps A, B, D cerrados ✅

**Gap D — Fallo parcial (dispatch creado, preset falló):**
- Frontend: rollback inmediato en SaleWizard y new-dispatch (try/catch → cancelDispatch)
- Backend: auto-cancel de dispatches AUTHORIZED > 5 min en get_active_dispatches

**Gap B — ATO expirado / celular apagado (análisis y revertido):**
- El auto-cancel reactivo fue revertido (comía ventas reales si completeDispatch fallaba)
- La solución real es mover completeDispatch a FusionBridge (ver abajo)

**Gap A — STOP durante FUELLING:**
- FusionBridge: nuevo endpoint `POST /api/dispatch/stop` con CLEAR_STOP diferido (2s)
- DispenserCard: ícono ⏹ pequeño durante FUELLING + evento onStopClick
- Dashboard: modal STOP con doble barrera anti-bolsillo (CANCELAR grande + Detener chico)
- Timeout 8s del modal + CLEAR_STOP automático en authorize (limpia busy buffers)

### 33. Celular apagado durante despacho — RESUELTO ✅

**Raíz del problema:** completeDispatch solo lo hacía el POS (celular) vía SSE.
Si el celular estaba apagado, NADIE completaba el dispatch → venta perdida.

**Solución:** FusionBridge ahora llama completeDispatch directamente al recibir
NEW_TRANSACTION del Wayne:
- `FusionEventHandler.java`: `completeDispatchOnBackend()` en virtual thread
- 3 reintentos con 1s backoff
- El POS sigue llamando completeDispatch como doble seguro (idempotente)
- `CLEAR_STOP` antes de cada PRESET en authorize (limpia busy buffers residuales)

**Escenarios validados:**
- ✅ Celular apagado durante FUELLING → al encender: "Cobrar $X"
- ✅ Celular apagado en AUTHORIZED → al encender: estado correcto
- ✅ STOP a mitad de despacho → CLEAR_STOP → NEW_TRANSACTION → cobro parcial
- ✅ Siguiente PRESET después de STOP → sin TRANS_ERR_PRESET_STOPPED

### Archivos modificados (esta sesión)

```
FusionBridge:
  DispatchResource.java        ← +/stop con CLEAR_STOP diferido, +CLEAR_STOP en authorize
  FusionEventHandler.java      ← +completeDispatchOnBackend (HTTP al backend, 3 retries)

POS:
  SaleWizard.svelte            ← rollback dispatch en catch (Gap D)
  new-dispatch/+page.svelte    ← rollback dispatch en catch (Gap D)
  +page.svelte                 ← modal STOP doble barrera + handleStopClick + executeStop
  DispenserCard.svelte         ← ícono ⏹ durante FUELLING + onStopClick prop
  bridge.ts                    ← +stopDispenser()
  bridge-client.ts             ← +stopDispenser() wrapper
  bridge.mock.ts               ← +stopDispenser() mock

Backend:
  dispatches.py                ← auto-cancel AUTHORIZED > 5 min (Gap D safety net)
```

---

## Logros acumulados Phase 9 (2026-06-04 → 2026-06-05)

### v0.11.0 — Price lists, wizard reorder, emission points, schema simplification

**22 frentes cerrados:** price list lookup (VIP/EMPLOYEE) antes de PRESET, wizard
reordenado (Placa → Producto → Cliente), 4 puntos de emisión (001-001 a 001-004),
`authorized_by_user_id` FK, eliminadas 4 columnas denormalizadas, `shift_id` se
actualiza al turno del cobrador, `customer_name` vía JOIN, `change_billing` 404.

### v0.12.0 — Cuadre de caja, transfers, lookup, billing, validación

### 23. Cuadre de caja y transferencias ✅

**3 bugs corregidos + 1 bugfix extra:**

1. **close_shift fórmula incompleta** — No restaba TRANSFER_OUT ni SAFE_DROP.
   Fórmula: `opening + income + sales - expense - transfers_out - safe_drops`
2. **get_cash_summary mismo problema** — Misma fórmula + campos poblados:
   `total_transfers_received`, `total_transfers_sent`, `total_safe_drops`
3. **Transferencia no creaba movimiento al receptor** — `create_transfer`
   (user→user) crea INCOME automático en turno del receptor con `related_user_id`
4. **Decimal→float** — `Numeric(12,2)` retorna `Decimal` vs `or 0.0` → `float`
   causaba 500 en close_shift. Fix: `float()` explícito en todas las sumas.

**Archivos:** `shifts.py`, `cash.py`

### 24. Test end-to-end vía API ✅

Login → turno → dispatch → complete → collect → close (diff=$0.00).
Cross-user: maria autoriza, carlos cobra → shift_id actualizado.
Transferencias: $20 y SAFE_DROP → cuadre $0 en ambos turnos.

### 25. persons/lookup integrado en POS ✅

- Tipo `PersonLookupResult` + `PersonLookupData`
- `lookupPerson()` → `GET /api/pos/persons/lookup?id_type=&id_number=`
- SaleWizard y new-dispatch usan `lookupPerson` (ya no `getCustomerById`)
- Tokens reales vía `auth` store (ya sin `'mock-token'` hardcodeados)

### 26. Facturación preferencial por vehículo ✅

- DB: `vehicles.billing_person_id` FK nullable → persons. NULL = usar titular
- Backend: `lookupVehicle` devuelve `billing_person` + `PUT /vehicles/{id}/billing-person`
- POS: badge "⭐ Facturación preferencial" + checkbox "Guardar como preferencial"
- Prioridad: billingCustomer > billing_person > owner

### 27. Auto-guardado de API externo ✅

`lookupPerson` → Sercobaco/SRI → `INSERT ... ON CONFLICT DO NOTHING` en `persons`.
2ª búsqueda mismo CED/RUC → instantáneo (BD local).
DB: `UNIQUE(id_type, id_number)` en persons.

### 28. Validación CED=10 / RUC=13 dígitos ✅

`$: idValid` reactivo + `maxlength` dinámico + `inputmode="numeric"`.
Botón Buscar deshabilitado hasta longitud correcta. Mensaje de error.

### 29. Botones "← Volver" en todos los pasos del wizard ✅

Agregados en: product, billing, presetType, presetValue.
"Volver" de idLookup recuerda si vino de plate o billing.
Auto-select removido (siempre se muestra paso product).

### 30. Edición de datos del cliente ✅

Botón "✏️ Editar datos" en paso billing → formulario inline (nombre, email,
teléfono, dirección). `PUT /api/pos/persons/{id}` + `updatePerson()`.
Backend `VehicleOwner` schema + `address`.

### 31. Flujo de registro de nueva persona mejorado ✅

- Cédula/RUC pre-llenada + readonly al entrar a registro
- Campos nombre (requerido), email (requerido, facturación electrónica),
  teléfono, dirección (opcionales)
- Botón "Continuar" deshabilitado hasta nombre + email llenos
- Después de registrar → directo a billing (no a product)
- Todos los campos se limpian al entrar/cancelar

---

## Archivos modificados en esta sesión

```
pos_backend/app/api/shifts.py         ← close_shift: +TRANSFER_OUT, +SAFE_DROP, float() cast
pos_backend/app/api/cash.py           ← cash_summary: +transfers fields, float() cast;
                                        create_transfer: +INCOME receptor
pos_backend/app/api/persons.py        ← auto-save external API, +person_id, fix PUT endpoint
pos_backend/app/api/vehicles.py       ← +billing_person, +vehicle_id, +address
pos_backend/app/models/person.py      ← +billing_person_id FK + relationship
pos_backend/app/schemas/__init__.py   ← +billing_person, +vehicle_id, +person_id, +address,
                                        +SetBillingPersonRequest, fix UpdatePersonRequest

pos/src/lib/api/types.ts              ← PersonLookupResult, +person_id, +address, +vehicle_id,
                                        +billing_person en VehicleResult
pos/src/lib/api/powerfin.ts           ← lookupPerson, setVehicleBillingPerson, updatePerson
pos/src/lib/api/powerfin.mock.ts      ← mocks para todos los nuevos endpoints
pos/src/lib/components/SaleWizard.svelte ← persons/lookup, billing preferencial,
                                        auto-save, edit customer, back buttons,
                                        validación CED/RUC, wizard estandarizado,
                                        registro mejorado, state leak fixes
pos/src/lib/components/CustomerSearch.svelte ← token real vía auth store
pos/src/routes/(pos)/new-dispatch/+page.svelte ← lookupPerson, token real, validación
```

---

## Pendiente para próxima sesión

### 🟡 Backlog

```
☐ 1. Pago mixto (efectivo + tarjeta)
☐ 2. identity_service.py — mover URL y token a .env o system_config
   (están quemados: IDENTITY_API_URL, IDENTITY_API_TOKEN)
☐ 3. Roles/permisos — implementar enforcement real:
   · ADMIN: todo
   · SUPERVISOR: ventas, reportes, cierre de turno, SRI retry
   · DISPATCHER: ventas, cierre de turno
   (Actualmente solo se validan en 2 endpoints SRI, el resto es libre)
```

**Ya resueltos:**
- ~~Ajustar ATO en consola Wayne de 0 → 180s~~ — Ajustado vía GUI del Fusion
- ~~Reconexión FusionBridge durante despacho activo~~ — RecoveryService implementado (Phase 10g)
- ~~Múltiples despachos simultáneos~~ — Validado funcionalmente
- ~~Prueba de cuadre de caja end-to-end con hardware real~~ — Realizado, todo cuadró
- ~~Migración Alembic para schema acumulado~~ — Revisiones `8c005ee89373` (initial) + `b261e8ceb69f` (accumulated). Modelo y DB 100% sincronizados (`alembic check` limpio). UNIQUE(id_type, id_number) agregado al modelo Person.

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
