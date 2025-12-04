"""API v1 router."""
from fastapi import APIRouter

from app.api.v1 import auth, tests, document

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(document.router, prefix="/document", tags=["Document Processing"])
api_router.include_router(tests.router, prefix="/tests", tags=["Knowledge Testing"])
