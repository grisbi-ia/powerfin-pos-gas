# PROGRESS.md — Powerfin POS · Historial cronológico de cambios

> Última actualización: **2026-09-18** · Rama: `main` · HEAD: `v0.39.2`

---

## v0.39.2 (2026-09-18) — Monitor SRI: solo despachos `COLLECTED`

- **Problema**: el monitor contaba despachos `AUTHORIZED` (ventas en curso) con
  `sri_status='PENDING'` como `NEVER_SENT`, y también algún `CANCELLED` con PENDING.
- **Fix**: `sri_monitor_service._base_conditions()` (antes `_date_conditions`) exige
  `status='COLLECTED'`; mismo filtro en el query de salud de Key49 (últimas 24 h).
- **Impacto medido (30 días)**: 1 `CANCELLED` fantasma + los `AUTHORIZED` transitorios.
  El ruido grande (“75 problemas” vs 4 reales en Key49) era el lote de **GAD Paute**
  (`COLLECTED` + `PENDING`), ya reconciliado a `AUTHORIZED`.
- **Tests**: +2 en `tests/test_admin_sri.py` (`AUTHORIZED` no cuenta en métricas ni
  documentos). Suite backend **547 passed** (era 545).

---

## v0.39.1 (2026-09-18) — Fix: el retry facturaba ventas en curso (solo `COLLECTED`)

### Incidente detectado tras desplegar v0.39.0
- Al revisar el deploy apareció el dispatch **22295**: recién creado, `status=AUTHORIZED`
  (venta **en curso**, aún sin despachar ni cobrar), `total=0.00`, pero `sri_status=PENDING`.
- **Causa**: `create_dispatch` nunca setea `sri_status`, así que el default del modelo
  (`PENDING`) aplica desde que se autoriza el despacho. El retry de v0.39.0 filtraba
  `status != 'CANCELLED'` → habría facturado esa venta en curso (incluso $0.00).
- **Sin daño**: 0 despachos `AUTHORIZED` con `key49_invoice_id`; todas las facturas del
  día eran `COLLECTED`.

### Mitigación inmediata (prod)
- Kill switch `system_config['sri_retry_enabled'] = 'false'` → el loop queda inerte.

### Fix (v0.39.1)
- `retry_pending_invoices()` ahora exige **`status == 'COLLECTED'`** (solo ventas
  cobradas son facturables) y una **edad mínima** `RETRY_MIN_AGE_SECONDS = 120` para no
  competir con la emisión viva post-cobro.
- Mismo guard en `scripts/recover_pending_invoices.py` (reemisión manual).

### Tests
- `tests/test_retry_pending_invoices.py`: 9 (2 nuevos: `AUTHORIZED` no se reintenta;
  `COLLECTED` demasiado joven se omite). Suite backend **545 passed** (era 543).

### Post-deploy
- Volver a habilitar el reintento: `UPDATE system_config SET value='true' WHERE key='sri_retry_enabled';`
  (o borrar la key para usar el default on).

---

## v0.39.0 (2026-09-18) — Reintento automático de facturas “nunca enviadas”

### Problema que lo motivó
- El 2026-09-17 quedaron **3 facturas `PENDING` sin `key49_invoice_id`** ($16,79),
  todas cobradas, con el mensaje `"Key49 no disponible — se reintentará"`.
- **Motivo real**: error de red transitorio al POSTear a Key49 (`TerminalOutOfService`:
  `ConnectError`/`TimeoutException`/`RemoteProtocolError`/`ReadError`). Aislado: las
  ventas de segundos antes/después sí se enviaron. No fue caída de Key49 ni dato inválido.
- **Nadie las reintentaba** y, además, el reintento existente estaba roto (ver abajo).

### Prueba que fijó la regla
- Reenvío del dispatch **22073** con su `access_key` original (`17092026…`, 17-09) y
  `issue_date` forzado a 2026-09-17 → Key49 responde:
  `HTTP 400 VALIDATION_ERROR — {"field":"issue_date","message":"Must be today's date (2026-09-18)","code":"INVALID_ISSUE_DATE"}`.
- **Conclusión**: reenviar sin cambiar la fecha es imposible; hay que regenerar la clave.
  Herramienta de verificación: `scripts/resend_pending_original_date.py` (dry-run por defecto).

### Cambios en `pos_backend`
- **Nuevo loop de fondo** `run_sri_retry_loop()` (`app/services/key49_service.py`, cada 300 s),
  arrancado desde `main.py` (no en tests) y apagado en shutdown. Separado del reconciler
  de solo lectura (`sri_sync_service`).
- **`retry_pending_invoices()` reescrito**:
  - **Regenera la clave de acceso con la fecha de hoy** cuando la guardada no es de hoy
    (mismo secuencial; la factura nunca fue aceptada). Helper `access_key_is_for_today()`.
  - **Cutoff configurable** `sri_retry_max_age_hours` (default 72 h; 0 = sin límite). Las
    más viejas se dejan `PENDING` para reemisión manual — antes se marcaban
    `FAILED "Vencida"` y se perdían.
  - **Bug de filtro corregido**: `credit_status != 'PENDING_BULK_INVOICE'` descartaba en
    SQL toda fila con `credit_status NULL` (todas las ventas normales) → ahora
    `IS DISTINCT FROM`, igual que el script de recuperación y el monitor.
  - **Lock de proceso** (`asyncio.Lock`) para que el loop y el endpoint HTTP no emitan
    la misma factura dos veces.
  - Devuelve `{retried, regenerated, expired, skipped, failed}`.
