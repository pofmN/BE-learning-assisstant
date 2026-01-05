"""Schemas module - Import all schemas."""
from app.schemas.user import User, UserCreate, UserUpdate, Token, TokenPayload
from app.schemas.document import Document, DocumentCreate, DocumentUpdate, DocumentWithText

from app.schemas.learning import (
    LearningProgress,
    LearningProgressCreate,
    LearningProgressUpdate,
    TopicRecommendation,
    WeakArea,
)
from app.schemas.common import Message, ErrorResponse, SuccessResponse
from app.schemas.course import CourseShareCreate, CourseShareResponse, CourseWithAccess

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
    "LearningProgress",
    "LearningProgressCreate",
    "LearningProgressUpdate",
    "TopicRecommendation",
    "WeakArea",
    "Message",
    "ErrorResponse",
    "SuccessResponse",
    "CourseShareCreate",
    "CourseShareResponse",
    "CourseWithAccess",
]
