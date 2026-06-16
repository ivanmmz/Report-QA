"""Retriever module for Windows RAG System."""
from typing import List, Dict, Any
import numpy as np

from core.reranker import Reranker


class DocumentRetriever:
    """Retrieve relevant chunks using vector similarity and optional reranking."""

    def __init__(self, vector_store, embedder, top_k: int = 5, reranker: Reranker | None = None):
        """Initialize retriever.

        Args:
            vector_store: Vector store instance with search method.
            embedder: Embedder instance.
            top_k: Number of results to retrieve.
            reranker: Optional reranker instance.
        """
        self.vector_store = vector_store
        self.embedder = embedder
        self.top_k = top_k
        self.reranker = reranker

    def retrieve(self, query: str, filters: Dict[str, Any] | None = None, top_k: int | None = None, rerank: bool | None = None) -> List[Dict[str, Any]]:
        """Retrieve top-k relevant chunks for query.

        Args:
            query: User query string.
            filters: Optional metadata filters.
            top_k: Override default top_k.
            rerank: Whether to rerank results. If None, uses reranker if available.

        Returns:
            List of result dicts with content, source, score, and metadata.
        """
        k = top_k or self.top_k
        
        # If reranking is enabled, retrieve more results for reranking
        search_k = k
        if (rerank is True or (rerank is None and self.reranker is not None)):
            search_k = k * 3  # Retrieve 3x for reranking
        
        query_embedding = self.embedder.embed_query(query)
        results = self.vector_store.search(query_embedding, k=search_k, filters=filters)
        
        # Apply reranking if enabled
        if (rerank is True or (rerank is None and self.reranker is not None)) and self.reranker:
            results = self.reranker.rerank(query, results, top_k=k)
        
        return results

    def retrieve_with_scores(self, query: str, top_k: int | None = None) -> tuple[List[str], List[float]]:
        """Retrieve chunks and their similarity scores.

        Args:
            query: User query string.
            top_k: Override default top_k.

        Returns:
            Tuple of (texts, scores).
        """
        k = top_k or self.top_k
        query_embedding = self.embedder.embed_query(query)
        results = self.vector_store.search(query_embedding, k=k)
        
        texts = [r["content"] for r in results]
        scores = [r.get("score", 0.0) for r in results]
        return texts, scores

    def update_embedder(self, embedder) -> None:
        """Update embedder reference.

        Args:
            embedder: New embedder instance.
        """
        self.embedder = embedder

    def update_reranker(self, reranker: Reranker | None) -> None:
        """Update reranker reference.

        Args:
            reranker: New reranker instance or None.
        """
        self.reranker = reranker