- **Gates**: `sri_retry_enabled` (default on) y `key49_enabled`.

### Intervención en PROD (2026-09-18)
- Reenvío de las **3 facturas del 17** con `recover_pending_invoices.py --min-age-hours 0
  --execute` → 3/3 finales (1 `AUTHORIZED` + 2 `NOTIFIED`), claves regeneradas a hoy
  (`18092026…`). Día 17–18: **0 pendientes**.
- **Verificado** `dispatch 20500` → `NOTIFIED` (el reconciler lo cerró el 09-13 22:28).
- **Limpiado** el RUC temporal de `person_id 10404` (`id_number = NULL`).

### Tests
- Nuevo `tests/test_retry_pending_invoices.py` (7 tests): clave del mismo día sin
  regenerar, cruce de medianoche regenera, >72 h se deja `PENDING`, fallo de
  regeneración visible, filas con id de Key49 se omiten, gates desactivados.
- **543 passed** (era 536). Sin cambios en `pos/`, `admin/` ni `fusion-bridge/`.

---

## v0.38.0 (2026-09-13) — Validación de cédula/RUC + el POS obliga a re-pedir la identificación

### Incidente que lo motivó
- El 2026-09-13 se perdieron **7 facturas** ($76.45): `Key49 HTTP 400 — Invalid
  identification for type 05`, **después** de haber despachado y cobrado. Los 6 clientes
  tenían cédula con **dígito verificador inválido**.
- Causa raíz en 3 capas: (1) **Sercobaco caído** (`No existe un contrato activo` desde el
  09-12) → el POS no podía verificar ninguna cédula; (2) `GET /api/pos/persons/lookup` se
  tragaba el error y caía al **registro manual sin aviso**; (3) **nadie validaba el dígito
  verificador** — el POS solo miraba la longitud y el backend nada. Además ya había 198
  clientes con ID inválido registrado, que al buscarse devolvían `found:true`.

### Reglas derivadas con datos reales (no de teoría)
| Tipo | Regla | ¿Bloquea? |
|---|---|---|
| Cédula | módulo 10 (provincia 01-24 y 30) | **Sí** — es exactamente lo que aplica Key49. 3.743 IDs ya aceptados por el SRI → **0 falsos negativos** |
| RUC natural (3er dígito 0-5) | cédula módulo 10 + `001` | **Sí** — 637/637 RUC naturales aceptados lo cumplen |
| RUC jurídica (9) / pública (6) | **solo estructura** | **No** — el módulo 11 del RUC **no es confiable**: el registro del SRI tiene RUC que lo fallan y facturan normal (CLICK SOLUCIONES `1793200847001`), y el sistema lineal sobre 90 RUC confirmados es **inconsistente** |
| Existencia | broker del SRI | **Sí** — `NOT_FOUND` bloquea; proveedor caído solo avisa |

### Backend
- **Nuevo** `app/services/id_validation.py` — fuente única de la regla.
- **422** con mensaje accionable en `POST /customers`, `GET /persons/lookup`,
  `GET /customers/by-id`; el número inválido **nunca se guarda**.
- **422** en `create_dispatch`, `collect` y `billing` si el cliente no tiene identificación
  (`id_number IS NULL`) o es inválida — también vía el dueño de la placa.
- `persons.id_number` **nulable** (migración `5c6d7e8f9a01`): `NULL` = “no verificada”.
- `PUT /api/pos/persons/{id}` acepta `id_type`/`id_number` → endpoint de **re-captura**
  (409 si el número ya está a nombre de otra persona).
- `identity_service`: se separó **`IdentityNotFoundError`** (el registro dice “no existe” →
  **bloquea**) de **`IdentityProviderError`** (proveedor caído → sigue con **aviso visible**).
- `person_id` aceptado en `CreateDispatchRequest`/`BillingRequest` (necesario cuando
  `customer_id` ya no existe porque el número se borró).
- `emitir_factura_global` falla explícito si el receptor no tiene identificación.

### Powerfin POS
- **Nuevo** `src/lib/utils/id-validation.ts` (espejo del backend) + 36 tests.
- Validación de dígito **en pantalla** en `SaleWizard` y `new-dispatch`, antes de buscar.
- **Paso Cliente bloqueado**: si el cliente no tiene identificación válida → banner rojo,
  `✓ Correcto` deshabilitado y único camino **“🪪 Ingresar identificación”** (paso `captureId`)
  → `PUT /api/pos/persons/{id}` → vuelve a la confirmación ya completo.
- `powerfin.ts`: se muestra el **`detail` real del backend** (antes mensaje genérico).

### Intervenciones manuales en PROD (2026-09-13)
1. **Deploy**: backend + frontend (`powerfin-gas deploy-backend` → `deploy-frontend`).
   FusionBridge y Admin **no** se tocaron. Migración aplicada: `alembic_version` = `5c6d7e8f9a01`.
