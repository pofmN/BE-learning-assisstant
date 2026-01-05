"""Models module - Import all models here for Alembic."""
from app.db.base import Base
from app.models.user import User
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.learning import LearningProgress
from app.models.course import Course, CourseSection, Quiz, FlashCard, StudiesNote, CourseShare, CourseEnrollment
from app.models.quiz_attempt import QuizSession, QuizAttempt, FlashcardReview, StudySession
from app.models.conversation import Conversation, ConversationMessage, ConversationSummary
from app.models.review_analysis import ReviewQuizAnalysis
from app.models.user_personality import UserPersonality

__all__ = ["Base", "User", "Document", "DocumentChunk", "LearningProgress", "Course", 
           "CourseSection", "Quiz", "FlashCard", "StudiesNote", "QuizSession", 
           "QuizAttempt", "FlashcardReview", "StudySession", "Conversation", 
           "ConversationMessage", "ConversationSummary", "ReviewQuizAnalysis",
           "UserPersonality", "CourseShare", "CourseEnrollment"]