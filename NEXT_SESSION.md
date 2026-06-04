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
| **8** | **—** | **Phase 9 — Integración & hardening (HOY)** |

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

## Logros de la sesión 2026-06-04

### 1. Mapeo de dispensadores — Synergy real ✅

Se consultó el Synergy vía `REQ_FCRT_PUMPS_CONFIG` y se mapearon los 8 pumps lógicos
a 4 dispensadores físicos en el POS Backend:

| Dispenser | Pumps Synergy | Productos | Estado |
|-----------|--------------|-----------|--------|
| SURT-01 GASOLINA | 001 + 002 | A: SUPER+ECO_PAIS, B: SUPER+ECO_PAIS | 🟢 IDLE |
| SURT-02 EXTRA-ECO | 003 + 004 | EXTRA-ECO ambos lados | ⚫ CLOSED |
| SURT-03 DIESEL 1 | 005 + 006 | DIESEL ambos lados | ⚫ CLOSED |
| SURT-04 DIESEL 2 | 007 + 008 | DIESEL ambos lados | ⚫ CLOSED |

**Validación física:** Se levantaron las 4 pistolas del SURT-01, confirmando:
- Lado A: hose 1 = SUPER, hose 2 = ECO_PAIS
- Lado B: hose 1 = SUPER, hose 2 = ECO_PAIS
- El Synergy reporta hose 2 para ECO_PAIS y hose 1 para SUPER (contrario al config label)
- ATO ajustado a 180s

### 2. Token hardcodeado → auth store ✅

`SaleWizard.svelte` y `PlateInput.svelte` usaban strings `'token'` y `'mock-token'`
en vez del JWT real del auth store. Se corrigieron 8 llamados en SaleWizard y 1 en PlateInput.
También se arregló `new-dispatch/+page.svelte` (importaba bridge.mock en vez del real).

### 3. POST /customers acepta actualizaciones ✅

El endpoint `POST /api/pos/customers` ahora actualiza campos (email, phone, address)
cuando el cliente ya existe, en vez de devolver 409 Conflict. Permite completar
datos faltantes en el flujo de venta.

### 4. Pantalla de cliente — datos completos ✅

La pantalla de confirmación de cliente muestra: nombre, ID, email, teléfono,
y lista de precios. El precio NO se muestra en esta pantalla (se mantiene en
memoria para el preset a Synergy).

### 5. Campo `unit_price` en el config ✅

Cada manguera en `GET /api/pos/config` ahora incluye `unit_price` desde la
lista de precios STANDARD. El POS usa este valor al seleccionar pistola.
Se eliminaron todos los hardcodes de precios (`3.103`, `2.950`) en SaleWizard.

### 6. Precios correctos por producto ✅

Corregidos en BD: SUPER=$4.50, ECO_PAIS=$2.90, DIESEL=$3.103 (estaban intercambiados).
Eliminadas leyendas de precio en pantallas de monto/galones.

### 7. `dispatch_details` ahora se usa correctamente ✅

- **Al crear:** Se crea una línea con `product_id`, `unit_price`, `tax_rate`, `quantity=0`
- **Al completar:** Se actualiza `quantity` con galones reales y se recalculan totales
- **Endpoints:** `unit_price` y `quantity` se leen de `dispatch_details`, no del campo `total`
- `dispatches.total/subtotal/tax_amount` ahora son totales reales calculados desde details

### 8. Pantalla de cobro — campo "Recibido" y modal de confirmación ✅

- Campo "Recibido $" solo visible cuando se selecciona EFECTIVO
- Vuelto = recibido − totalAPagar (no preset − despachado)
- Modal de confirmación antes de procesar el cobro
- Eliminada la sección de "Vuelto" automático de la pantalla "Despacho Completado"

### 9. Reconciliación multi-dispositivo con fuente única ✅

