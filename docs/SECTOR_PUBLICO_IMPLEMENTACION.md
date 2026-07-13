# Sector Público — Plan de Implementación

> Documento de implementación. Listo para ejecutar.
> Fecha: 2026-07-07 · Basado en análisis de código actual

---

## 🎯 Objetivo

Permitir ventas de combustible a entidades del sector público con contrato
**NO_INDEFINIDO**, donde:

1. El contrato tiene un monto fijo en dólares distribuido por producto
2. Los despachos se anclan al contrato y descuentan del cupo
3. **No se generan facturas electrónicas individuales** (sin secuencial SRI, sin Key49)
4. Periódicamente se emite una **factura global** que agrupa todos los despachos acumulados
5. El flujo de venta normal (`SALE`) **no se modifica en absoluto**

---

## 📐 Arquitectura del cambio

```
CONTRATO NO_INDEFINIDO (Sector Público)
  │
  ├─ credit_contract_products: $3,000 SUPER, $2,500 DIESEL
  ├─ credit_contract_vehicles: GMC-1234, GMC-1235, ...
  │
  └─ Despachos individuales:
       ├─ Sin secuencial SRI
       ├─ Sin access_key (49 dígitos)
       ├─ Sin envío a Key49
       └─ credit_status = "PENDING_BULK_INVOICE"

  Periódicamente:
  └─ Factura GLOBAL → Key49 → SRI
       ├─ Todos los PENDING_BULK_INVOICE → INVOICED
       └─ Una sola factura con N ítems
```

---

## 📊 Estado actual (lo que ya existe)

### ✅ No necesita cambios

| Componente | Estado | Detalle |
|---|---|---|
| Modelo `credit_contracts` | ✅ Completo | `contract_type`, `sercop_type`, `cupo`, `is_active` |
| Modelo `credit_contract_products` | ✅ Completo | `amount` por producto |
| Modelo `credit_contract_vehicles` | ✅ Completo | Fechas, `is_active` |
| `dispatches.credit_contract_id` | ✅ Existe | FK a `credit_contracts` |
| `dispatches.credit_status` | ✅ Existe | CHECK: PENDING_INVOICE, INVOICED |
| `dispatch_types.CREDIT` | ✅ Existe | `affects_cash=False`, `requires_customer=True` |
| CRUD contratos | ✅ Completo | 6 endpoints en `credit_contracts.py` |
| `calcular_cupo_disponible()` | ✅ Funciona | INDEFINIDO vs NO_INDEFINIDO |
| `validate_credit_dispatch()` | ✅ Funciona | 3 checks: vehículo, producto, cupo |
| `find_active_contract_for_vehicle()` | ✅ Funciona | JOIN + fechas |
| `POST /{id}/invoice` | ✅ Existe | Marca individual como INVOICED |

---

## 🔨 Fases de implementación

---

### FASE 1 — Modelo: nuevo `credit_status` y migración

**Objetivo**: Agregar `PENDING_BULK_INVOICE` al CHECK constraint de `credit_status`.

**Archivos**:
- `pos_backend/app/models/dispatch.py`
- `pos_backend/alembic/versions/` (nueva migración)

**Paso 1.1** — Modificar el modelo:
```python
# dispatch.py — línea del CheckConstraint
# ACTUAL:
"credit_status IS NULL OR credit_status IN ('PENDING_INVOICE', 'INVOICED')",
# NUEVO:
"credit_status IS NULL OR credit_status IN ('PENDING_INVOICE', 'PENDING_BULK_INVOICE', 'INVOICED')",
```

**Paso 1.2** — Crear migración Alembic:
```bash
cd pos_backend
source venv/bin/activate
alembic revision --autogenerate -m "add_pending_bulk_invoice_to_credit_status"
```

**Paso 1.3** — Verificar la migración generada. Debe contener:
```python
# En upgrade():
op.drop_constraint('ck_dispatches_credit_status', 'dispatches', type_='check')
op.create_check_constraint(
    'ck_dispatches_credit_status', 'dispatches',
    "credit_status IS NULL OR credit_status IN ('PENDING_INVOICE', 'PENDING_BULK_INVOICE', 'INVOICED')"
)

# En downgrade():
op.drop_constraint('ck_dispatches_credit_status', 'dispatches', type_='check')
op.create_check_constraint(
    'ck_dispatches_credit_status', 'dispatches',
    "credit_status IS NULL OR credit_status IN ('PENDING_INVOICE', 'INVOICED')"
)
```

**Paso 1.4** — Ejecutar migración:
```bash
alembic upgrade head
```

**Verificación**:
```bash
# Debe pasar sin errores
pytest tests/ -k "dispatch" -v
```

**Impacto en producción**: Cero. Solo se agrega un valor válido al constraint.

---

### FASE 2 — Backend: bloquear SRI para sector público

**Objetivo**: Los despachos de sector público NO generan secuencial, access_key,
ni se envían a Key49 individualmente.

**Archivos**:
- `pos_backend/app/api/dispatches.py`

#### Paso 2.1 — `create_dispatch`: asignar `credit_status` correcto

En `create_dispatch()`, donde se asigna `credit_status` (actualmente siempre
`"PENDING_INVOICE"`), distinguir según el tipo de contrato:

```python
# Localizar el bloque actual (aprox línea 130-150):
if credit_contract_id:
    from app.models.credit import CreditContract
    contract = (await db.execute(
        select(CreditContract).where(CreditContract.contract_id == credit_contract_id)
    )).scalar_one_or_none()
    if contract:
        product_id = body.items[0].product_id if body.items else None
        if product_id:
            await validate_credit_dispatch(
                db, 0, product_id, body.unit_price
            )
        # ─── NUEVO: distinguir tipo de contrato ───
        if contract.contract_type == "NO_INDEFINIDO":
            credit_status = "PENDING_BULK_INVOICE"  # ← sector público
        else:
            credit_status = "PENDING_INVOICE"        # ← crédito privado
```

