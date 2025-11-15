"""Models module - Import all models here for Alembic."""
from app.db.base import Base
from app.models.user import User
from app.models.document import Document
from app.models.mcq import MCQ
from app.models.test import TestResult, TestAnswer
from app.models.learning import LearningProgress

__all__ = ["Base", "User", "Document", "MCQ", "TestResult", "TestAnswer", "LearningProgress"]
