from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class Course(Base):
    """Course model."""

    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    language = Column(String, nullable=True)  # e.g., English, Vietnamese
    level = Column(String, nullable=True)  # e.g., Beginner, Intermediate, Advanced
    requirements = Column(Text, nullable=True)
    question_type = Column(String, nullable=True)  # e.g., multiple_choice, true_false
    status = Column(String, default="pending")  # pending, processing, completed, failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    document = relationship("Document", backref="courses")
    sections = relationship("CourseSection", back_populates="course", cascade="all, delete-orphan")
    quizzes = relationship("Quiz", back_populates="course", cascade="all, delete-orphan")


class CourseSection(Base):
    """Course section model for organizing course content."""

    __tablename__ = "course_sections"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    section_order = Column(Integer, nullable=False)
    cluster_id = Column(Integer, nullable=True)  # Reference to document chunk cluster
    key_points = Column(JSON, nullable=True)  # List of key points
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    course = relationship("Course", back_populates="sections")


class Quiz(Base):
    """Quiz model for course assessments."""

    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    question = Column(Text, nullable=False)
    question_type = Column(String, default="multiple_choice")  # multiple_choice, true_false, short_answer
    question_data = Column(JSON, nullable=True)  # List of answer options for multiple choice
    explanation = Column(Text, nullable=True)
    difficulty = Column(String, nullable=True)  # easy, medium, hard
    section_id = Column(Integer, ForeignKey("course_sections.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    course = relationship("Course", back_populates="quizzes")
    section = relationship("CourseSection", backref="quizzes")

class FlashCard(Base):
    """Flashcard model for course review."""

    __tablename__ = "flashcards"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    section_id = Column(Integer, ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    course = relationship("Course", backref="flashcards")
    section = relationship("CourseSection", backref="flashcards")

class StudiesNote(Base):
    """Study note model for course summaries."""

    __tablename__ = "studies_notes"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    section_id = Column(Integer, ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    course = relationship("Course", backref="studies_notes")
    section = relationship("CourseSection", backref="studies_notes")