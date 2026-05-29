# NEXT_SESSION.md — Powerfin POS

## Estado actual (2026-05-29)

### ✅ Fases completadas

| Fase | Tag | Descripción |
|------|-----|-------------|
| 1 | `v0.1.0` | FusionBridge TCP connection |
| 2 | — | APIs PowerFin documentadas (21 endpoints) |
| 3 | `v0.2.0` | Powerfin POS base — login, surtidores |
| 4 | `v0.3.0` | Flujo de venta completo |
| 5 | `v0.5.0` | Impresión térmica — ESC/POS, config multi-isla, templates editables |
| 5.1 | `v0.6.0` | Módulo de caja + refactor turnos + historial + usuarios en línea |
| 6 | `v0.7.0` | **Validación hardware real — Wayne Synergy** ✅ |

### 📊 Tests

```bash
# FusionBridge — 72 tests
cd fusion-bridge && ./mvnw test   # BUILD SUCCESS

# POS — 41 tests (Vitest)
cd pos && npm run test            # 41 passed

# Total: 113 tests pasando
```

---

## Logros de la sesión 2026-05-29

### 1. PRESET_EMPTY resuelto ✅

**Causa:** Parámetros del Transaction Engine (Retries, ZeroSale, AuthTimeout) no se propagaban de ForecourtManager a las bombas. Quedaban en `-1`.

**Solución:** Desconexión/reconexión física del cable serial del dispensador forzó la reinicialización del Transaction Engine desde la DB del Fusion.

**Hallazgo:** Los cambios de configuración de comportamiento (ATO, Retries) requieren reinicializar el dispensador. Los cambios de precios se propagan en caliente.

### 2. Conexión FusionBridge → Synergy real ✅

- `FusionTcpClient` apunta a `192.168.1.20:3011`
- `SUBSCRIBE|ALL` para recibir todos los eventos (suscripciones individuales no funcionan en Rel-5.19.1)
- `REQ_PUMP_PRESET` como comando principal de autorización
- `REQ_PUMP_AUTH` como Plan B manual (endpoint `/api/dispatch/authorize-auth`)
- Keep-alive ECHO cada 120s, reconexión con backoff

### 3. Precio dinámico ✅

- `HO=1@PRECIO` en el PRESET: la bomba despacha al precio del cliente
- `LV=1` agregado para evitar error `Price Level [0]`
- Precio DIESEL actualizado en Synergy: $9.999 → $3.103
- Al expirar ATO, el precio se restaura automáticamente al de consola
- `PAY_IN` viaja con todos los datos del cliente (OV, CLI, PLC, LISTA)

### 4. Mapeo surtidor/manguera multi-pump ✅

**Realidad física:** 1 dispensador DIESEL con 2 mangueras.
**Synergy:** Configurado como 2 pumps independientes (pump 1 → lado A, pump 2 → lado B).

**Solución en código:**
- `HoseConfig.fusion_pump_id`: cada manguera declara a qué pump del Fusion pertenece
- `convertToDispenserState`: mergea múltiples Fusion pumps en UN solo `DispenserState`
- `online = any(pump OK)`: el surtidor está online si al menos un pump no está CLOSED/ERROR
- Estados globales (CLOSED, ERROR, STOPPED) se aplican a todas las mangueras del pump

### 5. Visualización de estados corregida ✅

| Bug | Causa | Fix |
|-----|-------|-----|
| Siempre "Disponible" | `getSideInfo` hardcodeaba `status:'IDLE'` | Usa `primaryHose.status` real |
| Surtidor "offline" | `online=false` global ignoraba pumps activos | `online = pumpStates.some(s => s)` |
| CLOSED invisible | `isActive` solo con `activeHose>0` | `isGlobalState` para CLOSED/ERROR/STOPPED |
| activeHose=0 en AUTHORIZED | `HO` vacío, el dato viene en `PR_HO` | `FusionEventHandler` extrae de `PR_HO` |
| 2 pumps → 1 dispenser se sobrescribían | `map()` creaba 2 objetos con mismo ID | Merge en UN solo `DispenserState` |

### 6. Mock PowerFin actualizado ✅

- 1 dispensador DIESEL con 2 lados (Side A → pump 1, Side B → pump 2)
- Precio STANDARD: $3.103/galón
- Cliente Juan Carlos Pérez → STANDARD (ya no VIP)
- Unidad: GALONES (no litros)

### 7. Herramientas y scripts ✅

| Script | Función |
|--------|---------|
| `diagnostico_preset.py` | Verificar estado + probar PRESET en bombas |
| `reiniciar_bomba.py` | Reinicializar Transaction Engine vía protocolo |
| `actualizar_precio.py` | Cambiar precio de combustible en Synergy |
| `start.sh` | Control de servicios (start/stop/status) |

### 8. Reglas de arquitectura ✅

- **NO silent fallbacks** agregado a `AGENTS.md`
- `CONFIGURACION_WAYNE.md`: procedimiento completo de cambios de configuración

---

## Configuración actual del sitio

| Dato | Valor |
|------|-------|
| Estación | NEOGAS |
| Surtidores | 1 físico (DIESEL, 2 mangueras) → 2 pumps lógicos en Synergy |
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

# Todo de una vez:
./start.sh           # POS + PowerFin
./start.sh bridge    # FusionBridge (tarda ~15s)

# O individual:
./start.sh powerfin  # PowerFin mock :8080
./start.sh bridge    # FusionBridge :8090
./start.sh pos       # POS :5173

# Control:
./start.sh stop      # Detener todo
./start.sh status    # Ver estado
```

Abrir: **`http://192.168.1.113:5173`** | Login: `carlos` / `1234`

---

## Pendiente para la próxima sesión

### Prioridad 1 — Prueba de despacho físico real

```
☐ Levantar pistola + palanca manual en dispensador físico
☐ Verificar transiciones de estado: IDLE → CALLING → AUTHORIZED → STARTING → FUELLING → EOT → IDLE
☐ Verificar NEW_TRANSACTION: SA, VO, AM, PU, PAY_IN correctos
☐ Verificar DELIVERY_PROGRESS en tiempo real
☐ Flujo completo: autorizar → despachar → cobrar → imprimir
☐ Probar despachos simultáneos en ambos lados
```

### Prioridad 2 — Prueba de topologías de dispensadores

```
☐ Probar mapeo con 2+ dispensadores físicos (varios fusion_pump_id por dispenser)
☐ Probar dispensador con múltiples mangueras por lado (ej: 2 grades por lado)
☐ Probar mezcla: algunos pumps 1:1 con dispensers, otros multi-pump → 1 dispenser
☐ Validar que convertToDispenserState mergea correctamente en todas las topologías
☐ Validar que online/offline funciona con combinaciones complejas
```

### Prioridad 3 — Impresión térmica

```
☐ Probar impresora en 192.168.1.31:9100
☐ Verificar formato de ticket ESC/POS
☐ Integrar impresión en flujo de cobro
```

### Prioridad 4 — Integración con PowerFin ERP real

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
- El error `Price Level [0]` en logs del Synergy es cosmético — el Fusion lo ignora
- `Retries [-1] ZeroSale [-1] AuthTimeout [-1]` en logs es DEBUG, no bloquea el PRESET
- El cambio de precio por protocolo requiere aprobación manual en consola (módulo "Price Change Add In")
- Siempre `rm -rf .svelte-kit` al reiniciar el POS para evitar caché de Vite
