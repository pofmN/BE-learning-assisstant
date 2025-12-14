"""
Semantic clustering service for document chunks.

This module provides intelligent clustering of document chunks based on their
embeddings, automatically adapting to different document sizes and types.
"""
import numpy as np
import umap
import hdbscan
from typing import List, Tuple, Dict, Any, Optional
from sklearn.metrics import pairwise_distances
from sklearn.cluster import AgglomerativeClustering
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class DocumentSize(Enum):
    """Document size categories for adaptive clustering."""
    TINY = "tiny"           # 1-6 chunks
    SMALL = "small"         # 7-30 chunks
    MEDIUM = "medium"       # 31-200 chunks
    LARGE = "large"         # 201-1000 chunks
    VERY_LARGE = "very_large"  # 1000+ chunks


@dataclass
class ClusteringConfig:
    """
    Configuration for document clustering algorithm.
    
    These defaults are tuned for general-purpose document clustering,
    working well on documents ranging from 1-page resumes to 800-page textbooks.
    """
    # UMAP dimensionality reduction parameters
    umap_n_neighbors: int = 10
    """Number of neighbors for UMAP. Lower = more local structure."""
    
    umap_n_components: int = 20
    """Target dimensionality after UMAP reduction."""
    
    umap_min_dist: float = 0.0
    """Minimum distance between points in UMAP space. 0 = tighter clusters."""
    
    umap_metric: str = "cosine"
    """Distance metric for UMAP. 'cosine' works best for text embeddings."""
    
    # HDBSCAN clustering parameters
    hdbscan_min_cluster_size: int = 5
    """Minimum number of chunks to form a cluster."""
    
    hdbscan_min_samples: int = 2
    """Number of samples in a neighborhood for a point to be a core point."""
    
    hdbscan_cluster_selection_epsilon: float = 0.0
    """Distance threshold for merging clusters. 0 = no merging (more clusters)."""
    
    # Size thresholds
    small_doc_threshold: int = 6
    """Documents with ≤ this many chunks get a single cluster."""
    
    large_doc_threshold: int = 1000
    """Documents with > this many chunks use optimized parameters."""
    
    max_chunks_for_umap: int = 10000
    """Maximum chunks for UMAP. Beyond this, use simpler clustering."""


