# NEXT_SESSION.md — Powerfin POS

## Estado actual (2026-06-08)

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
| **10a** | **v0.13.0** | **Phase 10 — Edge cases: cancel/stop mid-flow, phone-off resilience, completeDispatch en FusionBridge** |

### 📊 Tests

```bash
FusionBridge — 72 tests    ./mvnw test    # BUILD SUCCESS
POS Backend  — 71 tests    pytest          # 71 passed
Powerfin POS — 41 tests    npm run test    # 41 passed
Total: 184 tests pasando
```

---

## Logros de la sesión (2026-06-08) — v0.13.0

### 32. Edge cases — Gaps A, B, D cerrados ✅

**Gap D — Fallo parcial (dispatch creado, preset falló):**
- Frontend: rollback inmediato en SaleWizard y new-dispatch (try/catch → cancelDispatch)
- Backend: auto-cancel de dispatches AUTHORIZED > 5 min en get_active_dispatches

**Gap B — ATO expirado / celular apagado (análisis y revertido):**
- El auto-cancel reactivo fue revertido (comía ventas reales si completeDispatch fallaba)
- La solución real es mover completeDispatch a FusionBridge (ver abajo)

**Gap A — STOP durante FUELLING:**
- FusionBridge: nuevo endpoint `POST /api/dispatch/stop` con CLEAR_STOP diferido (2s)
- DispenserCard: ícono ⏹ pequeño durante FUELLING + evento onStopClick
- Dashboard: modal STOP con doble barrera anti-bolsillo (CANCELAR grande + Detener chico)
- Timeout 8s del modal + CLEAR_STOP automático en authorize (limpia busy buffers)

### 33. Celular apagado durante despacho — RESUELTO ✅

**Raíz del problema:** completeDispatch solo lo hacía el POS (celular) vía SSE.
Si el celular estaba apagado, NADIE completaba el dispatch → venta perdida.

**Solución:** FusionBridge ahora llama completeDispatch directamente al recibir
NEW_TRANSACTION del Wayne:
- `FusionEventHandler.java`: `completeDispatchOnBackend()` en virtual thread
- 3 reintentos con 1s backoff
- El POS sigue llamando completeDispatch como doble seguro (idempotente)
- `CLEAR_STOP` antes de cada PRESET en authorize (limpia busy buffers residuales)

**Escenarios validados:**
- ✅ Celular apagado durante FUELLING → al encender: "Cobrar $X"
- ✅ Celular apagado en AUTHORIZED → al encender: estado correcto
- ✅ STOP a mitad de despacho → CLEAR_STOP → NEW_TRANSACTION → cobro parcial
- ✅ Siguiente PRESET después de STOP → sin TRANS_ERR_PRESET_STOPPED

### Archivos modificados (esta sesión)

```
FusionBridge:
  DispatchResource.java        ← +/stop con CLEAR_STOP diferido, +CLEAR_STOP en authorize
  FusionEventHandler.java      ← +completeDispatchOnBackend (HTTP al backend, 3 retries)

POS:
  SaleWizard.svelte            ← rollback dispatch en catch (Gap D)
  new-dispatch/+page.svelte    ← rollback dispatch en catch (Gap D)
  +page.svelte                 ← modal STOP doble barrera + handleStopClick + executeStop
  DispenserCard.svelte         ← ícono ⏹ durante FUELLING + onStopClick prop
  bridge.ts                    ← +stopDispenser()
  bridge-client.ts             ← +stopDispenser() wrapper
  bridge.mock.ts               ← +stopDispenser() mock

Backend:
  dispatches.py                ← auto-cancel AUTHORIZED > 5 min (Gap D safety net)
```

---

## Logros acumulados Phase 9 (2026-06-04 → 2026-06-05)

### v0.11.0 — Price lists, wizard reorder, emission points, schema simplification

**22 frentes cerrados:** price list lookup (VIP/EMPLOYEE) antes de PRESET, wizard
reordenado (Placa → Producto → Cliente), 4 puntos de emisión (001-001 a 001-004),
`authorized_by_user_id` FK, eliminadas 4 columnas denormalizadas, `shift_id` se
actualiza al turno del cobrador, `customer_name` vía JOIN, `change_billing` 404.

### v0.12.0 — Cuadre de caja, transfers, lookup, billing, validación

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

### 🟡 Prioridad 4 — Edge cases restantes

```
☐ 2. Despacho con pago mixto (efectivo + tarjeta) — una venta
     pagada con dos métodos simultáneos
☐ 3. Reconexión de FusionBridge durante despacho activo — TCP se cae
     mientras hay un preset vivo en el dispensador
☐ 4. Múltiples despachos simultáneos — ambos lados del SURT-01
     despachando al mismo tiempo
```

### 🟠 Próximos hitos — Impresión y Cuadre de Caja

```
☐ Prueba de impresión térmica física (192.168.1.31:9100)
   — validar que el ticket imprime correctamente con hardware real
☐ Prueba de cuadre de caja end-to-end con hardware real
   — close_shift con transfers, safe_drops, diferencia $0
☐ Ajustar ATO en consola Wayne de 0 → 180s (si no se ha hecho)
```

### 🟢 Prioridad 5 — Deuda técnica

```
☐ 5. Migración Alembic para cambios de schema acumulados en Phase 9
     (billing_person_id, emission_points, authorized_by_user_id, etc.)
☐ 6. Revisar si dispatch_details.quantity=0 inicial debe ser NULL
☐ 7. Verificar precios VIP/EMPLOYEE/FAMILY dinámicos desde BD end-to-end
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
- **STOP durante FUELLING**: ⏹ → STOP → (2s) → CLEAR_STOP → NEW_TRANSACTION → cobro parcial.
  CLEAR_STOP automático en cada authorize limpia busy buffers residuales.
- **Celular apagado**: FusionBridge completa el dispatch directamente (no depende del POS).
  3 reintentos con 1s backoff. El POS también llama como doble seguro (idempotente).
- **Consola Wayne en oficina** (no en islas) → el POS es la ÚNICA forma de detener un despacho.
- **Modal STOP**: doble barrera anti-bolsillo (CANCELAR grande + Detener pequeño + timeout 8s).
