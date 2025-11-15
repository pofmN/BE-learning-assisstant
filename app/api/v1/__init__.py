"""API v1 router."""
from fastapi import APIRouter

from app.api.v1 import auth, documents, mcqs, tests, learning, chat

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
api_router.include_router(mcqs.router, prefix="/mcqs", tags=["MCQ Generation"])
api_router.include_router(tests.router, prefix="/tests", tags=["Knowledge Testing"])
api_router.include_router(learning.router, prefix="/learning", tags=["Personalized Learning"])
api_router.include_router(chat.router, prefix="/chat", tags=["Virtual Teacher"])
