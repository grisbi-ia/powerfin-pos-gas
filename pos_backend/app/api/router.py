"""Main API router — includes all sub-routers."""

from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.cash import router as cash_router
from app.api.config import router as config_router
from app.api.credit_contracts import router as credit_router
from app.api.customers import router as customers_router
from app.api.dispatches import router as dispatch_router
from app.api.identity import router as identity_router
from app.api.persons import router as persons_router
from app.api.prices import router as prices_router
from app.api.products import router as products_router
from app.api.shifts import router as shifts_router
from app.api.vehicles import router as vehicles_router

from app.api.admin.auth import router as admin_auth_router
from app.api.admin.company import router as admin_company_router
from app.api.admin.dispensers import router as admin_dispensers_router
from app.api.admin.emission_points import router as admin_emission_points_router
from app.api.admin.grades import router as admin_grades_router
from app.api.admin.payment_methods import router as admin_payment_methods_router
from app.api.admin.price_lists import router as admin_price_lists_router
from app.api.admin.products import router as admin_products_router
from app.api.admin.roles import router as admin_roles_router
from app.api.admin.system_config import router as admin_system_config_router
from app.api.admin.users import router as admin_users_router

router = APIRouter()

router.include_router(auth_router)
router.include_router(config_router)
router.include_router(vehicles_router)
router.include_router(customers_router)
router.include_router(persons_router)
router.include_router(prices_router)
router.include_router(shifts_router)
router.include_router(dispatch_router)
router.include_router(identity_router)
router.include_router(cash_router)
router.include_router(credit_router)
router.include_router(products_router)
router.include_router(admin_auth_router)
router.include_router(admin_company_router)
router.include_router(admin_dispensers_router)
router.include_router(admin_emission_points_router)
router.include_router(admin_grades_router)
router.include_router(admin_payment_methods_router)
router.include_router(admin_price_lists_router)
router.include_router(admin_products_router)
router.include_router(admin_roles_router)
router.include_router(admin_system_config_router)
router.include_router(admin_users_router)
