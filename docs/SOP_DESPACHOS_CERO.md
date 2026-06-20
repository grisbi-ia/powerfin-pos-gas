# SOP — Despachos con valores CERO o display del Wayne pegado

> Última actualización: 2026-06-20

## Dos escenarios distintos — no confundir

| | Escenario A: "Cobrar $0.00" | Escenario B: "Cobrar $XX pero no deja" |
|---|---|---|
| **Síntoma** | Dashboard muestra `COBRAR $0.00` | Dashboard muestra `COBRAR $20.00` (o cualquier monto > 0) |
| **Error al cobrar** | Ninguno (antes) o "no se puede cobrar $0.00" (ahora) | "El despacho aún no ha terminado. Espere a que el surtidor complete el despacho." |
| **¿Salió combustible?** | **SÍ** | **NO** (o no se sabe) |
| **¿Wayne mandó `NEW_TRANSACTION`?** | **SÍ**, pero con `AM=0` (carrera) o el backend no lo procesó (HTTP/2) | **NO** — el preset expiró por ATO=180s |
| **Status en BD** | `COMPLETED` con `total=0.00` | `AUTHORIZED` con `total=0.00` |
| **Causa raíz** | HTTP/2 body loss (arreglado en v0.19.4) | Wayne timeout sin despachar, nadie cancela el dispatch |
| **Frecuencia** | No ha vuelto en 3 días | Ocurrió hoy (1 caso) |
| **Arreglo manual** | Actualizar `dispatches` + `dispatch_details` con valores reales | Cancelar dispatch en BD + limpiar display Wayne |

---

## Escenario A: Despacho COMPLETED con total $0.00 (bug viejo — arreglado)

### Causa (ya corregida en commits e584b56 + a2f0e12)

Java 21 `HttpClient` negociaba HTTP/2 por defecto. FastAPI/Uvicorn solo soporta HTTP/1.1.
El body de `complete_dispatch` se generaba correctamente pero **llegaba vacío** al backend.
Resultado: `422 body: Field required (missing)` → dispatch quedaba `COMPLETED` con `total=0.00`.

**Fix aplicado:**
```java
// FusionEventHandler.java — constructor
this.httpClient = HttpClient.newBuilder()
    .connectTimeout(Duration.ofSeconds(5))
    .version(HttpClient.Version.HTTP_1_1)  // ← esta línea solucionó
    .build();
```

### Defensas adicionales (commit e584b56)

| Capa | Qué hace |
|------|----------|
| `complete_dispatch` | Si COMPLETED + total=0 + amount>0 → **corrige** totals (antes ignoraba) |
| `complete-by-pump` | Busca AUTHORIZED + COMPLETED(total=0); ignora si ya tiene totals |
| `collect_dispatch` | Exige `status==COMPLETED` + `total>0` + `effective_amount>0` |
| `cancel_dispatch` | Limpia `sri_status=NULL` al cancelar |

### Si llegara a ocurrir de nuevo (poco probable)

```bash
# 1. Identificar el dispatch problemático
psql -h localhost -p 5433 -U postgres -d powerfin_gas -c \
  "SELECT dispatch_id, order_id, status, total, hose_id FROM dispatches 
   WHERE status = 'COMPLETED' AND total = 0 ORDER BY created_at DESC LIMIT 5;"

# 2. Ver el monto real en el Wayne (display físico de la bomba)

# 3. Actualizar BD con valores reales
#    Ejemplo: despacho de $22.00 con IVA 15%
#    subtotal = 22.00 / 1.15 = 19.13
#    tax = 22.00 - 19.13 = 2.87
psql -h localhost -p 5433 -U postgres -d powerfin_gas << 'SQL'
BEGIN;
UPDATE dispatches SET subtotal = 19.13, tax_amount = 2.87, total = 22.00
WHERE dispatch_id = <ID>;
UPDATE dispatch_details SET quantity = <GALONES>, subtotal = 19.13, 
       tax_amount = 2.87, total = 22.00
WHERE dispatch_id = <ID>;
COMMIT;
SQL
```

---

## Escenario B: Dispatch AUTHORIZED con total $0.00 (bug nuevo)

### Causa

1. POS envía PRESET ($20 MONEY) al Wayne → Wayne autoriza → `ST=AUTHORIZED`
2. El cliente **NUNCA** despacha combustible
3. A los 180 segundos (ATO del Wayne), la autorización expira
4. Wayne vuelve a `IDLE` **sin emitir `EVT_PUMP_NEW_TRANSACTION`**
5. El dispatch queda en `AUTHORIZED` para siempre

### Evidencia en logs

```
12:27:23  Preset sent: pump=1 hose=2 order=OV-...510 value=20
12:27:23  Dispenser 1 status: AUTHORIZED (MONEY_PRESET+IDLE)
          ← 3 minutos de silencio
12:30:24  Dispenser 1 status: IDLE (hose:0)  ← NUNCA hubo NEW_TRANSACTION
```

