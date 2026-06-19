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

Branches: `main` (stable), `develop` (WIP), `feature/*`, `fix/*`
Tags per phase: v0.1.0, v0.2.0, ..., v1.0.0

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
2. Update ROADMAP.md → mark completed tasks with [x], advance phase
3. Update AGENTS.md → if changed conventions, new rules, or phase status
4. Commit all changes
5. Tag the version:
   git tag -a v0.1.0 -m "Phase 1: FusionBridge TCP connection"
   git push origin develop --tags
```

**If any test fails → do NOT version, fix first.**
Nunca se versiona código roto.

## Repo layout — where to find things

```
powerfin_pos_gas/
├── docs/                        ← authoritative reference (read before coding)
│   ├── admin/                   ← 🆕 Admin-specific docs
│   │   ├── ADMIN_UI.md          ← Admin interface architecture
│   │   ├── ADMIN_ROADMAP.md     ← Admin progress tracker (checklist vivo)
│   │   └── UX_STANDARDS.md      ← UI/UX standards (colors, components, patterns)
│   ├── FUSION_PROTOCOL.md       ← TCP protocol (validated real data)
│   ├── FUSION_BRIDGE.md         ← Quarkus architecture + code sketches
│   ├── POWERFIN_POS.md          ← SvelteKit architecture + code sketches
│   ├── API_CONTRACT.md          ← endpoint contracts between all systems
│   ├── INFRAESTRUCTURA.md       ← Debian setup, systemd, Nginx, Cloudflare, deploy
│   ├── FLUJOS_OPERATIVOS.md     ← dispatcher workflows + mockups
│   ├── ROADMAP.md               ← 17-phase development plan
│   ├── POS_BACKEND.md           ← POS Backend schema, APIs, business rules
│   └── IDENTITY_API.md          ← External identity lookup (Sercobaco/SRI)
├── pos_backend/                 ← Python FastAPI backend
├── fusion-bridge/               ← Quarkus sub-project (Java 21)
├── pos/                         ← SvelteKit sub-project — Powerfin POS
└── admin/                       ← 🆕 SvelteKit sub-project — Powerfin Admin
```

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

**Pendiente.**
- [ ] Pago mixto (efectivo + tarjeta)
- [ ] Flujo de crédito en el POS (selector en SaleWizard)
- [ ] Roles/permisos enforcement real
- [ ] identity_service.py — mover URL y token a system_config
- [ ] Despachos ya enviados al SRI con $0.00 — conciliar manualmente

**Phase 12 — Admin Backend CRUD + Auth (v0.20.0 — in progress).**
- [x] POST /api/admin/auth/login — login admin (username+password, JWT 4h)
- [x] Admin auth guard + require_permission(resource, action)
- [x] Users CRUD: GET (list/search/paginate), POST, GET/:id, PUT, DELETE (soft)
- [ ] Roles CRUD: GET, POST, PUT
- [ ] Products CRUD: GET, POST, PUT, DELETE
- [ ] Grades CRUD: GET, POST, PUT, DELETE
- [ ] Price-lists CRUD + items: GET, POST, PUT, DELETE
- [ ] Dispensers + hoses CRUD: GET, POST, PUT
- [ ] Emission-points CRUD: GET, POST, PUT
- [ ] GET/PUT: company-info
- [ ] GET/PUT: system-config (by key)
- [ ] Payment-methods CRUD: GET, POST, PUT
- [x] Paginación y búsqueda en endpoints implementados
- [x] 36 tests admin (10 auth + 26 users)
- [x] 93 tests POS intactos — sin regresiones

**Phase 13 — Admin Backend Dashboard + Reportes (v0.21.0).**
- [ ] Dashboard: summary, sales-by-day, sales-by-product, sales-by-payment
- [ ] Dashboard: top-customers, top-products
- [ ] Reports: sales, dispatches, shifts, cash-summary
- [ ] Export: PDF (reportlab) + Excel (openpyxl)

**Phase 14 — Admin Frontend Layout + CRUD (v0.22.0).**
- [ ] Proyecto SvelteKit independiente en admin/
- [ ] Layout responsive: AdminShell + Sidebar + Topbar
- [ ] Auth: login admin + JWT interceptor + route guarding
- [ ] DataTable con sort, paginate, search, responsive (→ DataCard)
- [ ] Pantallas CRUD: users, products, grades, prices, dispensers, etc.

**Phase 15 — Admin Frontend Dashboard (v0.23.0).**
- [ ] KPI cards + date range picker
- [ ] Chart.js: sales-by-day (línea), products (donut), payment (pie)
- [ ] Top customers, top products, responsive charts

**Phase 16 — Admin Frontend Reportes + Export (v0.24.0).**
- [ ] Pantallas de reportes con filtros avanzados
- [ ] ExportButton → PDF / Excel con feedback de descarga

**Phase 17 — Cloudflare + Deploy + Go-live (v1.0.0).**
- [ ] Cloudflare Tunnel + DNS + WAF
- [ ] Nginx config con rate limiting
- [ ] Deploy script actualizado
- [ ] Prueba E2E: admin → POS

## When building

### POS Backend (Python)
- Stack: FastAPI + SQLAlchemy 2.0 (async) + asyncpg + Alembic
- Virtual env: `pos_backend/venv/`
- Run: `source venv/bin/activate && uvicorn app.main:app --reload --port 8080`
- Test: `pytest` (93 tests)
- DB: `localhost:5433/powerfin_gas` (user: postgres, pass: 1234abcd)
- Test DB: `localhost:5433/powerfin_gas_test`

### FusionBridge (Java)
- Java package base: `com.powerfin.pos.bridge.*`
- Quarkus annotations: `@ApplicationScoped`, `@RunOnVirtualThread` (I/O), `@Scheduled`, `@ConfigProperty`
- Logging: `io.quarkus.logging.Log` — never `System.out.println`

### Powerfin POS (SvelteKit)
- Svelte components: PascalCase (e.g. `DispenserCard.svelte`), TS files: kebab-case
- No business logic in Svelte components — use `$lib/api/` and stores
- Print policy config: `PRINTER_POLICY` env var (ALWAYS | ASK | NEVER)
- ESC/POS library: `escpos-coffee` 4.1.0

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
- Deploy: Nginx location /admin → SPA estática, independiente de /pos

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