2. **Factura `003-501-000004859`** (nunca enviada, 7 h en PENDING): reemitida con
   `scripts/recover_pending_invoices.py --dispatch-id 21031 --min-age-hours 0 --execute` → `NOTIFIED`.
3. **7 facturas fallidas del día** ($76.45): titular reasignado a
   **AURACORE SOLUCIONES SAS** (`person_id 10472`, RUC `0195160252001`, creado) por $56.45 y
   **VALAREZO PATRICIO** (`person_id 3750`) por $20.00 → las 7 emitidas y autorizadas.
   Respaldo del estado original: `/tmp/reasignacion_antes.tsv`.
4. **Limpieza de IDs inválidos**: `scripts/limpiar_ids_invalidos.py --apply` → **198 clientes**
   con `id_number = NULL` (182 cédulas + 16 RUC inexistentes). Respaldo:
   `/tmp/ids_invalidos_backup_20260914_023929.csv`.
5. Resultado del día fiscal: **266 facturas emitidas, 0 fallidas, 0 pendientes** ($3.721,05).
6. **12 facturas `FAILED` de septiembre** ($149.51, fechas 09‑01 a 09‑12), todas rechazadas por
   Key49 por identificación inválida y **ninguna con `key49_invoice_id`** → reasignadas a
   **5 titulares** y reemitidas **con fecha de hoy** (indicación del contador: el neteo es
   mensual, la fecha no es problema). Reparto equilibrado por monto:

   | Titular | person_id | Facturas | Monto |
   |---|---|---|---|
   | Justin barahona | `10299` | 3 | $35.00 |
   | AURACORE SOLUCIONES SAS | `10472` | 3 | $34.00 |
   | AVILA CEVALLOS GLADYS EUFEMIA | `9321` | 2 | $30.00 |
   | VALAREZO PATRICIO | `3750` | 2 | $25.50 |
   | SOLIS NARZON | `5254` | 2 | $25.01 |

   Resultado: **11/12 finales** (10 `NOTIFIED` + 1 `AUTHORIZED`), 1 en `RECEIVED`
   (dispatch 20500, en proceso en el SRI; lo cierra el reconciler). Verificado contra la API
   de Key49 que el receptor quedó correcto en cada documento.
   Respaldo: `/tmp/reasignacion_sept.tsv` · reparto: `/tmp/reparto_sept.sql`.
   **Septiembre queda con 0 facturas con problema.**

### Hallazgos operativos documentados
- **Nada reintenta las facturas “nunca enviadas”** (`PENDING` sin `key49_invoice_id`): el
  reconciler (120 s) solo lee filas que ya tienen id de Key49, y `retry_pending_invoices`
  **no tiene scheduler**. Backlog: 23 facturas jun/jul ($418.76), todas con ID **válida**.
- El SOP afirmaba que `retry-sri` recalcula la clave de acceso: **es falso** → solo sirve el
  mismo día. Corregido en `docs/SOP_REENVIO_SRI_KEY49.md` (nueva Opción D con el script).
- **Extranjeros sin cédula ni RUC**: el POS solo ofrece CED/RUC → no tienen dónde pasar.
- `agent_llm` **no tiene `CREATE`** en `public` → el respaldo de la limpieza va a CSV.

### Archivos modificados
- Backend: `services/id_validation.py` (nuevo), `services/identity_service.py`,
  `services/key49_service.py`, `api/persons.py`, `api/customers.py`, `api/dispatches.py`,
  `models/person.py`, `schemas/__init__.py`, `alembic/versions/5c6d7e8f9a01_*.py` (nueva)
- POS: `lib/utils/id-validation.ts` (nuevo) + `.test.ts`, `lib/components/SaleWizard.svelte`,
  `routes/(pos)/new-dispatch/+page.svelte`, `lib/api/powerfin.ts`, `lib/api/types.ts`,
  `lib/api/powerfin.mock.ts`, `lib/stores/pendingOrders.ts`
- Scripts: `scripts/limpiar_ids_invalidos.py` (nuevo)
- Docs: `docs/FLUJOS_VENTA_ESCENARIOS.md` (reescritura v2), `docs/SOP_REENVIO_SRI_KEY49.md`,
  `AGENTS.md`, `NEXT_SESSION.md`, `PROGRESS.md`

### Validación
- pos_backend: **536 tests pasando** (era 461). POS: **77 tests** (era 41) y `svelte-check`
  con **0 errores**.

---

## Versiones anteriores no registradas en este archivo

> Reconstruido desde el historial de git y `NEXT_SESSION.md` (donde está el detalle).
> El archivo quedó sin entradas entre v0.35.7 y v0.37.3; se registran aquí de forma compacta
> para no dejar el hueco en silencio.

