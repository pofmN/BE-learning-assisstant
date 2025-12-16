"""Models module - Import all models here for Alembic."""
from app.db.base import Base
from app.models.user import User
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.learning import LearningProgress
from app.models.course import Course, CourseSection, Quiz, FlashCard, StudiesNote
from app.models.quiz_attempt import QuizSession, QuizAttempt, FlashcardReview, StudySession

__all__ = ["Base", "User", "Document", "DocumentChunk", "LearningProgress", "Course", "CourseSection", "Quiz", "FlashCard", "StudiesNote", "QuizSession", "QuizAttempt", "FlashcardReview", "StudySession"]