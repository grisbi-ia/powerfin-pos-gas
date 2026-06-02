# POS Backend — Sistema de Punto de Venta Independiente

## Propósito

Backend de Punto de Venta para estaciones de combustible, desacoplado del ERP PowerFin.
Sirve como sistema POS autónomo para cualquier gasolinera independientemente del ERP
contable que utilice.

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────┐
│ Powerfin POS │────▶│  POS Backend    │────▶│  PostgreSQL  │
│  (SvelteKit) │     │ (FastAPI :8080) │     │  (negocio)   │
└──────┬───────┘     └─────────────────┘     └──────────────┘
       │
       │ auth, dispensers, print
       ▼
┌──────────────┐     ┌──────────────┐
│ FusionBridge │────▶│   Synergy    │
│ (Quarkus:8090│     │ 192.168.1.20 │
└──────────────┘     └──────────────┘
```

---

## Decisiones de diseño

| Decisión | Resultado |
|---|---|
| **Multi-sucursal** | NO. Cada estación es independiente. Código contable de sucursal en `system_config` |
| **Cajas físicas** | NO como tabla. Cada usuario tiene `accounting_cash_code` (texto) para imputación contable |
| **Inventario** | NO. Lo maneja el sistema contable externo |
| **Crédito** | NO en persons/vehicles. Se maneja vía Contratos de Crédito |
| **Pagos mixtos** | SÍ. Un despacho puede pagarse con múltiples métodos (tabla `dispatch_payments`) |
| **Yalobox** | SÍ. Campo `yalobox_wallet` en `persons` + método de pago `YALOBOX` |
| **Secuenciales SRI** | `SELECT ... FOR UPDATE` atómico sobre `emission_points` |
| **Lista de precios** | El vehículo define la lista de precios. Si no tiene, hereda de la persona. Prioridad: vehicle > person > default |
| **Stack** | Python 3.11+ / FastAPI / SQLAlchemy 2.0 / asyncpg / Alembic / bcrypt+PyJWT |

---

## Schema — 26 tablas

### Bloque 1: Empresa y configuración

```sql
-- Single-row table: datos de la empresa
CREATE TABLE company_info (
    company_id      INTEGER PRIMARY KEY DEFAULT 1 CHECK (company_id = 1),
    ruc             VARCHAR(13)  NOT NULL,
    name            VARCHAR(200) NOT NULL,
    commercial_name VARCHAR(200),
    address         VARCHAR(300),
    phone           VARCHAR(20),
    email           VARCHAR(100),
    logo_url        TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE
);

-- Key-value: parámetros del sistema
CREATE TABLE system_config (
    key             VARCHAR(100) PRIMARY KEY,
    value           TEXT NOT NULL,
    description     VARCHAR(300),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Keys esperados:
--   'accounting_branch_code'   → '001'
--   'default_currency'         → 'USD'
--   'invoice_footer_message'   → 'Gracias por su compra...'
```

### Bloque 2: Usuarios y roles

```sql
CREATE TABLE roles (
    role_id         SERIAL PRIMARY KEY,
    code            VARCHAR(30)  NOT NULL UNIQUE,  -- DISPATCHER, SUPERVISOR, ADMIN
    name            VARCHAR(100) NOT NULL,
    permissions_json JSONB,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE users (
    user_id               SERIAL PRIMARY KEY,
    username              VARCHAR(50)  NOT NULL UNIQUE,
    pin_hash              VARCHAR(255) NOT NULL,       -- bcrypt
    name                  VARCHAR(150) NOT NULL,
    role_id               INTEGER NOT NULL REFERENCES roles(role_id),
    accounting_cash_code  VARCHAR(50),                 -- "CAJA-01-001" para contabilidad
    is_active             BOOLEAN NOT NULL DEFAULT TRUE
);
```

### Bloque 3: Puntos de emisión tributaria (SRI)

```sql
CREATE TABLE emission_points (
    emission_point_id      SERIAL PRIMARY KEY,
    establishment          VARCHAR(3)  NOT NULL,        -- '001'
    emission_point         VARCHAR(3)  NOT NULL,        -- '001' → 001-001
    current_sequential     BIGINT NOT NULL DEFAULT 1,
    sequential_start       BIGINT NOT NULL,
    sequential_end         BIGINT NOT NULL,
    doc_type               VARCHAR(20) NOT NULL DEFAULT 'FACTURA',
    authorization_number   VARCHAR(50),
    authorization_date     DATE,
    authorization_expiry   DATE,
    is_active              BOOLEAN NOT NULL DEFAULT TRUE,

    UNIQUE(establishment, emission_point, doc_type)
);

-- 🔒 ATOMIC: consumir secuencial
-- BEGIN;
--   SELECT current_sequential FROM emission_points
--   WHERE emission_point_id = :id FOR UPDATE;
--   UPDATE emission_points SET current_sequential = current_sequential + 1
--   WHERE emission_point_id = :id;
-- COMMIT;
```

### Bloque 4: Dispensadores y mangueras

```sql
CREATE TABLE dispensers (
    dispenser_id       SERIAL PRIMARY KEY,
    emission_point_id  INTEGER REFERENCES emission_points(emission_point_id),
    code               VARCHAR(20)  NOT NULL,
    name               VARCHAR(100) NOT NULL,
    fusion_pump_id     INTEGER NOT NULL,
    printer_ip         VARCHAR(45),                     -- IPv4 o IPv6
    printer_port       INTEGER DEFAULT 9100,
    is_active          BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE hoses (
    hose_id          SERIAL PRIMARY KEY,
    dispenser_id     INTEGER NOT NULL REFERENCES dispensers(dispenser_id),
    side             CHAR(1) NOT NULL CHECK (side IN ('A', 'B')),
    fusion_pump_id   INTEGER NOT NULL,
    fusion_hose_id   INTEGER NOT NULL,
    grade_id         VARCHAR(20) NOT NULL               -- FK lógico a grades.code
);
```

### Bloque 5: Productos, categorías, impuestos, precios

```sql
CREATE TABLE product_categories (
    category_id   SERIAL PRIMARY KEY,
    code          VARCHAR(30)  NOT NULL UNIQUE,   -- FUEL, OIL, ADDITIVE, AMBIENTAL
    name          VARCHAR(100) NOT NULL,
    is_fuel       BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE tax_types (
    tax_type_id   SERIAL PRIMARY KEY,
    code          VARCHAR(20)  NOT NULL UNIQUE,   -- IVA_12, IVA_0, ICE, IRBPNR
    name          VARCHAR(100) NOT NULL,
    rate          NUMERIC(5,4) NOT NULL DEFAULT 0  -- 0.1200 = 12%
);

CREATE TABLE products (
    product_id    SERIAL PRIMARY KEY,
    code          VARCHAR(30)  NOT NULL UNIQUE,
    name          VARCHAR(150) NOT NULL,
    category_id   INTEGER NOT NULL REFERENCES product_categories(category_id),
    unit          VARCHAR(20)  NOT NULL DEFAULT 'UNIDAD',  -- GAL, UNIDAD, LITRO
    base_price    NUMERIC(10,4) NOT NULL DEFAULT 0,
    tax_type_id   INTEGER REFERENCES tax_types(tax_type_id),
    is_active     BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE grades (
    grade_id      SERIAL PRIMARY KEY,
    code          VARCHAR(20)  NOT NULL UNIQUE,   -- DIESEL, SUPER, ECO_PAIS
    name          VARCHAR(100) NOT NULL,
    product_id    INTEGER NOT NULL REFERENCES products(product_id)
);

CREATE TABLE price_lists (
    price_list_id SERIAL PRIMARY KEY,
    code          VARCHAR(30) NOT NULL UNIQUE,    -- STANDARD, VIP, EMPLOYEE, FAMILY
    name          VARCHAR(100) NOT NULL,
    is_default    BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE price_list_items (
    price_list_item_id SERIAL PRIMARY KEY,
    price_list_id      INTEGER NOT NULL REFERENCES price_lists(price_list_id),
    product_id         INTEGER NOT NULL REFERENCES products(product_id),
    unit_price         NUMERIC(10,4) NOT NULL,

    UNIQUE(price_list_id, product_id)
);
```

### Bloque 6: Personas y vehículos

```sql
CREATE TABLE persons (
    person_id       SERIAL PRIMARY KEY,
    id_type         VARCHAR(5)   NOT NULL,         -- CED, RUC, PAS
    id_number       VARCHAR(13)  NOT NULL,
    name            VARCHAR(200) NOT NULL,
    address         VARCHAR(300),
    phone           VARCHAR(20),
    email           VARCHAR(100),
    price_list_id   INTEGER REFERENCES price_lists(price_list_id),
    yalobox_wallet  VARCHAR(50),                   -- ID billetera Yalobox
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,

    UNIQUE(id_type, id_number)
);

CREATE TABLE vehicles (
    vehicle_id     SERIAL PRIMARY KEY,
    plate          VARCHAR(10) NOT NULL UNIQUE,
    person_id      INTEGER NOT NULL REFERENCES persons(person_id),
    price_list_id  INTEGER REFERENCES price_lists(price_list_id),
    is_active      BOOLEAN NOT NULL DEFAULT TRUE
);
-- Prioridad de lista de precios: vehicle.price_list > person.price_list > price_lists.is_default
```

### Bloque 7: Contratos de Crédito

```sql
-- Contrato maestro de crédito
CREATE TABLE credit_contracts (
    contract_id      SERIAL PRIMARY KEY,
    contract_code    VARCHAR(30)  NOT NULL UNIQUE,
    person_id        INTEGER NOT NULL REFERENCES persons(person_id),
    contract_date    DATE NOT NULL DEFAULT CURRENT_DATE,
    cupo             NUMERIC(14,2) NOT NULL,           -- cupo total del contrato
    contract_type    VARCHAR(15) NOT NULL
                     CHECK (contract_type IN ('INDEFINIDO', 'NO_INDEFINIDO')),
    sercop_type      VARCHAR(30) NOT NULL DEFAULT 'NO_DEFINIDO'
                     CHECK (sercop_type IN (
                         'INFIMA_CUANTIA', 'ADJUDICACION',
                         'CONTRATACION_DIRECTA', 'NO_DEFINIDO'
                     )),
    notes            TEXT,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Flota de vehículos anclados al contrato
CREATE TABLE credit_contract_vehicles (
    contract_vehicle_id SERIAL PRIMARY KEY,
    contract_id         INTEGER NOT NULL REFERENCES credit_contracts(contract_id),
    vehicle_id          INTEGER NOT NULL REFERENCES vehicles(vehicle_id),
    date_from           DATE NOT NULL,
    date_to             DATE,                              -- NULL = sin fecha fin (vigente)
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,

    UNIQUE(contract_id, vehicle_id)
);

-- Montos asignados por producto dentro del contrato
CREATE TABLE credit_contract_products (
    contract_product_id SERIAL PRIMARY KEY,
    contract_id         INTEGER NOT NULL REFERENCES credit_contracts(contract_id),
    product_id          INTEGER NOT NULL REFERENCES products(product_id),
    amount              NUMERIC(14,2) NOT NULL,            -- $6,000.00 para SUPER

    UNIQUE(contract_id, product_id)
);
```

**Lógica de cupo disponible:**

```python
# INDEFINIDO: solo descuenta despachos NO facturados
available = contract.cupo - sum(
    d.total for d in dispatches
    WHERE credit_contract_id = :contract_id
    AND credit_status = 'PENDING_INVOICE'
    AND status != 'CANCELLED'
)

# NO_INDEFINIDO: descuenta TODOS los despachos (facturados y no facturados)
available = contract.cupo - sum(
    d.total for d in dispatches
    WHERE credit_contract_id = :contract_id
    AND status != 'CANCELLED'
)
```

**Validación al autorizar un despacho a crédito:**

```python
# 1. Vehículo pertenece a un contrato activo
contract_vehicle = SELECT FROM credit_contract_vehicles cv
    JOIN credit_contracts c ON cv.contract_id = c.contract_id
    WHERE cv.vehicle_id = :vehicle_id
    AND c.is_active = TRUE
    AND cv.is_active = TRUE
    AND cv.date_from <= CURRENT_DATE
    AND (cv.date_to IS NULL OR cv.date_to >= CURRENT_DATE)

# 2. Producto tiene monto asignado en el contrato
contract_product = SELECT FROM credit_contract_products
    WHERE contract_id = :contract_id AND product_id = :product_id

# 3. Cupo disponible >= monto del despacho
available = calcular_cupo_disponible(contract_id, contract_type)
if dispatch.total > available → RECHAZAR: "Cupo insuficiente"

# 4. Despacho registra el contrato y queda PENDING_INVOICE
dispatches.credit_contract_id = :contract_id
dispatches.credit_status = 'PENDING_INVOICE'
```

### Bloque 8: Métodos de pago

```sql
CREATE TABLE payment_methods (
    payment_method_id  SERIAL PRIMARY KEY,
    code               VARCHAR(30) NOT NULL UNIQUE,
    name               VARCHAR(100) NOT NULL,
    requires_reference BOOLEAN NOT NULL DEFAULT FALSE,
    is_active          BOOLEAN NOT NULL DEFAULT TRUE
);
-- Valores base: EFECTIVO, TARJETA, QR, CREDITO, DEUNA, JEPFAST, SIPY, YALOBOX
```

### Bloque 9: Turnos

```sql
CREATE TABLE shifts (
    shift_id         SERIAL PRIMARY KEY,
    user_id          INTEGER NOT NULL REFERENCES users(user_id),
    opening_cash     NUMERIC(12,2) NOT NULL DEFAULT 0,
    closing_cash     NUMERIC(12,2),
    status           VARCHAR(10) NOT NULL DEFAULT 'OPEN'
                     CHECK (status IN ('OPEN', 'CLOSED')),
    opened_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at        TIMESTAMPTZ,
    accounting_date  DATE NOT NULL DEFAULT CURRENT_DATE
);

CREATE INDEX idx_shifts_user_status ON shifts(user_id, status);
```

### Bloque 10: Despachos

```sql
CREATE TABLE dispatch_types (
    dispatch_type_id  SERIAL PRIMARY KEY,
    code              VARCHAR(30) NOT NULL UNIQUE,
    name              VARCHAR(100) NOT NULL,
    requires_customer BOOLEAN NOT NULL DEFAULT TRUE,
    affects_cash      BOOLEAN NOT NULL DEFAULT TRUE
);
-- Valores base: SALE, CREDIT, CALIBRATION, TEST

CREATE TABLE dispatches (
    dispatch_id        SERIAL PRIMARY KEY,
    order_id           VARCHAR(30) NOT NULL UNIQUE,      -- OV-20260602-090000-001
    shift_id           INTEGER NOT NULL REFERENCES shifts(shift_id),
    dispenser_id       INTEGER NOT NULL REFERENCES dispensers(dispenser_id),
    emission_point_id  INTEGER REFERENCES emission_points(emission_point_id),
    sequential_number  VARCHAR(20),                      -- 001-001-000000045
    dispatch_type_id   INTEGER NOT NULL REFERENCES dispatch_types(dispatch_type_id),
    vehicle_id         INTEGER REFERENCES vehicles(vehicle_id),
    person_id          INTEGER REFERENCES persons(person_id),  -- billing recipient
    credit_contract_id INTEGER REFERENCES credit_contracts(contract_id),  -- 🆕 contrato crédito
    credit_status      VARCHAR(20)                       -- 🆕 PENDING_INVOICE | INVOICED
                       CHECK (credit_status IN ('PENDING_INVOICE', 'INVOICED')),
    subtotal           NUMERIC(12,2) NOT NULL DEFAULT 0,
    tax_amount         NUMERIC(12,2) NOT NULL DEFAULT 0,
    total              NUMERIC(12,2) NOT NULL DEFAULT 0,
    status             VARCHAR(15) NOT NULL DEFAULT 'AUTHORIZED'
                       CHECK (status IN ('AUTHORIZED', 'COMPLETED', 'COLLECTED', 'CANCELLED')),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at       TIMESTAMPTZ,
    authorized_by      VARCHAR(150),
    customer_name      VARCHAR(200)                      -- denormalized for cross-device sync
);

CREATE INDEX idx_dispatches_shift ON dispatches(shift_id);
CREATE INDEX idx_dispatches_status ON dispatches(status);

CREATE TABLE dispatch_details (
    detail_id     SERIAL PRIMARY KEY,
    dispatch_id   INTEGER NOT NULL REFERENCES dispatches(dispatch_id),
    product_id    INTEGER NOT NULL REFERENCES products(product_id),
    quantity      NUMERIC(12,4) NOT NULL,
    unit_price    NUMERIC(10,4) NOT NULL,
    tax_rate      NUMERIC(5,4) NOT NULL DEFAULT 0,
    tax_amount    NUMERIC(12,2) NOT NULL DEFAULT 0,
    subtotal      NUMERIC(12,2) NOT NULL DEFAULT 0,
    total         NUMERIC(12,2) NOT NULL DEFAULT 0
);

CREATE TABLE dispatch_payments (
    payment_id         SERIAL PRIMARY KEY,
    dispatch_id        INTEGER NOT NULL REFERENCES dispatches(dispatch_id),
    payment_method_id  INTEGER NOT NULL REFERENCES payment_methods(payment_method_id),
    amount             NUMERIC(12,2) NOT NULL,
    reference_code     VARCHAR(100),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_dispatch_payments_dispatch ON dispatch_payments(dispatch_id);
```

### Bloque 11: Caja y transferencias

```sql
CREATE TABLE cash_movements (
    movement_id      SERIAL PRIMARY KEY,
    shift_id         INTEGER NOT NULL REFERENCES shifts(shift_id),
    type             VARCHAR(20) NOT NULL
                     CHECK (type IN ('INCOME', 'EXPENSE', 'SAFE_DROP', 'TRANSFER_OUT')),
    amount           NUMERIC(12,2) NOT NULL,
    observation      VARCHAR(300),
    running_balance  NUMERIC(12,2) NOT NULL DEFAULT 0,
    related_user_id  INTEGER REFERENCES users(user_id),
    related_user_name VARCHAR(150),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_cash_movements_shift ON cash_movements(shift_id);

CREATE TABLE transfers (
    transfer_id     SERIAL PRIMARY KEY,
    from_shift_id   INTEGER NOT NULL REFERENCES shifts(shift_id),
    to_user_id      INTEGER,                              -- NULL = Caja Fuerte
    to_user_name    VARCHAR(150) NOT NULL,
    amount          NUMERIC(12,2) NOT NULL,
    observation     VARCHAR(300),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## API Endpoints

### Endpoints existentes (del mock actual)

| Método | Endpoint | Tablas principales |
|---|---|---|
| POST | `/api/pos/auth/login` | users, roles |
| GET | `/api/pos/config` | company_info, dispensers, hoses, grades, products, price_lists, price_list_items, payment_methods |
| GET | `/api/pos/vehicles?plate=` | vehicles, persons, price_lists (vehicle.price_list → person.price_list → default) |
| GET | `/api/pos/customers?q=` | persons, vehicles |
| GET | `/api/pos/customers/by-id?id_type=&id_number=` | persons |
| POST | `/api/pos/customers` | persons, vehicles |
| GET | `/api/pos/prices?vehicleId=&gradeId=` | vehicles, persons, price_list_items, products, grades. Prioridad: vehicle.price_list > person.price_list > default |
| POST | `/api/pos/shifts/open` | shifts |
| GET | `/api/pos/shifts/current` | shifts, users |
| POST | `/api/pos/shifts/{id}/close` | shifts, dispatches, cash_movements |
| POST | `/api/pos/dispatches` | dispatches, dispatch_details, emission_points |
| POST | `/api/pos/dispatches/{id}/complete` | dispatches, dispatch_details (idempotente) |
| POST | `/api/pos/dispatches/{id}/collect` | dispatches, dispatch_payments |
| POST | `/api/pos/dispatches/{id}/cancel` | dispatches |
| POST | `/api/pos/dispatches/{id}/billing` | dispatches |
| GET | `/api/pos/shifts/{id}/dispatches` | dispatches, dispatch_details, persons, vehicles |
| POST | `/api/pos/cash-movements` | cash_movements |
| GET | `/api/pos/shifts/{id}/cash-movements` | cash_movements |
| GET | `/api/pos/shifts/{id}/cash-summary` | cash_movements, dispatches |
| GET | `/api/pos/users/online` | shifts, users, dispatches |
| POST | `/api/pos/transfers` | transfers, cash_movements |

### Endpoints NUEVOS

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/pos/products` | Catálogo de productos (combustibles + no combustibles) |
| GET | `/api/pos/product-categories` | Categorías de productos |
| GET | `/api/pos/price-lists` | Listas de precios disponibles |
| GET | `/api/pos/dispatch-types` | Tipos de despacho (venta, crédito, calibración, prueba) |
| PUT | `/api/pos/persons/{id}` | Actualizar datos de persona (yalobox_wallet, lista de precios, etc.) |
| GET | `/api/pos/credit-contracts` | Listar contratos de crédito activos |
| GET | `/api/pos/credit-contracts/{id}` | Detalle de contrato con flota y montos |
| POST | `/api/pos/credit-contracts` | Crear contrato de crédito |
| PUT | `/api/pos/credit-contracts/{id}` | Editar contrato |
| GET | `/api/pos/credit-contracts/{id}/available` | Cupo disponible en tiempo real |
| POST | `/api/pos/dispatches/{id}/invoice` | Marcar despacho a crédito como facturado |

---

## Flujos validados

### Flujo 1: Venta de combustible + aceite con pago mixto

```
1. Cliente: Juan Pérez (CED 0912345678), price_list: VIP
   → DIESEL $2.950/gal, ACEITE 20W50 $12.00

2. POST /api/pos/dispatches
   → Crea dispatch + dispatch_details
   → Consume secuencial de emission_point (SELECT FOR UPDATE)
   → sequential_number = '001-001-000000045'

3. POST /api/pos/dispatches/{id}/complete
   → status = COMPLETED
   → actualiza final_amount, final_volume en dispatch_details

4. POST /api/pos/dispatches/{id}/collect
   → dispatch_payments:
       EFECTIVO: $20.00
       YALOBOX:  $14.72  (usa persons.yalobox_wallet del cliente)
   → status = COLLECTED

Totales: subtotal $31.00 + IVA $3.72 = $34.72 ✅
```

### Flujo 2: Despacho a crédito con contrato

```
1. Contrato: CT-2026-001, INDEFINIDO, cupo $5,000
   Cliente: Transportes Andinos (RUC 1790012345001)
   Flota: ABC1234 (vigente), XYZ5678 (vigente)
   Productos: DIESEL $3,000, SUPER $2,000

2. Vehículo ABC1234 llega a tanquear DIESEL a crédito
   → Validación 1: ¿ABC1234 está en contrato activo? ✅
   → Validación 2: ¿Fecha actual dentro de date_from..date_to? ✅
   → Validación 3: ¿DIESEL tiene monto asignado? $3,000 ✅
   → Validación 4: Cupo disponible (INDEFINIDO) = $5,000 - PENDING_INVOICE
     → PENDING_INVOICE actual: $1,200 → disponible: $3,800
   → Nuevo despacho: $150 DIESEL
   → $150 <= $3,800 ✅ AUTORIZA

3. POST /api/pos/dispatches
   → dispatch_type = CREDIT
   → credit_contract_id = CT-2026-001
   → credit_status = 'PENDING_INVOICE'

4. A fin de mes, facturación:
   POST /api/pos/dispatches/{id}/invoice
   → credit_status = 'INVOICED'
   → INDEFINIDO: cupo disponible ahora ignora este despacho
   → NO_INDEFINIDO: cupo disponible NO cambia (ya estaba descontado)
```

### Flujo 3: Cierre de turno con código contable

```
1. Usuario: Carlos Sarmiento, accounting_cash_code = 'CAJA-01-001'

2. POST /api/pos/shifts/{id}/close
   → Suma ventas en EFECTIVO del turno
   → Suma movimientos de caja (INCOME - EXPENSE)
   → Calcula difference vs closing_cash declarado

3. Respuesta incluye:
   → accounting_cash_code = 'CAJA-01-001'  ← para sistema contable
   → accounting_branch_code = '001'        ← de system_config
   ✅ Sistema contable sabe a qué cuenta y sucursal imputar
```

### Flujo 4: Calibración (sin cliente, sin factura, sin caja)

```
1. dispatch_type = CALIBRATION
   → requires_customer = false → person_id puede ser NULL
   → affects_cash = false → no afecta cierre de turno

2. POST /api/pos/dispatches
   → emission_point_id = NULL (no consume secuencial SRI)
   → sequential_number = NULL
   → person_id = NULL, vehicle_id = NULL

3. dispatch_details:
   → DIESEL, 2.0 gal × $0.00 = $0.00
   ✅ Queda registrado como CALIBRATION para trazabilidad
```

---

## Seed data

### Roles

| code | name | permissions |
|---|---|---|
| DISPATCHER | Despachador | ventas, cobros, turnos |
| SUPERVISOR | Supervisor | todo despachador + cierre de turno, reportes |
| ADMIN | Administrador | todo + configuración del sistema |

### Tipos de despacho

| code | name | requires_customer | affects_cash |
|---|---|---|---|
| SALE | Venta Normal | true | true |
| CREDIT | Venta a Crédito | true | true |
| CALIBRATION | Calibración | false | false |
| TEST | Prueba | false | false |

### Categorías de productos

| code | name | is_fuel |
|---|---|---|
| FUEL | Combustibles | true |
| OIL | Aceites y Lubricantes | false |
| ADDITIVE | Aditivos | false |
| AMBIENTAL | Ambientales | false |

### Métodos de pago

| code | name | requires_reference |
|---|---|---|
| EFECTIVO | Efectivo | false |
| TARJETA | Tarjeta Crédito/Débito | true |
| QR | QR / Transferencia | false |
| CREDITO | Crédito | false |
| DEUNA | DeUna | true |
| JEPFAST | JepFast | true |
| SIPY | Sipy | true |
| YALOBOX | Yalobox | false |

### Tipos de contratación SERCOP

| code | name |
|---|---|
| INFIMA_CUANTIA | Ínfima Cuantía |
| ADJUDICACION | Adjudicación |
| CONTRATACION_DIRECTA | Contratación Directa |
| NO_DEFINIDO | No Definido |

### Tipos de impuestos

| code | name | rate |
|---|---|---|
| IVA_12 | IVA 12% | 0.1200 |
| IVA_0 | IVA 0% | 0.0000 |
| ICE | ICE | 0.0000 |

---

## Reglas de negocio críticas

### 1. Secuenciales atómicos (SRI)

```python
# Pseudocódigo — SELECT ... FOR UPDATE
async def consume_sequential(db, emission_point_id):
    async with db.begin():
        ep = await db.execute(
            select(EmissionPoint)
            .where(EmissionPoint.id == emission_point_id)
            .with_for_update()
        )
        ep = ep.scalar_one()
        if ep.current_sequential > ep.sequential_end:
            raise Exception("Secuencial agotado — renovar autorización SRI")
        seq = ep.current_sequential
        ep.current_sequential += 1
        sequential_number = f"{ep.establishment}-{ep.emission_point}-{seq:09d}"
    return sequential_number
```

### 2. Contratos de crédito — verificación al autorizar

```python
async def validate_credit_dispatch(db, vehicle_id, product_id, amount):
    # 1. Vehículo en contrato activo y en rango de fechas
    cv = await db.execute(
        select(credit_contract_vehicles, credit_contracts)
        .join(credit_contracts)
        .where(
            credit_contract_vehicles.vehicle_id == vehicle_id,
            credit_contracts.is_active == True,
            credit_contract_vehicles.is_active == True,
            credit_contract_vehicles.date_from <= date.today(),
            or_(
                credit_contract_vehicles.date_to.is_(None),
                credit_contract_vehicles.date_to >= date.today()
            )
        )
    )
    if not cv: raise HTTPException(400, "Vehículo sin contrato de crédito activo")

    contract = cv.credit_contracts

    # 2. Producto con monto asignado
    cp = await db.get(credit_contract_products, 
                      (contract.contract_id, product_id))
    if not cp: raise HTTPException(400, "Producto no asignado al contrato")

    # 3. Cupo disponible
    available = await calcular_cupo_disponible(db, contract)
    if amount > available:
        raise HTTPException(400, f"Cupo insuficiente. Disponible: ${available:,.2f}")

    return contract
```

### 3. Cálculo de cupo disponible por tipo de contrato

```python
async def calcular_cupo_disponible(db, contract: CreditContract) -> Decimal:
    """
    INDEFINIDO:  cupo - despachos NO facturados (PENDING_INVOICE)
    NO_INDEFINIDO: cupo - TODOS los despachos (facturados o no)
    """
    base_query = select(func.coalesce(func.sum(Dispatches.total), 0)).where(
        Dispatches.credit_contract_id == contract.contract_id,
        Dispatches.status != 'CANCELLED'
    )

    if contract.contract_type == 'INDEFINIDO':
        base_query = base_query.where(
            Dispatches.credit_status == 'PENDING_INVOICE'
        )
    # NO_INDEFINIDO: no filtra por credit_status — descuenta todo

    consumed = await db.scalar(base_query)
    return contract.cupo - (consumed or 0)
```

### 4. Yalobox — pago automático

- Al seleccionar método YALOBOX, el sistema toma `persons.yalobox_wallet` del cliente
- El despachador no necesita ingresar el ID de billetera manualmente
- Si `yalobox_wallet` es NULL → error: "Cliente sin billetera Yalobox registrada"

### 5. Idempotencia de /complete

- Si ya fue procesada (status != AUTHORIZED), retornar OK sin modificar
- Si viene de NEW_TRANSACTION SSE (fire-and-forget), puede llegar duplicado

### 6. Eliminación de Consumidor Final

- Por regulación SRI, toda venta requiere cliente identificado (cédula o RUC)
- `dispatch_types.SALE.requires_customer = true`
- Solo CALIBRATION y TEST permiten `person_id = NULL`

---

## Convenciones de nombres

| Contexto | Formato | Ejemplo |
|---|---|---|
| order_id | `OV-YYYYMMDD-HHMMSS-NNN` | `OV-20260602-090000-001` |
| sequential_number | `EEE-PPP-SSSSSSSSS` | `001-001-000000045` |
| Endpoints | `/api/pos/{resource}` | `/api/pos/dispatches` |
| Tablas | snake_case plural | `dispatch_details` |
| PKs | `{table_singular}_id` | `dispatch_id` |
| Códigos | UPPER_SNAKE | `DIESEL`, `IVA_12` |

---

## Stack técnico

```yaml
language: python 3.11+
framework: fastapi
orm: sqlalchemy 2.0 (async)
driver: asyncpg
migrations: alembic
auth: bcrypt + PyJWT
server: uvicorn
testing: pytest + httpx + pytest-asyncio
```

---

## Archivos del proyecto

```
powerfin-backend/
├── alembic/
│   ├── versions/
│   └── env.py
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app factory
│   ├── config.py            # Settings from env vars
│   ├── database.py          # AsyncSession + engine
│   ├── models/
│   │   ├── __init__.py
│   │   ├── company.py        # CompanyInfo, SystemConfig
│   │   ├── user.py           # User, Role
│   │   ├── tributary.py      # EmissionPoint
│   │   ├── dispenser.py      # Dispenser, Hose
│   │   ├── product.py        # ProductCategory, TaxType, Product, Grade
│   │   ├── pricing.py        # PriceList, PriceListItem
│   │   ├── person.py         # Person, Vehicle
│   │   ├── payment.py        # PaymentMethod
│   │   ├── credit.py         # CreditContract, CreditContractVehicle, CreditContractProduct
│   │   ├── shift.py          # Shift
│   │   └── dispatch.py       # DispatchType, Dispatch, DispatchDetail, DispatchPayment,
│   │                         # CashMovement, Transfer
│   ├── schemas/
│   │   └── ...               # Pydantic request/response models
│   ├── api/
│   │   ├── __init__.py
│   │   ├── router.py         # Main router
│   │   ├── deps.py           # Dependencies (get_db, get_current_user)
│   │   ├── auth.py
│   │   ├── config.py
│   │   ├── vehicles.py
│   │   ├── customers.py
│   │   ├── persons.py        # 🆕 person CRUD
│   │   ├── prices.py
│   │   ├── products.py       # 🆕 product catalog
│   │   ├── shifts.py
│   │   ├── dispatches.py
│   │   ├── cash.py
│   │   ├── credit_contracts.py  # 🆕 contratos de crédito
│   │   └── users.py
│   └── services/
│       ├── __init__.py
│       ├── auth_service.py
│       ├── sequential_service.py  # 🔒 atomic sequential
│       ├── credit_service.py      # 🆕 validación contratos, cupo disponible
│       ├── dispatch_service.py
│       ├── shift_service.py
│       └── cash_service.py
├── tests/
│   ├── conftest.py
│   └── test_*.py
├── alembic.ini
├── requirements.txt
├── pyproject.toml
├── .env.example
└── seed_data.py              # Datos iniciales
```

---

## Fecha: 2026-06-02 | Versión: 1.1-draft | Tablas: 26
