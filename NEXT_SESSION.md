# NEXT_SESSION.md — Powerfin POS

## Estado actual (2026-09-11) — v0.35.7

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

### ⏳ Pendiente: recuperación de ~2.190 facturas PENDING
- **234** con <24h (se reemiten con el retry normal) y **~1.959** con >24h
  (el retry actual las marca `FAILED "Vencida"` porque el SRI rechaza fecha pasada).
- **Plan propuesto:** script por lotes que regenera `access_key` con fecha de HOY
  y reemite, con reconciliación previa contra Key49 vía
  `GET /v1/invoices?access_key=…` para no duplicar.
- ⚠️ **Requiere aprobación explícita antes de ejecutar en prod** (decisión fiscal:
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
