# NEXT_SESSION.md — Powerfin POS

## Estado actual (2026-06-01)

### ✅ Fases completadas

| Fase | Tag | Descripción |
|------|-----|-------------|
| 1 | `v0.1.0` | FusionBridge TCP connection |
| 2 | — | APIs PowerFin documentadas (21 endpoints) |
| 3 | `v0.2.0` | Powerfin POS base — login, surtidores |
| 4 | `v0.3.0` | Flujo de venta completo |
| 5 | `v0.5.0` | Impresión térmica — ESC/POS, config multi-isla, templates editables |
| 5.1 | `v0.6.0` | Módulo de caja + refactor turnos + historial + usuarios en línea |
| 6 | `v0.7.0` | Validación hardware real — Wayne Synergy |
| 6.1 | `v0.7.1` | Bugfix: match de IDs dispensador/manguera, flujo de cobro |
| 6.2 | `v0.8.0` | **Sincronización multi-dispositivo + cancelación manual** ✅ |

### 📊 Tests

```bash
# FusionBridge — 72 tests
cd fusion-bridge && ./mvnw test   # BUILD SUCCESS

# POS — 41 tests (Vitest)
cd pos && npm run test            # 41 passed

# Total: 113 tests pasando
```

---

## Logros de la sesión 2026-06-01

### 1. Sincronización multi-dispositivo ✅

**Problema:** `pendingOrders` en `localStorage` por navegador. Dispositivo B no veía órdenes creadas en dispositivo A.

**Solución — 4 capas de protección:**

| Capa | Mecanismo | Latencia |
|------|-----------|----------|
| 1 | SSE `NEW_TRANSACTION` → `completeOrder()` | <1s |
| 2 | Reconciliación automática `getShiftDispatches()` → `reconcile()` | 3s |
| 3 | Verificación bajo demanda al hacer clic: `pollDispensers()` + `reconcileWithPowerFin()` | ~300ms |
| 4 | Botón 🔄 refresco manual | ~300ms |

**Archivos modificados:** `+page.svelte`, `DispenserCard.svelte`, `Header.svelte`, `pendingOrders.ts`

### 2. Botón de cancelación manual ✅

**Funcionalidad:** Cancelar autorización de despacho sin esperar los 180s de ATO.

**Reglas de seguridad:**
- Solo visible en estados AUTHORIZED / CALLING / STARTING (nunca durante FUELLING)
- Solo para el usuario que inició la venta (`authorizedBy === $currentUser.name`)
- Diálogo de confirmación obligatorio antes de ejecutar
- Flujo: CLEAR_PRESET al Synergy → `cancelDispatch` en PowerFin → `removeOrder` local

**Archivos modificados:** `DispenserCard.svelte`, `+page.svelte`, `bridge.ts`, `bridge-client.ts`

### 3. Bugfix: cancelDispenser enviaba pump equivocado ✅

**Bug:** `cancelDispenser(dispenserId=1)` siempre enviaba `CLEAR_PRESET_ID_001` al Pump 1, incluso para cancelar el Lado B (Pump 2).

**Fix:** `handleCancelClick` busca `fusion_pump_id` del hose en `$config.dispensers[].sides[]` y lo pasa al endpoint.

### 4. Bugfix: `authorized_by` siempre era 'Carlos Sarmiento' ✅

**Bug:** El servidor Python usaba `active_shift["user_name"]` que siempre era 'Carlos Sarmiento' (hardcodeado). El POS no enviaba `user_name` al abrir turno. `pendingOrders.addOrder()` tomaba `$shift.user_name` en vez de `$currentUser.name`.

**Fix (3 lugares):**
- `SaleWizard`: `authorized_by` y `authorizedBy` usan `$currentUser?.name`
- `+page.svelte`: `handleOpenShift` envía `user_name: $currentUser.name`
- `powerfin_server.py`: `authorized_by = body.get("authorized_by", ...)`

### 5. Bugfix: PowerFin nunca pasaba de AUTHORIZED a COMPLETED ✅

**Bug:** `NEW_TRANSACTION` SSE solo llamaba `pendingOrders.completeOrder()` (local). PowerFin se quedaba en AUTHORIZED. Al reconciliar en otro dispositivo, el status se mapeaba a FUELLING y no mostraba "Cobrar".

