# SOP — Reenvío de facturas al SRI vía Key49

> **Propósito**: Diagnosticar y reenviar facturas electrónicas que quedaron pendientes
> o fallidas en el envío al SRI a través de Key49.

```
Última actualización: 2026-09-18 (v0.39.1)
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

# Respuesta esperada (v0.39.0):
# {"retried": 5, "regenerated": 2, "expired": 0, "skipped": 0, "failed": 0}
```

**Qué hace internamente** (v0.39.1):
1. Busca los despachos **`status='COLLECTED'`** con `sri_status = PENDING` **sin
   `key49_invoice_id`**, excluyendo `PENDING_BULK_INVOICE` y con al menos 120 s de
   antigüedad (para no competir con la emisión viva post-cobro).
   ⚠️ Solo ventas **cobradas**: un despacho recién `AUTHORIZED` nace con
   `sri_status='PENDING'` (default del modelo) y **no** debe facturarse.
2. Para cada uno:
   - Si la **clave de acceso es de hoy** → `emitir_factura()` a Key49 tal cual.
   - Si la clave es **de un día anterior** → **regenera la clave con la fecha de hoy**
     (Key49 rechaza fechas pasadas) y luego emite.
   - Si el despacho es **más viejo que `sri_retry_max_age_hours`** (default 72 h) →
     se deja `PENDING` para reemisión manual (ya **no** se marca `FAILED`).
3. Retorna `{retried, regenerated, expired, skipped, failed}`.

> 💡 **Desde v0.39.0 esto corre solo**: el loop de fondo `run_sri_retry_loop`
> (cada 300 s) llama a `retry_pending_invoices()`. El endpoint HTTP sirve para
> forzarlo a mano. Gates: `sri_retry_enabled` (default on) y `key49_enabled`.
> Serializado con un lock de proceso para no emitir dos veces.

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

### 5.1 Factura con fecha pasada — Key49 exige `issue_date = hoy`

Key49 responde `HTTP 400 VALIDATION_ERROR — {"field":"issue_date","code":"INVALID_ISSUE_DATE","message":"Must be today's date"}`
si se reenvía con la fecha de emisión original (probado el 2026-09-18 con el
dispatch 22073: `scripts/resend_pending_original_date.py`). **Reenviar siempre
implica regenerar la clave de acceso con la fecha de hoy.**

1. **Automático (v0.39.0)**: el retry regenera la clave por su cuenta para cualquier
   `PENDING` dentro de `sri_retry_max_age_hours` (default **72 h**, `0` = sin límite).
   Si la factura falló de noche y se reintenta al día siguiente, sale con la fecha nueva.
2. **Manual (fuera de la ventana)**: `recover_pending_invoices.py --min-age-hours 0`
   (Opción D, sección 3.2b) — regenera la clave y emite con fecha de hoy.
3. **Anular y re-facturar**: cancelar el despacho original y crear uno nuevo con
   fecha actual. Solo viable si no hay combustible real entregado.
4. **Conciliación manual**: documentar como emitida fuera del SRI y reportar en la
   declaración mensual. Si se facturó en el **ERP**, ver 5.6.

> ⚠️ Reemitir **cambia la fecha del comprobante** y el código numérico impreso:
> la clave del ticket original deja de coincidir. Una **reimpresión** desde el POS
> sale con la clave correcta.

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

### 5.5 ¿Por qué el SRI autoriza una factura con un RUC/cédula inválido?

Es la pregunta que más confunde: una factura puede estar **`NOTIFIED`/`AUTHORIZED`**
y, aun así, la identificación del comprador ser **matemáticamente inválida**.

**Caso real (2026-09-13):** factura `003-501-000004803` (dispatch `20924`, $10,00,
cliente *Fabián nieves*, `person_id` 10404). La factura está autorizada por el SRI,
pero el RUC `0104248314001`:

* embebe la cédula `0104248314`, que **no cumple el módulo 10**;
* y el registro del SRI responde **`NOT_FOUND` (`RUC no encontrado en SRI`)**.

**La causa es que cada capa valida cosas distintas:**

| Capa | Qué comprueba | Veredicto |
|------|---------------|-----------|
| **SRI — autorización online** | Estructura XML (XSD), **firma electrónica**, emisor autorizado, establecimiento/punto de emisión, clave de acceso (módulo 11 del emisor) | ✅ Autoriza |
| **SRI — dígito del comprador** | El requisito existe ("RUC con dígito verificador correcto, cédula con módulo 10") pero el servicio de recepción **no lo calcula**: es responsabilidad **declarativa** del emisor | ⚠️ No lo verifica |
| **Key49 (antes del endurecimiento)** | Solo estructura → reenviaba tal cual | ✅ Aceptaba |
| **Key49 (endurecido)** | Estructura **+ validación semántica** de la identificación | ❌ `Invalid identification for type 04/05` |
| **POS Backend (v0.38.0)** | Módulo 10 en cédula; RUC = estructura + cédula embebida válida + registro del SRI (`id_validation.py`) | ❌ Detecta y bloquea al capturar |

En resumen: **la autorización del SRI no dice "el RUC del comprador existe"**, solo
que el XML es correcto y está firmado por un emisor autorizado. Por eso la factura es
válida para el SRI aunque el número del comprador sea falso. Key49 endureció su
validación después (fue el origen del backlog `FAILED`), y nosotros validamos en el
**origen de la captura** para no descubrirlo tras el cobro.

**Riesgo de dejar el dato inválido** (no invalida la factura, pero sí acarrea
problemas): el SRI puede **observarla/glosarla** en revisión y el comprador **no puede
usarla como crédito tributario**. Requisito citado en la página oficial del SRI
(*Validez de comprobantes electrónicos*).