Comparar con despachos normales:
```
12:35:59  AUTHORIZED → STARTING → FUELLING → NEW_TRANSACTION → IDLE ✓
```

### Diagnóstico rápido

```bash
# ¿El Wayne mandó NEW_TRANSACTION?
journalctl -u fusion-bridge --since "FECHA_INICIO" --until "FECHA_FIN" --no-pager \
  | grep -i "New transaction.*pump=<NUM>" 

# Si no aparece → Escenario B (preset expiró sin despachar)
# Si aparece con AM=0 → Escenario A (HTTP/2, ya arreglado)
```

### Arreglo manual

```bash
# 1. Cancelar el dispatch en BD
psql -h localhost -p 5433 -U postgres -d powerfin_gas -c \
  "UPDATE dispatches SET status = 'CANCELLED', sri_status = NULL WHERE dispatch_id = <ID>;"

# 2. Verificar si el display del Wayne está pegado (ver abajo)
```

---

## Display del Wayne pegado en "COBRAR $XX.00"

### Causa

El POS **nunca ejecuta el handshake de pago** con el Wayne después de cobrar.
Las funciones `paymentLock()`, `paymentClear()`, `paymentUnlock()` existen en `bridge.ts`
pero no se llaman desde `SaleWizard.svelte`.

El display del Wayne se queda pegado mostrando la última transacción completada
porque nunca se ejecutó `REQ_PAYMENT_CLEAR_SALE`.

### Cómo identificar el saleId del Wayne

El `saleId` (SA) es un ID interno del Wayne. Se obtiene del evento `NEW_TRANSACTION`.

```bash
# Buscar el NEW_TRANSACTION de la bomba en cuestión
journalctl -u fusion-bridge --since "FECHA" --until "FECHA" --no-pager \
  | grep "New transaction.*pump=<NUM>"

# Ejemplo de salida:
# New transaction — saleId=910, pump=1, hose=2, volume=6.643, amount=22.00, orderId=OV-...
#                                  ^^^^ este es el saleId
```

### Limpiar el display manualmente (3 pasos)

```bash
SALE_ID="910"  # el que obtuviste del paso anterior

# 1. Lock
curl -s -X POST http://localhost:8090/api/dispatch/payment-lock \
  -H 'Content-Type: application/json' \
  -d "{\"sale_id\":\"$SALE_ID\",\"lock_id\":\"$SALE_ID\"}"

# 2. Clear (limpia la transacción del display)
curl -s -X POST http://localhost:8090/api/dispatch/payment-clear \
  -H 'Content-Type: application/json' \
  -d "{\"sale_id\":\"$SALE_ID\",\"method\":\"CASH\",\"lock_id\":\"$SALE_ID\"}"

# 3. Unlock
curl -s -X POST http://localhost:8090/api/dispatch/payment-unlock \
  -H 'Content-Type: application/json' \
  -d "{\"sale_id\":\"$SALE_ID\",\"lock_id\":\"$SALE_ID\"}"
```

Después de esto el display del Wayne debe volver a IDLE.

---

## Resumen de gaps pendientes de código

| Gap | Descripción | Prioridad |
|-----|-------------|-----------|
| Handshake faltante | `SaleWizard.handleCollect()` no llama `paymentLock/Clear/Unlock` | **ALTA** — display pegado en cada venta |
| Cancelación automática | Dispatch huérfano cuando Wayne ATO expira sin NEW_TRANSACTION | Media — requiere tracking en FusionBridge |
| `fusionSaleId` en frontend | El `saleId` de Wayne no se almacena en `DispatchOrder` | Media — necesario para el handshake |

---

## Logs útiles para diagnóstico

```bash
# Ver todos los eventos de una bomba específica
journalctl -u fusion-bridge --since "YYYY-MM-DD HH:MM" --until "YYYY-MM-DD HH:MM" --no-pager \
  | grep -i "Dispenser <NUM>\|pump=<NUM>"

# Ver solo NEW_TRANSACTION
journalctl -u fusion-bridge --since "YYYY-MM-DD" --no-pager \
  | grep "New transaction"

# Ver completeDispatch (confirma que el backend recibió la llamada)
journalctl -u fusion-bridge --since "YYYY-MM-DD" --no-pager \
  | grep "completeDispatch"

# Estado actual de despachos activos
psql -h localhost -p 5433 -U postgres -d powerfin_gas -c \
  "SELECT dispatch_id, order_id, status, total, preset_value, hose_id, 
          to_char(created_at,'HH24:MI:SS') as creado
   FROM dispatches 
   WHERE status IN ('AUTHORIZED','COMPLETED') 
   ORDER BY created_at DESC;"

# Despachos con total cero (anomalías)
psql -h localhost -p 5433 -U postgres -d powerfin_gas -c \
  "SELECT dispatch_id, order_id, status, total, created_at 
   FROM dispatches WHERE total = 0 AND status NOT IN ('CANCELLED','PENDING')
   ORDER BY created_at DESC;"
```