#### Paso 2.2 — `create_dispatch`: no consumir secuencial para sector público

En el bloque donde se consume el secuencial (actualmente `if dispatch_type.affects_cash or dispatch_type.dispatch_type_id == 2`):

```python
# ACTUAL (aprox línea 138):
if dispatch_type.affects_cash or dispatch_type.dispatch_type_id == 2:

# NUEVO:
if dispatch_type.affects_cash or (
    dispatch_type.dispatch_type_id == 2
    and credit_status != "PENDING_BULK_INVOICE"
):
```

**Lógica**: CREDIT + sector público → sin secuencial. CREDIT + privado → con secuencial.

#### Paso 2.3 — `create_dispatch`: no generar access_key para sector público

En el bloque donde se genera el access_key SRI (aprox línea 190-220):

```python
# ACTUAL:
if ep and sequential_number:
    try:
        parts = sequential_number.split("-")
        ...
        dispatch.access_key = access_key

# NUEVO:
if ep and sequential_number and credit_status != "PENDING_BULK_INVOICE":
    try:
        parts = sequential_number.split("-")
        ...
        dispatch.access_key = access_key
```

#### Paso 2.4 — `collect_dispatch`: no enviar a Key49 si es sector público

En `collect_dispatch()`, donde se dispara `_key49_background()`:

```python
# ACTUAL:
try:
    import asyncio
    dispatch_id = dispatch.dispatch_id
    asyncio.create_task(_key49_background(dispatch_id))
except Exception:
    pass

# NUEVO:
if dispatch.credit_status != "PENDING_BULK_INVOICE":
    try:
        import asyncio
        dispatch_id = dispatch.dispatch_id
        asyncio.create_task(_key49_background(dispatch_id))
    except Exception:
        pass
```

#### Paso 2.5 — `key49_service.py`: filtrar `PENDING_BULK_INVOICE` en retry

En `retry_pending_invoices()`:

```python
# ACTUAL:
result = await db.execute(
    select(Dispatch).where(
        Dispatch.sri_status == "PENDING",
        Dispatch.status != "CANCELLED"
    )
)

# NUEVO:
result = await db.execute(
    select(Dispatch).where(
        Dispatch.sri_status == "PENDING",
        Dispatch.status != "CANCELLED",
        Dispatch.credit_status != "PENDING_BULK_INVOICE"
    )
)
```

Y en `emitir_factura()`:

```python
# NUEVO guard al inicio de emitir_factura:
if dispatch.credit_status == "PENDING_BULK_INVOICE":
    return False  # Nunca enviar factura individual de sector público
```

**Verificación Fase 2**:
```bash
pytest tests/ -k "dispatch" -v
pytest tests/ -k "credit" -v
# Deben pasar todos los tests existentes sin modificar
```

---

### FASE 3 — Backend: validación de cupo POR PRODUCTO

**Objetivo**: El cupo se valida al nivel de producto asignado en el contrato,
no solo contra el cupo total.

**Archivos**:
- `pos_backend/app/services/credit_service.py`
- `pos_backend/tests/` (nuevos tests)

#### Paso 3.1 — Nueva función `calcular_cupo_disponible_por_producto()`

```python
# En credit_service.py, después de calcular_cupo_disponible()

async def calcular_cupo_disponible_por_producto(
    db: AsyncSession, contract_id: int, product_id: int
) -> Decimal:
    """
    Calculate available credit for a specific product within a contract.

    Returns the allocated amount minus consumed dispatches for that product.
    Uses the same logic as calcular_cupo_disponible but scoped to one product.
    """
    # Get allocated amount for this product
    allocated = await get_contract_product_amount(db, contract_id, product_id)
    if allocated is None:
        return Decimal("0")

    # Get consumed amount for this product in this contract
    base_query = select(func.coalesce(func.sum(Dispatch.total), 0)).where(
        Dispatch.credit_contract_id == contract_id,
        Dispatch.status != "CANCELLED",
    )

    # Scoped to product via dispatch_details
    base_query = base_query.join(
        DispatchDetail,
        dispatch_detail.dispatch_id == Dispatch.dispatch_id
    ).where(
        dispatch_detail.product_id == product_id
    )

    # Get contract to determine type
    contract_result = await db.execute(
        select(CreditContract).where(CreditContract.contract_id == contract_id)
    )
    contract = contract_result.scalar_one_or_none()
    
    if contract and contract.contract_type == "INDEFINIDO":
        base_query = base_query.where(
            Dispatch.credit_status == "PENDING_INVOICE"
        )

    result = await db.execute(base_query)
    consumed = result.scalar_one() or Decimal("0")
    return allocated - consumed
```

**Nota**: Necesitarás importar `DispatchDetail` y `CreditContract` al inicio:
```python
from app.models.dispatch import Dispatch, DispatchDetail
```

#### Paso 3.2 — Modificar `validate_credit_dispatch()` para auto-limitar al cupo

**Regla de negocio**: Si el monto solicitado supera el cupo disponible, el sistema
NO debe rechazar la venta. Debe **auto-limitar el monto** al saldo disponible.

Ejemplo: cupo DIESEL = $100, despachador pide $150 → el sistema despacha $100.

Esto aplica en **dos capas**:
1. **Frontend** (Fase 7): SaleWizard muestra warning y auto-ajusta el preset
2. **Backend** (Fase 3): `validate_credit_dispatch` devuelve el monto efectivo (capped)

