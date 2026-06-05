# NEXT_SESSION.md — Powerfin POS

## Estado actual (2026-06-05)

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
| **9** | **v0.10.0** | **Phase 9 — Integración & hardening (completada)** |

### 📊 Tests

```bash
FusionBridge — 72 tests    ./mvnw test    # BUILD SUCCESS
POS Backend  — 71 tests    pytest          # 71 passed
Powerfin POS — 41 tests    npm run test    # 41 passed
Total: 184 tests pasando
```

---

## Logros de la sesión (2026-06-05)

### 23. Cuadre de caja y transferencias ✅

**3 bugs corregidos + 1 bugfix extra:**

1. **close_shift fórmula incompleta** — No restaba TRANSFER_OUT ni SAFE_DROP.
   Fórmula: `opening + income + sales - expense - transfers_out - safe_drops`
2. **get_cash_summary mismo problema** — Misma fórmula + campos poblados:
   `total_transfers_received`, `total_transfers_sent`, `total_safe_drops`
3. **Transferencia no creaba movimiento al receptor** — `create_transfer`
   (user→user) crea INCOME automático en turno del receptor con `related_user_id`
4. **Decimal→float** — `Numeric(12,2)` retorna `Decimal` vs `or 0.0` → `float`
   causaba 500 en close_shift. Fix: `float()` explícito en todas las sumas.

**Archivos:** `shifts.py`, `cash.py`

### 24. Test end-to-end vía API ✅

Login → turno → dispatch → complete → collect → close (diff=$0.00).
Cross-user: maria autoriza, carlos cobra → shift_id actualizado.
Transferencias: $20 y SAFE_DROP → cuadre $0 en ambos turnos.

### 25. persons/lookup integrado en POS ✅

- Tipo `PersonLookupResult` + `PersonLookupData`
- `lookupPerson()` → `GET /api/pos/persons/lookup?id_type=&id_number=`
- SaleWizard y new-dispatch usan `lookupPerson` (ya no `getCustomerById`)
- Tokens reales vía `auth` store (ya sin `'mock-token'` hardcodeados)

### 26. Facturación preferencial por vehículo ✅

- DB: `vehicles.billing_person_id` FK nullable → persons. NULL = usar titular
- Backend: `lookupVehicle` devuelve `billing_person` + `PUT /vehicles/{id}/billing-person`
- POS: badge "⭐ Facturación preferencial" + checkbox "Guardar como preferencial"
- Prioridad: billingCustomer > billing_person > owner

### 27. Auto-guardado de API externo ✅

`lookupPerson` → Sercobaco/SRI → `INSERT ... ON CONFLICT DO NOTHING` en `persons`.
2ª búsqueda mismo CED/RUC → instantáneo (BD local).
DB: `UNIQUE(id_type, id_number)` en persons.

### 28. Validación CED=10 / RUC=13 dígitos ✅

`$: idValid` reactivo + `maxlength` dinámico + `inputmode="numeric"`.
Botón Buscar deshabilitado hasta longitud correcta. Mensaje de error.

### 29. Botones "← Volver" en todos los pasos del wizard ✅

Agregados en: product, billing, presetType, presetValue.
"Volver" de idLookup recuerda si vino de plate o billing.
Auto-select removido (siempre se muestra paso product).

### 30. Edición de datos del cliente ✅

Botón "✏️ Editar datos" en paso billing → formulario inline (nombre, email,
teléfono, dirección). `PUT /api/pos/persons/{id}` + `updatePerson()`.
Backend `VehicleOwner` schema + `address`.

### 31. Flujo de registro de nueva persona mejorado ✅

- Cédula/RUC pre-llenada + readonly al entrar a registro
- Campos nombre (requerido), email (requerido, facturación electrónica),
  teléfono, dirección (opcionales)
- Botón "Continuar" deshabilitado hasta nombre + email llenos
- Después de registrar → directo a billing (no a product)
- Todos los campos se limpian al entrar/cancelar

---

## Archivos modificados en esta sesión

```
pos_backend/app/api/shifts.py         ← close_shift: +TRANSFER_OUT, +SAFE_DROP, float() cast
pos_backend/app/api/cash.py           ← cash_summary: +transfers fields, float() cast;
                                        create_transfer: +INCOME receptor
pos_backend/app/api/persons.py        ← auto-save external API, +person_id, fix PUT endpoint
pos_backend/app/api/vehicles.py       ← +billing_person, +vehicle_id, +address
pos_backend/app/models/person.py      ← +billing_person_id FK + relationship
pos_backend/app/schemas/__init__.py   ← +billing_person, +vehicle_id, +person_id, +address,
                                        +SetBillingPersonRequest, fix UpdatePersonRequest

pos/src/lib/api/types.ts              ← PersonLookupResult, +person_id, +address, +vehicle_id,
                                        +billing_person en VehicleResult
pos/src/lib/api/powerfin.ts           ← lookupPerson, setVehicleBillingPerson, updatePerson
pos/src/lib/api/powerfin.mock.ts      ← mocks para todos los nuevos endpoints
pos/src/lib/components/SaleWizard.svelte ← persons/lookup, billing preferencial,
                                        auto-save, edit customer, back buttons,
                                        validación CED/RUC, wizard estandarizado,
                                        registro mejorado, state leak fixes
pos/src/lib/components/CustomerSearch.svelte ← token real vía auth store
pos/src/routes/(pos)/new-dispatch/+page.svelte ← lookupPerson, token real, validación
```

---

## Pendiente para próxima sesión

### 🟡 Prioridad 4 — Edge cases

```
☐ Despacho cancelado a mitad del flujo
☐ Despacho con pago mixto (efectivo + tarjeta)
☐ Reconexión de FusionBridge durante despacho activo
☐ Múltiples despachos simultáneos (ambos lados del SURT-01)
```

### 🟢 Prioridad 5 — Deuda técnica

```
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

## Cómo arrancar todo

```bash
cd /home/pvalarezo/grisbiapps/powerfin_pos_gas
rm -rf pos/.svelte-kit pos/node_modules/.vite
./start.sh backend  # POS Backend :8080
./start.sh bridge   # FusionBridge :8090
./start.sh pos      # POS :5173
./start.sh stop     # Detener todo
./start.sh status   # Ver estado
```

Abrir: **`http://192.168.1.113:5173`** | Login: `carlos` / `1234` o `maria` / `1234`

---

## NOTAS

- El dispensador físico requiere **palanca manual** además de levantar la pistola.
- `SUBSCRIBE|ALL` necesario en firmware Rel-5.19.1.
- **NO usar `LID` ni `LM` en PRESET** — firmware Rel-5.19.1 crea locks permanentes.
- **No existe Consumidor Final** — toda venta requiere cliente con cédula o RUC.
- **ATO en 180 segundos** — los presets expiran después de 3 minutos sin levantar pistola.
- **`shift_id` cambia al cobrar**: AUTHORIZED/COMPLETED → shift autorizador; COLLECTED → shift cobrador.
- **Cuadre de caja**: `WHERE shift_id = mi_turno AND status = 'COLLECTED'`.
- **Auto-guardado**: buscar CED/RUC en API externo → se guarda en BD local automáticamente.
- **Facturación preferencial**: `vehicles.billing_person_id` — NULL = usar titular.
- **Validación**: CED = 10 dígitos, RUC = 13 dígitos.
- **Registro nueva persona**: nombre + email requeridos (facturación electrónica).
