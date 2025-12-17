"""
Conversation models for document Q&A chat.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class Conversation(Base):
    """
    Conversation session for document Q&A.
    Each conversation is tied to a specific document.
    """
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    title = Column(String(255), nullable=True)  # Auto-generated from first question
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("ConversationMessage", back_populates="conversation", cascade="all, delete-orphan")
    summaries = relationship("ConversationSummary", back_populates="conversation", cascade="all, delete-orphan")


class ConversationMessage(Base):
    """
    Individual messages (question/answer pairs) in a conversation.
    """
    __tablename__ = "conversation_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    
    # Store which document chunks were used to generate this answer
    source_chunk_ids = Column(Text, nullable=True)  # JSON array of chunk IDs: "[1, 5, 12]"
    
    # Metadata
    tokens_used = Column(Integer, nullable=True)  # For tracking API usage
    model_used = Column(String(100), nullable=True)  # e.g., "gpt-4o-mini"
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")


class ConversationSummary(Base):
    """
    Auto-generated summaries of conversation segments.
    Created every 5 Q&A pairs for bot memory.
    """
    __tablename__ = "conversation_summaries"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Which messages this summary covers
    start_message_id = Column(Integer, nullable=False)
    end_message_id = Column(Integer, nullable=False)
    
    # The summary content
    summary = Column(Text, nullable=False)
    
    # Metadata
    message_count = Column(Integer, default=10)  # Usually 10 messages (5 Q&A pairs)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    conversation = relationship("Conversation", back_populates="summaries")