"""
Docstring for app.models.document_chunk
"""

from sqlalchemy import Column, Integer, DateTime, ForeignKey, Text
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False
    )
    chunk_text = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    cluster_id = Column(Integer, nullable=True)
    embedding_vector = Column(Vector(1024), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", back_populates="chunks")
