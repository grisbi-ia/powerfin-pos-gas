# NEXT_SESSION.md — Powerfin POS

## Estado actual (2026-09-13) — v0.38.0

### 📌 Acciones ejecutadas en PRODUCCIÓN hoy (2026-09-13)

| # | Acción | Resultado |
|---|---|---|
| 1 | **Deploy** backend + frontend (`deploy-backend` → `deploy-frontend`) | Migración `5c6d7e8f9a01` aplicada; FusionBridge y Admin **no** tocados. Verificado: `:5173` 200, `:5174` 200, `:8090/health` UP con `fusionConnected:true`, backend vivo tras Nginx |
| 2 | **Factura `003-501-000004859`** (dispatch 21031, nunca enviada, 7 h en `PENDING`) | Reemitida con `recover_pending_invoices.py --dispatch-id 21031 --min-age-hours 0 --execute` → **`NOTIFIED`** (`key49_invoice_id 92bc97d0-…`), autorizada 19:48 |
| 3 | **7 facturas fallidas del día** ($76.45) — titular reasignado y emitidas | **AURACORE SOLUCIONES SAS** (`person_id 10472`, RUC `0195160252001`, **creada**; $56.45) y **VALAREZO PATRICIO** (`person_id 3750`, $20.00) → **7/7 autorizadas**, 6 `NOTIFIED` + 1 `AUTHORIZED`. Respaldo previo: `/tmp/reasignacion_antes.tsv` |
| 4 | **Limpieza de IDs inválidos** (`limpiar_ids_invalidos.py --apply`) | **198 clientes** con `id_number = NULL` (182 cédulas + 16 RUC inexistentes). Respaldo CSV: `/tmp/ids_invalidos_backup_20260914_023929.csv`. Ningún titular de contrato de crédito activo afectado |
| 5 | **Día fiscal 2026-09-13** | **266 facturas, $3.721,05 — 0 fallidas, 0 pendientes de envío** |

**Pendiente inmediato del dueño:** avisar a los despachadores que, para los clientes limpiados,
 el POS pedirá la cédula (paso 🪪) — y que **ROMUALDO ONCE (4483)** y **CARLOS CARDENAS (5338)
no tienen vehículo**, así que solo se encuentran con la pestaña **“Por Nombre”**.

**Nota de entorno:** `agent_llm` tiene **lectura/escritura de datos pero NO `CREATE`** en el
schema `public` (por eso el respaldo de la limpieza va a CSV). Tampoco hay SSH desde la máquina
de desarrollo al servidor: los scripts de recuperación se corren contra la BD de producción
(golpean la API de Key49 directamente).

### ✅ Validación de cédula/RUC + el POS obliga a re-pedir la identificación

**Incidente que lo motivó:** el 2026-09-13 se perdieron **7 facturas** ($76.45) con
`Key49 HTTP 400 VALIDATION_ERROR — Invalid identification for type 05`, **después**
de haber despachado y cobrado. Los 6 clientes tenían cédula con dígito verificador
inválido. Causa raíz en 3 capas:

1. **Sercobaco caído** (`No existe un contrato activo...`, desde el 09-12) → el POS
   no puede verificar ninguna cédula.
2. `GET /api/pos/persons/lookup` se tragaba el error y devolvía `found:false` → el
   despachador caía al registro manual **sin ningún aviso** y escribía lo que le decían.
3. **Nadie validaba el dígito verificador.** El POS solo validaba **longitud**
   (`SaleWizard.svelte`, `idValid = length === 10/13`) y el backend nada. Además ya
   había **198 clientes activos con ID inválido**, así que al buscarlos devolvía
   `found:true` y la venta seguía.

**Reglas derivadas con datos reales (no de teoría):**

| Tipo | Regla | ¿Bloqueante? |
|---|---|---|
| Cédula | módulo 10 (provincia 01-24 y 30) | **Sí** — es exactamente lo que aplica Key49. 3.743 IDs ya aceptados por el SRI → **0 falsos negativos** |
| RUC persona natural (3er dígito 0-5) | cédula módulo 10 + `001` | **Sí** — 637/637 RUC naturales aceptados por el SRI la cumplen |
| RUC jurídica (9) / pública (6) | **solo estructura** | **No** — el módulo 11 **no es confiable**: el registro del SRI tiene RUC que lo fallan (CLICK SOLUCIONES 1793200847001 factura normal) y el sistema lineal sobre 90 RUC confirmados es **inconsistente**. Bloquear con él rechazaría clientes reales |
| Existencia en el registro | broker del SRI | **Sí** — es la autoridad para RUC |

**Cambios (pos_backend):**
- **Nuevo** `app/services/id_validation.py` — fuente única de la regla + tests
  (`tests/test_id_validation.py`, 57 casos: IDs reales aceptados y los 6 rechazados del 09-13).