| Versión | Fecha | Resumen |
|---|---|---|
| `v0.37.3` | 2026-09-12 | Se **exige cliente en `SALE`** (`requires_customer` ahora se valida) y se persiste `dispatches.plate_raw` para no perder la placa cuando el vehículo no está registrado. Errores explícitos (422/404) |
| `v0.37.2` | 2026-09-12 | El **reconciler SRI cubre todos los estados no-finales** (con cooldown para `REJECTED`/`FAILED`). El incidente Key49 (tenant en ambiente PRUEBAS → error SRI 35) se diagnosticó y recuperó con sync masivo |
| `v0.37.1` | 2026-09-12 | Monitor SRI distingue **“En Key49” vs “no llegaron”**; export Excel de despachos sin factura |
| `v0.37.0` | 2026-09-11 | **Reconciler SRI de fondo** (`sri_sync_service`) para despachos atascados en `PENDING` |
| `v0.36.0` | 2026-09-10 | **Módulo Monitoreo SRI/Key49 en Admin** (Fase 1, solo lectura, feature flag off por defecto) |
| `v0.35.7` | 2026-09-09 | El body de error de Key49 se captura en `sri_messages`; `RUC Proveedor` en `additional_info`; `--shard` en el script de recuperación; script de recuperación de facturas pendientes |

---

## v0.35.6 (2026-08-20) — Fix: reimpresión respeta fecha/hora original + deploy dual IP

### Fix: reimpresión de ticket de despacho con fecha/hora original
- Bug: al reimprimir un ticket desde Historial, `handleReprint()` usaba `new Date()`
  (fecha/hora del momento de reimprimir) en vez de la fecha/hora del despacho.
- Fix: usar `order.created_at` (mismo valor que muestra el historial) con fallback a
  hora actual si viniera vacío. La impresión original (al momento del cobro) no cambia.
- Fix adicional (mismo patrón, mismo archivo): `reprintClose()` usa `raw.closed_at`
  (fecha real del cierre de turno) en lugar de `new Date()`.
- Verificado: FusionBridge solo pasa `date`/`time` del frontend (no genera fecha propia);
  la reimpresión de movimientos de caja ya usaba `m.created_at` (correcto).
- Archivo: `pos/src/routes/(pos)/history/+page.svelte`
- Validación: `npm run check` 0 errores + tests 41/41 ✅

### Deploy: 2 IPs de acceso al servidor (Tailscale + LAN oficina)
- `scripts/deploy-to-server.sh`: `REMOTE_SERVER="app@100.97.47.123"` (Tailscale, default)
  y `LOCAL_SERVER="app@192.168.1.25"` (LAN oficina — si Tailscale está caído).
- Nuevo argumento: `./scripts/deploy-to-server.sh <target> local` o por variable de
  entorno `DEPLOY_HOST=local ./scripts/deploy-to-server.sh <target>`.
- Verificación de conectividad previa (5s timeout) con mensaje claro si falla:
  "¿Tailscale está caído? usá `local`" / "verificá la red de la oficina".
- Host inválido rechazado; sin argumentos muestra uso sin intentar conectar.
- `docs/DEPLOY_QUICK.md`: documentadas ambas rutas (tabla, Etapa 1, Etapa 2, instalación).

### Archivos modificados
- `pos/src/routes/(pos)/history/+page.svelte` — fix reimpresión (despacho + cierre turno)
- `scripts/deploy-to-server.sh` — IP dual + check de conectividad + selector de host
- `docs/DEPLOY_QUICK.md` — documentación de las 2 IPs
- `PROGRESS.md`, `NEXT_SESSION.md` — actualizados

---

## v0.35.5 (2026-08-05) — Fix: payment collection bounce + SRI reconciliation + mechanical meters

### Fix: SaleWizard — rebote en pantalla de cobro con tarjeta/transferencia
- Bug: al cobrar con método que requiere comprobante (tarjeta, transferencia),
  `handleCollect()` ponía `confirmed = true` antes del API call. Si el API fallaba,
  `confirmed = false` causaba un rebote visual sin mostrar el error.
- Fix: nuevo estado `collecting` — spinner "⏳ Procesando..." mientras el API
  responde. `confirmed = true` solo se pone tras éxito. Botones deshabilitados
  durante `collecting` para prevenir doble-click.
- Archivo: `pos/src/lib/components/SaleWizard.svelte`
- Tests: 41/41 ✅ sin regresiones

### SRI/Key49 — reconciliación manual de NOTIFIED + PENDING
- 34 despachos NOTIFIED verificados contra Key49 — todos presentes, notificados al SRI
- 4 despachos PENDING (polling timeout) actualizados a NOTIFIED con datos reales de Key49
- Resultado: 38 NOTIFIED ($611.85) + 4 AUTHORIZED ($123.51) — 100% enviados a Key49
- Cero despachos perdidos

### Intervenciones manuales en PROD
- Despacho #12450 recreado: $62.04 DIESEL, dispenser 3, MINERA PIRINCAY (perdido por corte de energía + cleanup)
- 2 pagos corregidos: EFECTIVO → TARJETA CREDITO/DEBITO (refs 656, 657)
- 4 PENDING → NOTIFIED con fechas reales de Key49

### Nuevo: Medidores mecánicos (mechanical meters)
- Modelo `MechanicalMeter` + CRUD admin API
- Lecturas inicial/final vinculadas a turnos
- Página POS: captura de lecturas al abrir/cerrar turno
- Migraciones Alembic: `2f3a4b5c6d7e` + `3a4b5c6d7e8f`
- Tests dedicados

### CODE_REVIEW_FINDINGS.md
- Revisión de código generada por 4 subagentes en paralelo (pos_backend, fusion-bridge, pos/, admin/)
- 19 hallazgos: 7 alta prioridad, 8 media, 4 baja
- Pendiente revisión sistemática en próxima sesión

