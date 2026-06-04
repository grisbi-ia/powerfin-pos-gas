# NEXT_SESSION.md — Powerfin POS

## Estado actual (2026-06-04)

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
| 6.1 | `v0.7.1` | Bugfix: match IDs dispensador/manguera, flujo de cobro |
| 6.2 | `v0.8.0` | Sincronización multi-dispositivo + cancelación manual |
| 6.3 | `v0.8.1` | Fix customer_name cross-device |
| 6.4 | `v0.8.2` | Cambio de facturación post-despacho |
| 6.5 | `v0.8.3` | Eliminación Consumidor Final + offline detection + fixes varios |
| 7 | `v0.9.0` | POS Backend — FastAPI + PostgreSQL (26 tablas, 38 endpoints, 71 tests) |
| **8** | **v0.10.0** | **Phase 9 — Integración & hardening (HOY, sesión 2)** |

### 📊 Tests

```bash
# FusionBridge — 72 tests
cd fusion-bridge && ./mvnw test   # BUILD SUCCESS

# POS Backend — 71 tests
cd pos_backend && source venv/bin/activate && pytest   # 71 passed

# POS — 41 tests (Vitest)
cd pos && npm run test            # 41 passed

# Total: 184 tests pasando
```

---

## Logros de la sesión anterior (2026-06-04, mañana)

### 1–10. Ver NEXT_SESSION.md previo

Mapeo de dispensadores, tokens hardcodeados, POST customers, pantalla cliente,
unit_price en config, precios correctos, dispatch_details, pantalla cobro,
reconciliación multi-device, sort_order.

---

## Logros de esta sesión (2026-06-04, tarde)

### 11. Precios por lista de cliente (VIP, EMPLOYEE, FAMILY) ✅

**Bug:** Al seleccionar cliente con lista VIP, el PRESET al Synergy siempre enviaba
el precio STANDARD. $1.00 de SUPER daba 0.222 gal tanto para STANDARD como VIP.

**Fix:** `handleBillingConfirm()` ahora llama a `GET /api/pos/prices` con el
`customerId` y `gradeId` para obtener el `unit_price` real de la lista del cliente.
También se actualizó `powerfin.getCustomerPrice()` para aceptar `vehicleId` opcional.

**Archivos:** `pos/src/lib/api/powerfin.ts`, `pos/src/lib/components/SaleWizard.svelte`

### 12. Reordenamiento del Wizard: Placa → Producto → Cliente ✅

**Antes:** Pistola → Placa → Cliente → Monto → Autorizar
**Ahora:** Placa → Producto → Cliente → Monto → Autorizar

El despachador copia la placa primero (un solo viaje al vehículo), luego selecciona
el producto. La lógica de auto-select (1 sola pistola) se movió al paso `product`.

**Archivos:** `pos/src/lib/components/SaleWizard.svelte`

### 13. Input de placa — tamaño reducido ✅

`text-lg` → `text-base`, `px-4` → `px-3`, agregado `min-w-0` para evitar
que el botón "Buscar" se salga del margen en dispositivos móviles.

### 14. Fix Decimal → string en módulo de Caja ✅

`formatCurrency()` en `cash/+page.svelte` ahora acepta `number | string`.
`Decimal("0")` se serializaba como `"0"` (sin punto decimal), el middleware
solo convertía strings con punto (`"0.00"`), y `.toFixed()` tronaba.

**Archivos:** `pos/src/routes/(pos)/cash/+page.svelte`

### 15. Puntos de emisión por dispensador ✅

**Antes:** 1 solo emission point (001-001) compartido entre los 4 surtidores.
**Ahora:** 4 emission points (001-001 a 001-004), cada dispensador con su secuencial.

**DB:** +3 emission points, `dispensers.emission_point_id` poblado.
**Backend:** `create_dispatch` busca EP vía `dispenser.emission_point_id` (no `LIMIT 1`).

**Archivos:** `pos_backend/app/api/dispatches.py`, datos en DB

### 16. `vehicle_id` y `person_id` en dispatch ✅

**Antes:** `person_id=None` hardcodeado, `vehicle_id` nunca seteado.
**Ahora:** `customer_id` → `person_id` (FK persons), `plate` → `vehicle_id` (FK vehicles).
Si el vehículo tiene persona y no se envió `customer_id`, se hereda.

**Archivos:** `pos_backend/app/api/dispatches.py`

### 17. `authorized_by_user_id` (FK → users) ✅

Agregado `authorized_by_user_id` al modelo `Dispatch`. Se puebla desde
`current_user.user_id` en `create_dispatch`.

### 18. Simplificación de columnas en `dispatches` ✅

