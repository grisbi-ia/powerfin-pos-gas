# AGENTS.md — Powerfin POS

## Architecture (4 systems, each with ONE job)

```
PowerFin ERP  — do NOT modify core. Only add /api/pos/* endpoints.
  OpenXava / Java 8 / PostgreSQL / :8080
  Source of truth for all business data.

POS Backend   — standalone POS business logic (replaces mock).
  Python 3.11+ / FastAPI / SQLAlchemy 2.0 / asyncpg / :8080
  Dir: pos_backend/
  Own PostgreSQL database (powerfin_gas, powerfin_gas_test).
  Handles: users, clients, shifts, dispatches, cash, credit contracts,
           pricing, tributary info, identity lookup (Sercobaco/SRI).

FusionBridge  — bridge between software and hardware.
  Quarkus 3.x / Java 21 / :8090
  Dir: fusion-bridge/

Powerfin POS   — dispatcher touch UI (PWA).
  SvelteKit 2.x / TypeScript / Tailwind CSS
  Dir: pos/
```

**Rule: none duplicates another's responsibility.** FusionBridge and Powerfin POS
have NO business database of their own. The POS Backend has its own PostgreSQL
but is independent from the ERP — it can work with any ERP via accounting exports.

## Hardware (validated against real Wayne Synergy)

```
Wayne Synergy:    <ip-dispensador>:3011  (Firmware Rel-5.19.1)
Printer Island 1: <ip-impresora-1>:9100  (ESC/POS, raw TCP socket, no CUPS/drivers)
Printer Island 2: <ip-impresora-2>:9100
Server:           <ip-servidor>          (Debian 12, direct install, NO Docker)
```

> Las IPs reales se configuran en la tabla `dispensers` (printer_ip, printer_port)
> y en `system_config`. NO hardcodear IPs en código ni docs.

## Fusion Protocol (critical — easy to get wrong)

- Plain text, pipe-delimited, `^` terminator
- Format: `<len>|<crypt>|<version>|<user_id>|<msg_type>|<event>|<dest>|<origin>|<params>|^`
- `crypt=5` means no encryption
- `len` = 5-digit length from `<version>` to `^` **inclusive** — this is the most common bug
- Keep-alive: ECHO every 120s (Timeout: 360s)
- Single persistent TCP connection to Fusion
- Event params format: `KEY=VALUE|KEY=VALUE`
- `dispatch_order_id` travels in `PAY_IN` field for recovery: `OV=orderId~CLI=...`

## Key architecture decisions (do NOT reverse)

1. No Docker — FusionBridge needs direct LAN TCP access
2. SSE (not WebSockets) for FusionBridge → Powerfin POS events
3. FusionBridge maintains one single TCP connection to Synergy
4. Printing is FusionBridge's responsibility, not the browser's
5. `accounting_date` ≠ shift date — turns can cross midnight
6. **NO silent fallbacks** — errors must be visible, never swallowed. No automatic Plan B (e.g. AUTH when PRESET fails). Fallbacks require explicit manual activation and developer approval.

## Language rules

- Documentation (docs/\*.md): Spanish
- Source code (Java, TypeScript, SQL, comments): English
- Commit messages: English, conventional commits format

## Commit conventions

```
feat(fusion-bridge): ...
fix(pos): ...
test(fusion-bridge): ...
docs: ...
chore: ...
```

Branches: `main` (stable — rama activa real, todo el trabajo aterriza aquí),
`feature/*`, `fix/*` (short-lived opcionales). Tags por fase: v0.1.0 ... v0.35.6, ..., v1.0.0

> Nota: aunque el flujo original contemplaba `develop` como WIP, en la práctica el
> proyecto trabaja directo sobre `main` con tags por versión. Deploy desde `main` tras tests.

## Git versioning — mandatory after every phase

Three-level versioning: **MAJOR.MINOR.PATCH**

```
MAJOR (X.0.0)  — breaking change, breaks backward compatibility
MINOR (0.X.0)  — new feature, no breaking changes
PATCH (0.0.X)  — bug fix or minor improvement
```

**Every phase MUST be versioned.** The flow at end of each phase:

