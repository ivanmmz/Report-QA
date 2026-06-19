"""Report generator module for Windows RAG System.

Generates structured reports from document data using RAG retrieval
and LLM-powered analysis. Supports multiple report templates:
- Summary Report
- Time-Based Analysis
- Trend Analysis
- Comparison Report
- Metric Dashboard
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from utils.logger import setup_logger
from core.data_extractor import DataExtractor, ExtractedDataPoint
from core.rag_pipeline import RAGPipeline
from llm.gateway import LLMGateway

logger = setup_logger("report_generator")


@dataclass
class ReportSection:
    """Represents a section of a report."""
    title: str
    content: str
    type: str  # 'text', 'data', 'chart', 'table', 'summary'
    sources: List[str]
    confidence: float = 1.0


@dataclass
class Report:
    """Represents a generated report."""
    title: str
    type: str
    generated_at: str
    sections: List[ReportSection]
    metadata: Dict[str, Any]
    summary: str = ""

    def to_markdown(self) -> str:
        """Convert report to markdown format.

        Returns:
            Markdown string.
        """
        lines = [
            f"# {self.title}",
            "",
            f"**Report Type:** {self.type}  ",
            f"**Generated:** {self.generated_at}  ",
            f"**Sources:** {', '.join(self.metadata.get('sources', []))}  ",
            "",
            "---",
            "",
        ]

        if self.summary:
            lines.extend([
                "## Executive Summary",
                "",
                self.summary,
                "",
                "---",
                "",
            ])

        for section in self.sections:
            lines.extend([
                f"## {section.title}",
                "",
                f"*Type: {section.type} | Confidence: {section.confidence:.0%}*",
                "",
                section.content,
                "",
                "---",
                "",
            ])

        return "\n".join(lines)


class ReportGenerator:
    """Generates structured reports from document data."""

    REPORT_TYPES = {
        "custom": "Custom Report",
    }

    def __init__(self, rag_pipeline: RAGPipeline, llm: LLMGateway):
        """Initialize report generator.

        Args:
            rag_pipeline: Initialized RAG pipeline.
            llm: LLM gateway.
        """
        self.rag = rag_pipeline
        self.llm = llm
        self.extractor = DataExtractor()

    def _retrieve_raw_context(
        self,
        query: str,
        top_k: int = 20,
    ) -> tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Retrieve raw document chunks without LLM summarization.

        Uses the retriever directly to get full-text document chunks,
        avoiding information loss from the RAG pipeline's LLM summarization step.

        Args:
            query: Search query.
            top_k: Number of chunks to retrieve.

        Returns:
            Tuple of (context_text, chunks, sources).
        """
        try:
            results = self.rag.retriever.retrieve(query, top_k=top_k)
        except Exception as e:
            logger.warning(f"Retrieval failed: {e}")
            return "", [], []

        if not results:
            return "", [], []

        # Build context from FULL document content (not snippets)
        context_parts = []
        chunks = []
        sources = []

        for i, r in enumerate(results):
            content = r.get("content", "")
            source = r.get("source", "Unknown")
            score = r.get("score", 0.0)

            context_parts.append(
                f"[Source {i+1}: {source}]\n{content}"
            )

            chunks.append({
                "content": content,  # Full content, not truncated
                "source": source,
                "page": r.get("metadata", {}).get("page", 1),
            })

            sources.append({
                "source": source,
                "score": round(score, 4),
                "snippet": content[:300],
            })

        context = "\n\n---\n\n".join(context_parts)
        return context, chunks, sources

    def generate(
        self,
        report_type: str,
        query: str = "",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        custom_prompt: Optional[str] = None,
    ) -> Report:
        """Generate a report of specified type.

        Retrieves raw document chunks directly (not LLM summaries)
        for accurate, data-rich report generation.

        Args:
            report_type: One of REPORT_TYPES keys.
            query: Optional query to focus the report.
            start_date: Optional start date filter.
            end_date: Optional end date filter.
            filters: Optional metadata filters.
            custom_prompt: Optional custom prompt for 'custom' type.

        Returns:
            Generated Report.
        """
        if report_type not in self.REPORT_TYPES:
            raise ValueError(f"Unknown report type: {report_type}. Must be one of {list(self.REPORT_TYPES.keys())}")

        logger.info(f"Generating {report_type} report with query: {query}")

        # Step 1: Retrieve raw document chunks directly (no LLM summarization)
        search_query = query if query else "key metrics performance data energy efficiency"
        context, chunks, sources = self._retrieve_raw_context(search_query, top_k=20)

        # Step 2: Extract structured data from the raw chunks
        data_points = self.extractor.extract_from_chunks(chunks)

        # Filter by date range (now preserves all data point types)
        if start_date or end_date:
            data_points = self.extractor.filter_by_date_range(data_points, start_date, end_date)

        # Step 3: Generate custom report
        report = self._generate_custom(
            query=query,
            context=context,
            sources=sources,
            data_points=data_points,
            custom_prompt=custom_prompt,
            start_date=start_date,
            end_date=end_date,
        )

        logger.info(f"Generated report with {len(report.sections)} sections")
        return report

    def _generate_custom(
        self,
        query: str,
        context: str,
        sources: List[Dict[str, Any]],
        data_points: List[ExtractedDataPoint],
        custom_prompt: Optional[str] = None,
        **kwargs,
    ) -> Report:
        """Generate custom report based on user prompt."""
        system_prompt = """You are a professional report writer. Generate a report based on the user's request.

Rules:
- Follow the user's instructions precisely
- Use markdown formatting
- Include specific data points and numbers
- Cite sources when possible
- Be thorough and structured"""

        user_prompt = custom_prompt or f"""Generate a comprehensive report based on the following data:

Retrieved Context:
{context}

Extracted Data Points:
{self._format_data_points(data_points[:50])}

Generate a detailed report with structured sections."""

        answer = self.llm.chat(user_prompt, "", system_prompt)
        sections = self._parse_sections(answer)

        return Report(
            title="Custom Report",
            type="custom",
            generated_at=datetime.now().isoformat(),
            summary="",
            sections=sections,
            metadata={
                "sources": list(set(s.get("source", "Unknown") for s in sources)),
                "data_points": len(data_points),
                "custom_prompt": custom_prompt,
            },
        )

    def _format_data_points(self, data_points: List[ExtractedDataPoint]) -> str:
        """Format data points for prompt.

        Args:
            data_points: List of data points.

        Returns:
            Formatted string.
        """
        lines = []
        for dp in data_points:
            lines.append(f"- [{dp.type}] {dp.value} (source: {dp.source}, page: {dp.page})")
        return "\n".join(lines)

    def _parse_sections(self, text: str) -> List[ReportSection]:
        """Parse markdown text into report sections.

        Args:
            text: Markdown text.

        Returns:
            List of ReportSection.
        """
        sections = []
        current_title = "Overview"
        current_content = []
        current_type = "text"

        lines = text.split("\n")
        for line in lines:
            if line.startswith("## "):
                # Save previous section
                if current_content:
                    sections.append(ReportSection(
                        title=current_title,
                        content="\n".join(current_content).strip(),
                        type=current_type,
                        sources=[],
                        confidence=0.9,
                    ))
                current_title = line[3:].strip()
                current_content = []
                current_type = "text"
            elif line.startswith("| ") and "|" in line[2:]:
                current_type = "table"
                current_content.append(line)
            else:
                current_content.append(line)

        # Save last section
        if current_content:
            sections.append(ReportSection(
                title=current_title,
                content="\n".join(current_content).strip(),
                type=current_type,
                sources=[],
                confidence=0.9,
            ))

        if not sections:
            sections.append(ReportSection(
                title="Analysis",
                content=text,
                type="text",
                sources=[],
                confidence=0.9,
            ))

        return sections

