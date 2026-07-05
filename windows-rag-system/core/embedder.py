"""API-based embedding module for Windows RAG System.

Makes direct HTTP requests to the embedding provider's API endpoint.
"""
from typing import List, Optional
import numpy as np
import httpx

from utils.logger import setup_logger

logger = setup_logger("embedder")

# Max input tokens for common embedding models.
# Used to pre-split oversized chunks before sending to the API.
# Falls back to 4096 for unknown models (safe conservative default).
MODEL_MAX_TOKENS = {
    "text-embedding-3-large": 8191,
    "text-embedding-3-small": 8191,
    "text-embedding-ada-002": 8191,
    "nvidia/nv-embed-v1": 4096,
    "Qwen3-Embedding-8B": 8192,
    "bge-m3": 8192,
}

LOCAL_FALLBACK_DIM = 1024

KNOWN_DIMENSIONS = {
    "nvidia/nv-embed-v1": 4096,
    "Qwen3-Embedding-8B": 4096,
    "bge-m3": 1024,
    "text-embedding-3-large": 3072,
    "text-embedding-3-small": 1536,
    "text-embedding-ada-002": 1536,
}


class APIEmbedder:
    """Embedding generator with API-first strategy."""

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
        
        # Resolve dimension if not provided
        if not dimension:
            dimension = KNOWN_DIMENSIONS.get(model_name)
            if not dimension:
                for k, v in KNOWN_DIMENSIONS.items():
                    if k in model_name:
                        dimension = v
                        break
        
        self._declared_dimension = dimension or LOCAL_FALLBACK_DIM
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

    def detect_dimension(self, probe_text: str = "hello") -> int:
        """Probe the API to detect the actual embedding dimension.

        Sends one API call and reads the vector length from the response.
        Stores the result internally and updates ``dimension`` for subsequent use.
        Falls back to the declared dimension (from KNOWN_DIMENSIONS or fallback)
        if the API call fails.

        Args:
            probe_text: Dummy text to embed for dimension detection.

        Returns:
            The detected embedding dimension.
        """
        try:
            embeddings = self._embed_api([probe_text])
            actual_dim = embeddings.shape[1]
            self._actual_dimension = actual_dim
            logger.info(
                f"Auto-detected dimension {actual_dim} for model "
                f"'{self.model_name}' (was {self._declared_dimension})"
            )
            if actual_dim != self._declared_dimension:
                logger.info(
                    f"KNOWN_DIMENSIONS entry for '{self.model_name}' is stale "
                    f"(declared {self._declared_dimension}, actual {actual_dim}). "
                    f"Update KNOWN_DIMENSIONS in embedder.py to silence this warning."
                )
            return actual_dim
        except Exception as e:
            logger.warning(
                f"Could not auto-detect dimension for '{self.model_name}': {e}. "
                f"Using declared dimension {self._declared_dimension}."
            )
            return self._declared_dimension

    def _get_dimension(self, model_name: str) -> int:
        """Return default embedding dimension."""
        return LOCAL_FALLBACK_DIM

    def _get_max_tokens(self, model_name: str) -> int:
        """Return max input tokens for the model. Used for chunk sizing."""
        name_lower = model_name.lower()
        for key, tokens in MODEL_MAX_TOKENS.items():
            if key in name_lower:
                return tokens
        return 4096  # safe default

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

        If a text exceeds the model's token limit, it is split by sentences
        and embeddings are averaged — this avoids silent file-drops during
        batch indexing.

        Args:
            texts: List of text strings.

        Returns:
            Numpy array of shape (n_texts, dimension).
        """
        if not texts:
            return np.zeros((0, self.dimension))

        max_chars = self._get_max_tokens(self.model_name)
        needs_split = [i for i, t in enumerate(texts) if len(t) > max_chars]

        if needs_split:
            split_texts = []
            mapping = []
            for i, t in enumerate(texts):
                if i in needs_split:
                    parts = self._split_oversized(t, max_chars)
                    split_texts.extend(parts)
                    mapping.extend([i] * len(parts))
                else:
                    split_texts.append(t)
                    mapping.append(i)

            logger.info(
                f"Splitting {len(needs_split)} oversized text(s) "
                f"(max {max_chars} chars each)"
            )

            all_embs = self._embed_api(split_texts)
            self._actual_dimension = all_embs.shape[1]

            merged = np.zeros((len(texts), all_embs.shape[1]), dtype=np.float32)
            counts = np.zeros(len(texts), dtype=np.int32)
            for j, orig_idx in enumerate(mapping):
                merged[orig_idx] += all_embs[j]
                counts[orig_idx] += 1
            for i in range(len(texts)):
                if counts[i] > 0:
                    merged[i] /= counts[i]
            return merged

        embeddings = self._embed_api(texts)
        self._actual_dimension = embeddings.shape[1]
        if self._actual_dimension != self._declared_dimension:
            logger.warning(
                f"Embedding model '{self.model_name}' returned {self._actual_dimension}-dim vectors "
                f"but was declared as {self._declared_dimension}-dim. "
                f"Update KNOWN_DIMENSIONS in embedder.py to match the actual dimension."
            )
        return embeddings

    def _split_oversized(self, text: str, max_chars: int) -> List[str]:
        """Split text at sentence boundaries so each piece ≤ max_chars."""
        import re
        parts = re.split(r'(?<=[。！？.!?\n])\s*', text)
        result = []
        current = ""
        for part in parts:
            if len(current) + len(part) > max_chars:
                if current:
                    result.append(current)
                current = part
            else:
                current += part
        if current:
            result.append(current)
        final = []
        for r in result:
            if len(r) > max_chars:
                for i in range(0, len(r), max_chars):
                    final.append(r[i:i + max_chars])
            else:
                final.append(r)
        return final

    def _embed_api(self, texts: List[str]) -> np.ndarray:
        """Attempt embedding via remote API with batching, retry, and per-chunk fallback.

        Returns:
            Numpy array of shape (n_texts, dimension).
        """
        # Batch texts to prevent Payload Too Large (413) or Token Limit (400) errors
        batch_size = 16
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_embs = self._embed_batch_api(batch_texts)
            all_embeddings.extend(batch_embs)
            
        return np.array(all_embeddings, dtype=np.float32)

    def _embed_batch_api(self, texts: List[str]) -> np.ndarray:
        """Attempt embedding a single batch via remote API with retry and per-chunk fallback."""
        import time
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
            for attempt in range(3):
                try:
                    with httpx.Client(timeout=120.0) as client:
                        response = client.post(endpoint, headers=headers, json=payload)
                        response.raise_for_status()
                        data = response.json()
                    embeddings = self._parse_embedding_response(data, len(texts))
                    return np.array(embeddings, dtype=np.float32)
                except httpx.HTTPStatusError as e:
                    status = e.response.status_code
                    detail = ""
                    try:
                        detail = f" - {e.response.text[:200]}"
                    except Exception:
                        pass

                    # Fall back to per-chunk if token limit (400), payload too large (413), or server errors (500/502/503/504)
                    if (status == 400 and "token" in (e.response.text or "").lower()) or status in (413, 500, 502, 503, 504):
                        logger.warning(
                            f"Limit reached (HTTP {status}) at {endpoint} with batch size {len(texts)}, "
                            f"falling back to per-chunk embedding"
                        )
                        return self._embed_one_by_one(texts, endpoint)

                    if status in (429, 500, 502, 503) and attempt < 2:
                        wait = 2 ** attempt
                        logger.warning(
                            f"HTTP {status} at {endpoint} (attempt {attempt + 1}/3), "
                            f"retrying in {wait}s{detail}"
                        )
                        time.sleep(wait)
                        continue

                    last_error = e
                    logger.error(f"Embedding API HTTP {status} at {endpoint}{detail}")
                    break

                except httpx.TimeoutException as e:
                    last_error = e
                    if attempt < 2:
                        wait = 2 ** attempt
                        logger.warning(
                            f"Timeout at {endpoint} (attempt {attempt + 1}/3), "
                            f"retrying in {wait}s"
                        )
                        time.sleep(wait)
                        continue
                    logger.error(f"Embedding API timeout at {endpoint}")

                except Exception as e:
                    last_error = e
                    logger.error(f"Embedding API request failed at {endpoint}: {e}")
                    break

        if last_error:
            detail = ""
            if isinstance(last_error, httpx.HTTPStatusError):
                try:
                    detail = f" - {last_error.response.text[:200]}"
                except Exception:
                    pass
                raise RuntimeError(
                    f"Embedding API error ({last_error.response.status_code}){detail}"
                ) from last_error
            raise RuntimeError(
                f"Embedding API request failed: {last_error}"
            ) from last_error

    def _embed_one_by_one(self, texts: List[str], endpoint: str) -> np.ndarray:
        """Fallback: embed each text individually to work around token limits."""
        import time
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        all_embeddings = []
        for idx, text in enumerate(texts):
            payload = {"model": self.model_name, "input": text}
            last_err = None
            for attempt in range(3):
                try:
                    with httpx.Client(timeout=120.0) as client:
                        r = client.post(endpoint, headers=headers, json=payload)
                        r.raise_for_status()
                        data = r.json()
                    emb = self._parse_embedding_response(data, 1)
                    all_embeddings.append(emb[0])
                    break
                except httpx.HTTPStatusError as e:
                    status = e.response.status_code
                    if status in (429, 500, 502, 503, 504) and attempt < 2:
                        wait = 2 ** attempt
                        logger.warning(
                            f"HTTP {status} at {endpoint} during one-by-one (attempt {attempt + 1}/3) on chunk {idx}, "
                            f"retrying in {wait}s"
                        )
                        time.sleep(wait)
                        continue
                    last_err = e
                    break
                except Exception as e:
                    if attempt < 2:
                        wait = 2 ** attempt
                        time.sleep(wait)
                        continue
                    last_err = e
                    break
            if last_err:
                raise last_err
        return np.array(all_embeddings, dtype=np.float32)

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