**Comprobar el caso concreto:**

```bash
# 1) Qué RUC guardó Key49 (fuente de verdad del documento emitido)
curl -s "https://key49.apx5.com/v1/invoices/<key49_invoice_id>" \
  -H "Authorization: Bearer <key49_api_key>" | jq '.data.recipient'

# 2) ¿El RUC/cédula es matemáticamente válido?
cd pos_backend && source venv/bin/activate
python -c "from app.services.id_validation import ruc_error; print(ruc_error('0104248314001'))"

# 3) ¿El SRI conoce ese RUC?
curl -s "http://<identity-api>/v1/info/ALL/sri/0104248314001" \
  -H "Authorization: Bearer <identity_token>" | jq '.httpStatus, .message'
```

**Consecuencia operativa:** un cliente cuyo `id_number` era inválido se limpia a
`NULL` (`scripts/limpiar_ids_invalidos.py`) para que el POS lo **vuelva a pedir** en el
próximo despacho. Las facturas **ya emitidas** con ese número **no se tocan** (existen
en el SRI); la limpieza es **hacia adelante**, no reescribe el pasado.

> ⚠️ **Lección:** nunca asumir que "el SRI la autorizó" implica "el dato del cliente
es correcto". Validar la identificación **antes** de despachar (v0.38.0).

---

---

## 5-A. Sector público facturado desde el ERP (NO_INDEFINIDO)

Los contratos `NO_INDEFINIDO` acumulan despachos como `PENDING_BULK_INVOICE` para
liquidarlos en una factura global. Cuando esa factura **se emite directamente en
Powerfin ERP** (no por el POS Backend), los despachos locales se quedan pendientes
y aparecen como problemas SRI (`NEVER_SENT` / `INVALID_DATA`). Para reconciliarlos:

```bash
cd pos_backend && source venv/bin/activate

# Lote de un contrato (dry-run por defecto)
python ../scripts/marcar_facturado_erp.py --contract-id <ID> --auth-date YYYY-MM-DD
python ../scripts/marcar_facturado_erp.py --contract-id <ID> --auth-date YYYY-MM-DD --apply

# Casos que se intentaron como factura individual pero terminaron en el lote del ERP
python ../scripts/marcar_facturado_erp.py --dispatch-id N --dispatch-id M \
    --auth-date YYYY-MM-DD --clear-sequential --apply
```

Qué escribe:
- `credit_status = 'INVOICED'` → lo saca de la cola de liquidación.
- `sri_status = 'AUTHORIZED'` → `FINAL_OK` en el monitor SRI y los reportes.
- `sri_authorization_date = <--auth-date>` y `sri_messages = NULL`.
- La clave/secuencial se dejan como están: con **varias** facturas del ERP no hay un
  documento único que referenciar.
- `--clear-sequential` además pone `sequential_number` y `access_key` en `NULL`
  (solo para despachos que nunca llegaron a Key49; el script **aborta** si alguna
  fila tiene `key49_invoice_id`).

> Idempotente, dry-run por defecto, y respalda cada fila afectada en
> `~/.powerfin_backups/*.csv` (fuera de `/tmp`).

**Caso real (2026-09-18)**: GAD de Paute (contrato 3, `person_id 9044`) → **186
 despachos, $11.209,49** reconciliados a `INVOICED / AUTHORIZED / 2026-08-24`.
 `persons.id_number` de 9044 sigue `NULL`: para volver a facturar en el ERP hay que
 reponerlo (y el contrato está `is_active=false`).

---

## 6. Configuración de Key49

```sql
-- Verificar configuración actual
SELECT key, value FROM system_config WHERE key LIKE 'key49%' OR key LIKE 'sri_%';
```

| Key | Descripción | Default |
|-----|------------|---------|
| `key49_enabled` | Habilitar emisión/reintento contra Key49 | `true` / `false` |
| `key49_base_url` | URL base de la API Key49 | `https://key49.apx5.com/v1` |
| `key49_api_key` | Token de autenticación | `k49_…` |
| `sri_sync_enabled` | Reconciler de solo lectura (estados no-finales) | `false` (activar) |
| `sri_retry_enabled` | Reintento automático de `PENDING` sin factura (v0.39.0) | `true` (si no existe) |
| `sri_retry_max_age_hours` | Ventana de reemisión automática; `0` = sin límite (v0.39.0) | `72` |
| `sri_monitor_enabled` | Módulo de monitoreo SRI en el Admin | `false` (activar) |

> El **ambiente SRI** (`1=PRUEBAS`, `2=PRODUCCIÓN`) no es una key de `system_config`:
> vive en `company_info.sri_environment`, y quien lo aplica es el **tenant de Key49**.

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

- `pos_backend/app/services/key49_service.py` — Emisión, retry y `run_sri_retry_loop`
- `pos_backend/app/services/sri_sync_service.py` — Reconciler de solo lectura
- `pos_backend/app/api/dispatches.py` — Endpoints `/retry-sri`, `/retry-pending-invoices`, `/bulk-invoice`
- `pos_backend/app/models/dispatch.py` — Columnas `sri_status`, `key49_access_key`, `sri_messages`
- `scripts/recover_pending_invoices.py` — Reemisión de días anteriores (regenera la clave)
- `scripts/marcar_facturado_erp.py` — Reconciliar despachos facturados en el ERP
- `docs/SOP_DESPACHOS_CERO.md` — Diagnóstico de despachos con monto $0.00
