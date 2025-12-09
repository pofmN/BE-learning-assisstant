"""
Document processing pipeline for text extraction, chunking, embedding, and storage.
Handles PDF, DOCX, PPTX, and TXT files.
"""
import logging
from typing import Optional
from sqlalchemy.orm import Session

from app.services.file_service import FileService
from app.core.helpers.extracter import DocumentExtractor
from app.core.helpers.chunker import TextChunker
from app.core.helpers.embedder import EmbeddingService
from app.core.helpers.saver import DocumentStorage
from app.core.helpers.cluster import ChunkClusterer
from app.models.document import Document
from app.models.document_chunk import DocumentChunk

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    Main document processing pipeline.
    Orchestrates extraction, chunking, embedding, and storage.
    """
    
    def __init__(self, db: Session):
        """
        Initialize document processor with database session.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.file_service = FileService()
        self.extractor = DocumentExtractor()
        self.chunker = TextChunker()
        self.embedder = EmbeddingService()
        self.storage = DocumentStorage(db)
        self.clusterer = ChunkClusterer()
        
    def process_and_store(
        self, 
        file_path: str, 
        filename: str,
        document_id: int,
        user_id: Optional[int] = None,
    ) -> int:
        """
        Process document through full pipeline and store to database.
        
        Args:
            file_path: Path to the file to be processed
            filename: Original filename
            user_id: ID of user who uploaded the document
            document_id: ID of the document being re-processed (optional)
            
        Returns:
            Document ID from database
            
        Raises:
            ValueError: If file type is unsupported or processing fails
        """
        try:
            if document_id:
                doc = self.db.query(Document).filter(Document.id == document_id, Document.owner_id == user_id).first()
                if doc:
                    logger.info(f"Re-processing existing document ID {document_id}")
                    doc.status = "processing" # type: ignore
                    self.db.commit()
            else:
                raise ValueError("Document ID must be provided for processing.")

            # Step 0: Get file bytes
            logger.info(f"Loading file bytes for '{filename}'")
            file_bytes = self.file_service.get_file_content(file_path)


            # Step 1: Extract text from document
            logger.info(f"Extracting text from '{filename}'")
            text = self.extractor.extract_text(file_bytes, filename)
            
            if not text.strip():
                raise ValueError(f"No text content extracted from '{filename}'")
            
            # Step 2: Split text into chunks
            logger.info(f"Chunking text from '{filename}'")
            chunks = self.chunker.chunk_text(text)
            logger.info(f"Created {len(chunks)} chunks from '{filename}'")
            
            # Step 3: Generate embeddings
            logger.info(f"Generating embeddings for '{filename}'")
            embeddings = self.embedder.embed_chunks(chunks)
            
            # Step 3.5: Cluster chunks by embedding
            logger.info(f"Clustering chunks for '{filename}'")
            cluster_ids, _ = self.clusterer.cluster(embeddings)            
            # Step 4: Store to database (pass cluster_ids)
            logger.info(f"Storing document '{filename}' to database")

            doc = self.db.query(Document).filter(Document.id == document_id).first()
            if doc:
                doc.extracted_text = text # type: ignore
                self.db.commit()

                # Add chunks with cluster IDs
                for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
                    cluster_id = cluster_ids[idx] if cluster_ids else None
                    chunk = DocumentChunk(
                        document_id=doc.id,
                        chunk_text=chunk_text,
                        chunk_index=idx,
                        cluster_id=cluster_id,
                        token_count=len(chunk_text.split()),
                        embedding_vector=embedding,
                    )
                    self.db.add(chunk)
                doc.status = "processed"  # type: ignore
                self.db.commit()
                logger.info(f"Stored {len(chunks)} chunks for document ID {doc.id}")
                return document_id

            logger.info(f"Successfully processed and stored '{filename}' with ID {document_id}")
            return document_id
            
        except Exception as e:
            logger.error(f"Failed to process document '{filename}': {str(e)}")
            try:
                doc = self.db.query(Document).filter(Document.id == document_id).first()
                if doc:
                    doc.status = "failed"  # type: ignore
                    self.db.commit()
            except Exception as db_e:
                logger.error(f"Failed to update document status to 'failed': {str(db_e)}")
            raise


# Convenience function for backward compatibility
def process_and_store_document(
    db: Session, 
    file_path: str, 
    filename: str,
    document_id: int,
    user_id: Optional[int] = None
) -> int:
    """
    Process and store a document (convenience function).
    
    Args:
        db: Database session
        file_bytes: Raw file content
        filename: Original filename
        user_id: User ID who uploaded
        
    Returns:
        Document ID
    """
    processor = DocumentProcessor(db)
    return processor.process_and_store(file_path, filename, document_id, user_id)