```python
# NUEVA versión de validate_credit_dispatch() — devuelve el monto efectivo

async def validate_credit_dispatch(
    db: AsyncSession,
    vehicle_id: int,
    product_id: int,
    amount: Decimal,
) -> tuple[CreditContract, Decimal]:
    """
    Full validation for a credit dispatch.
    Returns (contract, effective_amount) where effective_amount ≤ amount.
    
    If the requested amount exceeds available credit, it is auto-capped
    to the available balance (both product-level and contract-level).
    
    Raises CreditValidationError only if:
    - No active contract for the vehicle
    - Product is not allocated in the contract
    - Available balance is $0.00 (fully consumed)
    """
    # 1. Vehicle must have an active contract
    contract = await find_active_contract_for_vehicle(db, vehicle_id)
    if not contract:
        raise CreditValidationError(
            "El vehículo no tiene un contrato de crédito activo."
        )

    # 2. Product must be allocated in the contract
    product_amount = await get_contract_product_amount(db, contract.contract_id, product_id)
    if product_amount is None:
        raise CreditValidationError(
            "El producto no está asignado al contrato de crédito."
        )

    effective = amount

    # 3. Auto-cap to product-level available balance
    product_available = await calcular_cupo_disponible_por_producto(
        db, contract.contract_id, product_id
    )
    if product_available <= Decimal("0"):
        raise CreditValidationError(
            f"Cupo agotado para este producto. "
            f"No queda saldo disponible."
        )
    if effective > product_available:
        effective = product_available  # ← auto-cap, no error

    # 4. Auto-cap to total contract balance (belt and suspenders)
    total_available = await calcular_cupo_disponible(db, contract)
    if total_available <= Decimal("0"):
        raise CreditValidationError(
            f"Cupo total del contrato agotado. "
            f"No queda saldo disponible."
        )
    if effective > total_available:
        effective = total_available  # ← auto-cap again if needed

    return contract, effective
```

**Cambio en `create_dispatch`**: el valor retornado ahora es una tupla, y se debe
usar `effective_amount` como el monto real del despacho:

```python
# En create_dispatch(), donde se llama validate_credit_dispatch:

contract, effective_amount = await validate_credit_dispatch(
    db, vehicle_id, product_id, Decimal(str(body.unit_price))
)
credit_contract_id = contract.contract_id
credit_status = "PENDING_BULK_INVOICE" if contract.contract_type == "NO_INDEFINIDO" else "PENDING_INVOICE"

# Si el monto fue auto-limitado, ajustar el preset_value que se envía al Wayne
if effective_amount < Decimal(str(body.preset_value or "0")):
    # El monto real despachado será capped al cupo
    body.preset_value = str(effective_amount)
```

> ⚠️ **Atención**: `body` es un objeto Pydantic inmutable. Para modificar
> `preset_value` se debe crear una copia o usar `object.__setattr__`. O mejor,
> pasar el `effective_amount` directamente al construir el objeto `Dispatch`
> y al enviar el PRESET al Wayne.

#### Paso 3.3 — Tests para validación por producto con auto-cap

Crear tests en un archivo nuevo o extender los existentes:

```python
# tests/test_credit_service_product.py

# Test 1: producto con cupo suficiente → devuelve mismo monto
# Test 2: producto con cupo insuficiente → auto-cap al disponible
#     Ej: cupo=$100, pide $150 → devuelve $100
# Test 3: producto no asignado al contrato → error
# Test 4: cupo agotado ($0.00) → error
# Test 5: cupo total suficiente pero cupo por producto insuficiente → auto-cap
# Test 6: contrato NO_INDEFINIDO descuenta todos los despachos
# Test 7: contrato INDEFINIDO solo descuenta PENDING_INVOICE
# Test 8: create_dispatch con monto > cupo → auto-limita y despacha el saldo
```

**Verificación Fase 3**:
```bash
pytest tests/ -v
# Todos los tests existentes + nuevos tests de producto
```

---

### FASE 4 — Backend: endpoint de liquidación / factura global

**Objetivo**: Endpoint que agrupa despachos `PENDING_BULK_INVOICE` en una sola
factura electrónica y la envía a Key49/SRI.

**Archivos**:
- `pos_backend/app/api/dispatches.py` (nuevo endpoint)
- `pos_backend/app/services/key49_service.py` (nueva función)
- `pos_backend/app/schemas/__init__.py` (nuevos schemas)

#### Paso 4.1 — Schemas nuevos

Agregar a `schemas/__init__.py`:

```python
# ── Bulk Invoice / Liquidación Sector Público ──────────────

class BulkInvoiceDispatchItem(BaseModel):
    dispatch_id: int
    order_id: str
    dispatch_date: datetime
    plate: str | None = None
    product_code: str
    product_name: str
    quantity: float
    unit_price: float
    subtotal: float
    tax_amount: float
    total: float

class BulkInvoiceRequest(BaseModel):
    contract_id: int
    emission_point_id: int  # punto de emisión para la factura global

class BulkInvoiceResponse(BaseModel):
    invoice_id: str | None = None  # Key49 invoice UUID
    access_key: str | None = None  # SRI access key
    sri_status: str | None = None
    dispatch_count: int = 0
    total_amount: float = 0.0
    invoiced_dispatch_ids: list[int] = []
    errors: list[str] = []
```

#### Paso 4.2 — Endpoint `POST /api/pos/dispatches/bulk-invoice`

Agregar a `dispatches.py`:

```python
@router.post("/bulk-invoice", response_model=BulkInvoiceResponse)
async def bulk_invoice_contract(
    body: BulkInvoiceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate a single global SRI invoice for all PENDING_BULK_INVOICE
    dispatches of a contract. Used for public sector liquidation.

    Only ADMIN and SUPERVISOR roles can trigger this.
    """
    if current_user.role and current_user.role.code not in ("ADMIN", "SUPERVISOR"):
        raise HTTPException(status_code=403, detail="Solo administradores")

    # 1. Validate contract exists and is NO_INDEFINIDO
    contract = (await db.execute(
        select(CreditContract).where(CreditContract.contract_id == body.contract_id)
    )).scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato no encontrado")
    if contract.contract_type != "NO_INDEFINIDO":
        raise HTTPException(
            status_code=400,
            detail="Solo contratos NO_INDEFINIDO (sector público) requieren liquidación"
        )

    # 2. Find all PENDING_BULK_INVOICE dispatches for this contract
    dispatches = (await db.execute(
        select(Dispatch).where(
            Dispatch.credit_contract_id == body.contract_id,
            Dispatch.credit_status == "PENDING_BULK_INVOICE",
            Dispatch.status == "COLLECTED",
        )
    )).scalars().all()

    if not dispatches:
        raise HTTPException(
            status_code=400,
            detail="No hay despachos pendientes de facturar para este contrato"
        )

    # 3. Consume ONE sequential number for the bulk invoice
    from app.services.sequential_service import consume_sequential
    sequential_number = None
    ep = (await db.execute(
        select(EmissionPoint).where(
            EmissionPoint.emission_point_id == body.emission_point_id,
            EmissionPoint.is_active == True,
        )
    )).scalar_one_or_none()
    if not ep:
        raise HTTPException(status_code=400, detail="Punto de emisión no encontrado")

    try:
        sequential_number = await consume_sequential(db, ep.emission_point_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al consumir secuencial: {e}")

    # 4. Calculate totals from all dispatches
    total_amount = sum(float(d.total or 0) for d in dispatches)

    # 5. Generate SRI access key for the global invoice
    # (Same 49-digit algorithm, using the single sequential)
    from app.services.access_key_service import generate_access_key
    from app.models.company import CompanyInfo
    
    company = (await db.execute(select(CompanyInfo).limit(1))).scalar_one_or_none()
    if not company or not company.ruc:
        raise HTTPException(status_code=400, detail="Empresa no configurada")

    parts = sequential_number.split("-")
    seq_int = int(parts[-1]) if len(parts) >= 3 else int(sequential_number)
    local_date = datetime.now(ECUADOR_TZ).date()
    access_key = generate_access_key(
        emission_date=local_date,
        doc_type=ep.doc_type or "FACTURA",
        ruc=company.ruc,
        sri_environment=company.sri_environment,
        establishment=ep.establishment,
        emission_point=ep.emission_point,
        sequential=seq_int,
        emission_type=company.emission_type or 1,
    )

    # 6. Build and send bulk invoice to Key49
    from app.services.key49_service import emitir_factura_global
    dispatch_ids = [d.dispatch_id for d in dispatches]
    
    result = await emitir_factura_global(
        db, body.contract_id, dispatch_ids,
        access_key, sequential_number, ep, company
    )

    # 7. Update all dispatch statuses to INVOICED
    for d in dispatches:
        d.credit_status = "INVOICED"
    await db.commit()

    return BulkInvoiceResponse(
        invoice_id=result.get("key49_invoice_id"),
        access_key=access_key,
        sri_status=result.get("sri_status"),
        dispatch_count=len(dispatches),
        total_amount=total_amount,
        invoiced_dispatch_ids=dispatch_ids,
        errors=result.get("errors", []),
    )
```

#### Paso 4.3 — Nueva función `emitir_factura_global()` en Key49

Agregar a `key49_service.py`:

```python
async def emitir_factura_global(
    db: AsyncSession,
    contract_id: int,
    dispatch_ids: list[int],
    access_key: str,
    sequential_number: str,
    ep,
    company,
) -> dict:
    """
    Build and send a SINGLE global invoice to Key49 that consolidates
    multiple dispatches into one SRI document.

    Returns dict with key49_invoice_id, sri_status, errors.
    """
    from app.models.credit import CreditContract
    from app.models.dispatch import DispatchDetail
    from app.models.person import Person
    from app.models.product import Product

    # Load dispatches with details
    dispatches = (await db.execute(
        select(Dispatch)
        .where(Dispatch.dispatch_id.in_(dispatch_ids))
        .order_by(Dispatch.created_at)
    )).scalars().all()

    if not dispatches:
        return {"errors": ["No dispatches found"]}

    # Get contract's person (the public entity)
    contract = (await db.execute(
        select(CreditContract).where(CreditContract.contract_id == contract_id)
    )).scalar_one_or_none()
    if not contract:
        return {"errors": ["Contract not found"]}

    person = (await db.execute(
        select(Person).where(Person.person_id == contract.person_id)
    )).scalar_one_or_none()
    if not person:
        return {"errors": ["Person not found"]}

    # Build items: one per dispatch (or group by product)
    items = []
    for d in dispatches:
        detail = (await db.execute(
            select(DispatchDetail).where(
                DispatchDetail.dispatch_id == d.dispatch_id
            )
        )).scalars().first()
        if not detail:
            continue
        
        product = (await db.execute(
            select(Product).where(Product.product_id == detail.product_id)
        )).scalar_one_or_none()
        
        items.append({
            "main_code": product.code if product else "FUEL",
            "description": (
                f"{product.name if product else 'Combustible'} — "
                f"Despacho {d.order_id} del {d.created_at.strftime('%Y-%m-%d')}"
                if d.created_at else f"{product.name if product else 'Combustible'}"
            ),
            "unit_of_measure": product.unit if product and product.unit else "GAL",
            "quantity": float(detail.quantity) if detail.quantity else 1,
            "unit_price": round(float(detail.subtotal) / max(float(detail.quantity), 0.0001), 4),
            "discount": 0.0,
            "taxes": [{
                "code": "2",
                "rate_code": _sri_rate_code(float(detail.tax_rate)),
                "rate": float(detail.tax_rate * 100) if detail.tax_rate else 15.0,
            }],
        })

    if not items:
        return {"errors": ["No items to invoice"]}

    # Parse sequential
    parts = sequential_number.split("-")
    seq_number = parts[-1].zfill(9) if len(parts) >= 3 else sequential_number.zfill(9)

    # Payment: "20" = Otros con utilización del sistema financiero
    payload = {
        "access_key": access_key,
        "establishment": ep.establishment,
        "issue_point": ep.emission_point,
        "sequence_number": seq_number,
        "issue_date": _ecuador_today(),
        "recipient": {
            "id_type": _sri_id_type(person.id_type or "RUC"),
            "id": person.id_number,
            "name": person.name or "ENTIDAD PÚBLICA",
            "address": person.address or "",
            "email": person.email or "",
            "phone": person.phone or "",
        },
        "items": items,
        "payments": [{
            "payment_method": "20",  # Otros con utilización del sistema financiero
            "total": sum(d.total or 0 for d in dispatches),
            "term": 0,
            "time_unit": "days",
        }],
        "additional_info": {
            "contract_code": contract.contract_code,
            "contract_type": "SECTOR_PUBLICO",
            "dispatch_count": str(len(dispatches)),
            "dispatch_ids": ",".join(str(did) for did in dispatch_ids),
        },
    }

    # Send to Key49
    config = await _get_key49_config(db)
    if not config["api_key"]:
        return {"errors": ["Key49 API key not configured"]}

    idempotency_key = f"bulk-{contract_id}-{datetime.now(ECUADOR_TZ).timestamp()}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{config['base_url']}/invoices",
                headers={
                    "Authorization": f"Bearer {config['api_key']}",
                    "Content-Type": "application/json",
                    "X-Idempotency-Key": idempotency_key,
                },
                json=payload,
            )

            if resp.status_code == 202:
                data = resp.json()["data"]
                return {
                    "key49_invoice_id": data["id"],
                    "sri_status": data.get("status", "CREATED"),
                    "errors": [],
                }
            elif resp.status_code == 400:
                err = resp.json()
                return {
                    "sri_status": "FAILED",
                    "errors": [
                        d.get("message", "")
                        for d in err.get("error", {}).get("details", [])
                    ],
                }
            else:
                return {
                    "sri_status": "PENDING",
                    "errors": [f"Key49 HTTP {resp.status_code}"],
                }

    except TERMINAL_OUT_OF_SERVICE:
        return {
            "sri_status": "PENDING",
            "errors": ["Key49 no disponible — se reintentará"],
        }
```

**Verificación Fase 4**:
```bash
pytest tests/ -v
# Nuevos tests específicos del endpoint bulk-invoice
```

---

### FASE 5 — Seed data: contrato de ejemplo sector público

**Objetivo**: Tener datos de prueba para desarrollo y tests.

**Archivo**: `pos_backend/seed_data.py`

Agregar al final del archivo, después del contrato existente:

```python
# ── Contrato Sector Público (ejemplo) ──────────────────────

async def seed_public_sector_contract(db: AsyncSession):
    """Create a sample public sector contract for testing."""
    
    # Check if already exists
    existing = (await db.execute(
        select(CreditContract).where(CreditContract.contract_code == "CT-PUB-001")
    )).scalar_one_or_none()
    if existing:
        return

    # Get a person (or create one)
    person = (await db.execute(
        select(Person).where(Person.id_number == "0160001230001")
    )).scalar_one_or_none()
    
    if not person:
        person = Person(
            id_type="RUC",
            id_number="0160001230001",
            name="MUNICIPIO DE PAUTE",
            address="Av. 24 de Mayo y Simón Bolívar",
            email="compras@paute.gob.ec",
            phone="072-251-000",
        )
        db.add(person)
        await db.flush()

    # Create contract
    contract = CreditContract(
        contract_code="CT-PUB-001",
        person_id=person.person_id,
        contract_date=date.today(),
        cupo=5500.00,
        contract_type="NO_INDEFINIDO",
        sercop_type="ADJUDICACION",
        notes="Contrato de combustible para flota municipal — Sector Público",
    )
    db.add(contract)
    await db.flush()

    # Products
    diesel = (await db.execute(
        select(Product).where(Product.code == "DIESEL")
    )).scalar_one_or_none()
    super_ = (await db.execute(
        select(Product).where(Product.code == "SUPER")
    )).scalar_one_or_none()
    eco = (await db.execute(
        select(Product).where(Product.code == "ECO_PAIS")
    )).scalar_one_or_none()

    if diesel:
        db.add(CreditContractProduct(
            contract_id=contract.contract_id,
            product_id=diesel.product_id,
            amount=2500.00,
        ))
    if super_:
        db.add(CreditContractProduct(
            contract_id=contract.contract_id,
            product_id=super_.product_id,
            amount=3000.00,
        ))
    # Note: ECO_PAIS not included in this contract

    # Vehicles
    vehicles = ["GMC-1234", "GMC-1235", "GMC-1236"]
    for plate in vehicles:
        v = (await db.execute(
            select(Vehicle).where(Vehicle.plate == plate)
        )).scalar_one_or_none()
        if not v:
            v = Vehicle(plate=plate, person_id=person.person_id)
            db.add(v)
            await db.flush()
        
        db.add(CreditContractVehicle(
            contract_id=contract.contract_id,
            vehicle_id=v.vehicle_id,
            date_from=date.today(),
            date_to=date.today() + timedelta(days=365),
        ))

    await db.commit()
    print("✅ Contrato Sector Público creado: CT-PUB-001 (MUNICIPIO DE PAUTE)")
```

Llamar la función en el bloque `if __name__ == "__main__"`:
```python
await seed_public_sector_contract(async_session)
```

