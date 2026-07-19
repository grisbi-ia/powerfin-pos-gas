# PROGRESS.md — Powerfin POS · Historial cronológico de cambios

> Última actualización: **2026-07-19** · Rama: `main` · HEAD: `v0.35.3`

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
