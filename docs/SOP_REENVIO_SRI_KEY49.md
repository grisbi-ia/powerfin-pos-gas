# SOP — Reenvío de facturas al SRI vía Key49

> **Propósito**: Diagnosticar y reenviar facturas electrónicas que quedaron pendientes
> o fallidas en el envío al SRI a través de Key49.

```
Última actualización: 2026-06-23
Relacionado: docs/ROADMAP.md (Phase 11e), docs/SOP_DESPACHOS_CERO.md
```

---

## 1. Arquitectura del flujo SRI

```
POS cobra despacho
  └─ collect_dispatch()
       ├─ Guarda total, cliente, IVA, etc. en DB
       ├─ Calcula clave de acceso SRI (49 dígitos, módulo 11)
       └─ Fire-and-forget → asyncio.create_task(_key49_background)
            └─ emitir_factura() → POST a API Key49
                 ├─ Éxito  → sri_status=AUTHORIZED, key49_access_key=xxx
                 ├─ Error SRI → sri_status=REJECTED, sri_messages=[...]
                 ├─ Error Key49 → sri_status=PENDING (se reintenta después)
                 └─ Timeout red → sri_status=PENDING

Reintento manual:
  └─ POST /api/pos/dispatches/retry-pending-invoices
       └─ retry_pending_invoices()
            ├─ PENDING + <24h → emitir_factura()
            └─ PENDING + >24h → sri_status=FAILED (SRI rechaza fecha pasada)
```

**Punto clave**: El envío al SRI es **fire-and-forget**. Si Key49 está caído o hay
problema de red, la factura queda `PENDING` y **no bloquea la venta**. El cobro
se completa normalmente. El reenvío se hace después, manual o por lote.

---

## 2. Diagnosticar — ¿qué facturas tienen problemas?

```sql
-- Resumen por estado
SELECT sri_status, COUNT(*) AS total, SUM(total) AS monto
FROM dispatches
WHERE status != 'CANCELLED'
GROUP BY sri_status
ORDER BY sri_status;

-- Facturas PENDING (nunca se enviaron o Key49 estaba caído)
SELECT order_id, sequential_number, total, sri_status, created_at
FROM dispatches
WHERE sri_status = 'PENDING'
  AND status != 'CANCELLED'
ORDER BY created_at DESC;

-- Facturas FAILED (intento falló, manual o automático)
SELECT order_id, sequential_number, total, sri_status,
       sri_messages, created_at
FROM dispatches
WHERE sri_status = 'FAILED'
  AND status != 'CANCELLED'
ORDER BY created_at DESC;

-- Facturas REJECTED (SRI las rechazó)
SELECT order_id, sequential_number, total, sri_status,
       sri_messages, created_at
FROM dispatches
WHERE sri_status = 'REJECTED'
  AND status != 'CANCELLED'
ORDER BY created_at DESC;

-- Facturas enviadas correctamente
SELECT order_id, sequential_number, access_key, key49_access_key,
       total, sri_status
FROM dispatches
WHERE sri_status = 'AUTHORIZED'
ORDER BY created_at DESC
LIMIT 20;
```

### Estados de `sri_status`

| Estado | Significado | ¿Reintentable? |
|--------|------------|:---:|
| `NULL` | Nunca intentado (despacho cancelado o sin cobrar) | — |
| `PENDING` | Pendiente de envío a Key49 | ✅ Sí |
| `CREATED` | Key49 recibió, creando comprobante | ⏳ Esperar |
| `SIGNED` | Key49 firmó digitalmente | ⏳ Esperar |
| `SENT` | Enviado al SRI, esperando respuesta | ⏳ Esperar |
| `AUTHORIZED` | ✅ SRI autorizó — OK | — |
| `REJECTED` | ❌ SRI rechazó | ✅ Sí (reset a PENDING) |
| `FAILED` | ❌ Error de Key49 o venció (>24h) | ✅ Sí (si <24h) |

---

## 3. Reenviar facturas

### 3.1 Requisitos previos

- Token de administrador (ADMIN o SUPERVISOR)
- Key49 habilitado: `system_config.key49_enabled = true`
- URL y API key de Key49 configurados en `system_config`
- Factura con menos de 24h de antigüedad (SRI rechaza fechas pasadas)

### 3.2 Opción A — Reenviar UNA factura específica

Útil cuando sabes exactamente qué `order_id` falló.

```bash
# 1. Obtener token de admin
TOKEN=$(curl -s -X POST http://localhost:8080/api/admin/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"TU_PASSWORD"}' | jq -r '.token')

# 2. Reenviar factura (reemplaza DP-20260620-001 con el order_id real)
curl -s -X POST "http://localhost:8080/api/pos/dispatches/DP-20260620-001/retry-sri" \
  -H "Authorization: Bearer $TOKEN" | jq

# Respuesta esperada:
# {"order_id":"DP-20260620-001","success":true,"sri_status":"AUTHORIZED"}
```