### Archivos modificados
- `pos/src/lib/components/SaleWizard.svelte` — fix rebote cobro
- `pos/src/lib/api/powerfin.ts`, `powerfin.mock.ts`, `types.ts` — meter readings API
- `pos/src/routes/shift/open/+page.svelte` — lecturas mecánicas al abrir
- `pos/src/routes/shift/close/+page.svelte` — lecturas mecánicas al cerrar
- `pos/src/routes/shift/meters/+page.svelte` — nueva página
- `pos/src/routes/(pos)/cash/+page.svelte` — mejoras UI
- `pos_backend/app/models/mechanical_meter.py` — nuevo modelo
- `pos_backend/app/api/admin/mechanical_meters.py` — nuevo endpoint admin
- `pos_backend/app/api/admin/dispensers.py` — mejoras
- `pos_backend/app/api/admin/reports.py` — mejoras reportes
- `pos_backend/app/api/config.py` — meter readings en config
- `pos_backend/app/api/shifts.py` — meter readings en turnos
- `pos_backend/app/schemas/__init__.py` — schemas nuevos
- `pos_backend/app/services/export_service.py` — mejoras export
- `pos_backend/app/models/dispenser.py` — relación mechanical_meter
- `fusion-bridge/.../FusionEventHandler.java` — fix
- `fusion-bridge/.../ReceiptBuilder.java`, `TemplateRenderer.java` — mejoras impresión
- `admin/src/routes/(admin)/dispensers/[id]/+page.svelte` — mejoras
- `admin/src/routes/(admin)/reports/+page.svelte` — mejoras
- `CODE_REVIEW_FINDINGS.md` — nuevo documento
- `PROGRESS.md`, `NEXT_SESSION.md` — actualizados

---

## v0.35.4 (2026-07-20) — Fix: Admin Dashboard gráficas mensuales sin datos

### Bug: gráficas "Mensual" no mostraban datos de otros meses
- Dashboard Admin, pestaña "Mensual": gráficas "Ventas por Día" y "Galones por Día"
  solo mostraban el mes seleccionado; los datos del mes anterior/siguiente no aparecían
- Causa: `ComparisonChart.svelte` alineaba datasets por etiqueta con nombre de mes
  incluido (`"17 Jun"` vs `"17 Jul"` → no match)
- Fix: comparar solo por número de día en modo `monthly`; también derivar `allLabels`
  desde cualquier dataset disponible (no solo `current`) por si el mes seleccionado está vacío

### DB_ACCESS.md actualizado
- IP principal: `100.97.47.123` (Tailscale — siempre disponible)
- IP respaldo: `192.168.1.25` (LAN local)
- Comandos de ejemplo usan la IP Tailscale por defecto

### Limpieza
- `docs/NEXT_SESION.md` borrado — duplicado desactualizado (v0.23.1) con typo en el nombre

### Archivos modificados
- `admin/src/lib/components/dashboard/ComparisonChart.svelte` — fix alineación mensual
- `docs/DB_ACCESS.md` — IPs duales (Tailscale + LAN)
- `docs/NEXT_SESION.md` — eliminado
- `PROGRESS.md`, `NEXT_SESSION.md` — actualizados

---

## v0.35.3 (2026-07-19) — Fix: close shift guard para despachos sin cobrar

### Bug: turno cerrado con despachos COMPLETED sin cobrar
- Despachador Alex Chiriap: turno #130 cerrado con despacho #7949 (3.062 gal, $10.00) sin cobrar
- Dispensador 2-B bloqueado: la validación de autorización rechaza nuevos despachos si hay COMPLETED
- Causa raíz: `close_shift` no validaba despachos pendientes antes de cerrar el turno
- Fix: guard que bloquea el cierre si hay ≥1 despacho en estado COMPLETED
- Mensaje: "No puedes cerrar el turno: hay N despacho(s) pendiente(s) de cobro..."
- 16/16 tests pasando, sin regresiones

### Intervención manual en PROD
- Despacho #7949: movido de shift 130 → 131, insertado dispatch_payment ($10.00 EFECTIVO)
- Pendiente de deploy del fix para prevenir recurrencia

### Archivos modificados
- `pos_backend/app/api/shifts.py` — guard en close_shift (+15 líneas)
- `PROGRESS.md`, `NEXT_SESSION.md`, `docs/NEXT_SESION.md`

---

## v0.35.2 (2026-07-14) — SRI cleanup + bulk invoice fix + cash summary

### SRI/Key49 — limpieza masiva
- 268 despachos regularizados: polling timeout + Key49 offline + datos inválidos
- $6,249 en facturas ahora autorizadas por el SRI
- 43 cédulas corregidas (dígito verificador módulo 10) + búsqueda API Sercobaco
- 16 RUCs corregidos con datos reales
- 4 REJECTED → reasignados a INGENIERIA DE SISTEMAS GRISBI
- CONSUMIDOR FINAL eliminado (no aplica en gasolineras)
- Resultado: 381 problemas → 0 accionables

### Fix: PENDING_BULK_INVOICE sequential leak
- Bug: contratos NO_INDEFINIDO consumían secuenciales al crear despacho
- credit_status no se seteaba sin `product_id` en el body
- Fix: resolver `contract_type` antes del sequential guard
- 53 secuenciales recuperados (vueltos a NULL)

