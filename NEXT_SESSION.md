# NEXT_SESSION.md — Powerfin POS

## Estado actual (2026-06-22)

### ✅ Fases completadas (todas)

| Fase | Tag | Descripción |
|------|-----|-------------|
| 1 | `v0.1.0` | FusionBridge TCP connection |
| 2 | — | APIs PowerFin documentadas |
| 3 | `v0.2.0` | Powerfin POS base |
| 4 | `v0.3.0` | Flujo de venta completo |
| 5 | `v0.5.0` | Impresión térmica ESC/POS |
| 6 | `v0.6.0` | Caja + turnos + historial |
| 7 | `v0.7.0` | Validación hardware Wayne Synergy |
| 7.x | `v0.7.1`-`v0.8.3` | Sync, cancel, billing, CF removal |
| 8 | `v0.9.0` | POS Backend — FastAPI + PostgreSQL |
| 9a | `v0.10.0` | Dispenser mapping, dispatch_details |
| 9b | `v0.11.0` | Price lists, wizard reorder |
| 9c | `v0.12.0` | Cuadre de caja, billing preferencial |
| 10a | `v0.13.0` | Edge cases: cancel/stop, phone-off |
| 10b | `v0.14.0` | Impresión ticket completo SRI |
| 10c | `v0.15.0` | Correcciones subtotal/IVA, saldos |
| 10d | `v0.16.0` | Key49 facturación electrónica SRI |
| 10e | `v0.16.1` | Zona horaria, clave Key49, IPs |
| 10f | `v0.17.0` | Cierre de turno completo |
| 10g | `v0.18.0` | RecoveryService reconexión |
| **11** | **`v0.19.0`** | UX, refactors, bugfixes |
| 11b | `v0.19.1` | Recovery phone-off bug |
| 11c | `v0.19.2` | 409 Conflict doble autorización |
| 11d | `v0.19.3` | preset_value persistido |
| 11e | `v0.19.4` | Despachos $0.00 4-capas |
| 11f | `v0.19.6` | Wayne payment handshake |
| 11g | `v0.19.8` | Cancel IDLE+FUELLING |
| 11h | `v0.19.9` | SQL ventas_turno, deploy fix, CUADRE_CAJA |
| **12a** | **`v0.24.0`** | Admin auth + users + roles + products CRUD |
| **12b** | **`v0.25.0`** | **Admin Phase 12 completa — 11 módulos, 51 endpoints, 338 tests** |

---

## Logros de la sesión (2026-06-22) — v0.25.0

### Phase 12 — Admin Backend CRUD + Auth ✅ COMPLETADO

**338 tests pasando, 0 regresiones, flujo de venta 100% intacto.**

Módulos implementados hoy (8 nuevos, 187 tests):

| # | Módulo | Endpoints | Tests |
|---|--------|-----------|-------|
| 12.3 | Roles CRUD | 4 | 28 |
| 12.4 | Products CRUD | 5 | 36 |
| 12.5 | Grades CRUD | 5 | 28 |
| 12.6 | Price Lists + Items | 9 | 37 |
| 12.7 | Dispensers + Hoses | 8 | 32 |
| 12.8 | Emission Points | 4 | 19 |
| 12.9 | Company Info | 2 | 6 |
| 12.10 | System Config | 2 | 4 |
| 12.11 | Payment Methods | 4 | 12 |

**Total Phase 12: 11 módulos, 51 endpoints, 238 tests admin.**

### Decisiones de diseño

