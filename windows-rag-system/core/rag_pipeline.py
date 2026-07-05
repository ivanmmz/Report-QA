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
    thinking: str | None = None


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

    def answer(
        self,
        query: str,
        history: List[Dict[str, str]] = None,
        top_k: int | None = None,
        stream: bool = False,
        canvas_content: str | None = None,
        thinking_intensity: str | None = None,
        intent: str | None = None,
    ) -> RAGAnswer | Generator[str, None, None]:
        """Generate answer for query.

        Args:
            query: User question.
            top_k: Override retrieval count.
            stream: If True, yield token chunks instead of full answer.
            canvas_content: Optional canvas document content.
            thinking_intensity: Optional intensity ('low', 'medium', 'high').
            intent: Optional pre-classified intent ('modify_canvas', 'read_canvas',
                'search_kb'). If provided, skip re-classification. If None and canvas_content
                is set, the LLM will be called to classify the intent.

        Returns:
            RAGAnswer or generator of token strings.
        """
        # Use the pre-classified intent if provided, otherwise classify now.
        if intent is None:
            intent = "search_kb"
            if canvas_content:
                intent = self.llm.classify_intent(query, canvas_content)
        logger.info(f"Intent: {intent}")

        # Retrieve context if intent is search_kb (canvas-only intents are handled
        # upstream in query_rag.py, but we still no-op here as a safety net).
        results = []
        if intent == "search_kb":
            try:
                results = self.retriever.retrieve(query, top_k=top_k)
            except Exception as e:
                logger.warning(f"Retrieval failed (embedding issue?), answering from LLM knowledge: {e}")
                results = []

        if not results:
            if stream:
                def _fallback():
                    yield from self.llm.stream_chat(query, "No specific documents found. Answer based on general knowledge.", history=history, intent=intent)
                return _fallback()
            # Construct context from canvas if present
            context = ""
            if canvas_content:
                context = (
                    "--- CURRENT CANVAS CONTENT (The document the user is currently viewing/editing) ---\n"
                    f"{canvas_content}\n"
                    "--- END OF CURRENT CANVAS CONTENT ---\n\n"
                )
            answer, thinking = self.llm.chat(query, context, history=history, thinking_intensity=thinking_intensity, intent=intent)
            return RAGAnswer(
                answer=answer,
                sources=[],
                query=query,
                context=context,
                thinking=thinking,
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
        if canvas_content:
            canvas_block = (
                "--- CURRENT CANVAS CONTENT (The document the user is currently viewing/editing) ---\n"
                f"{canvas_content}\n"
                "--- END OF CURRENT CANVAS CONTENT ---\n\n"
            )
            context = canvas_block + context
        logger.info(f"Built context: {len(context)} chars from {len(context_parts)} chunks (canvas content included: {bool(canvas_content)})")

        if stream:
            return self.llm.stream_chat(query, context, history=history, thinking_intensity=thinking_intensity, intent=intent)

        answer, thinking = self.llm.chat(query, context, history=history, thinking_intensity=thinking_intensity, intent=intent)

        logger.info(f"LLM answer: {len(answer)} chars, preview={answer[:80] if answer else 'EMPTY!'}")

        return RAGAnswer(
            answer=answer,
            sources=results,
            query=query,
            context=context,
            thinking=thinking,
        )
