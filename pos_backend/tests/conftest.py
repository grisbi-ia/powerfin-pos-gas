"""Pytest configuration — shared fixtures for unit and integration tests."""

import asyncio
from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import *  # noqa: F401,F403
from app.services.auth_service import create_access_token, hash_pin

TEST_DB_URL = settings.database_url.replace(
    settings.database_name, f"{settings.database_name}_test"
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def engine():
    """Single engine with NullPool for test isolation."""
    return create_async_engine(TEST_DB_URL, echo=False, poolclass=NullPool)


@pytest_asyncio.fixture(autouse=True, scope="session")
async def setup_db(engine):
    """Create tables once before all tests, drop once after."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db(engine) -> AsyncSession:
    """Fresh session with seed data for each test."""
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with Session() as session:
        await _seed_data(session)
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db: AsyncSession):
    """HTTP test client wired to the real app."""
    async def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
def auth_headers(db):
    token = create_access_token(2, "carlos")
    return {"Authorization": f"Bearer {token}"}


async def _seed_data(db: AsyncSession):
    """Insert minimal seed data."""
    from app.models.company import CompanyInfo, SystemConfig
    from app.models.credit import CreditContract, CreditContractProduct, CreditContractVehicle
    from app.models.dispatch import DispatchType
    from app.models.dispenser import Dispenser, Hose
    from app.models.payment import PaymentMethod
    from app.models.person import Person, Vehicle
    from app.models.pricing import PriceList, PriceListItem
    from app.models.product import Grade, Product, ProductCategory, TaxType
    from app.models.tributary import EmissionPoint
    from app.models.user import Role, User

    db.add(CompanyInfo(ruc="1790012345001", name="TEST GAS", commercial_name="TEST"))
    db.add(SystemConfig(key="accounting_branch_code", value="001"))
    db.add(SystemConfig(key="default_currency", value="USD"))
    db.add(SystemConfig(key="key49_api_key", value="k49_test_00000000000000000000"))
    db.add(SystemConfig(key="key49_base_url", value="https://key49.apx5.com/v1"))
    db.add(SystemConfig(key="key49_sandbox", value="true"))
    db.add(SystemConfig(key="key49_enabled", value="true"))

    admin_role = Role(code="ADMIN", name="Admin")
    disp_role = Role(code="DISPATCHER", name="Despachador")
    db.add_all([admin_role, disp_role])
    await db.flush()

    db.add_all([
        User(user_id=1, username="admin", pin_hash=hash_pin("1234"), name="Admin", role_id=admin_role.role_id),
        User(user_id=2, username="carlos", pin_hash=hash_pin("1234"), name="Carlos Sarmiento", role_id=disp_role.role_id, accounting_cash_code="CAJA-01"),
    ])

    db.add(TaxType(code="IVA_15", name="IVA 15%", rate=0.1500))
    db.add(TaxType(code="IVA_0", name="IVA 0%", rate=0.0))
    await db.flush()

    fuel_cat = ProductCategory(category_id=1, code="FUEL", name="Combustibles", is_fuel=True)
    oil_cat = ProductCategory(category_id=2, code="OIL", name="Aceites", is_fuel=False)
    db.add_all([fuel_cat, oil_cat])
    await db.flush()

    db.add_all([
        Product(product_id=1, code="DIESEL", name="Diesel", category_id=1, unit="GAL", base_price=3.103, tax_type_id=1),
        Product(product_id=2, code="SUPER", name="Super", category_id=1, unit="GAL", base_price=4.500, tax_type_id=1),
        Product(product_id=3, code="ACEITE", name="Aceite 20W50", category_id=2, unit="UNIDAD", base_price=15.00, tax_type_id=1),
    ])
    await db.flush()

    db.add(Grade(grade_id=1, code="DIESEL", name="Diesel", product_id=1))
    db.add(Grade(grade_id=2, code="SUPER", name="Super", product_id=2))

    std = PriceList(price_list_id=1, code="STANDARD", name="Precio Normal", is_default=True)
    vip = PriceList(price_list_id=2, code="VIP", name="VIP", is_default=False)
    db.add_all([std, vip])
    await db.flush()

    db.add_all([
        PriceListItem(price_list_id=1, product_id=1, unit_price=3.103),
        PriceListItem(price_list_id=1, product_id=2, unit_price=4.500),
        PriceListItem(price_list_id=2, product_id=1, unit_price=2.950),
        PriceListItem(price_list_id=2, product_id=2, unit_price=4.250),
    ])

    db.add_all([
        Person(person_id=1, id_type="CED", id_number="0912345678", name="Juan Carlos Pérez", price_list_id=2),
        Person(person_id=2, id_type="RUC", id_number="1790012345001", name="Transportes Andinos S.A.", price_list_id=1),
    ])

    db.add(Vehicle(vehicle_id=1, plate="ABC1234", person_id=1, price_list_id=2))
    db.add(Vehicle(vehicle_id=2, plate="XYZ5678", person_id=2, price_list_id=1))

    db.add_all([
        PaymentMethod(payment_method_id=1, code="EFECTIVO", name="Efectivo", sri_code="01", requires_reference=False),
        PaymentMethod(payment_method_id=2, code="TARJETA", name="Tarjeta", sri_code="19", requires_reference=True),
        PaymentMethod(payment_method_id=3, code="CREDITO", name="Crédito", sri_code="20", requires_reference=False),
        PaymentMethod(payment_method_id=4, code="YALOBOX", name="Yalobox", sri_code="20", requires_reference=False),
    ])

    db.add(EmissionPoint(
        emission_point_id=1, establishment="001", emission_point="001",
        current_sequential=1, sequential_start=1, sequential_end=9999,
    ))
    await db.flush()

    d1 = Dispenser(dispenser_id=1, emission_point_id=1, code="SURT-01", name="Surtidor DIESEL", printer_ip="192.168.1.31")
    db.add(d1)
    await db.flush()

    db.add_all([
        Hose(hose_id=1, dispenser_id=1, side="A", fusion_pump_id=1, fusion_hose_id=1, grade_id="DIESEL"),
        Hose(hose_id=2, dispenser_id=1, side="B", fusion_pump_id=2, fusion_hose_id=1, grade_id="DIESEL"),
    ])

    db.add_all([
        DispatchType(dispatch_type_id=1, code="SALE", name="Venta Normal", requires_customer=True, affects_cash=True),
        DispatchType(dispatch_type_id=2, code="CREDIT", name="Venta a Crédito", requires_customer=True, affects_cash=False),
        DispatchType(dispatch_type_id=3, code="CALIBRATION", name="Calibración", requires_customer=False, affects_cash=False),
        DispatchType(dispatch_type_id=4, code="TEST", name="Prueba", requires_customer=False, affects_cash=False),
    ])

    contract = CreditContract(
        contract_id=1, contract_code="CT-001", person_id=2,
        contract_date=date.today(), cupo=Decimal("5000.00"),
        contract_type="INDEFINIDO", sercop_type="NO_DEFINIDO",
    )
    db.add(contract)
    await db.flush()

    db.add(CreditContractVehicle(contract_vehicle_id=1, contract_id=1, vehicle_id=2, date_from=date(2026, 1, 1)))
    db.add(CreditContractProduct(contract_product_id=1, contract_id=1, product_id=1, amount=Decimal("3000.00")))

    await db.commit()

    await db.execute(sa_text("SELECT setval('persons_person_id_seq', (SELECT MAX(person_id) FROM persons))"))
    await db.execute(sa_text("SELECT setval('users_user_id_seq', (SELECT MAX(user_id) FROM users))"))
    await db.execute(sa_text("SELECT setval('vehicles_vehicle_id_seq', (SELECT MAX(vehicle_id) FROM vehicles))"))
    await db.execute(sa_text("SELECT setval('emission_points_emission_point_id_seq', (SELECT MAX(emission_point_id) FROM emission_points))"))
    await db.execute(sa_text("SELECT setval('credit_contracts_contract_id_seq', (SELECT MAX(contract_id) FROM credit_contracts))"))
    await db.execute(sa_text("SELECT setval('roles_role_id_seq', (SELECT MAX(role_id) FROM roles))"))
    await db.execute(sa_text("SELECT setval('product_categories_category_id_seq', (SELECT MAX(category_id) FROM product_categories))"))
    await db.execute(sa_text("SELECT setval('tax_types_tax_type_id_seq', (SELECT MAX(tax_type_id) FROM tax_types))"))
    await db.execute(sa_text("SELECT setval('products_product_id_seq', (SELECT MAX(product_id) FROM products))"))
    await db.execute(sa_text("SELECT setval('grades_grade_id_seq', (SELECT MAX(grade_id) FROM grades))"))
    await db.execute(sa_text("SELECT setval('price_lists_price_list_id_seq', (SELECT MAX(price_list_id) FROM price_lists))"))
    await db.execute(sa_text("SELECT setval('payment_methods_payment_method_id_seq', (SELECT MAX(payment_method_id) FROM payment_methods))"))
    await db.execute(sa_text("SELECT setval('dispensers_dispenser_id_seq', (SELECT MAX(dispenser_id) FROM dispensers))"))
    await db.execute(sa_text("SELECT setval('hoses_hose_id_seq', (SELECT MAX(hose_id) FROM hoses))"))
    await db.execute(sa_text("SELECT setval('dispatch_types_dispatch_type_id_seq', (SELECT MAX(dispatch_type_id) FROM dispatch_types))"))
    await db.commit()
