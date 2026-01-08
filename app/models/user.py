"""
User model for authentication and authorization.
"""
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class User(Base):
    """User model."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=True)
    full_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=True)
    role = Column(String, default="student")  # student, admin
    avatar_url = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)

    oauth_provider = Column(String, nullable=True)  # e.g., google, facebook
    oauth_id = Column(String, nullable=True)  # ID from the OAuth provider

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    documents = relationship("Document", back_populates="owner", cascade="all, delete-orphan")
    learning_progress = relationship(
        "LearningProgress", back_populates="user", cascade="all, delete-orphan"
    )
    password_reset_tokens = relationship(
        "PasswordResetToken", back_populates="user", cascade="all, delete-orphan"
    )
    # Add to User model
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    personality = relationship("UserPersonality", back_populates="user", uselist=False, cascade="all, delete-orphan")

class PasswordResetToken(Base):
    """Password reset token model."""

    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="password_reset_tokens")
