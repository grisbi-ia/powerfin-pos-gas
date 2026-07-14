# Auditoría del ciclo de vida de un despacho — 2026-07-14

Cada despacho pasa por 6 fases. Este documento mapea cada transición,
cada guardia, y cada punto donde el combustible podría perderse.

---

## FASE 1: CREACIÓN (POS → Backend)

**Trigger:** Despachador hace clic en "Autorizar" en el SaleWizard.

### Paso 1a: `POST /api/pos/dispatches` (create_dispatch)

| # | Guardia | ¿Protege? |
|---|---------|-----------|
| G1 | `pg_advisory_xact_lock(hose_id)` — bloqueo a nivel BD | ✅ Evita doble autorización simultánea |
| G2 | `SELECT 1 WHERE hose_id=X AND status IN ('AUTHORIZED','COMPLETED')` | ✅ 409 si ya hay despacho activo |
| G3 | `shift.status == 'OPEN' AND shift.user_id == current_user` | ✅ 400 si no hay turno |
| G4 | `dispatch_type = lookup(code)` | ✅ 400 si tipo inválido |
| G5 | Credit validation (si aplica) | ✅ Valida contrato y cupo |
| G6 | Sequential number consumption | ⚠️ `except: pass` — no bloquea la venta |
| G7 | `db.add(dispatch)` + `db.flush()` + `db.add(detail)` + `db.commit()` | ✅ Transacción atómica |

**Estado resultante:** `AUTHORIZED`, `total=$0.00`

### Paso 1b: `POST /api/dispatch/authorize` (FusionBridge)

**⚠️ PUNTO CRÍTICO:** Entre 1a y 1b hay una brecha. Si 1a falla (error HTTP, timeout de red), el POS **NUNCA** llama a 1b. Esto es correcto — no hay PRESET sin DB.

| # | Guardia | ¿Protege? |
|---|---------|-----------|
| G8 | `if not tcpClient.isConnected(): return 503` | ✅ Sin conexión al Wayne, no hay PRESET |
| G9 | `FusionMessageBuilder.buildClearStop()` antes del PRESET | ✅ Limpia buffers del pump |
| G10 | `statusCache.setActiveHose()` inmediato | ✅ UI muestra estado correcto |

### Paso 1c: Rollback automático (SaleWizard catch)

```javascript
} catch (err) {
    if (orderId) {
        await powerfin.cancelDispatch(token, orderId);  // ← cancela en backend
    }
}
```

| # | Guardia | ¿Protege? |
|---|---------|-----------|
| G11 | Si `createDispatch` falló → `orderId=null` → no se llama cancel | ✅ |
| G12 | Si `authorizeDispatch` falló → `orderId` existe → se cancela en BD | ✅ |
| **G13** | **Si `authorizeDispatch` envió PRESET pero el HTTP response se perdió** → el POS cancela en BD pero el pump YA está cargando | ⚠️ **GAP** — mismo bug de hoy |

### 🔴 GAP G13: PRESET enviado, respuesta HTTP perdida

**Escenario:**
1. `createDispatch` → OK, `orderId` retornado
2. `authorizeDispatch` → FusionBridge recibe, envía PRESET al Wayne, pump arranca
3. **Respuesta HTTP de FusionBridge al POS se pierde** (timeout, WiFi, etc.)
4. POS: `catch` → `cancelDispatch(orderId)` → BD: CANCELLED
5. Pump sigue cargando. `NEW_TRANSACTION` llega → `complete_dispatch` → dispatch está CANCELLED → Fix #3 lo reactiva ✅

**¿Fix #3 cubre G13?** Sí — pero solo si `amount > 0` y no hay dispatch más nuevo en la manguera. Si el pump NO completó (ATO timeout antes de que alguien cargue), `amount=0` y Fix #3 no reactiva. Esto es correcto — no hubo combustible.

---

## FASE 2: CARGA (Pump dispensando)

**Trigger:** Wayne pump recibe PRESET, cliente aprieta la pistola.

### Estados del pump observables:

```
AUTHORIZED → STARTING → FUELLING → (PAUSED → FUELLING) → IDLE + NEW_TRANSACTION
```

### Guardias durante la carga:

| # | Guardia | ¿Protege? |
|---|---------|-----------|
| G14 | `dispatch_cleanup`: Fix #2 — FULL=1800s, otros=900s | ✅ Tanquero no se cancela antes de 30 min |
| G15 | `dispatch_cleanup`: Fix #1 — verifica pump status vía FusionBridge | ✅ No cancela si pump está FUELLING/STARTING |
| G16 | POS `handleStopClick`: envía STOP al Wayne + CLEAR_STOP | ✅ Frena el flujo, genera NEW_TRANSACTION parcial |
| G17 | POS `executeStop` NO cancela el despacho | ✅ Parcial queda AUTHORIZED → COMPLETED → cobrable |

---

## FASE 3: COMPLETADO (Pump termina)

**Trigger:** Cliente asienta la pistola, o llega al preset.

### FusionBridge → EVT_PUMP_NEW_TRANSACTION

| # | Ruta | Condición |
|---|------|-----------|
| R1 | `completeDispatchOnBackend(orderId, ...)` | `PAY_IN` contiene `OV=orderId` |
| R2 | `completeDispatchByPumpOnBackend(pumpId, hoseId, ...)` | `PAY_IN` sin `OV=` |
| R3 | 3 retries con 1s backoff | Ambas rutas |

### Backend: `complete_dispatch` y `complete_by_pump`

