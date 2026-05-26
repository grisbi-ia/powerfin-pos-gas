# PROMPT_NEXT_SESSION.md — Powerfin POS

## Resumen de lo realizado hoy (2026-05-20)

### 1. Corrección de estados en tiempo real (6 bugs)

**Bug 1 — Estado siempre en Lado A[0]**: El POS no sabía qué manguera estaba activa porque FusionBridge no trackeaba `activeHose`. Solución: campo `activeHose` en `DispenserStatusCache`, extracción de `HO` en `FusionEventHandler`, exposición en REST API, y mapeo por `fusion_hose_id` en `convertToDispenserState`.

**Bug 2 — Nombres de eventos SSE incorrectos**: `+page.svelte` escuchaba `HOSE_STATUS`/`SALE_COMPLETED` pero FusionBridge envía `PUMP_STATUS_CHANGE`/`NEW_TRANSACTION`.

**Bug 3 — SSE doble-wrapping de Quarkus**: `StationEventBus` formateaba manualmente `event:` y `data:`, y Quarkus los envolvía en otro `data:` → eventos ilegibles para el navegador. Solución: refactor a `SseEventSink` + `Sse.newEventBuilder()` con `SseEvent` record.

**Bug 4 — Dashboard se desmontaba**: Al navegar a `/sale`, el dashboard se destruía y perdía SSE/polling. Solución: auto-redirect en `SaleWizard` tras 1.5s.

**Bug 5 — Reactividad Svelte**: `DispenserCard.$sides` no se recomputaba al cambiar el prop `dispenser`. Solución: `$: sides = dispenser && …` para forzar tracking del prop.

**Bug 6 — `autoCompleteOrders` con datos viejos**: `pollDispensers()` es async pero no se esperaba antes de llamar `autoCompleteOrders()`. Solución: mover `autoCompleteOrders()` dentro de `pollDispensers()` tras el `await`.

### 2. Mapeo `fusion_hose_id` en autorización

**Archivo:** `pos/src/lib/components/SaleWizard.svelte`
- La autorización usaba `hose.hose_id` (ID global PowerFin) en vez de `hose.fusion_hose_id` (número de manguera en la bomba Fusion).
- Para Surtidor 1 coincidían (1=1, 5=5), pero para Surtidor 2 enviaba hose 9 y la bomba solo tiene 8 mangueras.
- Fix: `hose_id: hose.fusion_hose_id` en `authorizeDispatch`.

**Archivo:** `pos/src/lib/api/bridge.mock.ts`
- `findHose` y `updateHose` actualizados para buscar por `fusionHoseId` en vez de `hoseId`.

### 3. Debug logs y limpieza

- Agregados y removidos logs de diagnóstico en `+page.svelte`, `bridge-client.ts`, `DispenserCard.svelte`, `SaleWizard.svelte`.
- Script de diagnóstico: `tools/test_sse_flow.sh`.

### 4. UX — Placa precargada

**Archivo:** `pos/src/lib/components/SaleWizard.svelte`
- `plate = 'ABC1234'` por defecto para acelerar pruebas.

### 5. Archivos modificados (27 archivos, +708/-463 líneas)

**FusionBridge (Java)**:
- `DispenserStatusCache.java` — campo `activeHose`
- `FusionEventHandler.java` — extrae `HO`, guarda `activeHose`
- `DispenserResource.java` — expone `activeHose` en JSON
- `DispatchResource.java` — registra `activeHose` al autorizar
- `StationEventBus.java` — refactor a `SseEvent` record
- `SseEventResource.java` — `SseEventSink` + `Sse.newEventBuilder()`
- `application.properties` — `fusion.ip=${FUSION_IP:localhost}`

**POS (TypeScript/Svelte)**:
- `bridge-client.ts` — `convertToDispenserState` usa `activeHose` + `fusion_hose_id`
- `bridge.ts` — tipos con `activeHose`, mock conversion
- `bridge.mock.ts` — `findHose`/`updateHose` por `fusionHoseId`
- `powerfin.mock.ts` — 4 surtidores, 24 pistolas
- `powerfin.ts` — real API calls
- `DispenserCard.svelte` — `dispenser &&` reactividad
- `SaleWizard.svelte` — `fusion_hose_id`, auto-redirect, plate default
- `+page.svelte` — SSE event names, `triggerSsePoll`, `autoCompleteOrders` en `pollDispensers`
- `env.ts` — flags `VITE_USE_MOCKS_POWERFIN` / `VITE_USE_MOCKS_BRIDGE`
- `vite.config.ts` — proxy config

