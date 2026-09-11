# Monitoreo SRI / Key49 — Admin

Interfaz de **solo lectura** para visualizar el estado de la facturación
electrónica (documentos enviados a Key49/SRI) y detectar documentos con
problemas. Vive **únicamente en Powerfin Admin**; el POS no se modifica.

> Estado: **Fase 1 — Observabilidad** (implementada).
> Fases 2 (acciones) y 3 (scheduler automático) están diseñadas y pendientes.

## 1. Cómo se activa

El módulo viene **desactivado por defecto**. Todos los endpoints devuelven
`403` mientras el flag no esté en `true`, por lo que no ejecuta ni una consulta
adicional.

Clave en `system_config`:

| Clave | Valor | Efecto |
|---|---|---|
| `sri_monitor_enabled` | `true` | Habilita el módulo en Admin |
| `sri_sync_enabled` | `true` | Habilita el **reconciler de fondo** (ver §2.1) |

Se puede activar sin SQL, vía API (el PUT crea la clave si no existe):

```bash
curl -X PUT "$API/api/admin/system-config/sri_monitor_enabled" \
  -H "Authorization: Bearer <JWT admin>" -H "Content-Type: application/json" \
  -d '{"value":"true","description":"Monitoreo SRI en Admin"}'
```

Para desactivarlo, `value=false`.

## 2. Ubicación en la UI

Admin → **Facturación SRI** (`/sri`). Dos pestañas:

### Resumen
- KPIs: Total emitidos · Autorizados (+% éxito) · En proceso · Con problemas ·
  Tiempo promedio a autorización.
- **Emisiones por día** (barras apiladas: autorizadas / en proceso / con problema).
- **Problemas por tipo** (ver taxonomía abajo).
- **Salud Key49**: API configurada, habilitado, y errores de las últimas 24h
  (plan expirado / no disponible / HTTP 402).

### Documentos
- Filtros: rango de fechas, estado SRI, tipo de problema, búsqueda
  (orden, cliente, cédula/RUC, placa) y "Solo con problemas".
- Tabla paginada con: fecha, orden, cliente, secuencial, total, estado,
  tipo de problema y mensaje.
- **Export PDF / Excel**.

### 2.1 Reconciler de fondo (PENDING_SENT)

El flujo de emisión es *fire-and-forget*: tras la venta, un poller revisa Key49
~20s (10 intentos × 2s). Cuando Key49/SRI tarda más (observado **~90–120s**), la
factura **sí se autoriza** pero el despacho queda `PENDING` — un desync silencioso
(histórico, no nuevo; solo era invisible).

El reconciler (`app/services/sri_sync_service.py`) corre cada **120s** y:
- Toma despachos `sri_status='PENDING'` **con** `key49_invoice_id` (o sea, ya enviados).
- Lee su estado real en Key49 y actualiza el estado local.
- **Nunca reemite** ni toca el flujo de venta.
- Ignora filas muy nuevas (<90s, aún las maneja el poller) o muy viejas (>72h).
- Está envuelto en `try/except` y detrás de `sri_sync_enabled` (default off).

## 3. Taxonomía de problemas

Cada documento se clasifica según `sri_status` y si tiene referencia en Key49:

| Tipo | Significado | Acción recomendada |
|---|---|---|
| `NEVER_SENT` | Nunca llegó a Key49 (sin `key49_invoice_id`) | Reemitir (Fase 2) |
| `PENDING_SENT` | Tiene id Key49 pero nuestro estado quedó `PENDING` (stale) | Sincronizar (Fase 2) |
| `KEY49_FAILED` | Key49 agotó reintentos (`retry_count=6`) | **Reprocesar en Key49** (manual) o anular+reemitir |
| `INVALID_DATA` | Falló antes de Key49 (ej. cédula/RUC inválido) | Corregir el cliente y reemitir |
| `REJECTED` | Rechazada por el SRI | Ver motivo → nota de crédito |
| `IN_PROGRESS` | `CREATED/SIGNED/SENT/RECEIVED` | Esperar / sincronizar |
| `OK` | `AUTHORIZED / NOTIFIED` | — |

## 4. Endpoints (Admin, `require_permission("sri","read")`)

Todos requieren el rol ADMIN/SUPERVISOR y el flag activo.

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/admin/sri/metrics` | KPIs + series (`date_from`, `date_to`, `emission_point_id`) |
| GET | `/api/admin/sri/documents` | Lista paginada con filtros |
| GET | `/api/admin/sri/documents/{dispatch_id}` | Detalle (incluye lectura viva a Key49 con `?live=true`) |
| GET | `/api/admin/sri/health` | Config + errores 24h (+ `?probe=true` para ping a Key49) |
| POST | `/api/admin/sri/documents/export` | Export PDF/Excel de la bandeja |

## 5. Diseño no invasivo (por qué no puede romper producción)

- **100% aditivo**: endpoints, servicio y páginas nuevas. No se toca ninguna
  ruta del flujo de venta (`collect`, `emitir_factura`, despacho, POS).
- **Feature flag** `sri_monitor_enabled` (default off). Apagado = cero queries.
- El servicio **solo lee** la BD. Nunca escribe ni llama a `emitir_factura`.
- La lectura viva a Key49 es **opt-in**, con timeout de 5s y `try/except`:
  nunca interrumpe un request.
- Sin migraciones sobre tablas existentes.

## 6. Fases siguientes (diseño acordado)

### Fase 2 — Acciones controladas
- `POST /api/admin/sri/sync` — sincroniza estados no-finales en lote.
- `POST /api/admin/sri/documents/{id}/sync` y `/reprocess` — individuales.
  El reproceso con **fecha de hoy** (`regenerate_access_key`) es **solo ADMIN
  y caso por caso** (decisión fiscal).
- `POST /api/admin/sri/reprocess` — lote **solo Tipo A del mismo día**.
- Tabla `sri_jobs` para progreso y auditoría; wizard con previsualización,
  confirmación y reporte descargable.

### Fase 3 — Scheduler automático (opt-in)
- Reintento periódico de `PENDING` <24h + sync de no-finales, con rate limit
  (Key49: 30 POST/min) y logging. Se activa con otro flag.

## 7. Notas

- El promedio "tiempo a autorización" puede verse inflado por facturas antiguas
  reprocesadas en lote.
- El caso `KEY49_FAILED` **no se puede resolver desde el POS/Admin** mientras
  Key49 no exponga un endpoint de reproceso (hoy no existe): requiere la UI de
  Key49 o anulación + reemisión.
- Referencias: `docs/KEY49-INTEGRATION-GUIDE.md`, `docs/DISPATCH_AUDIT.md`.
