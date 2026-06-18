# NEXT_SESSION.md — Powerfin POS

## Estado actual (2026-06-17)

### ✅ Fases completadas

| Fase | Tag | Descripción |
|------|-----|-------------|
| 1 | `v0.1.0` | FusionBridge TCP connection |
| 2 | — | APIs PowerFin documentadas (21 endpoints) |
| 3 | `v0.2.0` | Powerfin POS base — login, surtidores |
| 4 | `v0.3.0` | Flujo de venta completo |
| 5 | `v0.5.0` | Impresión térmica — ESC/POS, config multi-isla, templates editables |
| 6 | `v0.6.0` | Módulo de caja + refactor turnos + historial + usuarios en línea |
| 7 | `v0.7.0` | Validación hardware real — Wayne Synergy |
| 7.1 | `v0.7.1` | Bugfix: match IDs dispensador/manguera, flujo de cobro |
| 7.2 | `v0.8.0` | Sincronización multi-dispositivo + cancelación manual |
| 7.3 | `v0.8.1` | Fix customer_name cross-device |
| 7.4 | `v0.8.2` | Cambio de facturación post-despacho |
| 7.5 | `v0.8.3` | Eliminación Consumidor Final + offline detection + fixes |
| 8 | `v0.9.0` | POS Backend — FastAPI + PostgreSQL (26 tablas, 38 endpoints, 71 tests) |
| 9a | `v0.10.0` | Phase 9 — dispenser mapping, dispatch_details, multi-device sync, collect flow |
| 9b | `v0.11.0` | Phase 9 — price lists (VIP/EMPLOYEE), wizard reorder, emission points, schema simplification |
| 9c | `v0.12.0` | Phase 9 — cuadre de caja, transfers, lookup, billing preferencial, auto-save, validación, registro |
| 10a | `v0.13.0` | Phase 10 — Edge cases: cancel/stop mid-flow, phone-off resilience, completeDispatch en FusionBridge |
| 10b | `v0.14.0` | Phase 10 — Impresión: ticket completo, clave de acceso SRI, Font B, datos desde BD |
| 10c | `v0.15.0` | Phase 10 — Correcciones: subtotal/IVA, código aleatorio, espacio corte, saldos negativos, comprobantes caja |
| 10d | `v0.16.0` | Phase 10 — Key49: facturación electrónica SRI, fire-and-forget, polling, reintentos |
| 10e | `v0.16.1` | Phase 10 — Correcciones: zona horaria, clave Key49, IPs impresora, subtotal→total, reimpresión |
| 10f | `v0.17.0` | Phase 10 — Cierre de turno completo: cuadre, surplus/shortage, depósito, template impresión |
| 10g | `v0.18.0` | Phase 10 — RecoveryService: reconexión FusionBridge durante despacho activo |
| **11** | **v0.19.0** | **Phase 11 — UX, refactors, bugfixes: dashboard visual, IDs vs strings, SRI column, búsqueda por nombre, placas predefinidas** |
| 11b | `v0.19.1` | Bugfix: recovery despacho AUTHORIZED cuando PAY_IN no eco-devuelto (phone-off) |
| 11c | `v0.19.2` | Bugfix: doble autorización mismo dispensador → 409 Conflict en create_dispatch |
| 11d | `v0.19.3` | Bugfix: preset_value persistido en BD + bloqueo cobro $0.00 (cross-page race condition) |
| **11e** | **v0.19.4** | **Bugfix: despachos en $0.00 — carrera AM=0, collect exige COMPLETED, cancel limpia SRI** |

---

## Logros de la sesión (2026-06-17) — v0.19.4

### 75. Migración Alembic completa ✅

**Problema**: Instalación limpia no podía ejecutar `alembic upgrade head` porque
la segunda migración solo tenía `alter_column` (comentarios) sin los `add_column`
necesarios. 15 columnas faltaban entre el schema inicial y el modelo ORM actual.

**Solución**:
- `b261e8ceb69f`: reescrita con `add_column` para 15+ columnas en 6 tablas
  (`company_info`, `dispatch_details`, `dispatches`, `products`, `vehicles`,
  `payment_methods`, `dispensers`, `shifts`)
- `seed_data.py`: removido `fusion_pump_id` de `Dispenser()` (ahora en `hoses`)
- `INSTALL.md` sección 9 actualizada: flujo `alembic upgrade head` → `seed_data.py`

### 76. Despachos en $0.00 — defensa en 4 capas ✅

**Problema**: Despachos se creaban con `total=$0.00`, se cobraban en $0.00 y se
enviaban al SRI con monto cero. Tres bugs contribuían:

1. **Carrera AM=0**: FusionBridge llamaba `complete_dispatch` con `amount="0"`
   (Wayne no enviaba AM en el primer evento). Cuando el POS reintentaba con el
   monto real, el backend respondía "ya está COMPLETED" y lo ignoraba.
2. **collect sin exigir COMPLETED**: `collect_dispatch` solo verificaba
   `status != COLLECTED`. Un despacho AUTHORIZED con total=0 se podía cobrar.
3. **CANCELLED iban al SRI**: `cancel_dispatch` no limpiaba `sri_status`.
   `retry_pending_invoices` no excluía CANCELLED.

**Solución — 4 defensas**:

