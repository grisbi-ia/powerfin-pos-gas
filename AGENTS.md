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
Wayne Synergy:    192.168.1.20:3011  (Firmware Rel-5.19.1)
Printer Island 1: 192.168.1.31:9100  (ESC/POS, raw TCP socket, no CUPS/drivers)
Printer Island 2: 192.168.1.32:9100
Server:           192.168.1.10       (Debian 12, direct install, NO Docker)
```

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
│   ├── FUSION_PROTOCOL.md       ← TCP protocol (validated real data)
│   ├── FUSION_BRIDGE.md         ← Quarkus architecture + code sketches
│   ├── POWERFIN_POS.md          ← SvelteKit architecture + code sketches
│   ├── API_CONTRACT.md          ← endpoint contracts between all systems
│   ├── INFRAESTRUCTURA.md       ← Debian setup, systemd, Nginx, deploy
│   ├── FLUJOS_OPERATIVOS.md     ← dispatcher workflows + mockups
│   ├── ROADMAP.md               ← 8-phase development plan
│   ├── POS_BACKEND.md           ← POS Backend schema, APIs, business rules
│   └── IDENTITY_API.md          ← External identity lookup (Sercobaco/SRI)
├── pos_backend/                 ← Python FastAPI backend (NEW)
├── fusion-bridge/               ← Quarkus sub-project (Java 21)
└── pos/                         ← SvelteKit sub-project (TypeScript)
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

**Phase 9 — Integration & hardening (in progress).**
- [x] POS Backend built and tested (71/71 tests passing)
- [x] Identity API integration (Sercobaco CED + SRI RUC)
- [x] Credit contracts with cupo disponible
- [x] Decimal→float middleware for POS compatibility
- [x] start.sh updated for pos_backend
- [ ] Map new dispensers (pumps 3, 4, 7, 8) to POS Backend
- [ ] End-to-end test: POS → pos_backend → FusionBridge → Synergy
- [ ] POS integration: use persons/lookup endpoint in customer search flow

## When building

### POS Backend (Python)
- Stack: FastAPI + SQLAlchemy 2.0 (async) + asyncpg + Alembic
- Virtual env: `pos_backend/venv/`
- Run: `source venv/bin/activate && uvicorn app.main:app --reload --port 8080`
- Test: `pytest` (71 tests)
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
```