### POS: Resumen de Turno
- Nueva página `/cash/summary` con ventas (efectivo/tarjeta/crédito), movimientos, resultado
- Botón "📊 Resumen de Turno" en módulo Caja
- Backend: `CashSummaryResponse.non_cash_sales`

### Cleanup: fast-cancel para tanque vacío
- Pump IDLE + AUTHORIZED $0 + 120s → cancel rápido (tanque vacío, ATO)

### Archivos modificados
- `pos_backend/app/services/dispatch_cleanup.py` — idle threshold 120s
- `pos_backend/app/api/dispatches.py` — bulk invoice sequential guard
- `pos_backend/app/api/cash.py` — non-cash sales in summary
- `pos_backend/app/schemas/__init__.py` — NonCashSalesItem + CashSummaryResponse
- `pos/src/lib/api/types.ts` — ShiftCashSummary actualizado
- `pos/src/routes/(pos)/cash/summary/+page.svelte` — nueva
- `pos/src/routes/(pos)/cash/+page.svelte` — botón resumen
- `NEXT_SESSION.md`, `PROGRESS.md`

---

## v0.35.1 (2026-07-14) — Hotfix: dispatch cleanup race condition

### 🔥 Incidente crítico
- MINERA PIRINCAY (persona 1101): despacho de 168.425 galones DIESEL por $539.63 no registrado
- Causa raíz: `dispatch_cleanup.py` canceló un despacho `FULL` mientras el pump seguía cargando
- `completeDispatch` descartó silenciosamente el `NEW_TRANSACTION` de $539.63 porque el despacho estaba `CANCELLED`
- Despacho #6749 reconstruido manualmente vía SQL desde datos reales del FusionBridge

### Fixes implementados

**Fix #1 — Cleanup verifica pump status vía FusionBridge**
- Antes de cancelar, consulta `/api/dispensers` para ver si el pump está `FUELLING`/`STARTING`/`AUTHORIZED`
- Si está activo, omite la cancelación
- `dispatch_cleanup.py` — función `_get_fusion_pump_statuses()`

**Fix #2 — Threshold progresivo por tipo de preset**
- `FULL` (VOLUME con valor "FULL"): **1800s (30 min)** — seguro para tanqueros
- `MONEY`/`VOLUME` (con valor numérico): **900s (15 min)** — típico ATO timeout
- `dispatch_cleanup.py` — función `_orphan_threshold()`

**Fix #3 — completeDispatch reactiva despachos cancelados con fuel real**
- Si `NEW_TRANSACTION` llega con `amount > 0` y el dispatch está `CANCELLED` → reactivar a `COMPLETED`
- Guardia anti-colisión: no reactiva si hay un dispatch más nuevo en la misma manguera
- `dispatches.py` — `complete_dispatch` y `complete_by_pump`

### Documentación
- Auditoría completa del ciclo de vida: `docs/DISPATCH_AUDIT.md` (40 guardias mapeadas)

### Archivos modificados
- `pos_backend/app/services/dispatch_cleanup.py` — reescritura completa
- `pos_backend/app/api/dispatches.py` — Fix #3 + guardia anti-colisión
- `pos_backend/tests/test_dispatch_cleanup.py` — 7 tests (2 nuevos: FULL preset)
- `docs/DISPATCH_AUDIT.md` — nuevo
- `NEXT_SESSION.md` — actualizado

### Tests: 404/404 ✅

---

## v0.35.0 (2026-07-13) — Crédito sector público + orphan cleanup + admin mejoras

- `PENDING_BULK_INVOICE` para contratos NO_INDEFINIDO (sector público)
- Factura global / liquidación para contratos públicos
- Admin: módulo contracts (listado + liquidación)
- 48 despachos GAD PAUTE → contrato IC-GADMCP-00049-2026
- Cleanup automático de despachos huérfanos (`dispatch_cleanup.py`)
- Ticket de crédito con bloque de firma en ESC/POS
- Admin reportes: Efectivo Actual, Turno, Usuario, Contrato, Galones
- Zona horaria Ecuador en exports, formato de moneda
- Bugfixes: auto-run alembic en deploy, chown preventivo, método crédito por prefijo
- Intervenciones manuales: restauración de despachos cancelados por cleanup viejo

**Commits:** `905db62` → `10c4d47` (15 commits)  
**Tag:** `v0.35.0`

---

## v0.34.0 (2026-07-13) — Crédito sector público + cleanup + tickets

- `PENDING_BULK_INVOICE` credit_status, factura global Key49
- `dispatch_cleanup.py`: cancelación automática de huérfanos
- Ticket de crédito con firma, contract_code en receipt data

**Commits:** `16a8d6d`  
**Tag:** `v0.34.0`

---

## v0.33.0 (2026-06-26) — Admin Dashboard Diario

- Dashboard con 3 modos (Hoy, Período, Comparación)
- KPIs, hourly sales, payment methods, last dispatches
- Multi-línea sales by day × product
- Gráficos: donut, pie, line charts con Chart.js

**Commits:** `bf438f4`  
**Tag:** `v0.33.0`

---

## v0.32.0 (2026-06-23) — Cloudflare Tunnel + docs finales

- Cloudflare Tunnel para acceso externo seguro
- DNS, WAF, rate limiting config
- Documentación final de deploy

