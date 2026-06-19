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
router.include_router(admin_users_router)