- **Nuevo** `tests/test_api_identification_guard.py` (16 tests) — cubre toda la barrera.
- `POST /api/pos/customers`, `GET /api/pos/persons/lookup`, `GET /api/pos/customers/by-id`
  → **422** con mensaje accionable. El número inválido **nunca se guarda**.
- `POST /api/pos/dispatches` y `POST .../collect` → **422** si el cliente no tiene
  identificación (`id_number IS NULL`) o es inválida. También en `POST .../billing`.
- **`persons.id_number` ahora es nulable** (migración `5c6d7e8f9a01`): `NULL` es el
  estado explícito “identificación no verificada”. El `UNIQUE (id_type, id_number)`
  se mantiene (Postgres permite varios NULL). `downgrade` falla ruidosamente si
  todavía hay NULL.
- `PUT /api/pos/persons/{id}` acepta `id_type`/`id_number` → es el endpoint de
  **re-captura**; valida el dígito, detecta duplicados con **409**.
- `identity_service.py`: se separó **`IdentityNotFoundError`** (el registro responde
  “no existe” → **bloquea**, 422) de **`IdentityProviderError`** (proveedor caído →
  sigue al registro manual **con aviso visible**). Antes ambos eran lo mismo y un RUC
  inexistente podía registrarse a mano.
- `CreateDispatchRequest`/`BillingRequest` aceptan `person_id` (el POS lo conoce desde
  el lookup; necesario cuando `id_number` es NULL, porque `customer_id` ya no existe).
- `emitir_factura_global` (sector público) falla explícito si el cliente no tiene ID.

**Cambios (POS):**
- **Nuevo** `src/lib/utils/id-validation.ts` (espejo del backend) + 36 tests.
  `SaleWizard` y `new-dispatch` ahora validan **checksum con mensaje en pantalla**,
  antes de buscar.
- **Paso Cliente bloqueado**: si el dueño/preferencial/cliente cargado no tiene
  identificación válida, se muestra banner rojo y **“✓ Correcto” queda deshabilitado**;
  el único camino es **“🪪 Ingresar identificación”** (nuevo paso `captureId`), que
  vuelve a pedir el número y hace `PUT /api/pos/persons/{id}`.
- `lookupPerson`, `registerCustomer`, `updatePerson`, `updateDispatchBilling` ahora
  muestran el **`detail` real del backend** (antes un mensaje genérico).
- Aviso visible cuando el proveedor está caído (“no se pudo verificar…”).

**Limpieza de datos:** `scripts/limpiar_ids_invalidos.py` — dry-run por defecto;
`--apply` escribe y primero respalda en `persons_invalid_id_backup`.
Detecta **198 clientes** (182 cédulas inválidas + 16 RUC inexistentes en el SRI).
⚠️ **NO ejecutado**: pendiente de aprobación.

**Tests:** pos_backend **536 passed** (era 461). POS: **77 passed** (era 41) +
`svelte-check` 0 errores.

### ⏳ Pendientes inmediatos (v0.38.0)
- [x] **Ejecutado 2026-09-13**: `scripts/limpiar_ids_invalidos.py --apply` → **198 clientes**
  quedaron sin identificación (`id_number = NULL`). Respaldo: `/tmp/ids_invalidos_backup_20260914_023929.csv`
  (198 filas con `person_id, id_type, old_id_number, name, reason`).
  ⚠️ El respaldo en tabla **no** se pudo hacer: `agent_llm` no tiene `CREATE` en `public` → el
  script ahora **respalda a CSV siempre** (y avisa si la tabla falla).
  Consecuencia esperada: en el próximo despacho de esos clientes el POS mostrará ⛔ y pedirá
  la cédula (paso 4f). 2 de ellos (ROMUALDO ONCE, CARLOS CARDENAS) **no tienen vehículo** →
  hay que buscarlos con la pestaña **“Por Nombre”**.
- Re-emitir las **7 facturas del 09-13** → ✅ **HECHO**: reasignadas a AURACORE SOLUCIONES SAS
  (`person_id 10472`, RUC `0195160252001`) y PATRICIO VALAREZO (`person_id 3750`) y emitidas
  al SRI (7/7 autorizadas, $76.45). Ver commit de docs y memoria.
- Queda pendiente el **backlog de 23 facturas** de junio/julio ($418.76) — decisión fiscal.
- **Sercobaco caído**: escalar el contrato (`No existe un contrato activo`).

---

### ⚙️ PENDIENTE — Nada reintenta las facturas “nunca enviadas”

**Detectado el 2026-09-13** al revisar el comprobante `003-501-000004859`
(orden `OV-20260913124828-174`, dispatch 21031), que estuvo **7 horas pegado** en
`PENDING` con el mensaje *“Key49 no disponible — se reintentará”*.

**Causa raíz:** el reintento de esas filas existe (`retry_pending_invoices`) pero
**ningún scheduler lo llama**. El único loop de fondo (`sri_sync_service`, cada 120 s)
**solo lee** Key49 y **solo** para despachos que **ya tienen** `key49_invoice_id`. Un
`PENDING` **sin** `key49_invoice_id` no lo toca nadie.

