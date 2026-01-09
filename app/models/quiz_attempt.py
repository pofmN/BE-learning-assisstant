"""
Models for tracking user quiz attempts and sessions.
"""
from sqlalchemy import Column, Integer, String, Boolean, JSON, DateTime, ForeignKey, Float, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class QuizSession(Base):
    """Quiz session model - tracks a user's quiz session."""
    
    __tablename__ = "quiz_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    section_id = Column(Integer, ForeignKey("course_sections.id", ondelete="SET NULL"), nullable=True)
    
    # Session type: regular, section, final_review
    session_type = Column(String(50), default="regular")
    
    # For final_review with existing quizzes: stores JSON array of quiz IDs
    selected_quiz_ids = Column(String, nullable=True)
    
    # For final_review with LLM-generated questions: stores full question data
    generated_questions = Column(Text, nullable=True)
    
    status = Column(String, default="in_progress")  # in_progress, completed, abandoned
    total_questions = Column(Integer, default=0)
    correct_answers = Column(Integer, default=0)
    score_percentage = Column(Float, default=0.0)
    
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", backref="quiz_sessions")
    course = relationship("Course", back_populates="quiz_sessions")
    section = relationship("CourseSection", backref="quiz_sessions")
    attempts = relationship("QuizAttempt", back_populates="session", cascade="all, delete-orphan")

class QuizAttempt(Base):
    """Quiz attempt model - tracks individual quiz question attempts."""
    
    __tablename__ = "quiz_attempts"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("quiz_sessions.id", ondelete="CASCADE"), nullable=False)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    user_answer = Column(JSON, nullable=False)  # User's answer data
    is_correct = Column(Boolean, nullable=False)
    time_spent = Column(Integer, nullable=True)  # Time in seconds
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    session = relationship("QuizSession", back_populates="attempts")
    quiz = relationship("Quiz", backref="attempts")
    user = relationship("User", backref="quiz_attempts")


class FlashcardReview(Base):
    """Flashcard review model - tracks flashcard study sessions."""
    
    __tablename__ = "flashcard_reviews"
    
    id = Column(Integer, primary_key=True, index=True)
    flashcard_id = Column(Integer, ForeignKey("flashcards.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    confidence_level = Column(Integer, nullable=False)  # 1-5 scale
    time_spent = Column(Integer, nullable=True)  # Time in seconds
    next_review_date = Column(DateTime(timezone=True), nullable=True)  # For spaced repetition
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    flashcard = relationship("FlashCard", backref="reviews")
    user = relationship("User", backref="flashcard_reviews")


class StudySession(Base):
    """Study session model - tracks overall study time and activity."""
    
    __tablename__ = "study_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    section_id = Column(Integer, ForeignKey("course_sections.id", ondelete="SET NULL"), nullable=True)
    
    activity_type = Column(String, nullable=False)  # quiz, flashcard, reading
    duration_seconds = Column(Integer, default=0)
    items_completed = Column(Integer, default=0)
    
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", backref="study_sessions")
    course = relationship("Course", back_populates="study_sessions")
    section = relationship("CourseSection", backref="study_sessions")
