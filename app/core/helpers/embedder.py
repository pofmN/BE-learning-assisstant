"""
Embedding service for generating vector embeddings using Voyage AI.
"""
import logging
import time
from typing import List, Optional
from voyageai.client import Client
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Service for generating text embeddings using Voyage AI.
    Handles batching and error handling for embedding operations.
    """
    
    DEFAULT_MODEL = "voyage-3-large"
    MAX_BATCH_SIZE = 24  # Voyage AI limit
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize embedding service.
        
        Args:
            api_key: Voyage AI API key (defaults to settings.VOYAGE_API_KEY)
        """
        self.api_key = api_key or settings.VOYAGE_API_KEY
        self._client: Optional[Client] = None
        
        if not self.api_key:
            raise ValueError("VOYAGE_API_KEY not configured")
    
    @property
    def client(self) -> Client:
        """Lazy initialization of Voyage AI client."""
        if self._client is None:
            self._client = Client(api_key=self.api_key)
            logger.info("Voyage AI client initialized")
        return self._client
    
    def embed_chunks(
        self, 
        chunks: List[str], 
        model: str = DEFAULT_MODEL,
        input_type: str = "document"
    ) -> List[List[float]]:
        """
        Generate embeddings for text chunks.
        
        Args:
            chunks: List of text chunks to embed
            model: Voyage AI model to use
            input_type: Type of input ("document" or "query")
            
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
                return self._embed_batch(valid_chunks, model, input_type)
            else:
                return self._embed_large_batch(valid_chunks, model, input_type)
                
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise
    
    def _embed_batch(
        self, 
        chunks: List[str], 
        model: str, 
        input_type: str
    ) -> List[List[float]]:
        """Embed a single batch of chunks."""
        response = self.client.embed(
            texts=chunks,
            model=model,
            input_type=input_type,
            output_dimension=1024
        )
        
        # Ensure all embeddings are floats
        embeddings = [
            [float(val) for val in emb] 
            for emb in response.embeddings
        ]
        
        logger.debug(f"Generated {len(embeddings)} embeddings")
        return embeddings
    
    def _embed_large_batch(
        self, 
        chunks: List[str], 
        model: str, 
        input_type: str
    ) -> List[List[float]]:
        """Embed chunks in multiple batches."""
        all_embeddings = []
        
        for i in range(0, len(chunks), self.MAX_BATCH_SIZE):
            batch = chunks[i:i + self.MAX_BATCH_SIZE]
            logger.debug(f"Processing batch {i//self.MAX_BATCH_SIZE + 1}")
            
            batch_embeddings = self._embed_batch(batch, model, input_type)
            time.sleep(30)
            all_embeddings.extend(batch_embeddings)
        
        return all_embeddings
    
    def embed_query(self, query: str, model: str = DEFAULT_MODEL) -> List[float]:
        """
        Generate embedding for a single query.
        
        Args:
            query: Query text to embed
            model: Voyage AI model to use
            
        Returns:
            Embedding vector as list of floats
        """
        if not query.strip():
            raise ValueError("Cannot embed empty query")
        
        logger.debug(f"Generating query embedding")
        
        response = self.client.embed(
            texts=[query.strip()],
            model=model,
            input_type="query",
            output_dimension=1024
        )
        
        embedding = [float(val) for val in response.embeddings[0]]
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