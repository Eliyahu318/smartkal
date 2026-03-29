from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.category import router as category_router
from app.api.v1.list import router as list_router
from app.api.v1.price import router as price_router
from app.api.v1.receipt import router as receipt_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth_router)
api_v1_router.include_router(category_router)
api_v1_router.include_router(list_router)
api_v1_router.include_router(price_router)
api_v1_router.include_router(receipt_router)