**Qué hace internamente**:
1. Resetea `sri_status` a `PENDING` (incluso si estaba `FAILED`)
2. Limpia `sri_messages`
3. Envía a Key49 **reutilizando la clave de acceso ya guardada** (`dispatches.access_key`)
4. Actualiza `sri_status` según respuesta

> ⚠️ **Ojo — NO recalcula la clave de acceso.** La implementación
> (`retry_single_invoice` en `app/api/dispatches.py`) solo resetea el estado y llama a
> `emitir_factura`, que usa `dispatch.access_key` tal como está guardada.
> Consecuencia: **solo sirve para reenviar el MISMO día de emisión**, porque la clave
> lleva la fecha embebida (ddMMyyyy) y `emitir_factura` manda `issue_date = hoy`.
> Si la fecha no coincide, el SRI rechaza el comprobante.
> Para facturas de días anteriores usar la **Opción D** (script de recuperación),
> que sí regenera la clave con la fecha de hoy.

### 3.2b Opción D — Reemitir facturas de días anteriores (regenera la clave)

Único camino para facturas "nunca enviadas" o con referencia fantasma de días
pasados, porque **regenera la clave de acceso con la fecha de hoy**.

```bash
cd pos_backend && source venv/bin/activate

# 1. Clasificar (sin llamadas a Key49)
python scripts/recover_pending_invoices.py --classify-only

# 2. Dry-run de UNA factura (reconcilia contra Key49 por access_key — no duplica)
DATABASE_HOST=100.97.47.123 DATABASE_PORT=5432 DATABASE_NAME=powerfin_gas \
DATABASE_USER=agent_llm DATABASE_PASSWORD=... PYTHONPATH=. \
  python scripts/recover_pending_invoices.py --dispatch-id 21031 --min-age-hours 0 --limit 1

# 3. Ejecutar (agregar --execute)
DATABASE_HOST=100.97.47.123 DATABASE_PORT=5432 DATABASE_NAME=powerfin_gas \
DATABASE_USER=agent_llm DATABASE_PASSWORD=... PYTHONPATH=. \
  python scripts/recover_pending_invoices.py --dispatch-id 21031 --min-age-hours 0 --limit 1 --execute
```

Parámetros útiles: `--month 2026-06` (por mes), `--limit N`, `--order newest`,
`--no-reconcile` (omite la verificación en Key49, **no recomendado**).
El reporte JSON queda en `/tmp/k49_recovery.json`.

**Efecto sobre el ticket del cliente**: la clave impresa deja de coincidir con la
enviada al SRI (el código numérico es aleatorio). Una **reimpresión** desde historial
sale con la clave correcta, porque el POS la lee de la BD.

> Nota: `--min-age-hours` por defecto es **24**, o sea que las facturas recientes se
> omiten. Para una del mismo día hay que pasar `--min-age-hours 0`.

### 3.3 Opción B — Reenviar TODAS las pendientes (lote)

Útil al final del día para procesar todo lo acumulado.

```bash
TOKEN=$(curl -s -X POST http://localhost:8080/api/admin/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"TU_PASSWORD"}' | jq -r '.token')

curl -s -X POST "http://localhost:8080/api/pos/dispatches/retry-pending-invoices" \
  -H "Authorization: Bearer $TOKEN" | jq

# Respuesta esperada:
# {"retried": 5, "expired": 2}
```

**Qué hace internamente**:
1. Busca todos los despachos con `sri_status = PENDING` (no cancelados)
2. Para cada uno:
   - Si tiene **<24h** → `emitir_factura()` a Key49
   - Si tiene **>24h** → marca como `FAILED` con mensaje: "Vencida: más de 24h desde emisión"
3. Retorna conteo: `{retried: N, expired: M}`

> ⚠️ Las facturas vencidas (>24h) **no se pueden recuperar por esta vía**.
> Ver sección 5 para opciones alternativas.

### 3.4 Opción C — Verificar estado de una factura en Key49

Consulta el estado actual en Key49 sin reintentar:

```bash
TOKEN=$(curl -s -X POST http://localhost:8080/api/admin/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"TU_PASSWORD"}' | jq -r '.token')

curl -s "http://localhost:8080/api/pos/dispatches/DP-20260620-001/sri-status" \
  -H "Authorization: Bearer $TOKEN" | jq
```

---

## 4. Verificación post-reenvío

Después de ejecutar el reenvío, verifica los resultados:

```sql
-- Conteo actualizado
SELECT sri_status, COUNT(*) AS total
FROM dispatches
WHERE status != 'CANCELLED'
GROUP BY sri_status;

-- Facturas que siguen con problemas
SELECT order_id, sequential_number, total, sri_status, sri_messages
FROM dispatches
WHERE sri_status IN ('PENDING', 'FAILED', 'REJECTED')
  AND status != 'CANCELLED'
ORDER BY created_at DESC;
```