```
1. Run all tests → must pass 100%
   FusionBridge:  ./mvnw test
   POS Backend:   cd pos_backend && source venv/bin/activate && pytest
   Powerfin POS:  npm run test && npm run check
   Powerfin Admin: cd admin && npm run check (y npm run build si toca frontend admin)
2. Update ROADMAP.md → mark completed tasks with [x], advance phase
3. Update AGENTS.md → if changed conventions, new rules, or phase status
4. Commit all changes
5. Tag the version:
   git tag -a v0.1.0 -m "Phase 1: FusionBridge TCP connection"
   git push origin main --tags
```

**If any test fails → do NOT version, fix first.**
Nunca se versiona código roto.

## Repo layout — where to find things

```
powerfin_pos_gas/
├── NEXT_SESSION.md              ← Estado vivo de la sesión (fuente #1 del día a día)
├── CODE_REVIEW_FINDINGS.md      ← 26 hallazgos de revisión por módulo (8🔴/9🟡/9🟢)
├── docs/                        ← authoritative reference (read before coding)
│   ├── admin/                   ← Admin docs
│   │   ├── ADMIN_UI.md          ← Admin interface architecture
│   │   ├── ADMIN_ROADMAP.md     ← Admin progress tracker (checklist vivo, fases 12-17 ✅)
│   │   ├── UX_STANDARDS.md      ← UI/UX standards (PRESCRIPTIVO para admin/)
│   │   ├── CLOUDFLARE_TUNNEL.md ← Túnel Cloudflare + DNS + WAF en producción
│   │   └── DASHBOARD_DIARIO.md  ← Dashboard Diario: 3 modos + comparación multi-período
│   ├── FUSION_PROTOCOL.md       ← TCP protocol (validated real data)
│   ├── FUSION_BRIDGE.md         ← Quarkus architecture + code sketches
│   ├── POWERFIN_POS.md          ← SvelteKit architecture + code sketches
│   ├── API_CONTRACT.md          ← endpoint contracts between all systems
│   ├── ROADMAP.md               ← 17-phase development plan
│   ├── POS_BACKEND.md           ← POS Backend schema, APIs, business rules
│   ├── IDENTITY_API.md          ← External identity lookup (Sercobaco/SRI)
│   ├── DEPLOY.md / DEPLOY_QUICK.md  ← Deploy dual IP (Tailscale + LAN)
│   ├── DB_ACCESS.md             ← Acceso BD producción (lectura agent_llm)
│   ├── DISPATCH_AUDIT.md        ← Auditoría: 40 guardias del flujo de despacho
│   ├── KEY49-INTEGRATION-GUIDE.md / SOP_REENVIO_SRI_KEY49.md ← SRI electrónico
│   └── (más: CUADRE_CAJA, TOPOLOGIA_DISPENSADORES, SISTEMA_PRUEBAS, SOP_*, ...)
├── pos_backend/                 ← Python FastAPI backend (+ /api/admin/*)
├── fusion-bridge/               ← Quarkus sub-project (Java 21)
├── pos/                         ← SvelteKit sub-project — Powerfin POS
├── admin/                       ← SvelteKit sub-project — Powerfin Admin (independiente)
└── scripts/                     ← deploy-to-server.sh (frontend/backend/admin/all)
```

> 📌 **Estado vivo:** NEXT_SESSION.md y docs/admin/ADMIN_ROADMAP.md se actualizan en cada
> sesión. AGENTS.md documenta convenciones y el resumen de fases — si hay conflicto,
> manda el documento más reciente.

## Current state

**Phase 1 — Foundation (completed).** FusionBridge project compiles, 35 unit tests
passing. All core classes implemented. Hardware validated with real Synergy.

**Phase 2 — APIs documented (completed).** 21 endpoints specified in API_CONTRACT.md.

**Phase 3 — Powerfin POS base (completed).** SvelteKit 2.x + TypeScript + Tailwind CSS.
Login, shifts, dispensers screen with SSE. 15 tests.

**Phase 4 — Sales flow (completed).** End-to-end flow with mock APIs. 31 tests.

**Phase 5 — Printing (completed).** ESC/POS thermal printing, multi-island config,
editable templates. Tests: 69 (bridge) + 41 (POS).

**Phase 6 — Cash + History + Users (completed).** Cash module, shift refactor,
online users dashboard, history with reprint.

**Phase 7 — Hardware validation (completed).** Real Synergy tested. Multi-device
sync, cancel button, billing change, Consumidor Final removal.

