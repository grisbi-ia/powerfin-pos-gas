# NEXT_SESSION.md — Powerfin POS

## Estado actual (2026-05-27)

### ✅ Fases completadas

| Fase | Tag | Descripción |
|------|-----|-------------|
| 1 | `v0.1.0` | FusionBridge TCP connection |
| 2 | — | APIs PowerFin documentadas (16 endpoints, pendiente implementar en ERP) |
| 3 | `v0.2.0` | Powerfin POS base — login, turno, surtidores |
| 4 | `v0.3.0` | Flujo de venta completo |
| 5 | `v0.5.0` | Impresión térmica — ESC/POS, config multi-isla, templates editables |

### 📊 Tests

```bash
# FusionBridge — 69 tests (35 core + 34 print)
cd fusion-bridge && ./mvnw test   # BUILD SUCCESS

# POS — 41 tests (Vitest)
cd pos && npm run test            # 41 passed

# Total: 110 tests pasando
```

### 🏗️ Ramas

```
main     — 0e0278d  Merge develop → Phase 5 complete
develop  — 0b4c60c  Phase 5 thermal printing commit
```

### 🔌 APIs documentadas para PowerFin ERP

16 endpoints listos para implementar en el ERP:
- `POST /api/pos/auth/login`
- `GET /api/pos/config`
- `GET /api/pos/vehicles?plate=`
- `GET /api/pos/customers?q=`
- `GET /api/pos/customers/by-id`
- `POST /api/pos/customers`
- `GET /api/pos/prices`
- `POST /api/pos/shifts/open`
- `GET /api/pos/shifts/current`
- `POST /api/pos/shifts/{id}/close`
- `GET /api/pos/shifts/{id}/dispatches`
- `POST /api/pos/dispatches`
- `POST /api/pos/dispatches/{id}/complete` (idempotente)
- `POST /api/pos/dispatches/{id}/cancel`
- `POST /api/pos/dispatches/{id}/collect`
- `POST /api/pos/cash-movements`

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
     │ • Config         │  │  • POST /api/dispatch     │
     │ • Customers      │  │  • SSE /api/events        │
     │ • Shifts         │  │  • POST /api/print        │
     │ • Dispatches     │  │  • GET/PUT /api/print/    │
     │ • Vehicles       │  │    config + template      │
     │ • Prices         │  │  • GET /health            │
     └──────────────────┘  └───────────┬───────────────┘
                                       │ TCP :3011
                           ┌──────────────────────────┐
                           │ fusion-simulator :3011    │
                           │ (Node.js, TCP)            │
                           │ • 4 surtidores (8/8/4/4) │
                           │ • Protocolo Fusion 100%   │
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

## Para la próxima sesión

### Prioridad 1: Fase 6 — Funcionalidades adicionales

```
☐ /history → Historial del turno actual
    ☐ Lista de despachos con estado
    ☐ Resumen parcial (ventas, volumen, monto)
☐ /shift/close → Cierre de turno
    ☐ Resumen completo con cuadre
    ☐ Ingreso de efectivo en caja
    ☐ Mostrar diferencia vs esperado
    ☐ Imprimir reporte de turno
☐ Movimientos de caja (ingreso/egreso)
☐ Cobertura de surtidor adicional ([+ Cubrir])
☐ Panel básico de supervisor (reportes del día)
```

### Prioridad 2: Implementar endpoints PowerFin ERP

- Los 16 endpoints están documentados con contratos completos en `docs/API_CONTRACT.md`
- El POS ya consume los mocks (`powerfin.mock.ts`) — solo falta el backend real
- Los tipos TypeScript están en `pos/src/lib/api/types.ts`
- El servidor Python de pruebas (`tools/powerfin_server.py`) implementa todos los endpoints con persistencia en archivo

### Prioridad 3: Pruebas con hardware real

- Conectar FusionBridge a `192.168.1.20:3011` (Wayne Synergy)
- Validar todos los estados contra dispensador físico
- Probar impresión en `192.168.1.31:9100` (impresora térmica)

### NOTAS

- `plate = 'ABC1234'` está hardcodeado en `SaleWizard.svelte:28` para facilitar pruebas manuales. Remover ANTES de producción.
- El delay de 2-5s en "Despachando" → "Cobrar" es aceptable (viene del intervalo de polling)
- No modificar la estructura de polling/SSE sin tests previos
- Siempre `rm -rf .svelte-kit` al reiniciar el POS para evitar caché de Vite
- Los tags v0.4.0/v0.4.1 ya existían antes de Phase 5 (creados por Reasonix para fixes SSE). Phase 5 es v0.5.0
