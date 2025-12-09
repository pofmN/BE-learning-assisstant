"""API v1 router."""
from fastapi import APIRouter

from app.api.v1 import auth, document, course

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(document.router, prefix="/document", tags=["Document Processing"])
api_router.include_router(course.router, prefix="/course", tags=["Course Management"])