"""API-based embedding module for Windows RAG System.

Makes direct HTTP requests to the embedding provider's API endpoint,
with local sentence-transformers fallback when API is unavailable.
"""
from typing import List, Optional
import numpy as np
import httpx

from utils.logger import setup_logger

logger = setup_logger("embedder")

# Known embedding dimensions for common models
KNOWN_DIMENSIONS = {
    "text-embedding-3-large": 3072,
    "text-embedding-3-small": 1536,
    "text-embedding-ada-002": 1536,
    "all-MiniLM-L6-v2": 384,
    "paraphrase-multilingual-MiniLM-L12-v2": 384,
    "BAAI/bge-small-zh-v1.5": 512,
    "BAAI/bge-large-zh-v1.5": 1024,
    "shibing624/text2vec-base-chinese": 768,
}

# Local fallback model - BGE-M3
# Default dimension is 1024 (bge-m3 output). Auto-detected from actual model
# output if the API-based model differs.
LOCAL_FALLBACK_MODEL = "BAAI/bge-m3"
LOCAL_FALLBACK_DIM = 1024


class APIEmbedder:
    """Embedding generator with API-first, local-fallback strategy.

    Attempts remote API embedding first. If the API is unavailable or
    authentication fails, falls back to a local sentence-transformers model.
    """

    def __init__(self, model_name: str, base_url: str, api_key: str, dimension: int | None = None):
        """Initialize the embedder.

        Args:
            model_name: Embedding model identifier (e.g., "Qwen3-Embedding-8B").
            base_url: Base URL for the embedding provider's API.
            api_key: API key for the embedding provider.
            dimension: Embedding dimension. Auto-detected from model name if None.
        """
        if not model_name:
            raise ValueError("Embedding model must be configured.")
        if not base_url:
            raise ValueError("Embedding provider base URL is required.")

        self.model_name = model_name
        self._declared_dimension = dimension or self._get_dimension(model_name)
        self._actual_dimension: int | None = None
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

        logger.info(f"Initialized APIEmbedder with model {model_name} at {base_url} (declared dimension {self._declared_dimension})")

    @property
    def dimension(self) -> int:
        """Return embedding dimension, detected from actual model output."""
        if self._actual_dimension is not None:
            return self._actual_dimension
        return self._declared_dimension

    def _get_dimension(self, model_name: str) -> int:
        """Return embedding dimension for known models."""
        name_lower = model_name.lower()
        # Exact match first
        for key, dim in KNOWN_DIMENSIONS.items():
            if key in name_lower:
                return dim
        # Fallback: match common dimension patterns
        if "3-large" in name_lower:
            return 3072
        # Default to 1024 (BGE-M3 dimension) which is the local fallback model
        logger.info(f"Unknown model '{model_name}', defaulting to {LOCAL_FALLBACK_DIM}-dim (local fallback)")
        return LOCAL_FALLBACK_DIM

    def _get_endpoint_urls(self) -> List[str]:
        """Get ordered list of endpoint URLs to try.

        Returns multiple candidate URLs to handle different provider formats:
        1. If base_url ends with '/embeddings', use it as-is (native endpoint).
        2. Also derive the standard OpenAI path (/v1/embeddings) for providers
           that need OpenAI-compatible routing.
        3. Also try stripping /v{N}/embeddings and using just /embeddings.
        """
        urls = []
        url = self.base_url.rstrip("/")

        if url.endswith("/embeddings"):
            urls.append(url)  # Native endpoint (e.g., /v2/embeddings)
            # Derive OpenAI-compatible path: /v{N}/embeddings -> /v1/embeddings
            import re
            m = re.search(r"/v\d+/embeddings$", url)
            if m:
                alt = url[:m.start()] + "/v1/embeddings"
                if alt != url:
                    urls.append(alt)
                # Also try bare /embeddings (some providers strip version)
                alt2 = url[:m.start()] + "/embeddings"
                if alt2 != url and alt2 not in urls:
                    urls.append(alt2)
        else:
            urls.append(f"{url}/embeddings")

        return urls

    def embed(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for a list of texts via direct HTTP request.

        Auto-detects the actual embedding dimension on first call.

        Args:
            texts: List of text strings.

        Returns:
            Numpy array of shape (n_texts, dimension).
        """
        if not texts:
            return np.zeros((0, self.dimension))

        # API-based embedding only (no local model fallback)
        embeddings = self._embed_api(texts)
        self._actual_dimension = embeddings.shape[1]
        return embeddings

    def _embed_api(self, texts: List[str]) -> np.ndarray:
        """Attempt embedding via remote API.

        Tries multiple endpoint URL patterns to handle different providers.

        Returns:
            Numpy array of shape (n_texts, dimension).

        Raises:
            RuntimeError: If all API endpoints fail.
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model_name,
            "input": texts if len(texts) > 1 else texts[0],
        }

        endpoints = self._get_endpoint_urls()
        last_error = None

        for endpoint in endpoints:
            try:
                with httpx.Client(timeout=120.0) as client:
                    response = client.post(endpoint, headers=headers, json=payload)
                    response.raise_for_status()
                    data = response.json()
                embeddings = self._parse_embedding_response(data, len(texts))
                return np.array(embeddings, dtype=np.float32)
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 404 and endpoint != endpoints[-1]:
                    logger.warning(f"Endpoint {endpoint} returned 404, trying next...")
                    continue
                detail = ""
                try:
                    detail = f" - {e.response.text[:200]}"
                except Exception:
                    pass
                logger.error(f"Embedding API HTTP {e.response.status_code} at {endpoint}{detail}")
            except httpx.TimeoutException as e:
                last_error = e
                logger.error(f"Embedding API timeout at {endpoint}")
            except Exception as e:
                last_error = e
                logger.error(f"Embedding API request failed at {endpoint}: {e}")

        # All API endpoints failed
        if last_error:
            detail = ""
            if isinstance(last_error, httpx.HTTPStatusError):
                try:
                    detail = f" - {last_error.response.text[:200]}"
                except Exception:
                    pass
                raise RuntimeError(f"Embedding API error ({last_error.response.status_code}){detail}") from last_error
            raise RuntimeError(f"Embedding API request failed: {last_error}") from last_error

    _local_model = None

    def _embed_local(self, texts: List[str]) -> np.ndarray:
        """Fallback embedding using local sentence-transformers model.

        Uses BGE-M3 (1024-dim) which matches the existing FAISS index created
        by the original BGEEmbedder, so no re-indexing is required.

        Downloads the model on first use (~2.2GB, cached locally).

        Returns:
            Numpy array of shape (n_texts, dimension).
        """
        try:
            if APIEmbedder._local_model is None:
                logger.info(f"Loading local embedding model: {LOCAL_FALLBACK_MODEL} (~2.2GB, first time may be slow)")
                from sentence_transformers import SentenceTransformer
                APIEmbedder._local_model = SentenceTransformer(LOCAL_FALLBACK_MODEL)
                logger.info("Local embedding model loaded successfully")
            model = APIEmbedder._local_model
            embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            return np.array(embeddings, dtype=np.float32)
        except ImportError:
            logger.error("sentence-transformers not installed. Run: pip install sentence-transformers")
            raise RuntimeError(
                "No embedding API available and sentence-transformers is not installed. "
                "Please install it: pip install sentence-transformers"
            )
        except Exception as e:
            logger.error(f"Local embedding fallback also failed: {e}")
            raise RuntimeError(
                f"All embedding methods failed. API returned an error and local model could not be loaded. "
                f"Local model error: {e}"
            ) from e

    def _parse_embedding_response(self, data: dict, expected_count: int) -> List[List[float]]:
        """Parse embeddings from various API response formats.

        Supports:
        1. Standard OpenAI format: {"data": [{"embedding": [...], ...}, ...]}
        2. Xunfei/other format: {"embeddings": [[...], [...]]}
        3. {"data": {"embeddings": [[...], [...]]}}
        """
        # Format 1: Standard OpenAI
        if "data" in data and isinstance(data["data"], list):
            items = data["data"]
            if items and isinstance(items[0], dict) and "embedding" in items[0]:
                return [item["embedding"] for item in items]
            if items and isinstance(items[0], (list, tuple)):
                return items

        # Format 2: Direct embeddings array
        if "embeddings" in data:
            emb = data["embeddings"]
            if isinstance(emb, list) and emb and isinstance(emb[0], (list, tuple)):
                return emb
            if isinstance(emb, dict) and "data" in emb:
                return [item["embedding"] for item in emb["data"]]

        # Format 3: Wrapped in data.embeddings
        if isinstance(data.get("data"), dict) and "embeddings" in data["data"]:
            return data["data"]["embeddings"]

        # Format 4: Response is a flat list
        if isinstance(data, list):
            return data

        raise ValueError(f"Unrecognized embedding response format. Keys: {list(data.keys()) if isinstance(data, dict) else type(data).__name__}")

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a single query string.

        Args:
            query: Query string.

        Returns:
            Embedding vector.
        """
        return self.embed([query])[0]

    def embed_chunks(self, chunks: List[str]) -> np.ndarray:
        """Embed document chunks.

        Args:
            chunks: List of chunk texts.

        Returns:
            Embedding matrix.
        """
        return self.embed(chunks)
