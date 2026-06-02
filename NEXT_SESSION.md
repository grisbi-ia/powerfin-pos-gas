# NEXT_SESSION.md — Powerfin POS

## Estado actual (2026-06-02)

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
| **7** | **—** | **POS Backend — FastAPI + PostgreSQL (HOY)** |

### 📊 Tests

```bash
# FusionBridge — 72 tests
cd fusion-bridge && ./mvnw test   # BUILD SUCCESS

# POS Backend — 71 tests (NUEVO)
cd pos_backend && source venv/bin/activate && pytest   # 71 passed

# POS — 41 tests (Vitest)
cd pos && npm run test            # 41 passed

# Total: 184 tests pasando
```

---

## Logros de la sesión 2026-06-02

### 1. POS Backend — Aplicativo real con PostgreSQL ✅

Se construyó `pos_backend/` desde cero, reemplazando el simulador Python
(`tools/powerfin_server.py`) por un backend real con base de datos.

**Stack:** Python 3.10+ / FastAPI / SQLAlchemy 2.0 (async) / asyncpg / Alembic / bcrypt + PyJWT

**Arquitectura:**
- **26 tablas** en PostgreSQL modelando todo el negocio: usuarios, roles, personas,
  vehículos, dispensadores, mangueras, productos, categorías, impuestos, listas de
  precios, métodos de pago, contratos de crédito, turnos, despachos, detalles,
  pagos mixtos, movimientos de caja, transferencias, puntos de emisión SRI.
- **38 endpoints REST** cubriendo: auth, config, vehicles, customers, persons,
  prices, shifts, dispatches (CRUD + complete/collect/cancel/billing/invoice),
  cash movements, transfers, credit contracts, products, dispatch types,
  identity lookup.
- **3 servicios core**: auth (bcrypt+JWT), sequential (SRI atómico FOR UPDATE),
  credit (validación contratos, cupo disponible).
- **71 tests unitarios y de integración** — 100% pasando.

### 2. Identity API — Búsqueda externa de personas ✅

Integración con APIs externas para auto-llenar datos de clientes:

| Fuente | Tipo | Endpoint | Latencia |
|---|---|---|---|
| Sercobaco | CED | `GET /v1/info/ALL/sercobaco/{cedula}` | ~500ms |
| SRI | RUC | `GET /v1/info/ALL/sri/{ruc}` | ~2.8s |

**Endpoint unificado:** `GET /api/pos/persons/lookup?id_type=&id_number=`
- Primero busca en PostgreSQL local
- Si no encuentra, consulta API externa (timeout 5s)
- Si nada funciona, retorna `found: false` → POS muestra formulario manual

Extracción de email y teléfono del API Sercobaco (formato `||` delimitado).

### 3. Contratos de Crédito ✅

- Tablas: `credit_contracts`, `credit_contract_vehicles`, `credit_contract_products`
- Tipos: INDEFINIDO (cupo − no facturados) / NO_INDEFINIDO (cupo − todo)
- Tipos SERCOP: Ínfima Cuantía, Adjudicación, Contratación Directa, No Definido
- Validación completa: vehículo en contrato activo + producto asignado + cupo disponible
- Endpoint: `GET /api/pos/credit-contracts/{id}/available` (cupo en tiempo real)

### 4. Decimal → Float Middleware ✅

Pydantic v2 serializa `Decimal` como strings (`"2.9500"`). El POS llama `.toFixed()`
sobre estos valores, causando `TypeError`. Se implementó un middleware ASGI que
convierte strings numéricos con decimales a números reales en las respuestas JSON,
preservando strings reales como códigos (`"001"`, `"DIESEL"`).

### 5. start.sh actualizado ✅

Nuevo comando `./start.sh backend` para iniciar el POS Backend. El comando
`powerfin` ahora redirige a `backend`. Stop actualizado para incluir uvicorn.

### 6. Documentación ✅

- `docs/POS_BACKEND.md` — schema completo, reglas de negocio, seed data
- `docs/IDENTITY_API.md` — APIs externas, credenciales, mapeo de campos
- `AGENTS.md` — actualizado con el 4to sistema y nueva estructura

### 7. Synergy — Verificación de pumps ✅

Conectividad confirmada con pumps 3, 4, 7, 8. Todos responden IDLE.

---

## Pendiente para mañana (2026-06-03)

### 🔴 Prioridad 1 — Mapear nuevo surtidor en BD

```
☐ Agregar dispensador 2 a la BD (pumps 3 y 4, o 7 y 8)
☐ Definir: código, nombre, combustible, punto de emisión
☐ Agregar hoses correspondientes
☐ Actualizar seed_data.py con el nuevo dispensador
☐ Verificar que GET /api/pos/config devuelve ambos dispensadores
```

### 🔴 Prioridad 2 — Pruebas end-to-end con POS Backend

```
☐ Iniciar pos_backend en :8080
☐ Iniciar FusionBridge en :8090 (si hay Synergy)
☐ Iniciar POS en :5173
☐ Probar flujo completo:
    login → abrir turno → buscar cliente → autorizar despacho →
    completar → cobrar (con pagos mixtos) → cerrar turno
☐ Probar multi-dispositivo: abrir POS en 2 navegadores
☐ Probar contratos de crédito desde el POS
```

### 🟡 Prioridad 3 — Integrar persons/lookup en el POS

```
☐ POS: reemplazar búsqueda de cliente actual por GET /api/pos/persons/lookup
☐ POS: mostrar datos del API externo cuando no hay cliente local
☐ POS: permitir registrar cliente nuevo con datos del API
```

### 🟡 Prioridad 4 — Documentar y commitear

```
☐ Hacer commit de todos los cambios de hoy
☐ Tag: v0.9.0 — POS Backend
```

---

## Configuración actual del sitio

| Dato | Valor |
|------|-------|
| Estación | NEOGAS |
| Surtidores Synergy | 8 pumps: 1,2 (DIESEL dual), 3,4,7,8 (disponibles), 5,6 (closed) |
| Combustible | DIESEL (Grade 3, P3) |
| Precio | $3.103/galón |
| Pump 1 → Side A | Fusion hose 1 |
| Pump 2 → Side B | Fusion hose 1 |
| ATO | 0s (requiere ajuste a 180s) |
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

# Limpiar estado viejo
./start.sh stop

# Arrancar
./start.sh backend  # POS Backend :8080 (tarda ~3s)
./start.sh bridge   # FusionBridge :8090 (tarda ~15s)
./start.sh pos      # POS :5173

# Control:
./start.sh stop     # Detener todo
./start.sh status   # Ver estado

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
- Siempre `rm -rf .svelte-kit` al reiniciar el POS para evitar caché de Vite
- **NO usar `LID` ni `LM` en PRESET** — firmware Rel-5.19.1 crea locks permanentes
- `localStorage` es caché local, NO source of truth. PowerFin vía reconciliación cada 3s es la autoridad.
- Al reiniciar `powerfin_server.py`, borrar `tools/powerfin_state.json` para evitar datos inconsistentes.
- **No existe Consumidor Final** — toda venta requiere cliente con cédula o RUC.
- El POS Backend reemplaza al mock Python. `powerfin_server.py` queda como legacy.
- **ATO en 0 segundos** — los presets expiran instantáneamente. Ajustar en consola a 180s.