**Simuladores**:
- `fusion-simulator/` — simulador TCP Wayne Fusion (nuevo)
- `tools/powerfin_server.py` — 4 surtidores, endpoint vehicles

---

## Arquitectura actual

```
┌──────────────────────────────────────────────────────────────────┐
│  Celular 1 ─┐                           Celular 2 ─┐             │
│  192.168.1.x│                           192.168.1.x│             │
└─────────────┼───────────────────────────────┼────────────────────┘
              │                               │
              ▼                               ▼
     ┌────────────────────────────────────────────┐
     │  Vite :5173 (POS dev server)               │
     │  Proxy: /api/pos → :8080                   │
     │  Proxy: /bridge   → :8090                  │
     └──────────┬──────────────────┬──────────────┘
                │                  │
                ▼                  ▼
     ┌──────────────────┐  ┌──────────────────────────┐
     │ powerfin_server  │  │  FusionBridge :8090       │
     │ :8080 (Python)   │  │  (Quarkus, Java 21)       │
     │                  │  │                           │
     │ • Login          │  │  • GET /api/dispensers    │
     │ • Config (4 surt,│  │  • POST /api/dispatch     │
     │   24 pistolas)   │  │  • SSE /api/events        │
     │ • Customers      │  │  • activeHose tracking    │
     │ • Shifts         │  │  • Print                  │
     │ • Dispatches     │  └───────────┬───────────────┘
     │ • Vehicles       │              │
     │ • Prices         │              │ TCP :3011
     └──────────────────┘  ┌──────────────────────────┐
                           │ fusion-simulator :3011    │
                           │ (Node.js, TCP)            │
                           │                           │
                           │ • 4 surtidores (8/8/4/4) │
                           │ • Protocolo Fusion 100%   │
                           │ • Estados realistas       │
                           └──────────────────────────┘
```

---

## Cómo arrancar todo

```bash
# Terminal 1 — Simulador Wayne Fusion
cd fusion-simulator && node server.js

# Terminal 2 — FusionBridge (Quarkus)
cd fusion-bridge && ./mvnw quarkus:dev

# Terminal 3 — PowerFin Server (Python)
python3 tools/powerfin_server.py

# Terminal 4 — POS (SvelteKit)
cd pos && npm run dev -- --host 0.0.0.0
```

Abrir en el celular: `http://192.168.1.10:5173`

---

## Tests

```bash
# FusionBridge (35 tests)
cd fusion-bridge && ./mvnw test

# POS (41 tests)
cd pos && npm run check && npm run test
```

**Total: 76 tests — todos pasando.**

---

## Para la próxima sesión

### Prioridad 1: Implementar endpoint `print/policy`
- `GET /bridge/api/print/policy` devuelve 404 actualmente
- Configurar política de impresión (ALWAYS | ASK | NEVER) en FusionBridge
- Soporte en `application.properties`: `printer.policy=ASK`

### Prioridad 2: Completar flujo de cobro real
- Verificar que `SaleWizard.handleCollect()` funcione con PowerFin real
- Sincronización del estado de orden tras cobro (COLLECTED → remover de UI)
- Prueba multi-dispositivo: cobrar en un dispositivo, ver reflejo en otro

### Prioridad 3: Limpieza pre-producción
- Remover `plate = 'ABC1234'` hardcodeado
- Agregar `export let data` en `+page.svelte` para eliminar warning `unknown prop 'params'`
- Revisar si `.svelte-kit/` debe estar en `.gitignore`

### Prioridad 4: Pruebas con hardware real (Wayne Synergy)
- Conectar FusionBridge a `192.168.1.20:3011`
- Validar todos los estados contra dispensador físico
- Probar impresión en `192.168.1.31:9100`

### NOTAS
- El delay de 2-5s en "Despachando" → "Cobrar" es aceptable (viene del intervalo de polling)
- No modificar la estructura de polling/SSE sin tests previos
- Siempre `rm -rf .svelte-kit` al reiniciar el POS para evitar caché de Vite