**Verificación Fase 5**:
```bash
cd pos_backend
source venv/bin/activate
python seed_data.py
# Debe imprimir: ✅ Contrato Sector Público creado: CT-PUB-001
```

---

### FASE 6 — Frontend Admin: pantalla de liquidación

**Objetivo**: Interfaz para que el administrador vea despachos pendientes y
emita la factura global.

**Archivos**:
- `admin/src/routes/(admin)/contracts/[id]/liquidate/+page.svelte` (nueva página)
- `admin/src/lib/api/admin.ts` (nuevas funciones)

#### Paso 6.1 — Funciones API en el frontend admin

```typescript
// admin/src/lib/api/admin.ts — agregar:

export interface BulkInvoiceDispatchItem {
  dispatch_id: number;
  order_id: string;
  dispatch_date: string;
  plate: string | null;
  product_code: string;
  product_name: string;
  quantity: number;
  unit_price: number;
  subtotal: number;
  tax_amount: number;
  total: number;
}

export interface BulkInvoiceRequest {
  contract_id: number;
  emission_point_id: number;
}

export interface BulkInvoiceResponse {
  invoice_id: string | null;
  access_key: string | null;
  sri_status: string | null;
  dispatch_count: number;
  total_amount: number;
  invoiced_dispatch_ids: number[];
  errors: string[];
}

// Obtener despachos pendientes de facturar para un contrato
export async function getPendingDispatches(
  token: string, contractId: number
): Promise<BulkInvoiceDispatchItem[]> {
  const res = await fetch(
    `${API_BASE}/api/pos/dispatches/pending-bulk?contract_id=${contractId}`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  if (!res.ok) throw new Error('Error al cargar despachos pendientes');
  return res.json();
}

// Emitir factura global
export async function bulkInvoice(
  token: string, body: BulkInvoiceRequest
): Promise<BulkInvoiceResponse> {
  const res = await fetch(
    `${API_BASE}/api/pos/dispatches/bulk-invoice`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    }
  );
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Error al emitir factura global');
  }
  return res.json();
}
```

#### Paso 6.2 — Página de liquidación

La página mostrará:
- Datos del contrato (entidad, monto, productos)
- Barra de progreso del cupo consumido por producto
- Tabla de despachos pendientes de facturar
- Total acumulado
- Botón "Emitir Factura Global"
- Feedback del resultado (factura emitida, clave SRI)

---

### FASE 7 — Frontend POS: adaptar SaleWizard para crédito público

**Objetivo**: El despachador pueda seleccionar modo "Crédito Sector Público"
cuando el vehículo tiene un contrato NO_INDEFINIDO activo.

**Archivos**:
- `pos/src/lib/components/SaleWizard.svelte`
- `pos/src/lib/api/powerfin.ts`
- `pos/src/lib/api/types.ts`

#### Paso 7.1 — Detectar contrato público al buscar placa

Después de `handlePlateSearch()`, cuando `vehicleResult` tenga datos, llamar
a un endpoint para verificar si el vehículo tiene contrato público activo.

El endpoint `GET /api/pos/credit-contracts` ya devuelve vehículos con sus
contratos. Se puede usar o crear uno más ligero.

#### Paso 7.2 — Modo "Crédito Sector Público" en el paso `billing`

Si se detecta contrato público:
- Mostrar banner "🏛️ Sector Público — Contrato CT-XXX-001"
- Mostrar cupo disponible por producto
- NO mostrar selector de método de pago
- NO permitir cambiar a efectivo

#### Paso 7.3 — Paso `presetValue` con validación de cupo

- Si el monto excede el cupo disponible para ESE producto, auto-limitar al saldo
- Mostrar aviso: "Cupo disponible: $100.00 — El monto se ajustó a $100.00"

#### Paso 7.4 — Paso `payment` (cobro) — modo crédito público

- No mostrar input de efectivo
- No mostrar selector de método de pago
- Mostrar resumen del despacho
- Botón: "✅ Confirmar despacho a crédito"
- El `collect_dispatch` se llama con `payment_method_id = CREDITO` y `collected_amount = 0`

---

### FASE 8 — Tests

**Objetivo**: Cobertura completa del nuevo flujo sin romper tests existentes.

#### Tests backend (nuevos)

| Archivo | Tests | Qué prueba |
|---|---|---|
| `tests/test_credit_service_product.py` | 6 | Validación por producto |
| `tests/test_dispatch_public_sector.py` | 12 | Crear, completar, cobrar sin SRI |
| `tests/test_bulk_invoice.py` | 8 | Liquidación / factura global |
| Tests existentes | 387 | Sin modificaciones — deben pasar intactos |

#### Tests específicos

```
Test: create_dispatch con NO_INDEFINIDO → credit_status = PENDING_BULK_INVOICE
Test: create_dispatch con NO_INDEFINIDO → sin sequential_number
Test: create_dispatch con NO_INDEFINIDO → sin access_key
Test: create_dispatch con INDEFINIDO → credit_status = PENDING_INVOICE (sin cambios)
Test: create_dispatch con INDEFINIDO → con sequential_number (sin cambios)
Test: collect_dispatch con PENDING_BULK_INVOICE → no llama Key49
Test: collect_dispatch con PENDING_INVOICE → sí llama Key49 (sin cambios)
Test: cancel_dispatch con credit_contract → limpia credit_status
Test: validate_credit_dispatch producto sin cupo → error
Test: validate_credit_dispatch producto no asignado → error
Test: bulk_invoice endpoint → 200 con despachos
Test: bulk_invoice endpoint → 400 sin despachos
Test: bulk_invoice endpoint → 400 contrato INDEFINIDO
Test: bulk_invoice endpoint → 403 DISPATCHER
Test: retry_pending_invoices ignora PENDING_BULK_INVOICE
Test: emitir_factura ignora PENDING_BULK_INVOICE
```