> El docstring de `retry_pending_invoices` dice *“Called periodically by the
> scheduler”* — **ese scheduler no existe.** Solo es alcanzable por HTTP
> (`POST /api/pos/dispatches/retry-pending-invoices`, ADMIN/SUPERVISOR).

**Solución propuesta:** que `run_sri_sync_loop` llame también a
`retry_pending_invoices()` una vez por ciclo (o cada N ciclos), envuelto en
`try/except` y respetando `key49_enabled`. ~30 min con test.

**Backlog actual (2026-09-13, verificado): 23 facturas nunca enviadas, $418.76**
(15 de junio + 8 de julio, todas con identificación **válida** — **ninguna fue por
cédula/RUC**). `sri_messages` de todas: `"Referencia Key49 inexistente (404) — se
reemitirá"` → quedaron marcadas para reemisión durante la recuperación del 11/12-09 y
**nadie las reemitió**. Se pueden rescatar con la Opción D del SOP (el script regenera
la clave con la fecha de hoy), pero **cambia la fecha del comprobante → decisión fiscal**.
Además hay **140 despachos de GAD PAUTE** que van por **factura global**, no por aquí.

---

### 🔴 PENDIENTE PRÓXIMA SESIÓN — Extranjeros sin cédula ni RUC (no tienen dónde pasar)

**Descubierto el 2026-09-13 al revisar el caso de los 198 IDs inválidos.** El bloqueo de
identificación (v0.38.0) deja a un extranjero **sin ningún documento ecuatoriano** sin
forma de cargar combustible: el POS exige Cédula o RUC y no hay pasaporte.

**Estado actual (verificado):**

| Punto | Hallazgo |
|---|---|
| POS | Solo pestañas **Cédula** y **RUC**. Nunca hubo Pasaporte |
| `persons.id_type` | `varchar(5)` → **no cabe** "PASAPORTE" |
| `persons.id_number` | `varchar(13)` — un pasaporte puede ser más largo |
| Datos reales | 9.463 clientes: 7.373 CED + 2.090 RUC, **cero pasaportes** en toda la historia |
| `id_validation.py` | Rechaza todo lo que no sea CED/RUC: *"Tipo de identificación no soportado"* |
| `key49_service.ID_TYPE_MAP` | **Ya tiene** `PASAPORTE → 06` (quedó previsto, nunca se cableó) |
| Puntos de emisión | Solo `doc_type = FACTURA`. **No existe nota de venta** |
| Key49 (guía del proyecto, línea 195 y 927) | `04=RUC, 05=Cédula, 06=Pasaporte, 07=Consumidor Final`; si `id_type=07` el id debe ser `9999999999999` y **esas facturas no se pueden anular** |

**Qué cambió con v0.38.0:** antes el despachador **inventaba** una cédula (10 dígitos al
azar) y la venta pasaba perdiendo la factura — de ahí parte de los 198 IDs basura
(nombres “Mono”, “Rfv”, “Ghv”). Ahora eso se **bloquea en el mostrador** con un mensaje
claro. Es más honesto, pero el turista se queda sin cargar.

> Matiz: un **residente extranjero con cédula ecuatoriana** funciona normal (tiene dígito
> verificador). Solo queda fuera quien no tiene **ningún** documento ecuatoriano.

**Opciones (decidir con el dueño antes de codificar):**

- **A) Pasaporte (SRI 06) — recomendada**
  - Validación: **sin dígito verificador**; solo formato alfanumérico (5–15).
  - `persons.id_type`: usar código `PAS` (cabe en varchar(5)) **o** ampliar la columna.
  - `persons.id_number`: ampliar a `varchar(20)`.
  - UI: tercera pestaña “Pasaporte” en los mismos puntos que Cédula/RUC.
  - Mapear `PAS → 06` en `ID_TYPE_MAP`.
  - Migración + tests: ~1,5–2 h.
  - **Validar antes:** que Key49/SRI acepten pasaporte en una factura de combustible
    (probar en el ambiente de pruebas de Key49 o con una venta real).
- **B) Consumidor Final (SRI 07, `id=9999999999999`)** — cubre a cualquier anónimo, ya
  soportado por Key49 según la guía; **pero** se eliminó a propósito en la Fase 7 y esas
  facturas **no se pueden anular**. Decisión fiscal, no técnica.
- **C) Identificación del exterior (SRI 08)** — la guía del proyecto **no** lo lista
  (solo 04/05/06/07); habría que confirmar con Key49 si lo acepta.

**Antes de codificar:** contar cuántos extranjeros sin documento ecuatoriano se atienden
por semana. Si es ~0, basta con el bloqueo explícito actual; si es frecuente, urge la
opción A.

---

## Estado anterior (2026-09-12) — v0.37.3

