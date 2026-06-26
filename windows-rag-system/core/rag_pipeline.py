"""RAG pipeline orchestrator for Windows RAG System."""
from typing import List, Dict, Any, Generator
from dataclasses import dataclass

from core.retriever import DocumentRetriever
from llm.gateway import LLMGateway
from utils.logger import setup_logger

logger = setup_logger("rag_pipeline")


@dataclass
class RAGAnswer:
    """Structured RAG response."""
    answer: str
    sources: List[Dict[str, Any]]
    query: str
    context: str


class RAGPipeline:
    """Orchestrates retrieval + generation for Q&A."""

    def __init__(self, retriever: DocumentRetriever, llm_gateway: LLMGateway):
        """Initialize pipeline.

        Args:
            retriever: Document retriever instance.
            llm_gateway: LLM gateway instance.
        """
        self.retriever = retriever
        self.llm = llm_gateway

    def answer(self, query: str, top_k: int | None = None, stream: bool = False) -> RAGAnswer | Generator[str, None, None]:
        """Generate answer for query.

        Args:
            query: User question.
            top_k: Override retrieval count.
            stream: If True, yield token chunks instead of full answer.

        Returns:
            RAGAnswer or generator of token strings.
        """
        # Retrieve context
        try:
            results = self.retriever.retrieve(query, top_k=top_k)
        except Exception as e:
            logger.warning(f"Retrieval failed (embedding issue?), answering from LLM knowledge: {e}")
            results = []

        if not results:
            if stream:
                def _fallback():
                    yield from self.llm.stream_chat(query, "No specific documents found. Answer based on general knowledge.")
                return _fallback()
            answer = self.llm.chat(query, "No specific documents found. Answer based on general knowledge.")
            return RAGAnswer(
                answer=answer,
                sources=[],
                query=query,
                context="",
            )

        # Build context from retrieved chunks using full chunk content to preserve tables
        MAX_CONTEXT_CHARS = 150000
        context_parts = []
        total_chars = 0

        for i, r in enumerate(results):
            content = r.get("content", "")
            source = f"[{i+1}] {r.get('source', 'Unknown')}"
            part = f"{source}\n{content}"
            if total_chars + len(part) > MAX_CONTEXT_CHARS:
                if not context_parts:
                    context_parts.append(part[:MAX_CONTEXT_CHARS])
                break
            context_parts.append(part)
            total_chars += len(part)

        context = "\n\n---\n\n".join(context_parts)
        logger.info(f"Built context: {len(context)} chars from {len(context_parts)} chunks")

        if stream:
            return self.llm.stream_chat(query, context)

        answer = self.llm.chat(query, context)

        logger.info(f"LLM answer: {len(answer)} chars, preview={answer[:80] if answer else 'EMPTY!'}")

        return RAGAnswer(
            answer=answer,
            sources=results,
            query=query,
            context=context,
        )
