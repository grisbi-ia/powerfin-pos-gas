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
| 6 | `v0.7.0` | Validación hardware real — Wayne Synergy |
| 6.1 | `v0.7.1` | **Bugfix: match de IDs dispensador/manguera, flujo de cobro** ✅ |

### 📊 Tests

```bash
# FusionBridge — 72 tests
cd fusion-bridge && ./mvnw test   # BUILD SUCCESS

# POS — 41 tests (Vitest)
cd pos && npm run test            # 41 passed

# Total: 113 tests pasando
```

---

## Logros de la sesión 2026-05-29 (tarde)

### 1. Flujo de cobro arreglado ✅

**Bug:** Después de despachar, el surtidor volvía a "Disponible" en vez de "Cobrar".

**Causa raíz — doble mismatch de IDs:**
- `completeOrder()` buscaba por `dispenserId` (ID del armario en config, siempre 1), pero el SSE traía `pumpNumber` (ID del lado en Synergy, 1 o 2). Side A funcionaba por coincidencia (ambos son 1), side B fallaba (config 1 ≠ Fusion 2).
- `completeOrder()` también matcheaba por `hoseId` config (1 o 2) vs `HO` del Fusion (siempre 1). Side B fallaba de nuevo (2 ≠ 1).

**Fix:** Se agregaron `fusionPumpId` y `fusionHoseId` a `PendingOrder`. `completeOrder()` ahora matchea por estos campos (que son los que reporta el Synergy). Documentado en `docs/TOPOLOGIA_DISPENSADORES.md`.

### 2. `finalVolume` siempre mostraba '0.00' ✅

**Causa:** `'0.00'` es truthy en JavaScript → `collectOrder.finalVolume || fallback` nunca ejecutaba el fallback.

**Fix:** `parseFloat(collectOrder.finalVolume) > 0 ? collectOrder.finalVolume : fallback`

### 3. Unidad de volumen hardcodeada ✅

**Fix:** Cambiado `{finalVolume} L` → `{finalVolume} {unitAbbr}` (muestra "gal" para galones).

### 4. `presetAmount = NaN` para tanque lleno ✅

**Fix:** `presetType === 'FULL' ? 0 : (val * unitPrice)`

### 5. Eliminado `autoCompleteOrders()` ✅

Era peligroso: completaba órdenes falsamente cuando el PRESET era rechazado (manguera siempre IDLE + orden FUELLING → falso positivo).

### 6. Eliminado `LID` y `LM` del PRESET ✅

El `LID|LM=NORMAL` en el PRESET creaba locks permanentes en el Synergy que no se liberaban con UNLOCK ni CLEAR_SALE. El firmware Rel-5.19.1 no los maneja correctamente. Documentado en logs de la sesión.

### 7. Endpoints de pago en FusionBridge ✅

Agregados `POST /api/dispatch/payment-lock`, `/payment-clear`, `/payment-unlock` en `DispatchResource.java`. Métodos cliente en `bridge.ts` y `bridge-client.ts`.

### 8. Herramientas de diagnóstico ✅

| Script | Función |
|--------|---------|
| `tools/info_fusion.py` | Consultar estado de dispensadores en Synergy |
| `tools/test_lock.py` | Probar REQ_PAYMENT_TRANSACTION_LOCK |
| `tools/unlock_fusion.py` | Desbloquear venta en Synergy |

### 9. Documentación de topología ✅

`docs/TOPOLOGIA_DISPENSADORES.md` — Explicación con referencia física: armario, lado, pistola. Mapeo de IDs entre PowerFin y Synergy. Match robusto para cualquier topología.

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

# Todo de una vez (sin FusionBridge):
./start.sh           # POS + PowerFin
./start.sh bridge    # FusionBridge (tarda ~15s)

# O individual:
./start.sh powerfin  # PowerFin mock :8080
./start.sh bridge    # FusionBridge :8090
./start.sh pos       # POS :5173

# Control:
./start.sh stop      # Detener todo
./start.sh status    # Ver estado

# Diagnosticar Synergy:
python3 tools/info_fusion.py
```

Abrir: **`http://192.168.1.113:5173`** | Login: `carlos` / `1234`

---

## Pendiente para la próxima sesión

### 🔴 Prioridad 1 — Sincronización multi-dispositivo (CRÍTICO)

**Problema:** `pendingOrders` se guarda en `localStorage` (por navegador). Si el dispositivo A crea una orden y el B no la ve, hay riesgo de:
- Doble cobro (B no sabe que ya se pagó en A)
- Estados inconsistentes (B muestra "Disponible" cuando A muestra "Cobrar")
- Fraude (alguien puede despachar sin que el cajero lo vea)

```
☐ Hacer que la reconciliación con PowerFin sea inmediata al montar la página
☐ Disparar reconciliación al recibir SALE_CLEARED por SSE
☐ Evaluar si FusionBridge debe broadcastear cambios de pendingOrders vía SSE
☐ Sincronizar estado de órdenes entre todos los dispositivos en ≤5s
☐ Probar: 2 navegadores abiertos, venta en A, B debe ver "Cobrar" en ≤5s
☐ Probar: cobro en A, B debe ver "Disponible" en ≤5s
☐ Probar: venta en A, B cierra sesión y reabre → debe ver "Cobrar"
```

**Posibles soluciones a evaluar:**

| Opción | Pros | Contras |
|--------|------|---------|
| Polling más agresivo (cada 5s en vez de 30s) | Simple | Carga al servidor |
| SSE broadcast de cambios de órdenes | Tiempo real, sin polling | FusionBridge no conoce las órdenes (están en PowerFin) |
| PowerFin → SSE relay | Fuente de verdad única | Requiere cambios en PowerFin mock y real |
| Shared localStorage vía backend | Consistente | Overengineered |

**Enfoque recomendado:** Reducir intervalo de reconciliación a 5s + disparar en eventos clave (mount, SALE_CLEARED SSE, después de cobrar). PowerFin es el source of truth, los dispositivos solo cachean.

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
- `localStorage` es por navegador — no usar como source of truth para multi-dispositivo. PowerFin ERP es la fuente de verdad vía reconciliación.