### ✅ Fix: ventas anónimas — se exige cliente y no se pierde la placa (v0.37.3)
- **Problema:** 9 despachos `SALE` se crearon sin `person_id` **ni** `vehicle_id` y
  luego fallaron con `Datos insuficientes para factura electrónica`.
- **Causa raíz (2 bugs):**
  1. `dispatch_types.requires_customer = true` para `SALE`, pero el backend **nunca
     lo validaba** en `POST /api/pos/dispatches`.
  2. Si llegaba una `plate` cuyo vehículo no existía y no había `customer_id`, la
     placa **se descartaba en silencio** (`dispatches.py`).
- **Fix:**
  1. **Se valida `requires_customer`.** Si falta el cliente → `422` con mensaje
     claro. Si el `customer_id` no existe → `404`. Si el cliente está inactivo →
     `422` (se usa 422 y no 409 porque el POS mapea todo 409 al mensaje de
     "dispensador en curso").
  2. **Nueva columna `dispatches.plate_raw`** (migración `4b5c6d7e8f90`): la placa
     se guarda **siempre**, aunque no exista el vehículo. Se usa como fallback en
     ticket/recibo, despachos activos, historial y `_get_plate` de Key49.
- **POS:** `new-dispatch` ahora muestra el mensaje real del backend (antes era
  genérico), consistente con `SaleWizard`.
- **Tests:** pos_backend **461 passed** (+5 nuevos: sin cliente, cliente
  inexistente, cliente inactivo, `plate_raw` con vehículo desconocido, CALIBRATION
  anónimo con placa). POS: `npm run check` 0 errores + 41/41 tests.
- **Migración verificada**: `alembic upgrade head` + `downgrade`/`upgrade` OK en dev.
- **Ojo al desplegar:** el deploy corre Alembic (columna aditiva, nullable).

### ⏳ Pendientes (del análisis B)
- **183 `FAILED`** históricos por cédula/RUC inválido (0 auto-recuperables).
  Excel de trabajo para completar datos: `/tmp/backlog_facturas_failed_2026-09-12.xlsx`
  y por cliente: `/tmp/clientes_facturas_con_problema_2026-09-12.xlsx`.
- **9 facturas sin cliente** (Fernando Calle) — irrecuperables desde datos; solo
  ticket físico. Con este fix no vuelve a pasar.
- ~~**228 clientes activos con ID inválido** → falta validar el dígito verificador
  módulo 10/11 al crear/editar cliente~~ → **RESUELTO en v0.38.0** (validación +
  nulabilidad + script de limpieza con respaldo).
- **Sercobaco (cédulas) caído**: `"No existe un contrato activo"` → escalar contrato.

---

## Estado anterior (2026-09-12) — v0.37.2

### 🔴 Incidente Key49 (ambiente PRUEBAS) — DIAGNOSTICADO Y RESUELTO
- **Síntoma:** en Key49 aparecía el error SRI 35 `ARCHIVO NO CUMPLE ESTRUCTURA XML`
  con `additional_info: "El ambiente de la solicitud PRODUCCIÓN no coincide con el
  de ejecución PRUEBAS"`. Ejemplo: factura `003-501-000004663` (dispatch `20705`).
- **Causa raíz:** el **tenant de Key49 estuvo en ambiente PRUEBAS** en ventanas del
  09-11 (~22:43–23:15) y 09-12 (~01:24–07:54) (+2 casos aislados el 09-11). Nuestro
  lado siempre envió correctamente (`company_info.sri_environment=2`, todas las
  access keys con dígito de ambiente `2`). El ambiente lo define el **tenant** de
  Key49, no el API key. Se corrigió solo desde 09-12 ~08:00. **No era bug nuestro.**
- **Evidencia clave:** Key49 **no expone `sri_messages` por API** para estos
  rechazos (llega `[]`), aunque su UI sí muestra el motivo; los docs en `RETRY`
  (retry_count 4-5) sí se reintentan y terminan `NOTIFIED`; el error 35 no.
- **Recuperación:**
  1. Sync de 29 docs stale (27 → `NOTIFIED`, 2 → `REJECTED`).
  2. Key49 reprocesó los rechazados desde su UI.
  3. Re-sync de 39 docs (34 `REJECTED` + 4 `FAILED` + 1 `RECEIVED`) → **todos
     `NOTIFIED`**. Verificado: 0 docs con `key49_invoice_id` en estado no-final.

### ✅ Fix: reconciler SRI cubre TODOS los estados no-finales (v0.37.2)
- **Problema:** `sri_sync_service.py` (cada 120s, `sri_sync_enabled=true`) solo
  tomaba `sri_status='PENDING'`. Cuando Key49 pasaba a `NOTIFIED` estando local en
  `RETRY`/`RECEIVED`/`FAILED`, **nunca se sincronizaba** → 27 docs quedaron stale.
