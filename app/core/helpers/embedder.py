"""
Embedding service for generating vector embeddings using OpenAI.
"""
import logging
import time
from typing import List, Optional
from openai import OpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Service for generating text embeddings using OpenAI.
    Handles batching and error handling for embedding operations.
    """
    
    DEFAULT_MODEL = "text-embedding-3-small"  # or "text-embedding-3-small" for faster/cheaper
    MAX_BATCH_SIZE = 2048  # OpenAI limit for text-embedding-3-*
    EMBEDDING_DIMENSION = 1024  # Can be 256, 1024, or 3072 for text-embedding-3-large
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize embedding service.
        
        Args:
            api_key: OpenAI API key (defaults to settings.OPENAI_API_KEY)
        """
        self.api_key = api_key or settings.OPENAI_API_KEY
        self._client: Optional[OpenAI] = None
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not configured")
    
    @property
    def client(self) -> OpenAI:
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key)
            logger.info("OpenAI client initialized")
        return self._client
    
    def embed_chunks(
        self, 
        chunks: List[str], 
        model: str = DEFAULT_MODEL,
        dimensions: int = EMBEDDING_DIMENSION
    ) -> List[List[float]]:
        """
        Generate embeddings for text chunks.
        
        Args:
            chunks: List of text chunks to embed
            model: OpenAI embedding model to use
            dimensions: Output dimension (256, 1024, or 3072 for text-embedding-3-large)
            
        Returns:
            List of embedding vectors (each is a list of floats)
            
        Raises:
            ValueError: If chunks is empty or contains invalid data
        """
        if not chunks:
            raise ValueError("Cannot embed empty chunks list")
        
        # Filter out empty chunks
        valid_chunks = [chunk.strip() for chunk in chunks if chunk.strip()]
        
        if not valid_chunks:
            raise ValueError("No valid chunks to embed (all empty)")
        
        logger.info(f"Generating embeddings for {len(valid_chunks)} chunks using {model}")
        
        try:
            # Process in batches if needed
            if len(valid_chunks) <= self.MAX_BATCH_SIZE:
                return self._embed_batch(valid_chunks, model, dimensions)
            else:
                return self._embed_large_batch(valid_chunks, model, dimensions)
                
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise
    
    def _embed_batch(
        self, 
        chunks: List[str], 
        model: str,
        dimensions: int
    ) -> List[List[float]]:
        """Embed a single batch of chunks."""
        response = self.client.embeddings.create(
            input=chunks,
            model=model,
            dimensions=dimensions
        )
        
        # Extract embeddings in the correct order
        embeddings = [
            [float(val) for val in data.embedding] 
            for data in response.data
        ]
        
        logger.debug(f"Generated {len(embeddings)} embeddings")
        return embeddings
    
    def _embed_large_batch(
        self, 
        chunks: List[str], 
        model: str,
        dimensions: int
    ) -> List[List[float]]:
        """Embed chunks in multiple batches."""
        all_embeddings = []
        
        for i in range(0, len(chunks), self.MAX_BATCH_SIZE):
            batch = chunks[i:i + self.MAX_BATCH_SIZE]
            batch_num = i // self.MAX_BATCH_SIZE + 1
            total_batches = (len(chunks) + self.MAX_BATCH_SIZE - 1) // self.MAX_BATCH_SIZE
            logger.debug(f"Processing batch {batch_num}/{total_batches} ({len(batch)} chunks)")
            
            batch_embeddings = self._embed_batch(batch, model, dimensions)
            all_embeddings.extend(batch_embeddings)
            
            # Add small delay to avoid rate limits (only if there are more batches)
            if i + self.MAX_BATCH_SIZE < len(chunks):
                time.sleep(0.1)
        
        return all_embeddings
    
    def embed_query(
        self, 
        query: str, 
        model: str = DEFAULT_MODEL,
        dimensions: int = EMBEDDING_DIMENSION
    ) -> List[float]:
        """
        Generate embedding for a single query.
        
        Args:
            query: Query text to embed
            model: OpenAI embedding model to use
            dimensions: Output dimension
            
        Returns:
            Embedding vector as list of floats
        """
        if not query.strip():
            raise ValueError("Cannot embed empty query")
        
        logger.debug(f"Generating query embedding")
        
        response = self.client.embeddings.create(
            input=[query.strip()],
            model=model,
            dimensions=dimensions
        )
        
        embedding = [float(val) for val in response.data[0].embedding]
        return embedding


# Convenience function for backward compatibility
def embed_chunks(chunks: List[str]) -> List[List[float]]:
    """
    Generate embeddings for chunks (convenience function).
    
    Args:
        chunks: List of text chunks to embed
        
    Returns:
        List of embedding vectors
    """
    service = EmbeddingService()
    return service.embed_chunks(chunks)