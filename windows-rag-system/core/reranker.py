"""Reranker module for Windows RAG System.

Provides LLM-based reranking for retrieved documents.
Creates its own OpenAI client using the reranker provider's config,
independent of the chat LLM gateway.
"""
from typing import List, Dict, Any, Optional
from openai import OpenAI

from utils.logger import setup_logger

logger = setup_logger("reranker")


class Reranker:
    """Reranks retrieved documents using LLM-based scoring."""

    def __init__(self, model: str, base_url: str, api_key: str):
        """Initialize reranker with its own API client.

        Args:
            model: Model name for reranking (e.g., "Qwen3-Reranker-0.6B").
            base_url: Base URL for the reranker provider's API.
            api_key: API key for the reranker provider.
        """
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = OpenAI(base_url=base_url, api_key=api_key or "dummy")

    def rerank(self, query: str, results: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        """Rerank results using LLM-based relevance scoring.

        Args:
            query: User query.
            results: Retrieved documents from vector store.
            top_k: Number of top results to return.

        Returns:
            Reranked and filtered results.
        """
        if not self.client or len(results) <= top_k:
            return results[:top_k]

        # Detect if this is an Nvidia ranking model
        is_nvidia = "nvidia" in self.model.lower() or "nvidia" in self.base_url.lower() or "nv-rerank" in self.model.lower()

        if is_nvidia:
            try:
                # 1. Automatically resolve the specialized ranking URL
                if self.base_url.endswith("/v1"):
                    ranking_url = f"{self.base_url}/ranking"
                else:
                    ranking_url = f"{self.base_url}/v1/ranking"

                # 2. Format payload according to Nvidia NIM specifications
                passages = [{"text": r.get("content", "")} for r in results]
                payload = {
                    "model": self.model,
                    "query": {"text": query},
                    "passages": passages
                }

                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }

                import requests
                logger.info(f"Routing to Nvidia ranking URL: {ranking_url} for model {self.model}")
                response = requests.post(ranking_url, headers=headers, json=payload, timeout=30.0)
                
                # If the specialized ranking endpoint is supported, process it
                if response.status_code == 200:
                    data = response.json()
                    rankings = data.get("rankings", [])

                    # Assign rerank_score (logit) to each result
                    for r in results:
                        r["rerank_score"] = -99.0

                    for item in rankings:
                        idx = item.get("index", -1)
                        logit = item.get("logit", -99.0)
                        if 0 <= idx < len(results):
                            results[idx]["rerank_score"] = float(logit)
                            results[idx]["original_rank"] = idx + 1

                    # Sort by rerank score descending
                    results.sort(key=lambda x: x.get("rerank_score", -99.0), reverse=True)
                    logger.info(f"Nvidia ranking successful. Top score: {results[0].get('rerank_score')}")
                    return results[:top_k]
                else:
                    logger.warning(f"Nvidia ranking URL returned status {response.status_code}, falling back to conversational chat")
            except Exception as e:
                logger.warning(f"Nvidia ranking failed: {e}, falling back to conversational chat")

        # Fallback to conversational chat-based reranking
        try:
            # Build scoring prompt
            docs_text = "\n\n".join(
                f"[{i+1}] {r.get('content', '')[:500]}"
                for i, r in enumerate(results)
            )

            system_prompt = """You are a relevance scoring assistant. Rate each document's relevance to the query on a scale of 1-10.

Respond ONLY with a JSON array in this exact format:
[{"id": 1, "score": 8}, {"id": 2, "score": 3}, ...]

Rules:
- Score 10 = perfectly relevant, directly answers the query
- Score 1 = completely irrelevant
- Be objective and consistent"""

            user_prompt = f"""Query: {query}

Documents:
{docs_text}

Score each document (1-10). Return JSON array only."""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=1000,
            )
            response_text = response.choices[0].message.content or ""

            # Parse JSON scores
            import json
            scores = self._parse_scores(response_text, len(results))

            # Attach scores and sort
            for i, (result, score) in enumerate(zip(results, scores)):
                result["rerank_score"] = score
                result["original_rank"] = i + 1

            # Sort by rerank score descending
            results.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)

            logger.info(f"Reranked {len(results)} documents, top score: {results[0].get('rerank_score', 0)}")
            return results[:top_k]

        except Exception as e:
            logger.warning(f"Reranking failed: {e}, returning original results")
            return results[:top_k]

    def _parse_scores(self, response: str, num_docs: int) -> List[float]:
        """Parse scores from LLM response.

        Args:
            response: LLM response text.
            num_docs: Number of documents.

        Returns:
            List of scores.
        """
        import json
        import re

        # Try to extract JSON array
        try:
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                if isinstance(data, list):
                    scores = [0.0] * num_docs
                    for item in data:
                        if isinstance(item, dict):
                            idx = item.get("id", 0) - 1
                            score = item.get("score", 0)
                            if 0 <= idx < num_docs:
                                scores[idx] = float(score)
                    return scores
        except Exception:
            pass

        # Fallback: try to parse numbers
        try:
            match = re.findall(r'\d+', response)
            if match:
                scores = [float(x) for x in match[:num_docs]]
                while len(scores) < num_docs:
                    scores.append(5.0)
                return scores
        except Exception:
            pass

        return [5.0] * num_docs
