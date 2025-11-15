"""Schemas module - Import all schemas."""
from app.schemas.user import User, UserCreate, UserUpdate, Token, TokenPayload
from app.schemas.document import Document, DocumentCreate, DocumentUpdate, DocumentWithText
from app.schemas.mcq import MCQ, MCQCreate, MCQUpdate, MCQGenerate, MCQGenerateResponse
from app.schemas.test import (
    TestSubmit,
    TestAnswerSubmit,
    TestResult,
    TestResultDetailed,
    TestAnswerResult,
)
from app.schemas.learning import (
    LearningProgress,
    LearningProgressCreate,
    LearningProgressUpdate,
    TopicRecommendation,
    WeakArea,
)
from app.schemas.common import Message, ErrorResponse, SuccessResponse

__all__ = [
    "User",
    "UserCreate",
    "UserUpdate",
    "Token",
    "TokenPayload",
    "Document",
    "DocumentCreate",
    "DocumentUpdate",
    "DocumentWithText",
    "MCQ",
    "MCQCreate",
    "MCQUpdate",
    "MCQGenerate",
    "MCQGenerateResponse",
    "TestSubmit",
    "TestAnswerSubmit",
    "TestResult",
    "TestResultDetailed",
    "TestAnswerResult",
    "LearningProgress",
    "LearningProgressCreate",
    "LearningProgressUpdate",
    "TopicRecommendation",
    "WeakArea",
    "Message",
    "ErrorResponse",
    "SuccessResponse",
]