- **Fix:** ahora reconcilia cualquier estado no-final con `key49_invoice_id`
  (incluye `REJECTED`/`FAILED`, para captar un reproceso de Key49).
- **Seguridad:**
  - Sigue siendo **solo lectura** sobre Key49 y **nunca reemite** (no llama a
    `emitir_factura`). No toca el flujo de venta.
  - Cooldown en memoria (`STALLED_RECHECK_SECONDS=3600`): los `REJECTED`/`FAILED`
    se re-consultan máximo 1 vez por hora (evita martillar el rate limit de Key49).
  - Omite el commit si el estado no cambió.
- **Tests:** `tests/test_sri_sync_service.py` 11 tests (era 4). Suite completa:
  **456 passed**. Verificado contra prod: el reconciler **no tiene filas que tocar** hoy.

### ⏳ Pendientes (NUEVOS, separados del incidente)
- **183 despachos `FAILED`** históricos por `Invalid identification for type 04/05`
  (cédula/RUC inválido) + algunos `Datos insuficientes`. Requieren corregir el dato
  del cliente y reemitir. 8 son ≥ 09-10.
- **23 `PENDING` sin `key49_invoice_id`** (15 de 2026-06, 8 de 2026-07) — backlog viejo.
- Mejora opcional: usar `updated_at` de Key49 como `sri_authorization_date` para los
  sincronizados (hoy queda con la hora del sync → infla el KPI "tiempo a autorización").

---

## Estado anterior (2026-09-11) — v0.36.0

### ✨ Nuevo: Módulo Monitoreo SRI/Key49 en Admin (Fase 1 — solo lectura)
- Sección **"Facturación SRI"** (`/sri`) en Admin, con pestañas **Resumen** y
  **Documentos**. Ver `docs/admin/SRI_MONITOR.md`.
- Resumen: KPIs (total, autorizados +% éxito, en proceso, con problemas, tiempo
  a autorización), emisiones por día, problemas por tipo y salud de Key49.
- Documentos: bandeja filtrable (estado, tipo de problema, búsqueda, rango) con
  **export PDF/Excel**.
- Taxonomía de problemas: `NEVER_SENT`, `PENDING_SENT`, `KEY49_FAILED`,
  `INVALID_DATA`, `REJECTED`, `IN_PROGRESS`, `OK`.
- **Feature flag `sri_monitor_enabled`** (default **off**) → el módulo no ejecuta
  consultas hasta activarlo. Activar con
  `PUT /api/admin/system-config/sri_monitor_enabled` `{"value":"true"}`.
- **No invasivo**: 100% aditivo, no toca el flujo de venta ni el POS.
- Tests: **445 passed** (13 nuevos). `admin npm run check` y `build` OK.
- **Fases 2/3 pendientes**: acciones (sync/reproceso en lote, jobs+auditoría) y
  scheduler automático opt-in. Reproceso con cambio de fecha: solo ADMIN, caso
  por caso. `KEY49_FAILED` sigue siendo manual en Key49.

---

## Estado anterior (2026-09-11) — v0.35.7

### 🔴 Incidente Key49 PLAN_EXPIRED (03→11 sep) — RESUELTO
- **Síntoma reportado:** "los Campos Adicionales no llegan" en producción.
- **Realidad:** NO se emitía ninguna factura nueva desde **2026-09-03 15:37**.
- **Causa raíz:** Key49 respondía `HTTP 402` con body
  `{"error":{"code":"PLAN_EXPIRED","message":"Plan expirado"}}`.
  El backend **descartaba el body** y guardaba solo `"Key49 HTTP 402"`, ocultando
  la causa (1.427 despachos afectados).
- **Diagnóstico:** `/tmp/k49_probe.py` arma el payload real con
  `_build_invoice_payload` (BD prod, solo lectura) y hace POST directo a Key49
  mostrando status + headers + body. Probado **con y sin** `RUC Proveedor` → mismo
  `402 PLAN_EXPIRED`. El campo nunca fue el problema.
- **Resolución:** Key49 renovó el plan. Reenvío real del despacho `20458` vía
  `emitir_factura` → `NOTIFIED` (key49_invoice_id `054239f8-…`). XML del SRI confirma:
  `<campoAdicional nombre="RUC Proveedor">0190411826001</campoAdicional>`.
- **Fix:** `_key49_error_message()` captura `code` + `message` + `details`
  (cap 500 chars, columna `sri_messages`) en `emitir_factura` y
  `emitir_factura_global`. 6 tests nuevos en `test_key49_error_message.py`.

### ⏳ Pendiente: recuperación de facturas PENDING (clasificadas)
El conjunto PENDING **no es homogéneo**. Clasificación real (excluye `CANCELLED` y
`PENDING_BULK_INVOICE`):
- **588 ya están en Key49** (`key49_invoice_id` presente) → el estado en nuestra BD
  está desactualizado. **Solo sincronizar** (NO reemitir: duplicaría).