- **model_dump(exclude_unset=True)** para updates parciales — permite limpiar campos con null explícito
- **Sequences en conftest**: +10 setval faltantes (products, roles, grades, price_lists, payment_methods, dispensers, hoses, dispatch_types, categories, taxes)
- **Migraciones 3-pasos**: nullable → backfill → NOT NULL con server_default (grades, price_lists, price_list_items, hoses)
- **Code immutable** en roles, products, grades — no se puede cambiar vía PUT
- **Sin DELETE** en roles y emission_points — FK references o recurso crítico
- **Items reactivación**: crear item con mismo producto reactiva el inactivo (price_list_items)
- **System config upsert**: PUT crea la key si no existe ({key:path} para keys con slashes)
- **Aislamiento total**: /api/admin/* usa get_admin_user (ADMIN/SUPERVISOR), DISPATCHER recibe 403. Cero impacto en /api/pos/*.

### Archivos creados/modificados

```
Routers admin (8 nuevos):
  app/api/admin/roles.py
  app/api/admin/products.py
  app/api/admin/grades.py
  app/api/admin/price_lists.py
  app/api/admin/dispensers.py
  app/api/admin/emission_points.py
  app/api/admin/company.py
  app/api/admin/system_config.py
  app/api/admin/payment_methods.py

Modelos (+ is_active):
  app/models/product.py       ← Grade.is_active
  app/models/pricing.py       ← PriceList.is_active, PriceListItem.is_active
  app/models/dispenser.py     ← Hose.is_active

Migraciones (3 nuevas):
  alembic/versions/5a02d184d729_add_is_active_to_grades.py
  alembic/versions/c7ccad66cca6_add_is_active_to_price_lists_and_items.py
  alembic/versions/2e2a37a14335_add_is_active_to_hoses.py

Schemas (+35 nuevos):
  app/schemas/__init__.py

Tests (8 archivos nuevos, 187 tests):
  tests/test_api_admin_roles.py           (28 tests)
  tests/test_api_admin_products.py         (36 tests)
  tests/test_api_admin_grades.py           (28 tests)
  tests/test_api_admin_price_lists.py      (37 tests)
  tests/test_api_admin_dispensers.py       (32 tests)
  tests/test_api_admin_emission_points.py  (19 tests)
  tests/test_api_admin_company_config.py   (10 tests)
  tests/test_api_admin_payment_methods.py  (12 tests)

Infra:
  app/api/router.py           ← +9 admin routers
  tests/conftest.py           ← +10 setval sequences
  docs/admin/ADMIN_ROADMAP.md ← Phase 12 completado
```

---

## Logros de la sesión (2026-06-20) — v0.19.6

### 78. Handshake de pago Wayne post-cobro ✅

**Problema**: El display del Wayne se quedaba pegado mostrando "COBRAR $XX.00"
después de cada venta cobrada. El POS ejecutaba `collect_dispatch` en el backend
correctamente (HTTP/1.1 fix de v0.19.4 funcionando), pero nunca ejecutaba el
handshake de 3 pasos con el Wayne: `LOCK → CLEAR_SALE → UNLOCK`.

Las funciones `paymentLock()`, `paymentClear()`, `paymentUnlock()` existían en
`bridge.ts` desde siempre pero nadie las llamaba desde el flujo de cobro.

**Solución**:
- `pendingOrders.ts`: Nuevo campo `fusionSaleId?` en `PendingOrder`. `completeOrder()`
  lo acepta y persiste en localStorage.
- `+page.svelte`: El handler SSE de `NEW_TRANSACTION` ya tenía `saleId` disponible —
  ahora se lo pasa a `completeOrder()`.
- `SaleWizard.svelte`: Después de `collectDispatch` + impresión exitosa, ejecuta
  `paymentLock → paymentClear → paymentUnlock` como fire-and-forget (no bloquea,
  try/catch silencioso). Si FusionBridge está caído, el display queda pegado
  igual que antes (sin regresión).

**Adicional**:
- `payment_method_id` se usa como label en `TY` del Wayne (IDs, no nombres).
- Documentado SOP completo en `docs/SOP_DESPACHOS_CERO.md` con 2 escenarios,
  diagnóstico, arreglo manual, y comandos de recovery.

### 79. SOP — Despachos con valores CERO o display pegado ✅

**Problema**: Dos escenarios distintos requieren diagnóstico y recovery manual.

**Documentación creada**: `docs/SOP_DESPACHOS_CERO.md`
- Escenario A: `COMPLETED` con `total=0.00` (HTTP/2 body loss, arreglado en v0.19.4).
- Escenario B: `AUTHORIZED` con `total=0.00` (Wayne ATO=180s timeout sin despachar,
  nunca emite NEW_TRANSACTION).
- Display Wayne pegado: cómo obtener `saleId` de logs y limpiar con 3 curls.
- Comandos de diagnóstico SQL y journalctl.

### Archivos modificados

```
POS Frontend (3):
  stores/pendingOrders.ts        ← +fusionSaleId en PendingOrder + completeOrder()
  routes/(pos)/+page.svelte      ← pasa saleId del SSE al store
  components/SaleWizard.svelte   ← handshake lock→clear→unlock post-cobro

Docs (1):
  docs/SOP_DESPACHOS_CERO.md     ← nuevo: diagnóstico y recovery (2 escenarios)
```

Deploy (1):
  scripts/powerfin-gas           ← +npm run build en deploy-frontend
```

### Tests

```
Powerfin POS — 41 tests    npm test                  # 41 passed, 0 regressions
svelte-check — 0 errors    npm run check             # 0 errors, 16 pre-existing warnings
```

---

## Logros de la sesión (2026-06-20, continuación) — v0.19.8

### 80. ✕ Cancelar para despachos huérfanos (IDLE + FUELLING) ✅

**Problema**: Cuando un cliente levanta la pistola y la cuelga sin despachar
combustible, el Wayne vuelve a IDLE sin emitir NEW_TRANSACTION. El dispatch
queda AUTHORIZED con total=$0.00. El botón ✕ Cancelar solo aparecía en estados
AUTHORIZED/CALLING/STARTING — al llegar a IDLE desaparecía y el DispenserCard
mostraba falsamente "COBRAR $XX" (confundiendo FUELLING+IDLE del phone-off
recovery de v0.19.1 con un despacho real completado).

El despachador quedaba atrapado: no podía cancelar (botón invisible), no podía
cobrar (backend bloquea collect si status≠COMPLETED).

**Solución — 2 capas**:
- **Frontend** (`DispenserCard.svelte`): `canCancel` ahora incluye
  `hose.status===IDLE && order.status===FUELLING`. El botón ✕ Cancelar aparece
  junto al "COBRAR $XX". El despachador tiene 2 opciones: Cancelar o intentar
  Cobrar (que fallará con mensaje claro).
- **Backend** (`dispatches.py:cancel_dispatch`): Doble barrera de seguridad.
  Bloquea cancelación si `status===COLLECTED` o `COMPLETED+total>0`. Esto
  impide que alguien despache combustible, cuelgue rápido, y cancele antes
  de que llegue NEW_TRANSACTION. El backend es la autoridad final.

**Flujo visual**:
```
Hose IDLE
├── order=COMPLETED → COBRAR $XX.00 (normal, cancel NO visible)
└── order=FUELLING  → COBRAR $XX.00 + ✕ Cancelar (v0.19.7)
                      Si total>0 en BD → backend rechaza cancel
```

### 81. Deploy: auto-build + auto-clean ✅

**Problema**: `powerfin-gas deploy-frontend` copiaba fuentes y reiniciaba sin
compilar. El build quedaba desactualizado. Adicional, los archivos en pre-deploy
se acumulaban sin limpiar.

**Solución**:
- `cmd_deploy_frontend()`: `npm run build` después de rsync, antes de restart.
  Si el build falla (`|| die`), no se reinicia y el pre-deploy se preserva.
- Los 3 deploys (frontend/backend/fusion) ahora llaman `cmd_clean` al final.
  Limpia automáticamente después de un deploy exitoso.

### Archivos modificados (v0.19.8)

```
Frontend (1):
  components/DispenserCard.svelte    ← canCancel extendido + documentación

Backend (1):
  api/dispatches.py                  ← cancel_dispatch con doble barrera
                                       (COLLECTED + COMPLETED+total>0)

Deploy (1):
  scripts/powerfin-gas               ← +npm run build + auto-clean en 3 deploys
```

### Tests

```
Powerfin POS — 41 tests    npm test                  # ✓ 41/41
Backend     — 93 tests    pytest                    # ✓ 93/93
svelte-check — 0 errors    npm run check             # ✓
```

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