---

## 5. Casos especiales

### 5.1 Factura vencida (>24h) — no se puede enviar al SRI

El SRI rechaza facturas con fecha de emisión pasada. La política automática las
marca como `FAILED`. Opciones:

1. **Anular y re-facturar**: Cancelar el despacho original, crear uno nuevo con
   fecha actual. Solo viable si el despacho no tiene combustible real entregado.
2. **Nota de crédito**: Emitir nota de crédito electrónica y re-facturar (requiere
   soporte de Key49 para notas de crédito).
3. **Conciliación manual**: Documentar la factura como emitida fuera del sistema
   SRI y reportar en la declaración mensual.

### 5.2 Factura con total $0.00 enviada al SRI

Si una factura de $0.00 llegó a `AUTHORIZED`, ya está en los sistemas del SRI.
No se puede "des-enviar". Toca:

```sql
-- Identificar facturas de $0.00 autorizadas en SRI
SELECT order_id, sequential_number, access_key, total, sri_status
FROM dispatches
WHERE sri_status = 'AUTHORIZED' AND total = 0;
```

Procedimiento: conciliar manualmente con el contador para la declaración mensual.

### 5.3 Key49 está caído (timeout / unreachable)

Las facturas quedan en `PENDING`. Reintentar más tarde con la opción B (lote).
El sistema **no tiene scheduler automático** — el reenvío es **siempre manual**
o por llamado al endpoint.

> ⚠️ Esto es un agujero conocido: el reconciler de fondo (cada 120 s) **solo lee**
> Key49 y **solo** para despachos que **ya tienen** `key49_invoice_id`. Un despacho
> `PENDING` **sin** `key49_invoice_id` (nunca llegó a Key49) **no lo toca nadie** y se
> queda pegado indefinidamente. Ver `NEXT_SESSION.md` (reintento automático pendiente).

### 5.4 Referencia fantasma de Key49 (404)

Síntoma: `sri_messages` = `"Referencia Key49 inexistente (404) — se reemitirá"` y
`key49_invoice_id` en NULL. Ocurre cuando la BD tenía un `key49_invoice_id` que Key49
desconoce (típico tras una recuperación). La fila queda marcada "se reemitirá" pero
**nadie la reemite** → usar la **Opción D** (script), que sí regenera la clave.

---

## 6. Configuración de Key49

```sql
-- Verificar configuración actual
SELECT key, value FROM system_config WHERE key LIKE 'key49%';
```

| Key | Descripción | Ejemplo |
|-----|------------|---------|
| `key49_enabled` | Habilitar facturación electrónica | `true` / `false` |
| `key49_api_url` | URL base de la API Key49 | `https://api.key49.com/v1` |
| `key49_api_key` | Token de autenticación | `sk-xxxxxxxx` |
| `key49_ambiente` | Ambiente SRI | `PRUEBAS` / `PRODUCCION` |

Si `key49_enabled = false`, el sistema **nunca** intenta enviar facturas al SRI
(todas quedan `PENDING`). Esto es útil en fase de pruebas.

---

## 7. Script rápido de diagnóstico

```bash
#!/bin/bash
# diagnosticar_sri.sh — ver estado SRI de facturas

BACKEND="http://localhost:8080"
TOKEN=$(curl -s -X POST "$BACKEND/api/admin/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"TU_PASSWORD"}' | jq -r '.token')

echo "=== Facturas PENDING ==="
curl -s "$BACKEND/api/admin/reports/sales?sri_status=PENDING&page_size=5" \
  -H "Authorization: Bearer $TOKEN" | jq '.items[] | {order_id, sequential_number, total, sri_status}'

echo ""
echo "=== Facturas FAILED ==="
curl -s "$BACKEND/api/admin/reports/sales?sri_status=FAILED&page_size=5" \
  -H "Authorization: Bearer $TOKEN" | jq '.items[] | {order_id, sequential_number, total, sri_status, sri_messages}'

echo ""
echo "=== Reenviar todas las pendientes ==="
read -p "¿Reenviar ahora? (s/N): " CONFIRM
if [ "$CONFIRM" = "s" ]; then
  curl -s -X POST "$BACKEND/api/pos/dispatches/retry-pending-invoices" \
    -H "Authorization: Bearer $TOKEN" | jq
fi
```

---

## Referencias

- `pos_backend/app/services/key49_service.py` — Lógica de emisión y retry
- `pos_backend/app/api/dispatches.py` — Endpoints `/retry-sri` y `/retry-pending-invoices`
- `pos_backend/app/models/dispatch.py` — Columnas `sri_status`, `key49_access_key`, `sri_messages`
- `docs/SOP_DESPACHOS_CERO.md` — Diagnóstico de despachos con monto $0.00