class ChunkClusterer:
    """
    Semantic clustering for document chunks using UMAP + HDBSCAN.
    
    This service automatically adapts clustering parameters based on document size
    to provide meaningful semantic groupings across different document types:
    - Short documents (resumes, articles): Preserves all content in 1-2 clusters
    - Medium documents (papers, reports): Groups into 5-15 semantic sections
    - Large documents (books, manuals): Creates hierarchical topic groups
    
    Example:
        >>> clusterer = ChunkClusterer()
        >>> embeddings = [[0.1, 0.2, ...], [0.3, 0.4, ...]]
        >>> cluster_ids, metadata = clusterer.cluster(embeddings)
        >>> print(f"Created {metadata['n_clusters']} clusters")
    """

    def __init__(self, config: Optional[ClusteringConfig] = None):
        """
        Initialize the chunk clusterer.
        
        Args:
            config: Optional custom configuration. Uses defaults if not provided.
        """
        self.config = config or ClusteringConfig()
        logger.info("ChunkClusterer initialized with config: %s", self.config)

    def cluster(
        self,
        embeddings: List[List[float]],
    ) -> Tuple[List[int], Dict[str, Any]]:
        """
        Cluster document chunks by semantic similarity.
        
        Args:
            embeddings: List of embedding vectors, one per chunk.
                       Each embedding should be the same dimension.
        
        Returns:
            Tuple of (cluster_ids, metadata):
                - cluster_ids: List[int] with cluster assignment for each chunk (0, 1, 2, ...)
                - metadata: Dict with clustering diagnostics and statistics
        
        Raises:
            ValueError: If embeddings is empty or contains inconsistent dimensions.
        
        Example:
            >>> cluster_ids, meta = clusterer.cluster(embeddings)
            >>> print(f"Clusters: {meta['n_clusters']}, Method: {meta['method']}")
        """
        # Validate input
        if not embeddings:
            logger.warning("Empty embeddings provided, returning empty result")
            return [], {"n_clusters": 0, "method": "empty", "n_chunks": 0}
        
        n = len(embeddings)
        doc_size = self._classify_document_size(n)
        
        logger.info(f"Clustering {n} chunks (size category: {doc_size.value})")
        
        # Convert to numpy array for processing
        try:
            embeddings_np = np.array(embeddings, dtype=np.float32)
            if embeddings_np.ndim != 2:
                raise ValueError(f"Embeddings must be 2D, got shape {embeddings_np.shape}")
        except Exception as e:
            raise ValueError(f"Invalid embeddings format: {e}")
        
        # Route to appropriate clustering strategy based on document size
        if doc_size == DocumentSize.TINY:
            return self._handle_tiny_document(n)
        elif doc_size == DocumentSize.VERY_LARGE:
            return self._handle_very_large_document(embeddings_np)
        else:
            return self._cluster_standard(embeddings_np, doc_size)

    def _classify_document_size(self, n_chunks: int) -> DocumentSize:
        """Classify document size category based on number of chunks."""
        if n_chunks <= self.config.small_doc_threshold:
            return DocumentSize.TINY
        elif n_chunks <= 50:  # Increased from 30 to skip UMAP for more documents
            return DocumentSize.SMALL
        elif n_chunks <= 200:
            return DocumentSize.MEDIUM
        elif n_chunks <= self.config.large_doc_threshold:
            return DocumentSize.LARGE
        else:
            return DocumentSize.VERY_LARGE

    def _handle_tiny_document(self, n_chunks: int) -> Tuple[List[int], Dict[str, Any]]:
        """
        Handle very small documents (≤6 chunks).
        No clustering needed - all chunks belong to single cluster.
        """
        logger.info(f"Tiny document ({n_chunks} chunks) → single cluster")
        return [0] * n_chunks, {
            "n_clusters": 1,
            "method": "tiny_document_fallback",
            "n_chunks": n_chunks,
            "doc_size": DocumentSize.TINY.value,
        }
    
    def _cluster_small_fast(self, embeddings_np: np.ndarray) -> Tuple[List[int], Dict[str, Any]]:
        """
        Fast clustering for small documents (7-50 chunks) using simple hierarchical clustering.
        Avoids slow UMAP processing.
        """
        n = len(embeddings_np)
        logger.info(f"Small document ({n} chunks) - using fast hierarchical clustering")
        
        # Estimate reasonable number of clusters for small documents
        n_clusters = max(2, min(5, n // 5))
        
        try:
            # Use simple hierarchical clustering directly on embeddings
            clusterer = AgglomerativeClustering(
                n_clusters=n_clusters,
                metric='cosine',
                linkage='average'
            )
            
            labels = clusterer.fit_predict(embeddings_np)  # type: ignore
            
            metadata = {
                "n_chunks": n,
                "n_clusters": n_clusters,
                "method": "hierarchical_fast_small",
                "doc_size": DocumentSize.SMALL.value,
                "cluster_distribution": dict(zip(*np.unique(labels, return_counts=True))),
            }
            
            logger.info(f"Small doc clustered: {n} chunks → {n_clusters} clusters (fast method)")
            return labels.tolist(), metadata
            
        except Exception as e:
            logger.error(f"Small document clustering failed: {e}, using single cluster")
            # Fallback: single cluster
            return [0] * n, {
                "n_chunks": n,
                "n_clusters": 1,
                "method": "single_cluster_fallback",
                "doc_size": DocumentSize.SMALL.value,
            }

    def _handle_very_large_document(
        self, 
        embeddings_np: np.ndarray
    ) -> Tuple[List[int], Dict[str, Any]]:
        """
        Handle very large documents (>1000 chunks).
        Uses more efficient hierarchical clustering to avoid memory issues.
        """
        n = len(embeddings_np)
        logger.info(f"Very large document ({n} chunks) - using Agglomerative clustering")
        
        # For very large docs, use simpler hierarchical clustering
        # Estimate reasonable number of clusters (larger docs = more clusters)
        n_clusters = max(10, min(50, n // 30))
        
        try:
            # Use mini-batch for UMAP on very large datasets
            from umap import UMAP
            
            reducer = UMAP(
                n_neighbors=min(15, n - 1),
                n_components=min(30, n // 50),
                metric="cosine",
                random_state=42,
                low_memory=True,  # Important for large datasets
            )
            
            reduced = reducer.fit_transform(embeddings_np)
            
            # Hierarchical clustering is more stable for large datasets
            clusterer = AgglomerativeClustering(
                n_clusters=n_clusters,
                metric='euclidean',
                linkage='ward'
            )
            
            labels = clusterer.fit_predict(reduced) # type: ignore
            
            metadata = {
                "n_chunks": n,
                "n_clusters": n_clusters,
                "method": "hierarchical_large_doc",
                "doc_size": DocumentSize.VERY_LARGE.value,
                "cluster_distribution": dict(zip(*np.unique(labels, return_counts=True))),
            }
            
            logger.info(f"Large doc clustered: {n} chunks → {n_clusters} clusters")
            return labels.tolist(), metadata
            
        except Exception as e:
            logger.error(f"Large document clustering failed: {e}, using fallback")
            # Fallback: divide into fixed number of sequential clusters
            cluster_size = max(20, n // 20)
            labels = [i // cluster_size for i in range(n)]
            n_clusters = max(labels) + 1
            
            return labels, {
                "n_chunks": n,
                "n_clusters": n_clusters,
                "method": "sequential_fallback",
                "doc_size": DocumentSize.VERY_LARGE.value,
            }

    def _cluster_standard(
        self, 
        embeddings_np: np.ndarray,
        doc_size: DocumentSize
    ) -> Tuple[List[int], Dict[str, Any]]:
        """
        Standard clustering for small-to-large documents using UMAP + HDBSCAN.
        
        This is the main clustering pipeline for most documents.
        """
        n = len(embeddings_np)
        
        # For SMALL documents (7-50 chunks), use faster clustering without UMAP
        if doc_size == DocumentSize.SMALL:
            return self._cluster_small_fast(embeddings_np)
        
        # Adaptive parameters based on document size
        params = self._get_adaptive_parameters(n, doc_size)
        
        # Step 1: Dimensionality reduction with UMAP
        umap_embeddings = self._reduce_dimensions(embeddings_np, params)
        
        # Step 2: Density-based clustering with HDBSCAN
        labels = self._perform_hdbscan(umap_embeddings, params)
        
        # Step 3: Handle noise points
        labels = self._handle_noise_points(labels, umap_embeddings)
        
        # Step 4: Remap to sequential cluster IDs
        final_cluster_ids, n_clusters = self._remap_cluster_ids(labels)
        
        # Compile metadata
        metadata = {
            "n_chunks": n,
            "n_clusters": n_clusters,
            "method": "umap_hdbscan",
            "doc_size": doc_size.value,
            "umap_n_neighbors": params["n_neighbors"],
            "umap_n_components": params["n_components"],
            "hdbscan_min_cluster_size": params["min_cluster_size"],
            "cluster_distribution": dict(zip(*np.unique(final_cluster_ids, return_counts=True))),
        }
        
        logger.info(
            f"Clustered {n} chunks → {n_clusters} clusters "
            f"(sizes: {metadata['cluster_distribution']})"
        )
        
        return final_cluster_ids, metadata

    def _get_adaptive_parameters(
        self, 
        n_chunks: int, 
        doc_size: DocumentSize
    ) -> Dict[str, Any]:
        """
        Calculate adaptive clustering parameters based on document size.
        
        Smaller documents need tighter clusters, larger documents allow more flexibility.
        """
        # UMAP parameters
        n_neighbors = min(self.config.umap_n_neighbors, n_chunks - 1)
        
        # Adaptive n_components: smaller docs need fewer dimensions
        if doc_size == DocumentSize.SMALL:
            n_components = min(10, max(5, n_chunks // 4))
        elif doc_size == DocumentSize.MEDIUM:
            n_components = min(15, max(10, n_chunks // 20))
        else:  # LARGE
            n_components = min(25, max(15, n_chunks // 30))
        
        # HDBSCAN min_cluster_size: scale with document size
        if doc_size == DocumentSize.SMALL:
            min_cluster_size = max(2, n_chunks // 15)
        elif doc_size == DocumentSize.MEDIUM:
            min_cluster_size = max(3, n_chunks // 30)
        else:  # LARGE
            min_cluster_size = max(5, n_chunks // 50)
        
        return {
            "n_neighbors": n_neighbors,
            "n_components": n_components,
            "min_cluster_size": min_cluster_size,
        }

    def _reduce_dimensions(
        self, 
        embeddings_np: np.ndarray,
        params: Dict[str, Any]
    ) -> np.ndarray:
        """
        Reduce embedding dimensionality using UMAP.
        
        Falls back to original embeddings if UMAP fails.
        """
        try:
            reducer = umap.UMAP(
                n_neighbors=params["n_neighbors"],
                n_components=params["n_components"],
                min_dist=self.config.umap_min_dist,
                metric=self.config.umap_metric,
                random_state=42,
                low_memory=False,
                densmap=False,
            )
            
            reduced = reducer.fit_transform(embeddings_np)
            
            logger.debug(
                f"UMAP: {embeddings_np.shape[1]}D → {params['n_components']}D "
                f"({len(embeddings_np)} points)"
            )
            
            return np.asarray(reduced, dtype=np.float32)
            
        except Exception as e:
            logger.warning(f"UMAP failed: {e}, using original embeddings")
            return embeddings_np

    def _perform_hdbscan(
        self, 
        embeddings: np.ndarray,
        params: Dict[str, Any]
    ) -> np.ndarray:
        """
        Perform density-based clustering with HDBSCAN.
        """
        # Ensure valid 2D array
        if not isinstance(embeddings, np.ndarray):
            embeddings = np.asarray(embeddings, dtype=np.float32)
        if embeddings.ndim != 2:
            embeddings = np.atleast_2d(embeddings)
        
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=params["min_cluster_size"],
            min_samples=self.config.hdbscan_min_samples,
            metric="euclidean",
            cluster_selection_method="eom",  # Excess of Mass - keeps small dense clusters
            cluster_selection_epsilon=self.config.hdbscan_cluster_selection_epsilon,
            core_dist_n_jobs=-1,  # Use all CPU cores
            prediction_data=True,  # Enable soft clustering if needed later
        )
        
        labels = clusterer.fit_predict(embeddings)
        
        n_noise = np.sum(labels == -1)
        n_clustered = len(labels) - n_noise
        
        logger.debug(
            f"HDBSCAN: {n_clustered} clustered, {n_noise} noise "
            f"(min_size={params['min_cluster_size']})"
        )
        
        return labels

    def _handle_noise_points(
        self, 
        labels: np.ndarray,
        embeddings: np.ndarray
    ) -> np.ndarray:
        """
        Assign noise points (-1) to nearest valid cluster.
        
        If all points are noise, create a single cluster.
        """
        if -1 not in labels:
            return labels
        
        noise_mask = labels == -1
        clean_mask = ~noise_mask
        
        n_noise = np.sum(noise_mask)
        
        if clean_mask.sum() > 0:
            # Assign each noise point to nearest real cluster
            dists = pairwise_distances(
                embeddings[noise_mask],
                embeddings[clean_mask],
                metric="euclidean",
            )
            nearest_indices = np.argmin(dists, axis=1)
            labels[noise_mask] = labels[clean_mask][nearest_indices]
            
            logger.debug(f"Assigned {n_noise} noise points to nearest clusters")
        else:
            # Extremely rare: everything is noise
            logger.warning("All points classified as noise, creating single cluster")
            labels = np.zeros(len(labels), dtype=int)
        
        return labels

    def _remap_cluster_ids(self, labels: np.ndarray) -> Tuple[List[int], int]:
        """
        Remap cluster labels to sequential integers starting from 0.
        
        Returns:
            (remapped_labels, n_clusters)
        """
        unique_labels = np.unique(labels)
        label_map = {old: new for new, old in enumerate(sorted(unique_labels))}
        
        final_ids = [label_map[label] for label in labels]
        n_clusters = len(unique_labels)
        
        return final_ids, n_clusters


# Convenience function for backward compatibility
def cluster_chunks(embeddings: List[List[float]]) -> Tuple[List[int], Dict[str, Any]]:
    """
    Cluster document chunks by embeddings (convenience function).
    
    Args:
        embeddings: List of embedding vectors
    
    Returns:
        (cluster_ids, metadata)
    """
    clusterer = ChunkClusterer()
    return clusterer.cluster(embeddings)