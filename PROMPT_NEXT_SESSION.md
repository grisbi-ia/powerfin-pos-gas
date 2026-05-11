# PROMPT_NEXT_SESSION — Powerfin POS

## Dónde nos quedamos

**Último tag:** `v0.4.0` — Phase 5: plate-centric sales flow con vehicle lookup, billing confirmation, y fallback registration.

**Branch:** `develop`

## Lo avanzado en esta sesión

### Nuevo flujo centrado en PLACA (requisito Ecuador)

El POS ya no busca clientes por nombre/cédula. El despachador **teclea la placa** del vehículo como clave primaria.

#### Endpoints agregados al contrato API (docs/API_CONTRACT.md)

- `GET /api/pos/vehicles?plate={plate}` — devuelve datos del vehículo + propietario
  - `vehicle_found: true` → datos completos o parciales (con `incomplete_fields[]`)
  - `vehicle_found: false` → no encontrado
- `GET /api/pos/customers/by-id?id_type=&id_number=&update_billing=true` — busqueda por ID
  - `update_billing=true` → indica a PowerFin que actualice permanentemente los datos de facturación

#### Nuevos componentes Svelte

| Componente | Propósito |
|------------|-----------|
| `PlateInput.svelte` | Input de placa con botón "Buscar" explícito (sin debounce) |
| `BillingConfirmation.svelte` | Muestra dueño del vehículo, pregunta "¿Correcto?" o "Cambiar" |
| `CustomerForm.svelte` | Formulario para completar email faltante o registrar nuevo cliente |

#### Tipos nuevos (types.ts)

- `VehicleResult` — con `incomplete_fields[]` para detectar datos faltantes
- `CustomerFormData` — datos del formulario de registro
- `RegisterCustomerResponse` — respuesta al registrar

### Lógica de negocios implementada

**Escenario 1 — Datos completos:**
```
PlateInput → lookupVehicle → BillingConfirmation → "Correcto" → AmountInput → Autorizar
```

**Escenario 2 — Datos incompletos (falta email):**
```
PlateInput → lookupVehicle → CustomerForm (mode: incomplete) → AmountInput → Autorizar
```

**Escenario 3 — Cambiar facturador:**
```
BillingConfirmation → "Cambiar" → idLookup → getCustomerById → BillingConfirmation → AmountInput → Autorizar
```

**Escenario 4 — Placa no encontrada:**
```
PlateInput → lookupVehicle (vehicle_found: false)
  → idLookup → getCustomerById
    ├── Encontrado → BillingConfirmation → AmountInput → Autorizar
    └── No encontrado → CustomerForm (mode: registration) → BillingConfirmation → AmountInput → Autorizar
```

**Escenario 5 — Registro de nuevo cliente:**
Luego del formulario de registro, se muestra BillingConfirmation para que el despachador confirme antes de continuar al monto.

## Qué testear en la siguiente sesión

### Flujos completos a validar uno por uno

1. **Flujo normal con datos completos**
   - Placa: `ABC1234` → debe mostrar "Juan Carlos Pérez" (VIP)
   - Confirmar → ingresar monto → autorizar → debe llegar a fueling con nombre y placa visibles

2. **Flujo con datos incompletos (sin email)**
   - Placa: `XYZ5678` → debe mostrar formulario "Datos incompletos" pidiendo email
   - Ingresar email → "Continuar" → debe mostrar BillingConfirmation con Transportes Andinos

3. **Flujo con placa no encontrada**
   - Placa: `ZZZ9999` → "Vehículo no encontrado" → pide identificación
   - Ingresar datos de identificación → buscar → si no encuentra → formulario de registro
   - Llenar formulario completo → "Continuar" → debe mostrar BillingConfirmation

4. **Flujo cambio de facturador**
   - Placa: `ABC1234` → BillingConfirmation muestra Juan Pérez
   - Presionar "Cambiar" → debe aparecer búsqueda por ID
   - Ingresar RUC `1790012345001` → debe encontrar Transportes Andinos
   - Confirmar → debe usar Transportes Andinos para facturación

5. **Flujo ID no encontrado (fallback a registro)**
   - Placa no encontrada → idLookup → ingresar ID que no existe
   - Debe mostrar CustomerForm (registration mode) en vez de error

6. **Validaciones del CustomerForm**
   - Botón "Continuar" debe habilitarse solo cuando campos obligatorios están llenos
   - En modo incomplete: email requerido
   - En modo registration: ID + nombre + email requeridos

7. **Validación de placa sin guión**
   - Escribir `ABC-1234` o `ABC1234` → ambos deben funcionar igual
   - Botón "Buscar" debe estar deshabilitado si placa tiene menos de 3 caracteres

### Archivos que no deben tocarse (sin romper)

- `BillingConfirmation.svelte` — recibe `vehicle: VehicleResult` y emite `onConfirm`/`onChangeBilling`
- `PlateInput.svelte` — recibe `onResult` y prop `disabled`
- `CustomerForm.svelte` — recibe `mode`, `plate`, `onSubmit`, `onCancel`, `loading`

### Estado de la UI en cada paso

- En `idLookup`, el título debe cambiar si viene de "vehículo no encontrado" vs "cambiar facturador"
- En `fueling`, debe verse el nombre del cliente y la placa debajo del surtidor
- El precio debe actualizarse según price_list (VIP = $1.100, STANDARD = $1.500)

## Estado de tests

- FusionBridge: 35 tests (./mvnw test)
- Powerfin POS: 38 tests (npm run test)
- **Total: 73 tests pasando**

Nota: Tests requieren Node 20+. Usar:
```bash
export PATH=$HOME/.n/bin:$PATH
```

## Datos de prueba (mock)

| Placa | Dueño | Price List | Estado |
|-------|-------|------------|--------|
| `ABC1234` | Juan Carlos Pérez (CED: 0912345678) | VIP | ✅ Completo |
| `XYZ5678` | Transportes Andinos S.A. (RUC: 1790012345001) | STANDARD | ⚠️ Sin email |
| `ZZZ9999` | — | — | ❌ No encontrado |
| `GHI9999` | — | — | ❌ No encontrado |

**Personas adicionales (para cambio de facturador):**
- María Fernanda López (RUC: 1001234567001) — STANDARD

**Login:** `carlos` / PIN `1234`

## Para iniciar la sesión

```bash
cd /home/pvalarezo/grisbiapps/powerfin_pos_gas
git checkout develop
git status
git log --oneline -5

# POS dev server
cd pos
export PATH=$HOME/.n/bin:$PATH
npm run dev

# Typecheck
npm run check

# Tests
npm run test
```

## Pendientes futuros (NO en esta sesión)

- Validación de formato de placa ecuatoriana (AAA-#### o AAA-###)
- Integración real con PowerFin (quitar mocks)
- Manejo de errores de red (offline, timeout)
- Precios dinámicos por grado de combustible
- Impresión de tickets (Fase 5 del roadmap)

## No olvidar

- Documentación en español, código en inglés
- Commits en inglés: feat(pos): / fix(pos): / test(pos):
- Versionar solo después de que todos los tests pasen
- Trabajar en `develop`, nunca en `main`
