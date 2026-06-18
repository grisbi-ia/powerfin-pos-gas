"""Seed data for development — populates all reference tables."""

import asyncio
from datetime import date

from sqlalchemy import select, text

from app.config import settings
from app.database import async_session, engine, Base
from app.models import (
    CompanyInfo,
    CreditContract,
    CreditContractProduct,
    CreditContractVehicle,
    DispatchType,
    Dispenser,
    EmissionPoint,
    Grade,
    Hose,
    PaymentMethod,
    Person,
    PriceList,
    PriceListItem,
    Product,
    ProductCategory,
    Role,
    SystemConfig,
    TaxType,
    User,
    Vehicle,
)


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        # ── System config ──
        configs = [
            SystemConfig(key="accounting_branch_code", value="001", description="Código de sucursal contable"),
            SystemConfig(key="default_currency", value="USD", description="Moneda por defecto"),
            SystemConfig(key="invoice_footer_message", value="Gracias por su compra", description="Mensaje pie de factura"),
        ]
        db.add_all(configs)

        # ── Company ──
        company = CompanyInfo(
            ruc="1790012345001",
            name="NEOGAS S.A.",
            commercial_name="NEOGAS",
            address="Av. Principal 123, Cuenca",
            phone="072345678",
            email="info@neogas.com",
        )
        db.add(company)

        # ── Roles ──
        roles = [
            Role(code="ADMIN", name="Administrador", permissions_json={"all": True}),
            Role(code="SUPERVISOR", name="Supervisor", permissions_json={"sales": True, "reports": True, "close_shift": True}),
            Role(code="DISPATCHER", name="Despachador", permissions_json={"sales": True, "close_shift": True}),
        ]
        db.add_all(roles)
        await db.flush()

        # ── Users ──
        import bcrypt
        pin_hash = bcrypt.hashpw(b"1234", bcrypt.gensalt()).decode()
        users = [
            User(username="admin", pin_hash=pin_hash, name="Administrador", role_id=1, accounting_cash_code="CAJA-001"),
            User(username="carlos", pin_hash=pin_hash, name="Carlos Sarmiento", role_id=3, accounting_cash_code="CAJA-01-001"),
            User(username="maria", pin_hash=pin_hash, name="María Fernanda López", role_id=3, accounting_cash_code="CAJA-01-002"),
            User(username="pedro", pin_hash=pin_hash, name="Pedro Ramírez", role_id=3, accounting_cash_code="CAJA-01-003"),
        ]
        db.add_all(users)
        await db.flush()

        # ── Tax types ──
        taxes = [
            TaxType(code="IVA_12", name="IVA 12%", rate=0.12),
            TaxType(code="IVA_0", name="IVA 0%", rate=0.0),
            TaxType(code="ICE", name="ICE", rate=0.0),
        ]
        db.add_all(taxes)
        await db.flush()

        # ── Product categories ──
        categories = [
            ProductCategory(code="FUEL", name="Combustibles", is_fuel=True),
            ProductCategory(code="OIL", name="Aceites y Lubricantes", is_fuel=False),
            ProductCategory(code="ADDITIVE", name="Aditivos", is_fuel=False),
            ProductCategory(code="AMBIENTAL", name="Ambientales", is_fuel=False),
        ]
        db.add_all(categories)
        await db.flush()

        # ── Products ──
        products = [
            Product(code="DIESEL", name="Diesel", category_id=1, unit="GAL", base_price=3.103, tax_type_id=1, is_active=True),
            Product(code="SUPER", name="Gasolina Super", category_id=1, unit="GAL", base_price=4.500, tax_type_id=1, is_active=True),
            Product(code="ECO_PAIS", name="Eco País", category_id=1, unit="GAL", base_price=2.900, tax_type_id=1, is_active=True),
            Product(code="ACEITE_20W50", name="Aceite 20W50", category_id=2, unit="UNIDAD", base_price=15.00, tax_type_id=1, is_active=True),
            Product(code="ADITIVO_MOTOR", name="Aditivo Motor", category_id=3, unit="UNIDAD", base_price=8.00, tax_type_id=1, is_active=True),
            Product(code="AMBIENTAL_PINO", name="Ambiental Pino", category_id=4, unit="UNIDAD", base_price=3.00, tax_type_id=1, is_active=True),
        ]
        db.add_all(products)
        await db.flush()

        # ── Grades ──
        grades = [
            Grade(code="DIESEL", name="Diesel", product_id=1),
            Grade(code="SUPER", name="Gasolina Super", product_id=2),
            Grade(code="ECO_PAIS", name="Eco País", product_id=3),
        ]
        db.add_all(grades)

        # ── Price lists ──
        price_lists = [
            PriceList(code="STANDARD", name="Precio Normal", is_default=True),
            PriceList(code="VIP", name="Cliente VIP", is_default=False),
            PriceList(code="EMPLOYEE", name="Empleados", is_default=False),
            PriceList(code="FAMILY", name="Familia", is_default=False),
        ]
        db.add_all(price_lists)
        await db.flush()

        # ── Price list items ──
        pl_items = [
            PriceListItem(price_list_id=1, product_id=1, unit_price=3.103),
            PriceListItem(price_list_id=1, product_id=2, unit_price=4.500),
            PriceListItem(price_list_id=1, product_id=3, unit_price=2.900),
            PriceListItem(price_list_id=1, product_id=4, unit_price=15.00),
            PriceListItem(price_list_id=1, product_id=5, unit_price=8.00),
            PriceListItem(price_list_id=1, product_id=6, unit_price=3.00),
            PriceListItem(price_list_id=2, product_id=1, unit_price=2.950),
            PriceListItem(price_list_id=2, product_id=2, unit_price=4.250),
            PriceListItem(price_list_id=3, product_id=1, unit_price=2.800),
            PriceListItem(price_list_id=4, product_id=1, unit_price=2.900),
        ]
        db.add_all(pl_items)

        # ── Persons ──
        persons = [
            Person(id_type="CED", id_number="0912345678", name="Juan Carlos Pérez",
                   email="jperez@email.com", phone="0991234567", price_list_id=2),
            Person(id_type="RUC", id_number="1790012345001", name="Transportes Andinos S.A.",
                   email="trans@andinos.com", phone="022345678", price_list_id=1),
            Person(id_type="RUC", id_number="1001234567001", name="María Fernanda López",
                   email="mflopez@email.com", phone="0987654321", price_list_id=1),
        ]
        db.add_all(persons)
        await db.flush()

        # ── Vehicles ──
        vehicles = [
            Vehicle(plate="ABC1234", person_id=1, price_list_id=2),
            Vehicle(plate="XYZ5678", person_id=2, price_list_id=1),
            Vehicle(plate="XYZ5679", person_id=2, price_list_id=1),
        ]
        db.add_all(vehicles)

        # ── Payment methods ──
        methods = [
            PaymentMethod(code="EFECTIVO", name="Efectivo", sri_code="01", requires_reference=False),
            PaymentMethod(code="TARJETA", name="Tarjeta Crédito/Débito", sri_code="19", requires_reference=True),
            PaymentMethod(code="QR", name="QR / Transferencia", sri_code="20", requires_reference=False),
            PaymentMethod(code="CREDITO", name="Crédito", sri_code="20", requires_reference=False),
            PaymentMethod(code="DEUNA", name="DeUna", sri_code="20", requires_reference=True),
            PaymentMethod(code="JEPFAST", name="JepFast", sri_code="20", requires_reference=True),
            PaymentMethod(code="SIPY", name="Sipy", sri_code="20", requires_reference=True),
            PaymentMethod(code="YALOBOX", name="Yalobox", sri_code="20", requires_reference=False),
        ]
        db.add_all(methods)
        await db.flush()

        # ── Emission points ──
        ep = EmissionPoint(
            establishment="001", emission_point="001",
            current_sequential=1, sequential_start=1, sequential_end=999999999,
            doc_type="FACTURA", authorization_number="1234567890",
            authorization_date=date.today(), authorization_expiry=date(2027, 12, 31),
        )
        db.add(ep)
        await db.flush()

        # ── Dispensers ──
        # 4 physical dispensers → 8 logical pumps in Synergy
        # Each physical dispenser = 2 sides (A/B) = 2 logical pumps
        # fusion_pump_id is now on hoses, not dispensers
        d1 = Dispenser(
            emission_point_id=1, code="SURT-01", name="Surtidor GASOLINA",
            printer_ip="192.168.1.31", printer_port=9100, sort_order=1,
        )
        d2 = Dispenser(
            emission_point_id=1, code="SURT-02", name="Surtidor EXTRA-ECO",
            printer_ip=None, printer_port=9100, sort_order=2,
        )
        d3 = Dispenser(
            emission_point_id=1, code="SURT-03", name="Surtidor DIESEL 1",
            printer_ip=None, printer_port=9100, sort_order=3,
        )
        d4 = Dispenser(
            emission_point_id=1, code="SURT-04", name="Surtidor DIESEL 2",
            printer_ip=None, printer_port=9100, sort_order=4,
        )
        db.add_all([d1, d2, d3, d4])
        await db.flush()

        # ── Hoses ──
        # Validated by physical test (2026-06-04):
        #   Lifting ECO_PAIS nozzle → Synergy reports hose=2
        #   Therefore: hose 1 = SUPER, hose 2 = ECO_PAIS
        #   Synergy config labels (P001H1GRADE=2 EXTRA-ECO, P001H2GRADE=1 SUPER)
        #   do NOT match physical nozzle positions.
        hoses = [
            # SURT-01 side A (pump 1): hose 1 = SUPER, hose 2 = ECO_PAIS
            Hose(dispenser_id=1, side="A", fusion_pump_id=1, fusion_hose_id=1, grade_id="SUPER"),
            Hose(dispenser_id=1, side="A", fusion_pump_id=1, fusion_hose_id=2, grade_id="ECO_PAIS"),
            # SURT-01 side B (pump 2): hose 1 = SUPER, hose 2 = ECO_PAIS
            Hose(dispenser_id=1, side="B", fusion_pump_id=2, fusion_hose_id=1, grade_id="SUPER"),
            Hose(dispenser_id=1, side="B", fusion_pump_id=2, fusion_hose_id=2, grade_id="ECO_PAIS"),
            # SURT-02: mono-producto (CLOSED)
            Hose(dispenser_id=2, side="A", fusion_pump_id=3, fusion_hose_id=1, grade_id="ECO_PAIS"),
            Hose(dispenser_id=2, side="B", fusion_pump_id=4, fusion_hose_id=1, grade_id="ECO_PAIS"),
            # SURT-03: mono-producto DIESEL (CLOSED)
            Hose(dispenser_id=3, side="A", fusion_pump_id=5, fusion_hose_id=1, grade_id="DIESEL"),
            Hose(dispenser_id=3, side="B", fusion_pump_id=6, fusion_hose_id=1, grade_id="DIESEL"),
            # SURT-04: mono-producto DIESEL (CLOSED)
            Hose(dispenser_id=4, side="A", fusion_pump_id=7, fusion_hose_id=1, grade_id="DIESEL"),
            Hose(dispenser_id=4, side="B", fusion_pump_id=8, fusion_hose_id=1, grade_id="DIESEL"),
        ]
        db.add_all(hoses)

        # ── Dispatch types ──
        dtypes = [
            DispatchType(code="SALE", name="Venta Normal", requires_customer=True, affects_cash=True),
            DispatchType(code="CREDIT", name="Venta a Crédito", requires_customer=True, affects_cash=False),
            DispatchType(code="CALIBRATION", name="Calibración", requires_customer=False, affects_cash=False),
            DispatchType(code="TEST", name="Prueba", requires_customer=False, affects_cash=False),
        ]
        db.add_all(dtypes)

        # ── Credit contract (example) ──
        contract = CreditContract(
            contract_code="CT-2026-001",
            person_id=2,
            contract_date=date.today(),
            cupo=5000.00,
            contract_type="INDEFINIDO",
            sercop_type="NO_DEFINIDO",
            notes="Contrato de prueba",
        )
        db.add(contract)
        await db.flush()

        ccv = [
            CreditContractVehicle(contract_id=1, vehicle_id=2, date_from=date(2026, 1, 1), date_to=None),
            CreditContractVehicle(contract_id=1, vehicle_id=3, date_from=date(2026, 1, 1), date_to=None),
        ]
        db.add_all(ccv)

        ccp = [
            CreditContractProduct(contract_id=1, product_id=1, amount=3000.00),
            CreditContractProduct(contract_id=1, product_id=2, amount=2000.00),
        ]
        db.add_all(ccp)

        await db.commit()

    print("✅ Seed data inserted successfully!")
    print(f"   Users: admin/1234, carlos/1234, maria/1234, pedro/1234")
    print(f"   Contract: CT-2026-001 (INDEFINIDO, $5,000 cupo)")
    print(f"   Dispensers (4 físicos, 8 pumps lógicos, 10 hoses):")
    print(f"     SURT-01 (pumps 1+2): GASOLINA bi-producto  🟢 IDLE")
    print(f"     SURT-02 (pumps 3+4): EXTRA-ECO mono-prod  ⚫ CLOSED")
    print(f"     SURT-03 (pumps 5+6): DIESEL mono-prod     ⚫ CLOSED")
    print(f"     SURT-04 (pumps 7+8): DIESEL mono-prod     ⚫ CLOSED")


if __name__ == "__main__":
    asyncio.run(seed())
