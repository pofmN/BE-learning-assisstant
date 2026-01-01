"""
Review Quiz Analysis Model - stores analysis and recommendations after final review quiz.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class ReviewQuizAnalysis(Base):
    """
    Stores analysis and recommendations after final review quiz completion.
    Compares user's original quiz performance with review quiz performance.
    """
    __tablename__ = "review_quiz_analysis"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # The final review quiz session (unique - one analysis per review session)
    review_session_id = Column(
        Integer, 
        ForeignKey("quiz_sessions.id", ondelete="CASCADE"), 
        unique=True, 
        nullable=False
    )
    
    # Performance comparison metrics
    total_original_attempts = Column(Integer, nullable=False)  # Total quizzes attempted before review
    original_avg_score = Column(Float, nullable=False)  # Average score across all previous attempts
    review_score = Column(Float, nullable=False)  # Score on final review quiz (0-100)
    improvement_percentage = Column(Float, nullable=False)  # review_score - original_avg_score
    
    # Question-level breakdown
    improved_count = Column(Integer, default=0)  # Was wrong, now correct 
    regressed_count = Column(Integer, default=0)  # Was correct, now wrong 
    persistent_weak_count = Column(Integer, default=0)  # Still wrong 
    consistent_strong_count = Column(Integer, default=0)  # Still correct 
    
    # Topic/Section analysis (JSON array)
    # Format: [{"section": "Intro", "original": 60.0, "review": 80.0, "improvement": 20.0}, ...]
    topic_breakdown = Column(Text, nullable=True)
    
    # LLM-generated recommendations (JSON array)
    # Format: [{"priority": "high", "topic": "X", "suggestion": "...", "reason": "..."}, ...]
    recommendations = Column(Text, nullable=True)
    
    # Additional insights (JSON object)
    # Format: {"weak_topics": [...], "study_time": "3-4 hours", "confidence": "medium"}
    insights = Column(Text, nullable=True)
    
    # Metadata
    analysis_generated_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", backref="review_analyses")
    course = relationship("Course", backref="review_analyses")
    review_session = relationship("QuizSession", backref="review_analysis")