- **1.441 sin factura** → reemitir. Desglose: `2026-07`: 7, `2026-08`: 3,
  `2026-09`: 1.431 (la cola del PLAN_EXPIRED).
- **140 `PENDING_BULK_INVOICE`** (julio, sector público/GAD) → van por factura
  **global**, no individual. Excluidos del script.

Herramienta: `pos_backend/scripts/recover_pending_invoices.py` (DRY-RUN por defecto,
reconciliación contra Key49 por `key49_invoice_id` y `?access_key=`, lotes con
`--limit`, ritmo con `--delay`, modos `--classify-only` / `--sync-existing`).
Regenera el `access_key` con fecha de HOY porque el SRI rechaza fechas pasadas.

Flujo recomendado: `--classify-only` → `--limit 5` (dry-run) → `--limit 5 --execute`
→ `--sync-existing --execute` → crecer lotes.

⚠️ **Requiere aprobación explícita antes de ejecutar en prod** (decisión fiscal:
facturas de ventas de días anteriores quedarían emitidas con fecha de hoy).

---

## Estado anterior (2026-08-20) — v0.35.6

### ✅ Logros de la sesión (20-ago-2026)

#### Fix: reimpresión de ticket respeta fecha/hora del despacho ✅
- Bug: al reimprimir desde Historial, el ticket usaba la fecha/hora del momento de reimprimir
  (`new Date()`) en vez de la fecha/hora original del despacho.
- Fix: `handleReprint()` usa `order.created_at` (el mismo valor que muestra el historial),
  con fallback a hora actual si viniera vacío.
- Mismo patrón corregido en `reprintClose()`: usa `raw.closed_at` (fecha real del cierre).
- Archivo: `pos/src/routes/(pos)/history/+page.svelte`
- Validación: `npm run check` 0 errores + tests 41/41 ✅
- Deploy: `./scripts/deploy-to-server.sh frontend` + `powerfin-gas deploy-frontend`

#### Deploy: 2 IPs de acceso (Tailscale + LAN oficina) ✅
- `deploy-to-server.sh`: default Tailscale `app@100.97.47.123`;
  `./scripts/deploy-to-server.sh <target> local` → LAN `app@192.168.1.25`
- Check de conectividad previo con hint claro si Tailscale está caído
- `docs/DEPLOY_QUICK.md` actualizado con ambas rutas

---

### ✅ Logros de la sesión (05-ago-2026)

#### Fix: SaleWizard — rebote en pantalla de cobro ✅
- Bug: al cobrar con tarjeta/transferencia (requiere comprobante), el botón "Grabar"
  causaba un rebote visual — `confirmed = true` antes del API, luego `false` si fallaba.
- Fix: nuevo estado `collecting` con spinner "⏳ Procesando...", `confirmed` solo tras éxito.
- Botones deshabilitados durante `collecting` para prevenir doble-click.
- Archivo: `pos/src/lib/components/SaleWizard.svelte`
- Deploy: `./scripts/deploy-to-server.sh frontend` + `powerfin-gas deploy-frontend`

#### SRI/Key49 — reconciliación manual ✅
- 34 despachos NOTIFIED verificados uno por uno contra API Key49: todos presentes
- 4 PENDING (polling timeout) actualizados a NOTIFIED con fechas reales
- Resultado: 42 cobrados, 100% enviados a Key49, 0 perdidos

#### Intervenciones manuales en PROD ✅
- Despacho #12450: $62.04 DIESEL recreado (MINERA PIRINCAY) — perdido por corte de energía + cleanup
- Pagos corregidos: #12440 ($26.00) y #12427 ($100.00) de EFECTIVO → TARJETA CREDITO/DEBITO
- 4 PENDING → NOTIFIED sincronizados con Key49

#### Nuevo: Medidores mecánicos (mechanical meters) ✅
- Modelo, API admin CRUD, lecturas vinculadas a turnos
- Páginas POS: captura de lecturas al abrir/cerrar turno
- 2 migraciones Alembic, tests dedicados

#### CODE_REVIEW_FINDINGS.md generado ✅
- Revisión por 4 módulos (pos_backend, fusion-bridge, pos/, admin/)
- 26 hallazgos: 8🔴 alta, 9🟡 media, 9🟢 baja
- Ver documento para detalle completo

---

### ✅ Logros de la sesión (20-jul-2026)

#### Fix: Admin Dashboard — gráficas mensuales sin datos de otros meses ✅
- Bug: pestaña "Mensual", gráficas "Ventas por Día" y "Galones por Día"
  solo mostraban el mes seleccionado; previous/next no aparecían
- Causa: `ComparisonChart.svelte` comparaba etiquetas con nombre de mes
  (`"17 Jun"` vs `"17 Jul"` → null)
- Fix: en modo `monthly`, alineación por número de día; `allLabels` desde
  cualquier dataset (no solo `current`)