**Fix:** El handler SSE `NEW_TRANSACTION` ahora también llama `powerfin.completeDispatch()` (fire-and-forget) para actualizar PowerFin.

### 6. Bugfix: verificación bajo demanda consultaba pump equivocado ✅

**Bug:** `getDispenser(dispenserId)` solo consultaba un pump (ej: Pump 1 para Lado A). Lado B (Pump 2) nunca se verificaba → dejaba pasar ventas en lado ocupado.

**Fix:** `handleSideClick` ahora llama `pollDispensers()` que obtiene TODOS los pumps.

---

## Configuración actual del sitio

| Dato | Valor |
|------|-------|
| Estación | NEOGAS |
| Surtidores | 1 físico (DIESEL, 2 lados) → 2 pumps lógicos en Synergy |
| Combustible | DIESEL (Grade 3, P3) |
| Precio | $3.103/galón |
| Pump 1 → Side A | Fusion hose 1 |
| Pump 2 → Side B | Fusion hose 1 |
| ATO | 180s |
| Moneda | DÓLARES ($) |
| Firmware | Rel-5.19.1 |

---

## Cómo arrancar todo

```bash
cd /home/pvalarezo/grisbiapps/powerfin_pos_gas

# Limpiar estado viejo (primera vez o después de cambios en powerfin_server.py)
./start.sh stop
rm -f tools/powerfin_state.json

# Arrancar
./start.sh powerfin  # PowerFin mock :8080
./start.sh bridge    # FusionBridge :8090 (tarda ~15s)
./start.sh pos       # POS :5173

# Control:
./start.sh stop      # Detener todo
./start.sh status    # Ver estado

# Diagnosticar Synergy:
python3 tools/info_fusion.py
```

Abrir: **`http://192.168.1.113:5173`** | Login: `carlos` / `1234` o `maria` / `1234`

---

## Pendiente para la próxima sesión

### 🔴 Prioridad 1 — Bug: customer_name se pierde en otros dispositivos

**Problema:** Al terminar una venta con estado "Cobrar", el dispositivo que inició la venta muestra el nombre correcto del cliente, pero los otros dispositivos muestran "Consumidor Final".

**Causa:** `powerfin.createDispatch()` envía `customer_id` y `plate` a PowerFin, pero NO envía `customer_name`. Al reconciliar en otro dispositivo, `reconcile()` toma `server.customer_name` que es `null` → fallback a `'Consumidor Final'`.

**Fix pendiente:** Agregar `customer_name` al `CreateDispatchRequest` y enviarlo en `SaleWizard.handleAuthorize()`.

### 🟠 Prioridad 2 — Prueba de impresión térmica

```
☐ Probar impresora en 192.168.1.31:9100
☐ Verificar formato de ticket ESC/POS
☐ Integrar impresión en flujo de cobro
```

### 🟡 Prioridad 3 — Prueba de topologías de dispensadores

```
☐ Probar mapeo con 2+ dispensadores físicos (varios fusion_pump_id por dispenser)
☐ Probar dispensador con múltiples mangueras por lado (ej: 2 grades por lado)
☐ Validar que convertToDispenserState mergea correctamente
☐ Validar que completeOrder matchea correctamente con fusionPumpId + fusionHoseId
```

### 🟢 Prioridad 4 — Integración con PowerFin ERP real

```
☐ Conectar FusionBridge al ERP real (cuando esté disponible)
☐ Validar APIs de clientes, precios, listas
☐ Validar cierre de turno con datos reales
```

---

## NOTAS

- `plate = 'ABC1234'` está hardcodeado en `SaleWizard.svelte:28` para pruebas. Remover ANTES de producción.
- El dispensador físico requiere **palanca manual** además de levantar la pistola (equipo antiguo)
- `SUBSCRIBE|ALL` es necesario en firmware Rel-5.19.1 (suscripciones individuales no funcionan)
- El cambio de precio por protocolo requiere aprobación manual en consola (módulo "Price Change Add In")
- Siempre `rm -rf .svelte-kit` al reiniciar el POS para evitar caché de Vite
- **NO usar `LID` ni `LM` en PRESET** — firmware Rel-5.19.1 crea locks permanentes que requieren reinicio del Synergy
- `localStorage` es caché local, NO source of truth. PowerFin vía reconciliación cada 3s es la autoridad.
- Al reiniciar `powerfin_server.py`, borrar `tools/powerfin_state.json` para evitar datos inconsistentes.