**Eliminadas (4):**
| Columna | Motivo |
|---------|--------|
| `authorized_by` VARCHAR | Redundante — `authorized_by_user_id` FK |
| `customer_name` VARCHAR | Redundante — `person_id` FK → `persons.name` |
| `collected_by_user_id` | Ya no se necesita (ver #19) |
| `collected_by_shift_id` | Ya no se necesita (ver #19) |

**Conservadas (2 FKs):**
| Columna | Significado |
|---------|-------------|
| `shift_id` | Turno del autorizador → se actualiza al del cobrador |
| `authorized_by_user_id` | Quién autorizó (FK users) |

### 19. `shift_id` se actualiza al cobrar ✅

**Lógica:** Al crear el dispatch, `shift_id` = turno del autorizador.
Al cobrar (`collect_dispatch`), `shift_id` se actualiza al turno del cobrador.

Esto simplifica el cuadre de caja: `WHERE shift_id = mi_turno AND status = 'COLLECTED'`
basta para obtener todo el efectivo en caja, sin importar quién autorizó.

### 20. `customer_name` resuelto vía JOIN en API ✅

`get_shift_dispatches` y `get_active_dispatches` ahora resuelven `customer_name`
haciendo lookup de `person_id` → `persons.name`.

### 21. `change_billing` — error si persona no existe ✅

`POST /api/pos/dispatches/{id}/billing` ahora devuelve 404 si el `customer_id`
no corresponde a una persona activa. Antes fallaba silenciosamente.

### 22. Store `pendingOrders` — `customerId` y `authorizedByUserId` ✅

- `PendingOrder` ahora tiene `customerId?: string` y `authorizedByUserId?: number`
- `addOrder` incluye ambos campos
- `updateOrderBilling` ahora pasa `customerId`
- `DispenserCard` compara `authorizedByUserId === currentUser.user_id` (no nombres)

---

## Archivos modificados en esta sesión

```
pos_backend/app/api/dispatches.py     ← emission points, vehicle_id, person_id,
                                        authorized_by_user_id, shift_id en collect,
                                        customer_name vía JOIN, change_billing 404
pos_backend/app/api/shifts.py         ← close_shift simplificado, customer_name JOIN
pos_backend/app/api/cash.py           ← cash_summary simplificado
pos_backend/app/models/dispatch.py    ← +authorized_by_user_id, -4 columnas
pos_backend/app/main.py               ← (revertido) Decimal middleware sin cambios

pos/src/lib/api/powerfin.ts           ← getCustomerPrice acepta vehicleId
pos/src/lib/api/powerfin.mock.ts      ← mock actualizado a nueva estructura
pos/src/lib/api/types.ts              ← DispatchOrder, CreateDispatchRequest limpios
pos/src/lib/components/SaleWizard.svelte ← reorden wizard, precio x lista, UI placa
pos/src/lib/components/DispenserCard.svelte ← cancel compara user_id
pos/src/lib/stores/pendingOrders.ts   ← customerId, authorizedByUserId
pos/src/routes/(pos)/cash/+page.svelte ← formatCurrency number|string
pos/src/routes/(pos)/new-dispatch/+page.svelte ← limpio customer_name, authorized_by
```

---

## Pendiente para próxima sesión

### 🔴 Prioridad 1 — Cuadre de caja y transferencias

```
☐ Revisar close_shift: verificar que opening_cash, sales_cash, income, expense,
   transfers_in, transfers_out, safe_drops cuadren correctamente
☐ Revisar transferencias entre usuarios: cuando A transfiere a B, el movimiento
   de B debe reflejarse como ingreso en su turno (o al menos en su balance)
☐ Probar cierre de turno con ventas cross-user (A autoriza, B cobra)
☐ Verificar que el saldo en caja (current_balance) sea correcto después de
   transferencias entre usuarios
☐ Revisar SAFE_DROP: el depósito a caja fuerte debe reducir el balance del
   turno pero NO afectar el cuadre de ventas
```

### 🟡 Prioridad 2 — Testear venta completa end-to-end

```
☐ Login como carlos → abrir turno
☐ Placa → buscar → seleccionar producto → confirmar cliente
☐ Seleccionar monto → autorizar despacho
☐ Levantar pistola física → ver progreso en dashboard
☐ Colgar → ver "Cobrar" en dashboard
☐ Entrar a cobrar → seleccionar EFECTIVO → ingresar recibido → confirmar
☐ Verificar que el despacho pasa a COLLECTED en BD
☐ Verificar vehicle_id y person_id poblados
☐ Verificar emission_point correcto según dispensador
☐ Repetir desde otro dispositivo (maria) → verificar sync multi-dispositivo
☐ Cerrar turno y verificar cuadre
```

### 🟡 Prioridad 3 — Integrar persons/lookup en el POS

```
☐ POS: reemplazar búsqueda de cliente actual por GET /api/pos/persons/lookup
☐ POS: mostrar datos del API externo (Sercobaco/SRI) cuando no hay cliente local
☐ POS: permitir registrar cliente nuevo con datos del API externo
```

### 🟡 Prioridad 4 — Edge cases

```
☐ Despacho cancelado a mitad del flujo
☐ Despacho con pago mixto (efectivo + tarjeta)
☐ Reconexión de FusionBridge durante despacho activo
☐ Múltiples despachos simultáneos (ambos lados del SURT-01)
```

### 🟢 Prioridad 5 — Deuda técnica

```
☐ Remover hardcode plate='ABC1234' en SaleWizard.svelte:28
☐ Precios VIP/EMPLOYEE/FAMILY dinámicos desde BD (ya se consultan, verificar)
☐ Migración Alembic para cambios de schema acumulados
☐ Revisar si dispatch_details.quantity=0 inicial debe ser NULL
```

---

## Configuración actual del sitio

| Dato | Valor |
|------|-------|
| Estación | NEOGAS |
| Surtidores | 4: SURT-01 (SUPER+ECO), SURT-02 (ECO), SURT-03 (DIESEL1), SURT-04 (DIESEL2) |
| Puntos emisión | 001-001 a 001-004 (uno por dispensador) |
| SURT-01 activo | SUPER ($4.50) + ECO_PAIS ($2.90) |
| Listas precio | STANDARD, VIP (SUPER $4.25, ECO $2.30), EMPLOYEE, FAMILY |
| ATO | 180s |
| Moneda | DÓLARES ($) |
| Firmware | Rel-5.19.1 |
| Formas de pago | EFECTIVO, TARJETA, QR, CREDITO, DEUNA, JEPFAST, SIPY, YALOBOX |
| Cliente requerido | Sí (cédula o RUC obligatorio — sin Consumidor Final) |

## Estructura final de `dispatches` (columnas clave)

| Columna | Tipo | Referencia |
|---------|------|-----------|
| `shift_id` | FK shifts | Turno del autorizador → actualizado al cobrar |
| `authorized_by_user_id` | FK users | Quién autorizó |
| `person_id` | FK persons | Cliente (facturación) |
| `vehicle_id` | FK vehicles | Vehículo despachado |
| `dispenser_id` | FK dispensers | Surtidor |
| `emission_point_id` | FK emission_points | Punto emisión SRI |

## Base de datos

| Dato | Valor |
|------|-------|
| Host | localhost:5433 |
| Database | powerfin_gas |
| Test DB | powerfin_gas_test |
| User | postgres |
| Password | 1234abcd |

## Cómo arrancar todo

```bash
cd /home/pvalarezo/grisbiapps/powerfin_pos_gas

# Limpiar caché y estado viejo
rm -rf pos/.svelte-kit pos/node_modules/.vite

# Arrancar
./start.sh backend  # POS Backend :8080 (tarda ~3s)
./start.sh bridge   # FusionBridge :8090 (tarda ~15s)
./start.sh pos      # POS :5173

# Control:
./start.sh stop     # Detener todo
./start.sh status   # Ver estado

# Monitorear Synergy:
tail -f /tmp/fusionbridge.log

# Diagnosticar Synergy:
python3 tools/info_fusion.py
```

Abrir: **`http://192.168.1.113:5173`** | Login: `carlos` / `1234` o `maria` / `1234`

---

## NOTAS

- `plate = 'ABC1234'` está hardcodeado en `SaleWizard.svelte` para pruebas. Remover ANTES de producción.
- El dispensador físico requiere **palanca manual** además de levantar la pistola (equipo antiguo).
- `SUBSCRIBE|ALL` es necesario en firmware Rel-5.19.1 (suscripciones individuales no funcionan).
- El cambio de precio por protocolo requiere aprobación manual en consola (módulo "Price Change Add In").
- **NO usar `LID` ni `LM` en PRESET** — firmware Rel-5.19.1 crea locks permanentes.
- `localStorage` es caché local, NO source of truth. PowerFin vía reconciliación cada 3s es la autoridad.
- **No existe Consumidor Final** — toda venta requiere cliente con cédula o RUC.
- El POS Backend reemplaza al mock Python. `powerfin_server.py` queda como legacy.
- **ATO en 180 segundos** — los presets expiran después de 3 minutos sin levantar pistola.
- `dispatch_details.quantity` empieza en 0 (no NULL) — se actualiza al completar el despacho.
- **`shift_id` cambia de dueño al cobrar**: AUTHORIZED/COMPLETED → shift del autorizador; COLLECTED → shift del cobrador.
- **Cuadre de caja simplificado**: `WHERE shift_id = mi_turno AND status = 'COLLECTED'` cubre todos los casos.