| # | Guardia | ¿Protege? |
|---|---------|-----------|
| G18 | `dispatch not found → return {"status":"ok"}` | ⚠️ SILENCIO — si el order_id no existe, se ignora |
| G19 | `status == COMPLETED, total > 0 → return {"status":"ok"}` | ✅ Idempotente, sin sobreescribir |
| G20 | `status == COMPLETED, total == 0, amount > 0 → corregir` | ✅ Carrera Wayne AM=0 |
| G21 | `status == CANCELLED, amount > 0 → reactivar` (Fix #3) | ✅ Recupera despacho cancelado |
| G22 | `status == CANCELLED, amount > 0 → guard: hose reusada?` (Fix #3 guard) | ✅ No reactiva si hay dispatch más nuevo |
| G23 | `status == CANCELLED, amount == 0 → return {"status":"ok"}` | ✅ Correcto — sin fuel, no reactivar |
| **G24** | **`complete_by_pump`: "no authorized dispatch" → return {"status":"ok"}** | 🔴 **SILENCIO** — fuel despachado sin orden |

### 🔴 GAP G24: complete_by_pump sin dispatch

**Escenario:** Alguien autoriza el pump directamente (llave física). El pump dispensa. FusionBridge recibe `NEW_TRANSACTION` sin `orderId`. `complete_by_pump` busca AUTHORIZED en esa manguera — no hay nada.

**Consecuencia:** Combustible despachado, $0 cobrados, NADIE se entera.

**Mitigación propuesta:** En vez de `return {"status":"ok"}`, insertar en tabla `unmatched_transactions` con pump, hose, volume, amount, timestamp. Al menos queda registro para conciliación manual.

---

## FASE 4: COBRO (POS → Backend)

**Trigger:** Despachador hace clic en "Cobrar" en el dashboard.

### `POST /api/pos/dispatches/{orderId}/collect`

| # | Guardia | ¿Protege? |
|---|---------|-----------|
| G25 | `status == COLLECTED → 409` | ✅ No doble cobro |
| G26 | `status != COMPLETED → 409` | ✅ No cobrar antes de que termine |
| G27 | `total <= 0 → 409` | ✅ No cobrar $0.00 |
| G28 | `effective_amount <= 0 AND no credit → 400` | ✅ No cobrar sin monto |

---

## FASE 5: CANCELACIÓN

### Ruta A: Manual (dashboard)

| # | Guardia | ¿Protege? |
|---|---------|-----------|
| G29 | POS: primero `cancelDispenser(fusionPumpId)` → FusionBridge → CLEAR_PRESET al Wayne | ✅ Frena el pump |
| G30 | POS: después `cancelDispatch(orderId)` → backend | ✅ Cambia estado en BD |
| G31 | Backend: `status == COLLECTED → 409` | ✅ No cancelar cobrado |
| G32 | Backend: `status == COMPLETED AND total > 0 → 409` | ✅ No cancelar con fuel |
| **G33** | **Backend: `status = "CANCELLED"` — NO envía comando al pump** | ⚠️ Solo cambia BD |

### Ruta B: Automática (SaleWizard catch)

| # | Guardia | ¿Protege? |
|---|---------|-----------|
| G34 | Solo se ejecuta si `createDispatch` OK y `authorizeDispatch` falla | ✅ |
| G35 | `cancelDispatch` es fire-and-forget (`.catch {}`) | ⚠️ Si falla, queda huérfano |

### Ruta C: Cleanup service

| # | Guardia | ¿Protege? |
|---|---------|-----------|
| G36 | Fix #2: threshold progresivo | ✅ |
| G37 | Fix #1: verifica pump status | ✅ |
| G38 | Solo AUTHORIZED + $0.00 | ✅ No toca COMPLETED/COLLECTED |

---

## FASE 6: SRI (Facturación electrónica)

**Trigger:** Fire-and-forget después de `collect`.

| # | Guardia | ¿Protege? |
|---|---------|-----------|
| G39 | `_key49_background` atrapa todas las excepciones | ✅ No bloquea la venta |
| G40 | `key49_enabled == false` → no intenta | ✅ |

---

## RESUMEN DE GAPS

| Gap | Severidad | Descripción | Estado |
|-----|-----------|-------------|--------|
| **G13** | 🔴 ALTA | PRESET enviado, respuesta HTTP perdida → cancel automático | ✅ Fix #3 |
| **G24** | 🔴 ALTA | `complete_by_pump` sin dispatch → silencio total | ❌ ABIERTO |
| G18 | 🟡 MEDIA | `complete_dispatch` sin dispatch → silencio | ⚠️ Podría loguear |
| G35 | 🟡 MEDIA | Rollback cancel fire-and-forget → huérfano silencioso | ⚠️ Limpiado por cleanup |
| G6 | 🟢 BAJA | Secuencial agotado → venta sigue | ⚠️ Ticket sin número |

---

## DIAGRAMA DE FLUJO

```
CREACIÓN                  CARGA                   COMPLETADO              COBRO
─────────                ───────                 ───────────             ─────
POS→create_dispatch      pump FUELLING           Wayne→NEW_TRANSACTION   POS→collect
  │ G1-G7                    │ G14-G17               │ G18-G24              │ G25-G28
  ▼                          ▼                       ▼                      ▼
AUTHORIZED               (dispensando)           COMPLETED              COLLECTED
$0.00                                              $XXX.XX
  │                                                        
  │ POS→authorize                                        
  │   │ G8-G10                                            
  │   ▼                                                   
  │ pump STARTING                                         
  │   │                                                   
  │   │ G13 ⚠️ (catch cancela si timeout)                 
  │   │ Fix #3 ✅ (reactiva si fuel real)                  
  │   ▼                                                   
  │ pump FUELLING                                         
  │                                                       
  │ CANCELACIÓN                                           
  ├── Manual: G29-G33                                     
  ├── Auto: G34-G35                                       
  └── Cleanup: G36-G38                                    
```

---

## G24 — El último gap abierto

**Recomendación:** Crear tabla `unmatched_transactions` y loguear en vez de silenciar.

```sql
CREATE TABLE unmatched_transactions (
    id SERIAL PRIMARY KEY,
    fusion_pump_id INT,
    fusion_hose_id INT,
    sale_id VARCHAR(50),
    volume DECIMAL,
    amount DECIMAL,
    unit_price DECIMAL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

```python
# En complete_by_pump, cuando no encuentra dispatch:
if not row:
    await db.execute(
        insert(UnmatchedTransaction).values(
            fusion_pump_id=body.fusion_pump_id,
            fusion_hose_id=body.fusion_hose_id,
            sale_id=body.fusion_sale_id,
            volume=body.volume,
            amount=body.amount,
            unit_price=body.unit_price,
        )
    )
    await db.commit()
    logger.warning("Unmatched transaction: pump=%d hose=%d amount=%s",
                   body.fusion_pump_id, body.fusion_hose_id, body.amount)
    return {"status": "logged", "detail": "unmatched — logged for audit"}
```

¿Quieres que implemente G24 ahora?
