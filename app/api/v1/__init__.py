"""API v1 router."""
from fastapi import APIRouter

from app.api.v1 import auth, document, course, flashcard, progress, quiz, studies_note, conversation, review_quiz

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(document.router, prefix="/document", tags=["Document Processing"])
api_router.include_router(course.router, prefix="/course", tags=["Course Management"])
api_router.include_router(studies_note.router, prefix="/studies-note", tags=["Study Notes"])
api_router.include_router(flashcard.router, prefix="/flashcard", tags=["Flashcards"])
api_router.include_router(progress.router, prefix="/progress", tags=["Progress Tracking"])
api_router.include_router(quiz.router, prefix="/quiz", tags=["Quizzes"])
api_router.include_router(conversation.router, prefix="/conversation", tags=["Q&A Chat"])
api_router.include_router(review_quiz.router, prefix="", tags=["Review Quiz"])