**Phase 8 — POS Backend (completed).** Standalone FastAPI backend with PostgreSQL.
26 tables, 38 endpoints, 71 tests. Identity API integration. Replaces Python mock.
Ready for production integration with POS frontend.

**Phase 9 — Integration & hardening (completed — v0.12.0).**
- [x] POS Backend built and tested (71/71 tests passing)
- [x] Identity API integration (Sercobaco CED + SRI RUC)
- [x] Credit contracts with cupo disponible
- [x] Decimal→float middleware for POS compatibility
- [x] start.sh updated for pos_backend
- [x] Map new dispensers (pumps 3, 4, 7, 8) to POS Backend
- [x] End-to-end test: POS → pos_backend → FusionBridge → Synergy
- [x] POS integration: persons/lookup endpoint in customer search flow
- [x] Billing preferencial por vehículo + auto-save Sercobaco/SRI
- [x] Validación CED=10/RUC=13 + registro mejorado
- [x] Cuadre de caja completo (transfers + safe drops)

**Phase 10a — Edge cases (completed — v0.13.0).**
- [x] Gap D: rollback dispatch si authorizeDispatch falla + auto-cancel > 5 min
- [x] Gap A: STOP durante FUELLING con doble barrera anti-bolsillo
- [x] Celular apagado/offline: completeDispatch en FusionBridge (3 retries)
- [x] CLEAR_STOP automático antes de PRESET + después de STOP (2s delay)
- [x] FusionBridge HttpClient para llamadas HTTP al backend

**Phase 10b — Impresión y clave de acceso SRI (completed — v0.14.0).**
- [x] DB: 10 columnas nuevas (company_info +6, products +1, dispatch_details +2, dispatches +1)
- [x] Clave de acceso SRI: 49 dígitos con módulo 11 (17 tests)
- [x] Ticket completo: empresa, cliente, subsidio, IVA 15%, factura, clave
- [x] Font B (ESC/POS compacto) + espaciado mínimo + sin líneas en blanco
- [x] Impresora configurada desde BD (printer_ip + printer_port en dispensers)
- [x] printer_policy desde system_config
- [x] Template con condicionales anidados, preview mode
- [x] Config API: LocationResponse, HoseResponse, DispenserConfig extendidos
- [x] Backend respuestas enriquecidas: customer_id, plate, address, phone, subsidy, access_key

**Phase 10c through 11e (completed — v0.15.0 through v0.19.4).**
- [x] Subtotal/IVA fix, random access key, print spacing, negative balance prevention
- [x] Key49 SRI electronic invoicing (fire-and-forget, polling, retries)
- [x] Zona horaria Ecuador, clave Key49, IPs impresora, reimpresión
- [x] Cierre de turno completo: cuadre, surplus/shortage, depósito, template
- [x] RecoveryService: reconexión FusionBridge durante despacho activo
- [x] Phase 11: UX, refactors, bugfixes (dashboard visual, IDs vs strings, SRI column, name search)
- [x] Recovery despacho AUTHORIZED sin PAY_IN (phone-off bug)
- [x] Doble autorización mismo dispensador → 409 Conflict
- [x] preset_value persistido + bloqueo cobro $0.00 (cross-page race)
- [x] Migración Alembic completa (15+ columnas en 6 tablas)
- [x] Despachos en $0.00: carrera AM=0, collect exige COMPLETED, cancel limpia SRI
- [x] Auto-cancel eliminado (redundante con ATO=180s del Wayne)
- [x] Frontend muestra mensajes de error reales del backend

**Vehículos predeterminados + Deploy (v0.23.0).**
- [x] GET /api/pos/vehicles/predefined/next — balanceo por despachos del día
- [x] Botón "🧉 Pedir Vehículo Interno" en SaleWizard + PlateInput
- [x] Sin autobúsqueda: llena placa, despachador pulsa Buscar
- [x] scripts/deploy-to-server.sh + powerfin-gas (CLI servidor)
- [x] Deploy en 2 etapas con pre-deploy, exclusiones de .env/caché
- [x] powerfin-gas backup-db con pg_dump y auto-limpieza
- [x] 7 tests backend + 41 frontend (0 regresiones)

