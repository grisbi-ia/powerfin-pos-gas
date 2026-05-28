# NEXT_SESSION.md — Powerfin POS

## Estado actual (2026-05-28)

### ✅ Fases completadas

| Fase | Tag | Descripción |
|------|-----|-------------|
| 1 | `v0.1.0` | FusionBridge TCP connection |
| 2 | — | APIs PowerFin documentadas (21 endpoints) |
| 3 | `v0.2.0` | Powerfin POS base — login, surtidores |
| 4 | `v0.3.0` | Flujo de venta completo |
| 5 | `v0.5.0` | Impresión térmica — ESC/POS, config multi-isla, templates editables |
| 5.1 | `v0.6.0` | Módulo de caja + refactor turnos + historial + usuarios en línea |

### 📊 Tests

```bash
# FusionBridge — 69 tests
cd fusion-bridge && ./mvnw test   # BUILD SUCCESS

# POS — 41 tests (Vitest)
cd pos && npm run test            # 41 passed

# Total: 110 tests pasando
```

### 🏗️ Ramas

```
main     — último merge de develop
develop  — cambios de la sesión pendientes de commit
```

---

## Cambios realizados esta sesión (v0.6.0)

### 1. Módulo de Caja — Ingresos, Egresos, Transferencias

**Archivos nuevos:**
- `pos/src/routes/(pos)/cash/+page.svelte` — Dashboard: saldo, botones rápidos, historial movimientos
- `pos/src/routes/(pos)/cash/movement/+page.svelte` — Form ingreso/egreso: valor + botones rápidos + observación
- `pos/src/routes/(pos)/cash/transfer/+page.svelte` — Form transferencia: selección de destinatario (incluye Caja Fuerte), valor, observación

**Archivos modificados:**
- `pos/src/lib/api/types.ts` — Tipos: `CashMovement`, `CashTransfer`, `OnlineUser`, `ShiftCashSummary`, `SAFE_VAULT_USER_ID`, `SAFE_VAULT_ROLE`
- `pos/src/lib/api/powerfin.ts` — Funciones: `createCashMovement`, `getCashMovements`, `getShiftCashSummary`, `getOnlineUsers`, `createTransfer`
- `pos/src/lib/api/powerfin.mock.ts` — Mocks con persistencia localStorage, cálculo dinámico de ventas por usuario
- `tools/powerfin_server.py` — Endpoints cash + cálculo de ventas por shift
- `pos/src/routes/(pos)/+page.svelte` — Botón "Caja" (💰) en nav

### 2. Refactor de Turnos

**Nuevo flujo:**
- Login → siempre va al dashboard (sin redirect a `/shift/open`)
- Sin turno abierto → card "Abrir Turno" con datos del usuario + fecha/hora, surtidores bloqueados
- Con turno abierto → todo funciona normalmente
- Apertura de turno: efectivo inicial fijo $0.00, solo confirmación
- Nav: "Cerrar turno" solo visible si hay turno abierto, "Caja"/"Historial" deshabilitados sin turno

**Archivos modificados:**
- `pos/src/routes/(pos)/+page.svelte` — Eliminado redirect, agregado card "Abrir Turno", bloqueo de operaciones
- `pos/src/routes/shift/open/+page.svelte` — Simplificado a confirmación (sin input de efectivo)
- `pos/src/routes/(pos)/cash/+page.svelte` — Guarda de turno
- `pos/src/routes/(pos)/cash/movement/+page.svelte` — Guarda de turno
- `pos/src/routes/(pos)/cash/transfer/+page.svelte` — Guarda de turno
- `pos/src/lib/components/SaleWizard.svelte` — Guarda de turno
- `pos/src/lib/components/Header.svelte` — Muestra turno solo si existe

### 3. Usuarios en Línea

**Archivo nuevo:**
- `pos/src/routes/(pos)/users/+page.svelte` — Dashboard de usuarios en línea: resumen general (en línea, ventas, monto) + lista individual con ventas y total facturado por turno. Accesible sin turno abierto.

**Archivos modificados:**
- `pos/src/lib/api/types.ts` — `OnlineUser` extendido con `sales_count` + `total_amount`
- `pos/src/lib/api/powerfin.mock.ts` — Cálculo dinámico de ventas desde `mockOrders`
- `tools/powerfin_server.py` — `GET /api/pos/users/online` incluye ventas por shift
- `pos/src/routes/(pos)/+page.svelte` — Botón "Usuarios" (👥) en nav, siempre visible

### 4. Historial de Turno

**Archivo modificado:**
- `pos/src/routes/(pos)/history/+page.svelte` — Completamente rediseñado:
  - Resumen: # despachos y monto total
  - Tab Despachos (⛽): lista de órdenes con estado, monto, cliente, placa, factura
  - **Botón "Reimprimir ticket"** en órdenes completadas
  - Tab Caja (💰): resumen ingresos/egresos + lista de movimientos con saldo running

### 5. API Endpoints consolidados (21 endpoints PowerFin)

