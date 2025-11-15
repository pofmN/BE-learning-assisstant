"""
MCQ (Multiple Choice Question) model.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class MCQ(Base):
    """Multiple Choice Question model."""

    __tablename__ = "mcqs"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    question = Column(Text, nullable=False)
    choices = Column(JSON, nullable=False)  # List of choices
    correct_answer = Column(String, nullable=False)  # e.g., "A", "B", "C", "D"
    explanation = Column(Text, nullable=True)
    difficulty = Column(String, default="medium")  # easy, medium, hard
    topic = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    document = relationship("Document", back_populates="mcqs")
    test_answers = relationship("TestAnswer", back_populates="mcq", cascade="all, delete-orphan")