- Archivo: `admin/src/lib/components/dashboard/ComparisonChart.svelte`
- Pendiente: deploy a PROD (`./scripts/deploy-to-server.sh admin`)

#### DB_ACCESS.md — IPs duales ✅
- IP principal: `100.97.47.123` (Tailscale, siempre disponible)
- IP respaldo: `192.168.1.25` (LAN, solo oficina)

#### Limpieza: docs/NEXT_SESION.md ✅
- Eliminado — duplicado con typo, desactualizado (v0.23.1)

---

### ✅ Logros de la sesión (19-jul-2026)

#### Fix: close shift guard para despachos sin cobrar ✅
- Bug: turno #130 (Alex Chiriap) cerrado con despacho #7949 sin cobrar → dispensador 2-B bloqueado
- Causa: `close_shift` no validaba despachos COMPLETED pendientes
- Fix: guard en `pos_backend/app/api/shifts.py` — bloquea cierre si hay ≥1 COMPLETED
- Intervención manual: despacho #7949 movido a turno 131 + payment insertado
- Tests: 16/16 ✅

---

### ✅ Logros de la sesión anterior (14-jul-2026)

#### SRI/Key49 — limpieza masiva de facturas electrónicas ✅
- 268 despachos regularizados (polling timeout + Key49 offline + datos inválidos)
- $6,249 en facturas ahora autorizadas por el SRI
- 43 cédulas corregidas (dígito verificador) + búsqueda vía API Sercobaco
- 16 RUCs corregidos con datos reales de clientes
- 4 REJECTED reasignados a GRISBI y enviados
- 1 CONSUMIDOR FINAL → eliminado (no aplica en gasolineras)
- Resultado final: 381 problemas → 0 accionables

#### Fix: PENDING_BULK_INVOICE no consume secuenciales ✅
- Bug: despachos de contratos NO_INDEFINIDO consumían secuenciales al crearse
- Causa: credit_status no se seteaba sin product_id → guard no funcionaba
- Fix: resolver contract_type antes del sequential guard
- 53 secuenciales quemados → vueltos a NULL

#### POS: Resumen de Turno en módulo Caja ✅
- Nueva página `/cash/summary` con desglose completo
- Efectivo, tarjeta, crédito, movimientos, resultado neto
- Botón "📊 Resumen de Turno" en pantalla de Caja
- Backend: `CashSummaryResponse.non_cash_sales` agregado

#### 🔥 Hotfix: dispatch cleanup race condition — incidente MINERA PIRINCAY ✅
- Despacho fantasma localizado en logs FusionBridge: 168.425 gal DIESEL = $539.63
- Despacho #6749 reconstruido en BD (CANCELLED → COMPLETED, $539.63)
- **Fix #1**: cleanup verifica pump status vía FusionBridge antes de cancelar
- **Fix #2**: threshold progresivo — FULL=1800s (30min), MONEY/VOLUME=900s (15min)
- **Fix #3**: completeDispatch reactiva CANCELLED con fuel real + guard anti-colisión
- Auditoría completa: `docs/DISPATCH_AUDIT.md` — 40 guardias mapeadas
- Tests: 404/404 ✅ (7 cleanup tests, 2 nuevos para FULL preset)
- Deploy a producción exitoso

#### Despachos a crédito — sector público + contratos ✅
- `PENDING_BULK_INVOICE` credit_status para contratos NO_INDEFINIDO
- Factura global / liquidación para sector público
- Migraciones: plate 15 chars, PENDING_BULK_INVOICE constraint
- Admin: módulo contracts (listado + liquidación)
- 48 despachos GAD PAUTE vinculados al contrato IC-GADMCP-00049-2026

#### Cleanup automático de despachos huérfanos ✅ (v0.35.0)
- Servicio `dispatch_cleanup.py`: cada 60s cancela AUTHORIZED + $0.00
- Endpoints: `GET /orphans`, `POST /cleanup-orphans`
- 5 tests dedicados
- ⚠️ v0.35.1: thresholds progresivos + verificación pump status

#### Ticket de crédito con firma ✅
- `contractCode` en receipt data (backend → FusionBridge)
- Bloque condicional `{#credit}` en template ESC/POS
- Línea de firma: FIRMA / RECIBIDO POR / CEDULA
- Reimpresión desde Historial incluye `contract_code`

#### Admin Reportes — mejoras ✅
- Columna **Efectivo Actual** en turnos (fórmula: apertura + ventas + ingresos − egresos − depósitos)
- Columnas **Turno**, **Usuario**, **Contrato** en reporte de ventas
- **Galones** en export de ventas
- Formato de fechas corregido (zona horaria Ecuador, UTC-5)
- Formato de moneda en DataTable

#### Bugfixes ✅
- `powerfin-gas`: auto-run alembic migrations on backend deploy
- `powerfin-gas`: chown preventivo antes de builds
- Método de pago crédito: buscar por prefijo `CREDIT` en vez de hardcodear `CREDITO`
- DB: plate VARCHAR(15), credit_status constraint actualizado
- Zona horaria Ecuador en exports (`.astimezone(ECUADOR_TZ)`)

