"""FAISS vector store for Windows RAG System."""
import json
import pickle
from pathlib import Path
from typing import List, Dict, Any
import numpy as np
import faiss

from utils.logger import setup_logger

logger = setup_logger("faiss_store")


class FAISSStore:
    """FAISS-based vector store with metadata persistence."""

    def __init__(self, dimension: int, index_path: str | None = None, metadata_path: str | None = None):
        """Initialize FAISS store.

        Args:
            dimension: Embedding dimension.
            index_path: Path to save/load FAISS index.
            metadata_path: Path to save/load chunk metadata.
        """
        self.dimension = dimension
        self.index_path = Path(index_path) if index_path else None
        self.metadata_path = Path(metadata_path) if metadata_path else None
        self.metadata: List[Dict[str, Any]] = []
        self.id_map: Dict[int, str] = {}
        self._index: faiss.Index | None = None
        self._next_id = 0

    @property
    def index(self) -> faiss.Index:
        """Lazy-load or create FAISS index."""
        if self._index is None:
            if self.index_path and self.index_path.exists():
                self._index = faiss.read_index(str(self.index_path))
                self._next_id = self._index.ntotal
            else:
                self._index = faiss.IndexFlatIP(self.dimension)  # Inner product for normalized vectors
        return self._index

    def add(self, embeddings: np.ndarray, chunks: List[Dict[str, Any]]) -> None:
        """Add embeddings with metadata.

        Args:
            embeddings: Array of shape (n, dimension).
            chunks: List of metadata dicts matching embeddings.
        """
        if len(embeddings) == 0:
            return

        self.index.add(embeddings.astype(np.float32))
        
        for chunk in chunks:
            self.id_map[self._next_id] = chunk.get("id", f"chunk_{self._next_id}")
            self.metadata.append(chunk)
            self._next_id += 1

    def search(self, query_embedding: np.ndarray, k: int = 5, filters: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        """Search for nearest neighbors.

        Args:
            query_embedding: Query vector.
            k: Number of results.
            filters: Optional metadata filters (simple dict equality).

        Returns:
            List of result dicts with content, source, score, metadata.
        """
        if self.index.ntotal == 0:
            return []

        query_embedding = np.array(query_embedding).astype(np.float32).reshape(1, -1)
        scores, indices = self.index.search(query_embedding, min(k, self.index.ntotal))
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            meta = self.metadata[idx]
            
            # Apply filters
            if filters:
                if not all(meta.get(key) == value for key, value in filters.items()):
                    continue
            
            results.append({
                "content": meta.get("content", ""),
                "source": meta.get("source", ""),
                "score": float(score),
                "metadata": meta,
            })
        
        return results

    def save(self) -> None:
        """Persist index and metadata to disk.

        Writes metadata first (less critical), then the FAISS index.
        On load, consistency is validated.
        """
        # Save metadata first
        if self.metadata_path:
            self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.metadata_path, "wb") as f:
                pickle.dump({
                    "metadata": self.metadata,
                    "id_map": self.id_map,
                    "next_id": self._next_id,
                }, f)

        # Save FAISS index
        if self.index_path:
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            faiss.write_index(self.index, str(self.index_path))

    def load(self) -> bool:
        """Load index and metadata from disk.

        Validates metadata count vs index vector count.

        Returns:
            True if anything was loaded, False if nothing to load.
        """
        index_loaded = False
        metadata_loaded = False

        if self.index_path and self.index_path.exists():
            try:
                self._index = faiss.read_index(str(self.index_path))
                self._next_id = self._index.ntotal
                index_loaded = True
            except Exception as e:
                logger.warning(f"Failed to load FAISS index: {e}")

        if self.metadata_path and self.metadata_path.exists():
            try:
                with open(self.metadata_path, "rb") as f:
                    data = pickle.load(f)
                self.metadata = data.get("metadata", [])
                self.id_map = data.get("id_map", {})
                self._next_id = data.get("next_id", self._next_id)
                metadata_loaded = True
            except Exception as e:
                logger.warning(f"Failed to load metadata pickle: {e}")
                if index_loaded:
                    logger.warning(
                        f"FAISS index loaded ({self._index.ntotal} vectors) "
                        f"but metadata is missing/corrupt. "
                        f"Search results will be empty. Re-index required."
                    )

        # Validate consistency
        if index_loaded and self.metadata and self._index.ntotal != len(self.metadata):
            logger.warning(
                f"FAISS index ({self._index.ntotal} vectors) and metadata "
                f"({len(self.metadata)} entries) are out of sync. "
                f"Search may produce wrong results. Re-index recommended."
            )

        return index_loaded or metadata_loaded

    def clear(self) -> None:
        """Clear all data."""
        self._index = faiss.IndexFlatIP(self.dimension)
        self.metadata = []
        self.id_map = {}
        self._next_id = 0

    def count(self) -> int:
        """Return total number of indexed vectors."""
        return self.index.ntotal
