from fastapi import APIRouter

from .orders import router as orders_router
from .payments import router as payments_router

api_router = APIRouter(prefix="/api")
api_router.include_router(orders_router, prefix="/orders", tags=["orders"])
api_router.include_router(payments_router, prefix="/payments", tags=["payments"])