#### Tests frontend POS

```
Test: SaleWizard detecta contrato público → muestra banner
Test: SaleWizard modo crédito público → no muestra selector efectivo
Test: SaleWizard modo crédito público → validación de cupo
```

---

### FASE 9 — Impresión y Reimpresión para Sector Público

**Objetivo**: El ticket de despacho muestra correctamente "Crédito Sector Público
— Pendiente de facturación" en vez de dejar campos de factura vacíos.

**Contexto**: Hay dos caminos de impresión que deben funcionar:

| Camino | Cuándo | Dónde |
|---|---|---|
| **Impresión al cobrar** | Justo después de `collect_dispatch` | `_build_receipt_data()` → `receiptData` → `doPrint()` |
| **Reimpresión desde Historial** | Días después, desde `/history` | `handleReprint()` construye `fuelData` desde `order` |

Actualmente, para sector público, `invoiceId` e `invoiceAuth` llegarán vacíos
(porque no se generó secuencial ni access_key). El ticket se imprime pero muestra
líneas en blanco donde debería ir la factura. Hay que incluir `creditStatus`
en el payload para que el template de FusionBridge sepa renderizar el mensaje correcto.

**Archivos**:
- `pos_backend/app/api/dispatches.py` (`_build_receipt_data`)
- `pos/src/routes/(pos)/history/+page.svelte` (`handleReprint`)

#### Paso 9.1 — Backend: agregar `creditStatus` al receipt

En `_build_receipt_data()`, agregar tres campos al `fuelData`:

```python
# En _build_receipt_data(), dentro del dict fuelData:

"creditStatus": dispatch.credit_status or "",
"creditContractId": dispatch.credit_contract_id or 0,
"isBulkInvoice": dispatch.credit_status == "PENDING_BULK_INVOICE",
```

**Ubicación**: Justo después de `"cashierName": cashier_name,` (última línea de fuelData).

Campos completos del receipt modificado:

```python
"fuelData": {
    # ... todos los campos existentes igual ...
    "cashierName": cashier_name,
    # ─── NUEVOS ───
    "creditStatus": dispatch.credit_status or "",
    "creditContractId": dispatch.credit_contract_id or 0,
    "isBulkInvoice": dispatch.credit_status == "PENDING_BULK_INVOICE",
},
```

#### Paso 9.2 — Frontend POS: pasar `creditStatus` en el fallback de impresión

En `SaleWizard.svelte`, función `doPrint()`, en la rama `else` (fallback sin receiptData),
agregar estos campos al `fuelData`:

```typescript
// En doPrint(), dentro del else { ... fuelData: { ... } }

creditStatus: collectOrder?.creditStatus ?? '',
creditContractId: collectOrder?.creditContractId ?? 0,
isBulkInvoice: collectOrder?.creditStatus === 'PENDING_BULK_INVOICE',
```

#### Paso 9.3 — Frontend History: agregar `creditStatus` en reimpresión

En `history/+page.svelte`, función `handleReprint()`, dentro del `fuelData`:

```typescript
// En handleReprint(), dentro del fuelData:

creditStatus: order.credit_status ?? '',
creditContractId: order.credit_contract_id ?? 0,
isBulkInvoice: order.credit_status === 'PENDING_BULK_INVOICE',
```

> **Nota**: El endpoint `get_active_dispatches` YA devuelve `credit_status` y
> `credit_contract_id` en el response. Solo hay que usarlos en `handleReprint`.

#### Paso 9.4 — Backend: asegurar que el objeto `order` incluya `credit_status`

Verificar que el endpoint de historial (usado para reimpresión) incluya `credit_status`
y `credit_contract_id` en cada objeto de despacho. `get_active_dispatches` ya lo hace.
Para despachos COLLECTED (historial de turnos cerrados), revisar si el endpoint de
historial también incluye estos campos.

```bash
# Verificar:
grep -n "credit" pos_backend/app/api/shifts.py
```

#### Paso 9.5 — FusionBridge: template de ticket (documentación)

> ⚠️ **Este paso es en el lado FusionBridge (Java)**. No se implementa ahora.
> Se deja documentado para referencia.

El template de `FUEL_RECEIPT` en FusionBridge debe manejar los nuevos campos:

```
Si isBulkInvoice == true:
  → Mostrar: "🏛️ CRÉDITO SECTOR PÚBLICO"
  → Mostrar: "Pendiente de facturación"
  → NO mostrar: Factura N° ____, Clave SRI ____

Si creditStatus == "PENDING_INVOICE":
  → Mostrar: "💳 CRÉDITO — Pendiente de facturación"
  → NO mostrar: Factura N° ____, Clave SRI ____

Si creditStatus == "" o null (venta normal):
  → Mostrar: Factura N° + Clave SRI (comportamiento actual)
```

Mientras FusionBridge no tenga este template, el ticket se imprimirá con los
campos de factura vacíos pero **sin errores**. El `paymentMethod` mostrará
"CREDITO" y los montos serán correctos.

#### Verificación Fase 9

```bash
# Backend: _build_receipt_data incluye los nuevos campos
pytest tests/ -k "dispatch" -v

# Frontend: svelte-check no debe reportar nuevos errores
cd pos && npm run check

# Prueba manual: hacer un despacho público, verificar ticket
# - invoiceId debe ser "" (vacío)
# - creditStatus debe ser "PENDING_BULK_INVOICE"
# - isBulkInvoice debe ser true
```

---

## 🔄 Orden de ejecución

