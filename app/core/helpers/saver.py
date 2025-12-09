"""
Document storage service for saving documents and chunks to database.
"""
import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_chunk import DocumentChunk

logger = logging.getLogger(__name__)


class DocumentStorage:
    """Handle storing documents and their chunks to the database."""
    
    def __init__(self, db: Session):
        """
        Initialize document storage.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def store_document_with_chunks(
        self,
        filename: str,
        chunks: List[str],
        embeddings: List[List[float]],
        user_id: Optional[int] = None,
        cluster_ids: Optional[List[Optional[int]]] = None  # <-- add this
    ) -> int:
        """
        Store document and its chunks with embeddings.
        
        Args:
            filename: Original filename
            chunks: List of text chunks
            embeddings: List of embedding vectors (one per chunk)
            user_id: ID of user who uploaded
            cluster_ids: Optional list of cluster IDs for each chunk
            
        Returns:
            Document ID
            
        Raises:
            ValueError: If chunks and embeddings lengths don't match
        """
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Chunks ({len(chunks)}) and embeddings ({len(embeddings)}) "
                f"length mismatch"
            )
        
        try:
            # Create document record
            total_tokens = sum(len(chunk.split()) for chunk in chunks)
            file_type = filename.split(".")[-1] if "." in filename else "unknown"
            document = Document(
                title=filename,
                filename=filename,
                file_path="",
                file_size=0,
                file_type=file_type,
                owner_id=user_id,
                status="processed"
            )
            
            self.db.add(document)
            self.db.flush()  # Get document.id before adding chunks
            
            logger.info(f"Created document record with ID {document.id}")
            
            # Create chunk records
            for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
                cluster_id = cluster_ids[idx] if cluster_ids else None
                chunk = DocumentChunk(
                    document_id=document.id,
                    chunk_text=chunk_text,
                    token_count=len(chunk_text.split()),
                    chunk_index=idx,
                    cluster_id=cluster_id,
                    embedding_vector=embedding,
                )
                self.db.add(chunk)
            
            self.db.commit()
            
            logger.info(
                f"Stored document '{filename}' with {len(chunks)} chunks "
                f"({total_tokens} tokens)"
            )
            
            return document.id #type: ignore
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to store document '{filename}': {e}")
            raise