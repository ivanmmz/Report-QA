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
        MAX_CONTEXT_CHARS = 30000
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

        import logging
        logging.getLogger("rag_pipeline").info(f"LLM answer: {len(answer)} chars, preview={answer[:80] if answer else 'EMPTY!'}")

        return RAGAnswer(
            answer=answer,
            sources=results,
            query=query,
            context=context,
        )

    def answer_with_citations(self, query: str, top_k: int | None = None) -> Dict[str, Any]:
        """Generate answer with formatted citations.

        Args:
            query: User question.
            top_k: Override retrieval count.

        Returns:
            Dict with answer, sources, and formatted citations.
        """
        rag_answer = self.answer(query, top_k)
        import logging as _lg
        _lg.getLogger("rag_pipeline").info(f"answer_with_citations: type={type(rag_answer).__name__}")
        if isinstance(rag_answer, RAGAnswer):
            _lg.getLogger("rag_pipeline").info(f"RAGAnswer answer len={len(rag_answer.answer)}, preview={rag_answer.answer[:80] if rag_answer.answer else 'EMPTY!'}")
            citations = []
            for i, src in enumerate(rag_answer.sources):
                citations.append({
                    "id": i + 1,
                    "source": src.get("source", "Unknown"),
                    "score": round(src.get("score", 0.0), 4),
                    "snippet": src.get("content", "")[:200] + "...",
                })
            
            return {
                "answer": rag_answer.answer,
                "query": query,
                "citations": citations,
                "sources_count": len(citations),
            }
        
        return {"answer": "", "query": query, "citations": [], "sources_count": 0}