```
Fase 1 ─► Modelo + Migración          (30 min)   ← Sin riesgo, base de todo
Fase 2 ─► Bloquear SRI                (45 min)   ← Core del cambio
Fase 3 ─► Validación por producto     (45 min)   ← Mejora de negocio
Fase 4 ─► Endpoint liquidación        (90 min)   ← Factura global
Fase 5 ─► Seed data                   (20 min)   ← Datos de prueba
Fase 6 ─► Admin liquidación           (90 min)   ← UI administrador
Fase 7 ─► POS SaleWizard              (90 min)   ← UI despachador
Fase 8 ─► Tests                       (60 min)   ← Cobertura
Fase 9 ─► Impresión + Reimpresión     (30 min)   ← Tickets correctos
                            ─────
                     Total: ~8.5 horas
```

---

## ✅ Checklist de verificación final

```
[ ] Fase 1: migration aplicada sin errores
[ ] Fase 1: 387 tests backend intactos
[ ] Fase 2: create_dispatch NO_INDEFINIDO → sin secuencial, sin access_key
[ ] Fase 2: collect_dispatch PENDING_BULK_INVOICE → sin Key49
[ ] Fase 2: create_dispatch INDEFINIDO → comportamiento sin cambios
[ ] Fase 2: create_dispatch SALE → comportamiento sin cambios
[ ] Fase 3: monto > cupo → auto-limita al saldo disponible (no rechaza)
[ ] Fase 3: cupo = $0.00 → error "Cupo agotado"
[ ] Fase 3: producto sin asignar → error claro
[ ] Fase 4: bulk-invoice genera factura global
[ ] Fase 4: bulk-invoice cambia todos a INVOICED
[ ] Fase 5: seed data CT-PUB-001 creado
[ ] Fase 6: admin muestra despachos pendientes
[ ] Fase 6: admin emite factura global
[ ] Fase 7: POS muestra banner sector público
[ ] Fase 7: POS no pide efectivo en crédito público
[ ] Fase 7: flujo normal de venta 100% intacto
[ ] Fase 8: todos los tests pasan (387 + nuevos)
[ ] Fase 8: svelte-check 0 errores
[ ] Fase 8: npm run build OK
[ ] Fase 9: receipt incluye creditStatus, isBulkInvoice
[ ] Fase 9: reimpresión desde historial incluye creditStatus
[ ] Fase 9: ticket no muestra campos de factura vacíos
[ ] Fase 9: ticket muestra "Pendiente de facturación" (tras update FusionBridge)
[ ] Deploy a producción sin downtime
[ ] Prueba E2E: venta sector público completa
[ ] Prueba E2E: liquidación de contrato
[ ] Prueba E2E: reimpresión de ticket sector público
```

---

## ⚠️ Notas importantes

1. **El flujo de venta normal NO se toca.** Cada cambio está condicionado a
   `credit_status == "PENDING_BULK_INVOICE"` o `contract_type == "NO_INDEFINIDO"`.

2. **El crédito privado (INDEFINIDO) sigue igual**, excepto si corregimos la
   validación por producto (Fase 3). Es una mejora, no un breaking change.

3. **La migración es solo un ALTER CHECK constraint** — zero downtime.

4. **La liquidación requiere rol ADMIN o SUPERVISOR** — el despachador no puede
   emitir facturas globales.

5. **Si Key49 no está disponible al liquidar**, el endpoint devuelve error y
   los despachos NO cambian a INVOICED. Se puede reintentar.

6. **El endpoint `/pending-bulk`** (Fase 4) es opcional si la página de admin
   carga los datos desde el endpoint de contratos existente.

7. **Impresión**: los tickets de sector público se imprimen normalmente.
   Muestran "CREDITO" como método de pago y los montos correctos. El template
   de FusionBridge necesitará una actualización menor para mostrar
   "Pendiente de facturación" en vez de dejar campos vacíos.

8. **Reimpresión**: funciona igual que una venta normal. El endpoint de historial
   ya devuelve `credit_status` y `credit_contract_id`, solo hay que usarlos
   en el frontend al construir el payload de impresión.

---

## 📁 Archivos del plan

| Fase | Archivo | Tipo |
|:----:|---------|:----:|
| 1 | `pos_backend/app/models/dispatch.py` | Modificar |
| 1 | `pos_backend/alembic/versions/xxx.py` | Nuevo (auto) |
| 2 | `pos_backend/app/api/dispatches.py` | Modificar |
| 2 | `pos_backend/app/services/key49_service.py` | Modificar |
| 3 | `pos_backend/app/services/credit_service.py` | Modificar |
| 3 | `pos_backend/tests/test_credit_service_product.py` | Nuevo |
| 4 | `pos_backend/app/api/dispatches.py` | Modificar |
| 4 | `pos_backend/app/services/key49_service.py` | Modificar |
| 4 | `pos_backend/app/schemas/__init__.py` | Modificar |
| 4 | `pos_backend/tests/test_bulk_invoice.py` | Nuevo |
| 5 | `pos_backend/seed_data.py` | Modificar |
| 6 | `admin/src/routes/(admin)/contracts/[id]/liquidate/+page.svelte` | Nuevo |
| 6 | `admin/src/lib/api/admin.ts` | Modificar |
| 7 | `pos/src/lib/components/SaleWizard.svelte` | Modificar |
| 7 | `pos/src/lib/api/powerfin.ts` | Modificar |
| 7 | `pos/src/lib/api/types.ts` | Modificar |
| 8 | `pos_backend/tests/` | Nuevos + verificar |
| 8 | `pos/tests/` | Nuevos + verificar |
| 9 | `pos_backend/app/api/dispatches.py` (`_build_receipt_data`) | Modificar |
| 9 | `pos/src/lib/components/SaleWizard.svelte` (`doPrint`) | Modificar |
| 9 | `pos/src/routes/(pos)/history/+page.svelte` (`handleReprint`) | Modificar |
| 9 | `pos_backend/app/api/shifts.py` | Verificar (historial) |