**Commits:** `4f27801` → `002f787`  
**Tag:** `v0.32.0`

---

## v0.31.0 (2026-06-22) — Admin deploy readiness

- Admin funcionando en producción (neoguayas2, :5174)
- Alembic migrations en git
- Nginx config, firewall, systemd services
- Documentación de instalación y deploy

**Commits:** `61d7d9c` → `16a0182`  
**Tag:** `v0.31.0`

---

## v0.30.0 (2026-06-22) — Admin Phases 14-16 completas

- Admin frontend layout + login + CRUD
- Dashboard con Chart.js (Phase 15)
- Reportes con charts, summary stats, export (Phase 16)
- Rebrand: Powerfin GAS - Admin

**Commits:** `02bbe2e` → `e6bd7c2`  
**Tag:** `v0.30.0`

---

## v0.29.0 (2026-06-22) — Svelte 5 compat fixes

- Reemplazo de `onMount` con `$effect` en 16 páginas admin
- Reemplazo de `svelte-sonner` con toast nativo
- Fix: SSR disabled para SPA, Vite 6 CSS error
- Fix: `{'all': true}` permission convention

**Commits:** `378cda1` → `0d7e160`  
**Tag:** `v0.29.0`

---

## v0.28.0 (2026-06-22) — Admin Dashboard (Phase 15)

- Gráficos: sales-by-day, products donut, payment pie
- KPI cards + date range picker
- Top customers, top products
- Responsive charts con Chart.js 4.x + svelte-chartjs

**Commits:** `84b8e55`  
**Tag:** `v0.28.0`

---

## v0.27.0 (2026-06-22) — Admin CRUD completo (Phase 14)

- Páginas CRUD: price-lists, dispensers, emission-points, reports
- Páginas: roles, products, grades, payment-methods, company-info, system-config
- Admin frontend: layout + login + DataTable + DataCard responsive

**Commits:** `6142cd3` → `a720c13`  
**Tag:** `v0.27.0`

---

## v0.26.0 (2026-06-22) — Admin Backend Dashboard + Reportes (Phase 13)

- Dashboard: summary, sales-by-day, sales-by-product, sales-by-payment
- Dashboard: top-customers, top-products
- Reports: sales, dispatches, shifts, cash-summary
- Export: PDF (reportlab) + Excel (openpyxl)

**Commits:** `c92cc29` → `077be6b`  
**Tag:** `v0.26.0`

---

## v0.25.0 (2026-06-22) — Admin Backend CRUD + Auth (Phase 12)

- 11 módulos CRUD, 51 endpoints, 238 tests
- Auth: JWT 4h, role-based permissions (ADMIN/SUPERVISOR/DISPATCHER)
- Users, roles, products, grades, price-lists, dispensers, emission-points
- Soft-delete, paginación, búsqueda

**Commits:** `996862b` → `3552336`  
**Tag:** `v0.25.0`

---

## v0.24.0 (2026-06-22) — Admin roles + products

- Roles CRUD + products CRUD con soft-delete
- Sequence fixes para PostgreSQL

**Commits:** `625336e`  
**Tag:** `v0.24.0`

---

## v0.23.1 (2026-06-19) — Fix: falsa alarma de efectivo

- Fix: falsa alarma de efectivo excedido
- Documentación de cash management

**Commits:** `f942abc`  
**Tag:** `v0.23.1`

---

## v0.23.0 (2026-06-19) — Vehículos predeterminados + deploy scripts

- `GET /api/pos/vehicles/predefined/next` — balanceo por despachos del día
- Botón "🧉 Pedir Vehículo Interno" en SaleWizard + PlateInput
- `scripts/deploy-to-server.sh` + `powerfin-gas` CLI
- Deploy en 2 etapas con pre-deploy, exclusiones
- `powerfin-gas backup-db` con pg_dump y auto-limpieza

**Commits:** `c570ea2`  
**Tag:** `v0.23.0`

---

## v0.22.0 (2026-06-18) — Admin auth + users CRUD backend

- `POST /api/admin/auth/login` — JWT 4h
- Admin auth guard + `require_permission(resource, action)`
- Users CRUD: GET (list/search/paginate), POST, GET/:id, PUT, DELETE (soft)
- 36 tests admin (10 auth + 26 users)

**Commits:** `c601831` → `a5fa161`  
**Tag:** `v0.22.0`

---

## v0.21.5 (2026-06-18) — FusionBridge HttpClient fixes

- Fix: force HTTP/1.1 — body lost in HTTP/2 negotiation
- Fix: debug logging improved
- Fix: `complete_by_pump` bypasses SQLAlchemy statement cache

**Commits:** `a2f0e12` → `a40af66`  
**Tag:** `v0.21.5`

---

## v0.19.9 (2026-06-21) — Documentación operativa

- `docs/CUADRE_CAJA.md` — guía de conciliación de turno
- SQL: mejora reporte `ventas_turno`

**Commits:** `3c64e4b` → `c8ad923`  
**Tag:** `v0.19.9`

---

## v0.19.8 (2026-06-20) — Deploy + cancel fixes

- Auto-clean pre-deploy después de deploy exitoso
- Documentación: lógica IDLE+FUELLING cancel en DispenserCard