- Nuevo endpoint `GET /api/pos/dispatches/active` — devuelve todos los despachos
  activos (AUTHORIZED + COMPLETED) de **todos** los turnos abiertos
- La reconciliación ya no requiere turno abierto — cualquier despachador ve
  todos los despachos pendientes de cobro
- `maria` ve los despachos de `carlos` y viceversa

### 10. Orden de dispensadores estable ✅

Campo `sort_order` en tabla `dispensers`. El endpoint devuelve `ORDER BY sort_order`.
El orden no cambia al renombrar o modificar dispensadores.

---

## Pendiente para próxima sesión

### 🔴 Prioridad 1 — Testear venta completa end-to-end

```
☐ Login como carlos → abrir turno
☐ Seleccionar SURT-01 lado A → ECO_PAIS (hose 2) o SUPER (hose 1)
☐ Buscar placa → ver datos del cliente → confirmar
☐ Seleccionar monto → autorizar despacho
☐ Levantar pistola física → ver progreso en dashboard
☐ Colgar → ver "Cobrar" en dashboard
☐ Entrar a cobrar → seleccionar EFECTIVO → ingresar recibido → confirmar
☐ Verificar que el despacho pasa a COLLECTED en BD
☐ Repetir desde otro dispositivo (maria) → verificar sync multi-dispositivo
```

### 🟡 Prioridad 2 — Integrar persons/lookup en el POS

```
☐ POS: reemplazar búsqueda de cliente actual por GET /api/pos/persons/lookup
☐ POS: mostrar datos del API externo (Sercobaco/SRI) cuando no hay cliente local
☐ POS: permitir registrar cliente nuevo con datos del API externo
```

### 🟡 Prioridad 3 — Pruebas de stress y edge cases

```
☐ Despacho cancelado a mitad del flujo
☐ Despacho con pago mixto (efectivo + tarjeta)
☐ Reconexión de FusionBridge durante despacho activo
☐ Múltiples despachos simultáneos (ambos lados del SURT-01)
```

### 🟢 Prioridad 4 — Deuda técnica

```
☐ Remover hardcode plate='ABC1234' si aún existe
☐ Precios VIP/EMPLOYEE/FAMILY dinámicos (no hardcodeados)
☐ Migración Alembic para cambios de schema (hose_id, grade_id, sort_order en dispatches y dispensers)
☐ El dispatch_details actual no guarda correctamente quantity=0 inicial (debería ser NULL)
```

---

## Configuración actual del sitio

| Dato | Valor |
|------|-------|
| Estación | NEOGAS |
| Surtidores Synergy | 8 pumps: 1,2 (GASOLINA dual), 3-8 (CLOSED) |
| SURT-01 | GASOLINA: SUPER ($4.50) + ECO_PAIS ($2.90) |
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

- `plate = 'ABC1234'` está hardcodeado en `SaleWizard.svelte:28` para pruebas. Remover ANTES de producción.
- El dispensador físico requiere **palanca manual** además de levantar la pistola (equipo antiguo)
- `SUBSCRIBE|ALL` es necesario en firmware Rel-5.19.1 (suscripciones individuales no funcionan)
- El cambio de precio por protocolo requiere aprobación manual en consola (módulo "Price Change Add In")
- **NO usar `LID` ni `LM` en PRESET** — firmware Rel-5.19.1 crea locks permanentes
- `localStorage` es caché local, NO source of truth. PowerFin vía reconciliación cada 3s es la autoridad.
- Al reiniciar `powerfin_server.py`, borrar `tools/powerfin_state.json` para evitar datos inconsistentes.
- **No existe Consumidor Final** — toda venta requiere cliente con cédula o RUC.
- El POS Backend reemplaza al mock Python. `powerfin_server.py` queda como legacy.
- **ATO en 180 segundos** — los presets expiran después de 3 minutos sin levantar pistola.
- `dispatch_details.quantity` empieza en 0 (no NULL) — se actualiza al completar el despacho.