| # | Método | Endpoint |
|---|--------|----------|
| 1 | `POST` | `/api/pos/auth/login` |
| 2 | `GET` | `/api/pos/config` |
| 3 | `GET` | `/api/pos/vehicles?plate=` |
| 4 | `GET` | `/api/pos/customers?q=` |
| 5 | `GET` | `/api/pos/customers/by-id` |
| 6 | `POST` | `/api/pos/customers` |
| 7 | `GET` | `/api/pos/prices` |
| 8 | `POST` | `/api/pos/shifts/open` |
| 9 | `GET` | `/api/pos/shifts/current` |
| 10 | `POST` | `/api/pos/shifts/{id}/close` |
| 11 | `GET` | `/api/pos/shifts/{id}/dispatches` |
| 12 | `POST` | `/api/pos/dispatches` |
| 13 | `POST` | `/api/pos/dispatches/{id}/complete` |
| 14 | `POST` | `/api/pos/dispatches/{id}/cancel` |
| 15 | `POST` | `/api/pos/dispatches/{id}/collect` |
| 16 | `POST` | `/api/pos/cash-movements` |
| 17 | `GET` | `/api/pos/shifts/{id}/cash-movements` |
| 18 | `GET` | `/api/pos/shifts/{id}/cash-summary` |
| 19 | `GET` | `/api/pos/users/online` |
| 20 | `POST` | `/api/pos/transfers` |
| 21 | `POST` | `/api/pos/cash-movements` (legacy) |

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

## Para la próxima sesión — Conexión directa a Wayne Synergy

### Objetivo: Quitar el simulador y conectar FusionBridge al Synergy real

### 1. Revisar y validar comandos Fusion a enviar

**Comandos que FusionBridge envía al Synergy:**

| Comando | Propósito | Parámetros clave |
|---------|-----------|-----------------|
| `REQ_PUMP_PRESET` | Autorizar despacho (monto fijo) | `PU=pump_id`, `HO=fusion_hose_id`, `PR=amount`, `OV=order_id`, `CLI=customer_id` |
| `REQ_VOLUME_PRESET` | Autorizar despacho (volumen fijo) | `PU=pump_id`, `HO=fusion_hose_id`, `VL=volume`, `OV=order_id` |
| `REQ_CLEAR_SALE` | Cancelar/limpiar preset en manguera | `PU=pump_id`, `HO=fusion_hose_id` |
| `ECHO` | Keep-alive (cada 120s) | — |

**Formato del protocolo:**
```
<len>|<crypt>|<version>|<user_id>|<msg_type>|<event>|<dest>|<origin>|<params>|^
```
- `len` = 5 dígitos, desde `<version>` hasta `^` inclusive
- `crypt=5` = sin encriptación
- Parámetros: `KEY=VALUE|KEY=VALUE`

### 2. Eventos que FusionBridge recibe del Synergy

| Evento | Significado | Datos útiles |
|--------|-------------|-------------|
| `PUMP_STATUS_CHANGE` | Cambio de estado de manguera | `PU`, `HO`, `ST` (IDLE/AUTHORIZED/FUELLING/STOPPED) |
| `DELIVERY_PROGRESS` | Progreso de despacho (vol+amount) | `PU`, `HO`, `VL`, `AM` |
| `NEW_TRANSACTION` | Venta completada | `PU`, `HO`, `VL`, `AM`, `UP`, `SA` (sale_id) |
| `TRANSACTION_LOCK` | Venta bloqueada para cobro | `PU`, `HO` |
| `SALE_CLEARED` | Venta liberada/limpiada | `PU`, `HO` |

### 3. Tareas pendientes

```
☐ Conectar FusionBridge a 192.168.1.20:3011 (Synergy real)
☐ Validar REQ_PUMP_PRESET con datos reales de la gasolinera
☐ Validar estados de manguera contra dispensador físico
☐ Probar ciclo completo: autorizar → despachar → completar → cobrar
☐ Validar keep-alive ECHO/120s contra Synergy
☐ Probar reconexión automática al cortar TCP
☐ Probar impresión en 192.168.1.31:9100
☐ Ajustar ATO en consola Wayne de 0 → 180 segundos
☐ Probar múltiples despachos simultáneos (lados A y B)
```

### 4. Archivos clave a revisar

```
fusion-bridge/src/main/java/com/powerfin/pos/bridge/
├── fusion/FusionTcpClient.java        ← Conexión TCP, reconexión, keep-alive
├── fusion/FusionMessage.java          ← Parser de mensajes (pipe-delimited)
├── fusion/FusionMessageBuilder.java   ← Constructor de comandos (len correcto)
├── fusion/FusionEventHandler.java     ← Manejo de eventos del Synergy
├── dispatch/DispatchResource.java     ← REST API para autorizar/cancelar
├── dispenser/DispenserStatusCache.java ← Cache de estado de surtidores
├── sse/StationEventBus.java           ← Broadcast SSE a clientes
└── sse/SseEventResource.java          ← Endpoint SSE
```

### 5. Comandos de prueba directa (desde el servidor)

```bash
# Test de conectividad
echo -n "00012|5|2||ECHO||||^" | nc -v 192.168.1.20 3011

# Test de estado de surtidores (suscribirse)
echo -n "00020|5|2||SUBSCRIBE||||^" | nc -v 192.168.1.20 3011

# Test de impresora
nc -zv 192.168.1.31 9100

# Health check FusionBridge
curl -s http://localhost:8090/health
```

### NOTAS

- `plate = 'ABC1234'` está hardcodeado en `SaleWizard.svelte:28` para pruebas. Remover ANTES de producción.
- El delay de 2-5s en "Despachando" → "Cobrar" es del intervalo de polling
- No modificar estructura de polling/SSE sin tests previos
- Siempre `rm -rf .svelte-kit` al reiniciar el POS para evitar caché de Vite
- Los tags v0.4.0/v0.4.1 ya existían (Reasonix, fixes SSE). Phase 5 es v0.5.0
- El estado del server Python se persiste en `tools/powerfin_state.json`. Borrar para reset.