**Commits:** `fcdec5f` → `231462c`  
**Tag:** `v0.19.8`

---

## v0.19.7 (2026-06-20) — Fix: cancel button para AUTHORIZED

- Fix: cancel button para despachos AUTHORIZED stuck en IDLE nozzle
- Fix: `powerfin-gas deploy-frontend` ahora corre `npm run build`

**Commits:** `68eb93e` → `8a20734`  
**Tag:** `v0.19.7`

---

## v0.19.6 (2026-06-20) — Wayne payment handshake

- Fix: Wayne payment handshake (LOCK→CLEAR→UNLOCK) después de collect
- Evita que el display del pump se quede stuck después del cobro

**Commits:** `dd64a94`  
**Tag:** `v0.19.6`

---

## v0.8.0 — v0.19.x (2026-05-27 → 2026-06-20) — Fases 5-11

### Phase 11 — UX, refactors, bugfixes (v0.19.x)
- Dashboard visual, IDs vs strings, SRI column, name search
- Recovery despacho AUTHORIZED sin PAY_IN (phone-off bug)
- Doble autorización → 409 Conflict
- preset_value persistido + bloqueo cobro $0.00
- Migración Alembic completa (15+ columnas en 6 tablas)
- Auto-cancel eliminado (redundante con ATO=180s)
- Frontend muestra errores reales del backend

### Phase 10c-11e (v0.15.0 → v0.19.4)
- Subtotal/IVA fix, random access key, print spacing
- Key49 SRI electronic invoicing (fire-and-forget, polling, retries)
- Zona horaria Ecuador, clave Key49, IPs impresora, reimpresión
- Cierre de turno completo: cuadre, surplus/shortage, depósito, template
- RecoveryService: reconexión FusionBridge durante despacho activo

### Phase 10a — Edge cases (v0.13.0)
- Rollback dispatch si authorizeDispatch falla + auto-cancel > 5 min
- STOP durante FUELLING con doble barrera anti-bolsillo
- Celular apagado/offline: completeDispatch en FusionBridge (3 retries)
- CLEAR_STOP automático antes de PRESET + después de STOP (2s delay)

### Phase 10b — Impresión y clave SRI (v0.14.0)
- 10 columnas nuevas en DB
- Clave de acceso SRI: 49 dígitos con módulo 11
- Ticket completo: empresa, cliente, subsidio, IVA 15%
- Font B (ESC/POS compacto), template con condicionales anidados

### Phase 9 — Integration & hardening (v0.12.0)
- POS Backend completo (71 tests)
- Identity API (Sercobaco CED + SRI RUC)
- Credit contracts con cupo disponible
- Decimal→float middleware para POS
- Cuadre de caja completo

### Phase 8 — POS Backend (v0.11.0)
- Standalone FastAPI backend, 26 tablas, 38 endpoints, 71 tests
- PostgreSQL powerfin_gas, Identity API integration

### Phase 7 — Hardware validation (v0.10.0)
- Real Synergy tested, multi-device sync
- Cancel button, billing change, Consumidor Final removal

### Phase 6 — Cash + History + Users (v0.9.0)
- Cash module, shift refactor, online users dashboard, history with reprint

### Phase 5 — Printing (v0.8.0)
- ESC/POS thermal printing, multi-island config, editable templates
- Tests: 69 (bridge) + 41 (POS)

---

## v0.7.1 — v0.7.0 (2026-05-28-29) — Synergy real, multi-pump

- Match de IDs dispensador/manguera, flujo de cobro
- Synergy real, precios dinámicos, mapeo multi-pump
- FusionBridge v0.7.0

**Commits:** `0132fd5` → `b462a81`

---

## v0.4.0 — v0.6.0 (2026-05-27-28) — Fases 4-6

- Phase 6: Cash, shifts, users, history
- Phase 5: Thermal printing (ESC/POS)
- Phase 4: End-to-end sales flow with mocks

**Commits:** `465b5ba` → `0b4c60c`

---

## v0.1.0 — v0.3.0 (2026-05-09-14) — Fundación

- Phase 1: FusionBridge TCP bridge (35 unit tests)
- Phase 2: APIs documentadas (21 endpoints)
- Phase 3: Powerfin POS base (SvelteKit 2.x + TypeScript + Tailwind)
- Unified SaleWizard, Fusion simulator, dashboard con auto-complete
- localStorage persistence, SSE broadcast, payment methods

**Commits:** `16d664b` → `e130e3c`

---

## Documentación del proyecto

| Archivo | Descripción |
|---------|-------------|
| `AGENTS.md` | Convenciones de arquitectura, lenguaje, commits |
| `docs/ROADMAP.md` | Plan de desarrollo de 17 fases |
| `docs/API_CONTRACT.md` | Contratos de endpoints entre sistemas |
| `docs/FUSION_PROTOCOL.md` | Protocolo TCP con Wayne Synergy |
| `docs/DISPATCH_AUDIT.md` | Auditoría del ciclo de vida del despacho (40 guardias) |
| `docs/DEPLOY_QUICK.md` | Guía rápida de deploy a producción |
| `docs/DB_ACCESS.md` | Acceso a base de datos de producción |
| `NEXT_SESSION.md` | Tareas pendientes para la próxima sesión |