#### Intervenciones manuales en BD
- 48 despachos GAD PAUTE → contrato #3, PENDING_BULK_INVOICE
- #6447: COMPLETED $10.00 → CANCELLED (turno cerrado)
- #6517: restaurado COMPLETED $102.28 (cancelado durante carga)
- #6573: restaurado COMPLETED $57.00 (cancelado por cleanup)
- #6623: cobrado manual (payment_method_id=0 bug)

### 🆕 Próximas tareas

```
🔴 ☐ 0. CODE_REVIEW — Revisar y resolver CODE_REVIEW_FINDINGS.md
   · 26 hallazgos: 8 alta prioridad, 9 media, 9 baja
   · Revisar uno por uno, marcar [x] al resolver o documentar decisión
   · Prioridad #1: posible doble conexión TCP en FusionBridge
   · Prioridad #2: secuencial fiscal se pierde en silencio
   · Prioridad #3: facturación SRI en background sin logging
   · Prioridad #4: token/credenciales hardcodeadas en identity_service.py
   · Prioridad #5: lógica de reactivación duplicada en dispatches.py
   · Prioridad #6: SaleWizard.svelte con lógica de negocio (refactorizar)
   · Ver documento completo: CODE_REVIEW_FINDINGS.md

🔴 ☐ 1. DEPLOY — Subir v0.35.5 a PROD
   · ./scripts/deploy-to-server.sh frontend  (fix rebote cobro)
   · ./scripts/deploy-to-server.sh all        (medidores mecánicos + resto)
   · ssh app@192.168.1.25 'powerfin-gas deploy-all'
   · powerfin-gas status

☐ 2. POS — Mejorar UI del flujo de crédito
   · Pantalla de búsqueda: simplificar botones (muchos causan confusión)
   · Indicador visual persistente de "modo crédito" durante todo el flujo
   · El despachador debe saber en cada paso si está en venta normal o crédito
   · Revisar: botón "Usar crédito del contrato", "No, venta normal", etc.

☐ 2. Admin — sección "Despachos con problemas"
   · Listar despachos en estados anómalos (AUTHORIZED $0.00, COMPLETED sin cobrar)
   · Botones de acción: Cancelar huérfano, Restaurar, Forzar completado
   · Solo ADMIN/SUPERVISOR — evitar intervención SQL manual

☐ 4. Admin — modificar precios de Lista de Precios
   · Pantalla price-lists/[id]: editar unit_price inline en la tabla de items

☐ 5. credit_contracts — agregar payment_method_id
   · Cada contrato sabe con qué método se cobra (sin buscar por código)

☐ 6. Precios programados — cambio automático a las 00:00 horas

☐ 7. Pago mixto (efectivo + tarjeta)
☐ 8. identity_service.py — mover URL y token a system_config
☐ 9. Nginx rate limiting login
```

---

## Configuración del sitio

| Dato | Valor |
|------|-------|
| Estación | NEOGAS |
| Surtidores | 4: 1 SUPER-ECO, 2 ECO, 3 DIESEL, 4 DIESEL |
| ATO Wayne | 180s (próximo cambio a 300s) |
| Cleanup FULL | 1800s (30 min) |
| Cleanup MONEY/VOLUME | 900s (15 min) |
| Cleanup IDLE (empty tank) | 120s (2 min) |
| Contratos | INDEFINIDO (GRISBI), NO_INDEFINIDO (GAD PAUTE) |

## Base de datos

| Dato | Valor |
|------|-------|
| Host (Tailscale) | 100.97.47.123:5432 |
| Host (LAN) | 192.168.1.25:5432 |
| Database | powerfin_gas |
| User (lectura) | agent_llm / AgentLLM123 |
| Ver | docs/DB_ACCESS.md |

## Lecciones aprendidas

- **NUNCA poner `confirmed = true` antes de que el API responda.** Usar un estado
  intermedio (`collecting`, `loading`) para feedback visual. El rebote `true→false`
  confunde al usuario y oculta el mensaje de error.
- **NUNCA cancelar AUTHORIZED $0.00 sin verificar si el surtidor está cargando.**
- **El cleanup service ahora verifica el pump status vía FusionBridge** antes de cancelar.
- **FULL presets (tanqueros) tienen 30 min de threshold** — no 15 min como antes.
- **completeDispatch/reactivate protege contra pérdida de datos** si un cleanup cancela prematuramente.
- **Siempre verificar logs de FusionBridge** (`journalctl -u fusion-bridge`) ante despachos sospechosos.
- **payment_method codes cambian entre entornos** — no hardcodear.
- **Las migraciones Alembic requieren `powerfin-gas migrate-db`** si no se usa auto.
- **`.svelte-kit/output` y `build/` pueden quedar con permisos de root`** — chown preventivo.