| Capa | Archivo | Qué hace |
|------|---------|----------|
| 1 | `dispatches.py:complete_dispatch` | Si COMPLETED con total=0 + nuevo amount>0 → corrige totals |
| 2 | `dispatches.py:complete-by-pump` | Busca AUTHORIZED + COMPLETED(total=0); ignora si ya tiene totals |
| 3 | `dispatches.py:collect_dispatch` | Exige `status==COMPLETED` + `total>0` + `effective_amount>0` |
| 4 | `dispatches.py:cancel_dispatch` | Limpia `sri_status=NULL` al cancelar |

**Adicional**:
- `key49_service.py`: `emitir_factura` y `retry_pending_invoices` excluyen CANCELLED
- Auto-cancel (>5 min) **eliminado** — redundante con ATO=180s del Wayne. Causaba
  cancelación de tanques llenos que tardan más de 5 min en despachar.
- Frontend: `powerfin.ts` extrae `detail` del error; `SaleWizard.svelte` muestra
  mensaje real del backend en vez de "Error al registrar cobro".

### 77. Precios: aclaración price_list_items vs products.base_price ✅

**Problema**: Usuario cambió `products.base_price` a $3.251 pero el sistema seguía
cobrando $3.103. El precio de venta SIEMPRE viene de `price_list_items.unit_price`
para la lista STANDARD. `products.base_price` solo es referencia/fallback.

**Solución**: Documentado el flujo de precios. El usuario actualizó ambas tablas.

---

## Pendiente para próxima sesión

### 🟡 Backlog

```
☐ 1. Pago mixto (efectivo + tarjeta)
☐ 2. identity_service.py — mover URL y token a .env o system_config
☐ 3. Roles/permisos — implementar enforcement real:
   · ADMIN: todo
   · SUPERVISOR: ventas, reportes, cierre de turno, SRI retry
   · DISPATCHER: ventas, cierre de turno
☐ 4. Flujo de crédito en el POS — selector en SaleWizard
☐ 5. Despachos ya enviados al SRI con $0.00 — conciliar manualmente
```

---

## Configuración actual del sitio

| Dato | Valor |
|------|-------|
| Estación | NEOGAS |
| Surtidores | 4: SURT-01 (SUPER+ECO), SURT-02 (ECO), SURT-03 (DIESEL1), SURT-04 (DIESEL2) |
| Puntos emisión | 001-001 a 001-004 (uno por dispensador) |
| Listas precio | STANDARD, VIP, EMPLOYEE, FAMILY |
| ATO | 180s |
| Moneda | DÓLARES ($) |
| Firmware | Rel-5.19.1 |
| Formas de pago | EFECTIVO, TARJETA, QR, CREDITO, DEUNA, JEPFAST, SIPY, YALOBOX |
| Cliente requerido | Sí (cédula o RUC obligatorio — sin Consumidor Final) |

## Base de datos

| Dato | Valor |
|------|-------|
| Host | localhost:5433 |
| Database | powerfin_gas |
| Test DB | powerfin_gas_test |
| User | postgres |
| Password | 1234abcd |

## Deploy a producción

```bash
cd /home/pvalarezo/grisbiapps/powerfin_pos_gas

# Backend
rsync -av \
  pos_backend/app/api/dispatches.py \
  pos_backend/app/services/key49_service.py \
  pos_backend/seed_data.py \
  pos_backend/alembic/versions/b261e8ceb69f_accumulated_schema_changes_phases_9_10.py \
  app@192.168.1.25:/opt/powerfin/pos/backend/

# Frontend
rsync -av \
  pos/src/lib/api/powerfin.ts \
  pos/src/lib/components/SaleWizard.svelte \
  app@192.168.1.25:/opt/powerfin/pos/pos/src/

# Reiniciar
ssh app@192.168.1.25 "sudo systemctl restart pos-backend pos-frontend"
```

---

## NOTAS

- El dispensador físico requiere **palanca manual** además de levantar la pistola.
- **NO usar `LID` ni `LM` en PRESET** — firmware Rel-5.19.1 crea locks permanentes.
- **No existe Consumidor Final** — toda venta requiere cliente con cédula o RUC.
- **ATO en 180 segundos** — los presets expiran después de 3 minutos sin levantar pistola.
- **`shift_id` cambia al cobrar**: AUTHORIZED/COMPLETED → shift autorizador; COLLECTED → shift cobrador.
- **Cuadre de caja**: `WHERE shift_id = mi_turno AND status = 'COLLECTED'`.
- **Auto-guardado**: buscar CED/RUC en API externo → se guarda en BD local automáticamente.
- **Facturación preferencial**: `vehicles.billing_person_id` — NULL = usar titular.
- **Celular apagado**: FusionBridge completa el dispatch directamente (no depende del POS).
- **Consola Wayne en oficina** → el POS es la ÚNICA forma de detener un despacho.
- **Precios**: el precio de venta SIEMPRE viene de `price_list_items.unit_price`.
  `products.base_price` es referencia/subsidio. Cambiar ambos para consistencia.
- **Despacho a crédito**: se decide al autorizar, no al cobrar. Requiere contrato activo
  con vehículo asignado y cupo disponible.
- **SRI codes**: vienen de `payment_methods.sri_code`, no hardcodeados.
- **Instalación limpia**: `alembic upgrade head` + `python seed_data.py`.
  Ver `docs/INSTALL.md` sección 9.
