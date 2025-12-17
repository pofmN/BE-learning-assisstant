"""
Document chunk retrieval using pgvector similarity search.
"""
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.document_chunk import DocumentChunk
from app.core.helpers.embedder import EmbeddingService

logger = logging.getLogger(__name__)


class DocumentRetriever:
    """
    Retrieves relevant document chunks using vector similarity search.
    """

    def __init__(self, db: Session):
        self.db = db
        self.embedding_service = EmbeddingService()

    def retrieve_relevant_chunks(
        self,
        query: str,
        document_ids: Optional[List[int]] = None,
        top_k: int = 5,
        similarity_threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve top-k most relevant chunks for a query using cosine similarity.

        Args:
            query: User's question or query
            document_ids: Optional list of document IDs to filter by
            top_k: Number of top results to return
            similarity_threshold: Minimum cosine similarity score (0-1)

        Returns:
            List of chunks with metadata, sorted by relevance
        """
        try:
            # Generate embedding for query
            logger.info(f"Generating embedding for query: {query[:100]}...")
            query_embedding = self.embedding_service.embed_query(query)

            # Build SQL query with pgvector cosine similarity
            # Using <=> operator for cosine distance (1 - cosine similarity)
            sql_query = """
                SELECT 
                    id,
                    document_id,
                    chunk_text,
                    chunk_index,
                    cluster_id,
                    (1 - (embedding_vector <=> :query_embedding)) as similarity
                FROM document_chunks
                WHERE embedding_vector IS NOT NULL
            """

            # Add document filter if provided
            params: Dict[str, Any] = {"query_embedding": str(query_embedding)}
            if document_ids:
                sql_query += " AND document_id = ANY(:document_ids)"
                params["document_ids"] = document_ids  # type: ignore

            # Add similarity threshold and ordering
            sql_query += """
                AND (1 - (embedding_vector <=> :query_embedding)) >= :threshold
                ORDER BY embedding_vector <=> :query_embedding
                LIMIT :top_k
            """
            params["threshold"] = similarity_threshold  # type: ignore
            params["top_k"] = top_k  # type: ignore

            # Execute query
            result = self.db.execute(text(sql_query), params)
            rows = result.fetchall()

            # Format results
            chunks = []
            for row in rows:
                chunks.append({
                    "id": row.id,
                    "document_id": row.document_id,
                    "chunk_text": row.chunk_text,
                    "chunk_index": row.chunk_index,
                    "cluster_id": row.cluster_id,
                    "similarity": float(row.similarity),
                })

            logger.info(f"Retrieved {len(chunks)} relevant chunks (threshold: {similarity_threshold})")
            return chunks

        except Exception as e:
            logger.error(f"Error retrieving chunks: {e}")
            raise

    def retrieve_chunks_by_ids(self, chunk_ids: List[int]) -> List[DocumentChunk]:
        """
        Retrieve specific chunks by their IDs.

        Args:
            chunk_ids: List of chunk IDs

        Returns:
            List of DocumentChunk objects
        """
        return self.db.query(DocumentChunk).filter(
            DocumentChunk.id.in_(chunk_ids)
        ).all()

    def get_document_context(
        self,
        document_id: int,
        cluster_ids: Optional[List[int]] = None,
        max_chunks: int = 20,
    ) -> List[DocumentChunk]:
        """
        Get contextual chunks from a document.

        Args:
            document_id: Document ID
            cluster_ids: Optional list of cluster IDs to filter by
            max_chunks: Maximum number of chunks to return

        Returns:
            List of DocumentChunk objects
        """
        query = self.db.query(DocumentChunk).filter(
            DocumentChunk.document_id == document_id
        )

        if cluster_ids:
            query = query.filter(DocumentChunk.cluster_id.in_(cluster_ids))

        return query.order_by(DocumentChunk.chunk_index).limit(max_chunks).all()