**Phase 12 — Admin Backend CRUD + Auth (completed — v0.25.0).** 11 módulos CRUD,
51 endpoints admin, 238 tests. Detalle vivo en docs/admin/ADMIN_ROADMAP.md.
- [x] POST /api/admin/auth/login — login admin (username+password, JWT 4h)
- [x] Admin auth guard + require_permission(resource, action) + convención {'all': true}
- [x] Users CRUD (search/paginate/sort, bcrypt, soft-delete)
- [x] Roles CRUD (code inmutable ^[A-Z_]+$, permissions_json)
- [x] Products CRUD (soft-delete, FK validation) + Grades CRUD
- [x] Price-lists CRUD + items · Dispensers + hoses CRUD
- [x] Emission-points CRUD · Payment-methods CRUD
- [x] GET/PUT company-info + system-config (por key)
- [x] Paginación obligatoria + búsqueda en todos los endpoints admin

**Phase 13 — Admin Backend Dashboard + Reportes (completed — v0.26.0).**
- [x] Dashboard: summary, sales-by-day/product/payment, top-customers, top-products
- [x] Evolution (daily/monthly/annual) + compare + top-periods + gallons-by-product
- [x] Reports: sales, dispatches, shifts, cash-summary (con export xlsx/pdf)
- [x] Export engine: PDF (reportlab) + Excel (openpyxl); Response (no StreamingResponse)

**Phase 14 — Admin Frontend Layout + CRUD (completed — v0.27.0/0.29.0, SvelteKit 5).**
- [x] Proyecto SvelteKit independiente en admin/ (no comparte nada con pos/)
- [x] Layout responsive: AdminShell + Sidebar + Topbar · login + JWT interceptor + guards
- [x] DataTable con sort/paginate/search, responsive → DataCard
- [x] Pantallas CRUD completas (users, roles, products, grades, prices, dispensers, etc.)
- [x] Compat Svelte 5: $effect en vez de onMount, toast nativo (sin svelte-sonner)
- [x] Rebrand "Powerfin GAS — Admin" (nombre empresa en sidebar/topbar)

**Phase 15 — Admin Frontend Dashboard (completed — v0.28.0/0.33.0).**
- [x] KPI cards + date range picker (default "Hoy")
- [x] Chart.js: sales-by-day (línea), products (donut), payment (pie)
- [x] Dashboard Diario: 3 modos (Hoy/Semana/Mes) + comparación multi-período
- [x] Top customers, top products, responsive charts

**Phase 16 — Admin Frontend Reportes + Export (completed — v0.30.0).**
- [x] Pantallas de reportes con filtros avanzados
- [x] ExportButton → PDF / Excel (POST) con feedback de descarga
- [x] Columnas Turno/Usuario/Contrato/Galones en ventas; Efectivo Actual en turnos
- [x] Fechas en zona horaria Ecuador (UTC-5) en tablas y exports

**Phase 17 — Cloudflare + Deploy + Go-live (completed — v0.32.0).** 🎉 En producción.
- [x] Deploy script (deploy-to-server.sh + powerfin-gas) con soporte admin
- [x] Admin en producción (NEOGAS, :5174) · Alembic migrations en git + auto-run al deployar
- [x] Cloudflare Tunnel + DNS + WAF · Deploy dual IP (Tailscale default / LAN con `local`)
- [x] Documentación (docs/admin/CLOUDFLARE_TUNNEL.md, DEPLOY_QUICK.md)
- [ ] Nginx rate limiting en login — pendiente
- [ ] Prueba E2E formal: admin → POS — pendiente

**Post-Phase 17 — Operación y hardening (v0.33.0 → v0.35.6).**
- [x] v0.34.0: crédito sector público (GAD PAUTE, PENDING_BULK_INVOICE), cleanup de
      huérfanos, ticket de crédito con firma + contract_code
- [x] v0.35.0: reportes admin con Turno/Usuario/Contrato, Efectivo Actual, timezone UTC-5
- [x] v0.35.1: fix race cleanup (verifica pump vía FusionBridge, thresholds progresivos
      FULL=30min / MONEY|VOLUME=15min / IDLE=2min)
- [x] v0.35.2: limpieza SRI/Key49 (381 → 0 accionables), fix PENDING_BULK_INVOICE,
      cash summary, idle cancel
- [x] v0.35.3: close_shift guard — bloquea cierre si hay COMPLETED sin cobrar
- [x] v0.35.4: fix gráficas mensuales (comparación por día del mes)
- [x] v0.35.5: fix rebote cobro (estado `collecting`), reconciliación SRI, medidores mecánicos
- [x] v0.35.6: reimpresión respeta fecha/hora original del despacho · deploy dual IP
- [x] v0.36.0: Módulo Monitoreo SRI/Key49 en Admin (Fase 1, solo lectura, feature flag
      `sri_monitor_enabled` off por defecto) — ver docs/admin/SRI_MONITOR.md
- [x] v0.37.0/v0.37.1: reconciler SRI de fondo (`sri_sync_service`), export Excel de
      despachos sin factura, monitor SRI distingue "En Key49" vs "no llegaron"
- [x] v0.37.2: incidente Key49 (tenant en ambiente PRUEBAS → error SRI 35) diagnosticado
      y recuperado por sync; reconciler ahora cubre **todos** los estados no-finales
      (con cooldown para `REJECTED`/`FAILED`). No toca el flujo de venta.
- [x] v0.37.3: se exige cliente en `SALE` (`requires_customer` ahora se valida) y se
      persiste `dispatches.plate_raw` para no perder la placa cuando el vehículo no
      está registrado. Errores explícitos (422/404), sin fallbacks silenciosos.
- [x] v0.38.0: validación de cédula/RUC (módulo 10 en cédula; el módulo 11 del RUC
      NO es confiable → estructura + registro del SRI) en backend y POS, y **el POS
      obliga a re-pedir la identificación**: `persons.id_number` nulable, guardias en
      lookup/registro/despacho/cobro/facturación, paso de re-captura en el POS,
      “no existe en el registro” separado de “proveedor caído”, y script de limpieza
      de IDs inválidos con respaldo. Motivo: 7 facturas perdidas el 09-13.
- [x] v0.39.0: reintento automático de facturas PENDING sin `key49_invoice_id`
      (`run_sri_retry_loop`), regeneración de la clave de acceso al cruzar medianoche,
      cutoff configurable `sri_retry_max_age_hours` (default 72 h) y fix del filtro
      `credit_status` con `IS DISTINCT FROM`.
- [x] v0.39.1: el retry exige `status='COLLECTED'` (antes podía facturar ventas en
      curso: un despacho recién `AUTHORIZED` nace con `sri_status='PENDING'`) y una edad
      mínima de 120 s. Kill switch `sri_retry_enabled`.
- [x] v0.39.2: el monitor SRI (`sri_monitor_service`) también exige `COLLECTED` —
      las ventas en curso (`AUTHORIZED` con `sri_status='PENDING'`) y los `CANCELLED`
      ya no se cuentan como problemas.

**Próximas tareas (fuente viva: NEXT_SESSION.md).**
- [x] **2026-09-13**: `scripts/limpiar_ids_invalidos.py --apply` ejecutado → **198 clientes**
      con `id_number = NULL` (respaldo CSV en `/tmp/ids_invalidos_backup_20260914_023929.csv`).
      El POS ahora pedirá la cédula en su próximo despacho. Backlog de 23 facturas jun/jul
      ($418.76) pendiente de decisión fiscal.
- [ ] **Extranjeros sin cédula ni RUC: no tienen dónde pasar** — el POS solo ofrece Cédula y
      RUC; evaluar tipo Pasaporte (SRI 06) o Consumidor Final (SRI 07). Detalle en NEXT_SESSION.md
- [ ] Auditoría de cambios de facturación: hoy `dispatches.person_id` se sobreescribe al cambiar
      el titular (se pierde el cliente original). Evaluar tabla `dispatch_billing_changes`
- [x] **Reintento automático de facturas “nunca enviadas”** (v0.39.0): loop de fondo
      `run_sri_retry_loop` + regeneración de la clave de acceso al cruzar medianoche
      (Key49 exige `issue_date = hoy`) + cutoff configurable (`sri_retry_max_age_hours`,
      default 72 h). Corregido además el filtro SQL que descartaba ventas con
      `credit_status NULL`. Queda el backlog de **23 facturas jun/jul, $418.76** para
      decisión fiscal (fuera de la ventana de 72 h). Detalle en NEXT_SESSION.md
- [ ] Sercobaco (broker de cédulas) caído: `No existe un contrato activo` → escalar contrato
- [ ] Resolver CODE_REVIEW_FINDINGS.md (26 hallazgos; 🔴 #1 doble conexión TCP
      FusionBridge, 🔴 #2 secuencial fiscal perdido en silencio, 🔴 #4 credenciales
      hardcodeadas en identity_service.py)
- [ ] UI flujo de crédito POS: simplificar botones + indicador persistente "modo crédito"
- [ ] Admin: sección "Despachos con problemas" (cancelar/restaurar sin SQL manual)
- [ ] Admin: editar precios inline en price-lists
- [ ] credit_contracts: agregar payment_method_id (sin buscar por código)
- [ ] Precios programados — cambio automático a las 00:00
- [ ] Pago mixto (efectivo + tarjeta)
- [ ] identity_service.py — mover URL y token a system_config
- [ ] Nginx rate limiting login + prueba E2E admin → POS

## When building

### POS Backend (Python)
- Stack: FastAPI + SQLAlchemy 2.0 (async) + asyncpg + Alembic
- Virtual env: `pos_backend/venv/`
- Run: `source venv/bin/activate && uvicorn app.main:app --reload --port 8080`
- Test: `pytest` (421 tests — endpoints POS + admin /api/admin/*)
- DB dev: `localhost:5433/powerfin_gas` (user: postgres, pass: 1234abcd)
- Test DB: `localhost:5433/powerfin_gas_test`
- DB prod (lectura): `100.97.47.123:5432` (Tailscale) / `192.168.1.25:5432` (LAN)
  — user: agent_llm, ver docs/DB_ACCESS.md
- Medidores mecánicos: modelo + lecturas vinculadas a turnos (abrir/cerrar turno POS)

### FusionBridge (Java)
- Java package base: `com.powerfin.pos.bridge.*`
- Quarkus annotations: `@ApplicationScoped`, `@RunOnVirtualThread` (I/O), `@Scheduled`, `@ConfigProperty`
- Logging: `io.quarkus.logging.Log` — never `System.out.println`
- Test: `./mvnw test` (67 tests)

### Powerfin POS (SvelteKit)
- Svelte components: PascalCase (e.g. `DispenserCard.svelte`), TS files: kebab-case
- No business logic in Svelte components — use `$lib/api/` and stores
- Print policy config: `PRINTER_POLICY` env var (ALWAYS | ASK | NEVER)
- ESC/POS library: `escpos-coffee` 4.1.0
- Test: `npm run test && npm run check` (41 vitest tests, 0 TS errors)

### Powerfin Admin (SvelteKit) — proyecto independiente
- Admin es un proyecto SvelteKit **separado** en `admin/`
- NO comparte build, package.json, ni dependencias con `pos/`
- Para estándares visuales, colores, componentes, y patrones UI: `docs/admin/UX_STANDARDS.md`
  ⚠️ UX_STANDARDS.md es PRESCRIPTIVO para admin/ y DESCRIPTIVO para pos/.
  NUNCA refactorizar pos/ solo por estética o consistencia con admin/.
- Responsive: mobile-first con Tailwind (sm/md/lg/xl/2xl)
- Charts: Chart.js 4.x + svelte-chartjs (ligero wrapper)
- Export: PDF (reportlab) + Excel (openpyxl) — generación en backend
- Auth: username + password (no PIN), JWT 4h, role-based permissions
- Roles: ADMIN (full), SUPERVISOR (read+export), DISPATCHER (sin acceso)
- Soft-delete para entidades con integridad referencial (users, products, grades)
- Paginación obligatoria en todos los endpoints admin
- Sin tests unitarios frontend por ahora (lógica admin cubierta por pytest 421)
- Deploy: Nginx location /admin → SPA estática, independiente de /pos

## Deploy (resumen — ver docs/DEPLOY_QUICK.md)

```bash
# Desde la máquina dev (2 rutas según red)
./scripts/deploy-to-server.sh all          # → Tailscale app@100.97.47.123 (default)
./scripts/deploy-to-server.sh all local    # → LAN app@192.168.1.25 (solo oficina)

# En el servidor
powerfin-gas deploy-all        # backend + frontend + admin (auto-run alembic)
powerfin-gas status            # servicios + health :8080 :8090 :5173 :5174
powerfin-gas backup-db         # pg_dump + auto-limpieza
powerfin-gas migrate-db        # migraciones Alembic manuales si no hay auto
```

## Reenviar facturas a Key49 (procedimiento)

> Fuente autoritativa: `docs/SOP_REENVIO_SRI_KEY49.md`. Resumen operativo:

**Diagnóstico previo** (siempre, antes de tocar nada):

```sql
-- PENDING sin factura = nunca llegó a Key49 (no lo toca el reconciler)
SELECT d.dispatch_id, d.order_id, d.sequential_number, d.total, d.created_at::date,
       p.id_type, p.id_number, p.name, d.sri_messages
FROM dispatches d LEFT JOIN persons p ON p.person_id = d.person_id
WHERE d.sri_status = 'PENDING' AND d.key49_invoice_id IS NULL
  AND d.status <> 'CANCELLED'
  AND d.credit_status IS DISTINCT FROM 'PENDING_BULK_INVOICE'
ORDER BY d.created_at;
```

**Ojo**: el reconciler de fondo (cada 120 s) **solo lee** Key49 y **solo** filas que
ya tienen `key49_invoice_id`. Un `PENDING` sin ese id **no se envía solo**: el reenvío
es **siempre manual**. Y el `retry-sri` HTTP **no recalcula la clave** → solo sirve el
mismo día de emisión.

### Factura del mismo día

```bash
# en el servidor
TOKEN=$(curl -s -X POST http://localhost:8080/api/admin/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"ADMIN","password":"CLAVE"}' | jq -r .access_token)

curl -s -X POST "http://localhost:8080/api/pos/dispatches/<ORDER_ID>/retry-sri" \
  -H "Authorization: Bearer $TOKEN"
```

### Factura de días anteriores (o “referencia fantasma” 404) — el método usado el 2026-09-13

Único camino que **regenera la clave de acceso con la fecha de hoy**. Corre **desde la
máquina de desarrollo** contra la BD de producción (no requiere SSH ni token):

```bash
cd pos_backend && source venv/bin/activate

# 1. clasificar (sin llamadas a Key49)
python scripts/recover_pending_invoices.py --classify-only

# 2. dry-run (reconcilia contra Key49 por access_key → no duplica)
DATABASE_HOST=100.97.47.123 DATABASE_PORT=5432 DATABASE_NAME=powerfin_gas \
DATABASE_USER=agent_llm DATABASE_PASSWORD=... PYTHONPATH=. \
  python scripts/recover_pending_invoices.py --dispatch-id <ID> --min-age-hours 0 --limit 1

# 3. ejecutar (agregar --execute)
DATABASE_HOST=100.97.47.123 DATABASE_PORT=5432 DATABASE_NAME=powerfin_gas \
DATABASE_USER=agent_llm DATABASE_PASSWORD=... PYTHONPATH=. \
  python scripts/recover_pending_invoices.py --dispatch-id <ID> --min-age-hours 0 --limit 1 --execute
```

- `--min-age-hours` por defecto es **24** → una factura del mismo día se omitiría:
pasar `--min-age-hours 0`.
- Otras opciones: `--month 2026-06`, `--limit N`, `--sync-existing` (solo refresca
desde Key49 sin reemitir), `--shard i/N`.
- Reporte JSON en `/tmp/k49_recovery.json`.
- **Verificar después**: `sri_status` debe quedar `NOTIFIED` o `AUTHORIZED` y
`key49_invoice_id` no nulo. Si queda `CREATED/SENT`, el reconciler lo pasa a
`NOTIFIED` en ~2 min.
- **Efecto en el ticket**: la clave impresa deja de coincidir (el código numérico se
regenera). Una **reimpresión** desde historial sale con la clave correcta.

## Connectivity tests (from server)

```bash
# Test Synergy
echo -n "00012|5|2||ECHO||||^" | nc -v 192.168.1.20 3011

# Test printer
nc -zv 192.168.1.31 9100

# Health check
curl -s http://localhost:8080/health   # POS Backend
curl -s http://localhost:8090/health   # FusionBridge

# Start all
./start.sh stop && ./start.sh backend && ./start.sh bridge && ./start.sh pos

# Build admin (independiente)
cd admin && npm run build
```

> ⚠️ Las IPs de los ejemplos son de la LAN de oficina (192.168.1.x). Las reales se
> configuran en BD (dispensers.printer_ip/printer_port, system_config). No hardcodear.
