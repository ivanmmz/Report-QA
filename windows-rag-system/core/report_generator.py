"""Report generator module for Windows RAG System.

Generates structured reports from document data using RAG retrieval
and LLM-powered analysis. Supports multiple report templates:
- Summary Report
- Time-Based Analysis
- Trend Analysis
- Comparison Report
- Metric Dashboard
"""
import json
from typing import List, Dict, Any, Optional, Generator
from dataclasses import dataclass, asdict
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

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dict.

        Returns:
            Dict representation.
        """
        return {
            "title": self.title,
            "type": self.type,
            "generated_at": self.generated_at,
            "summary": self.summary,
            "metadata": self.metadata,
            "sections": [asdict(s) for s in self.sections],
        }

    def to_json(self) -> str:
        """Convert report to JSON string.

        Returns:
            JSON string.
        """
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


class ReportGenerator:
    """Generates structured reports from document data."""

    REPORT_TYPES = {
        "summary": "Executive Summary",
        "time_analysis": "Time-Based Analysis",
        "trend": "Trend Analysis",
        "comparison": "Comparison Report",
        "metrics": "Metrics Dashboard",
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

        # Step 3: Generate report based on type
        generator_method = getattr(self, f"_generate_{report_type}", self._generate_custom)
        report = generator_method(
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

    def _generate_summary(
        self,
        query: str,
        context: str,
        sources: List[Dict[str, Any]],
        data_points: List[ExtractedDataPoint],
        **kwargs,
    ) -> Report:
        """Generate executive summary report."""
        system_prompt = """You are an expert report writer. Generate a concise executive summary.

Rules:
- Focus on key findings and actionable insights
- Include specific numbers and metrics when available
- Structure with clear headings
- Be factual and objective
- Use markdown formatting"""

        user_prompt = f"""Generate an executive summary based on the following document analysis:

Retrieved Context:
{context}

Extracted Data Points:
{self._format_data_points(data_points[:50])}

Generate a structured executive summary with:
1. Key Findings
2. Important Metrics
3. Recommendations
4. Data Sources"""

        answer = self.llm.chat(user_prompt, "", system_prompt)

        sections = self._parse_sections(answer)

        return Report(
            title="Executive Summary Report",
            type="summary",
            generated_at=datetime.now().isoformat(),
            summary=answer[:500] + "..." if len(answer) > 500 else answer,
            sections=sections,
            metadata={
                "sources": list(set(s.get("source", "Unknown") for s in sources)),
                "data_points": len(data_points),
                "query": query,
            },
        )

    def _generate_time_analysis(
        self,
        query: str,
        context: str,
        sources: List[Dict[str, Any]],
        data_points: List[ExtractedDataPoint],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs,
    ) -> Report:
        """Generate time-based analysis report."""
        dates = self.extractor.get_unique_dates(data_points)
        date_range = ""
        if start_date and end_date:
            date_range = f"Date Range: {start_date} to {end_date}"
        elif dates:
            date_range = f"Available Dates: {dates[0]} to {dates[-1]}"

        system_prompt = """You are a data analyst specializing in time-based analysis.
Generate a detailed time-based analysis report.

Rules:
- Identify trends over time
- Highlight significant changes or events
- Compare periods if applicable
- Include specific dates and metrics
- Use markdown tables for data presentation"""

        user_prompt = f"""Generate a time-based analysis report.

{date_range}

Retrieved Context:
{context}

Extracted Data Points:
{self._format_data_points(data_points[:50])}

Generate a report with:
1. Timeline Overview
2. Key Events by Period
3. Metric Changes Over Time
4. Trends and Patterns
5. Insights and Recommendations"""

        answer = self.llm.chat(user_prompt, "", system_prompt)
        sections = self._parse_sections(answer)

        return Report(
            title="Time-Based Analysis Report",
            type="time_analysis",
            generated_at=datetime.now().isoformat(),
            summary=date_range,
            sections=sections,
            metadata={
                "sources": list(set(s.get("source", "Unknown") for s in sources)),
                "date_range": {"start": start_date, "end": end_date, "available": dates},
                "data_points": len(data_points),
            },
        )

    def _generate_trend(
        self,
        query: str,
        context: str,
        sources: List[Dict[str, Any]],
        data_points: List[ExtractedDataPoint],
        **kwargs,
    ) -> Report:
        """Generate trend analysis report."""
        system_prompt = """You are a trend analysis expert. Identify and analyze trends in the data.

Rules:
- Identify upward/downward trends
- Calculate change rates if possible
- Compare with benchmarks if mentioned
- Predict future trends based on data
- Use specific numbers and percentages"""

        user_prompt = f"""Generate a trend analysis report.

Retrieved Context:
{context}

Extracted Data Points:
{self._format_data_points(data_points[:50])}

Generate a report with:
1. Trend Overview
2. Key Metrics Trends
3. Period Comparisons
4. Anomalies and Significant Changes
5. Future Projections
6. Recommendations"""

        answer = self.llm.chat(user_prompt, "", system_prompt)
        sections = self._parse_sections(answer)

        return Report(
            title="Trend Analysis Report",
            type="trend",
            generated_at=datetime.now().isoformat(),
            summary="",
            sections=sections,
            metadata={
                "sources": list(set(s.get("source", "Unknown") for s in sources)),
                "data_points": len(data_points),
            },
        )

    def _generate_comparison(
        self,
        query: str,
        context: str,
        sources: List[Dict[str, Any]],
        data_points: List[ExtractedDataPoint],
        **kwargs,
    ) -> Report:
        """Generate comparison report."""
        system_prompt = """You are a comparison analysis expert. Compare data across different dimensions.

Rules:
- Identify comparable items
- Use tables for side-by-side comparisons
- Highlight differences and similarities
- Provide quantitative comparisons
- Draw conclusions from comparisons"""

        user_prompt = f"""Generate a comparison report.

Retrieved Context:
{context}

Extracted Data Points:
{self._format_data_points(data_points[:50])}

Generate a report with:
1. Comparison Overview
2. Side-by-Side Comparisons
3. Key Differences
4. Key Similarities
5. Conclusions and Recommendations"""

        answer = self.llm.chat(user_prompt, "", system_prompt)
        sections = self._parse_sections(answer)

        return Report(
            title="Comparison Report",
            type="comparison",
            generated_at=datetime.now().isoformat(),
            summary="",
            sections=sections,
            metadata={
                "sources": list(set(s.get("source", "Unknown") for s in sources)),
                "data_points": len(data_points),
            },
        )

    def _generate_metrics(
        self,
        query: str,
        context: str,
        sources: List[Dict[str, Any]],
        data_points: List[ExtractedDataPoint],
        **kwargs,
    ) -> Report:
        """Generate metrics dashboard report."""
        metrics = [dp for dp in data_points if dp.type == "metric"]

        system_prompt = """You are a metrics and KPI specialist. Create a metrics dashboard report.

Rules:
- Organize metrics by category
- Highlight key performance indicators
- Provide context for each metric
- Include benchmarks if available
- Use tables for metric presentation"""

        user_prompt = f"""Generate a metrics dashboard report.

Retrieved Context:
{context}

Extracted Metrics:
{self._format_data_points(metrics[:50])}

Generate a report with:
1. KPI Overview
2. Performance Metrics by Category
3. Key Metrics Table
4. Benchmarks and Targets
5. Insights and Recommendations"""

        answer = self.llm.chat(user_prompt, "", system_prompt)
        sections = self._parse_sections(answer)

        # Add a data section with raw metrics
        metrics_table = self._format_metrics_table(metrics)
        sections.insert(0, ReportSection(
            title="Raw Metrics Data",
            content=metrics_table,
            type="table",
            sources=list(set(s.get("source", "Unknown") for s in sources)),
            confidence=0.9,
        ))

        return Report(
            title="Metrics Dashboard Report",
            type="metrics",
            generated_at=datetime.now().isoformat(),
            summary=f"Total metrics extracted: {len(metrics)}",
            sections=sections,
            metadata={
                "sources": list(set(s.get("source", "Unknown") for s in sources)),
                "metrics_count": len(metrics),
            },
        )

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

    def _format_metrics_table(self, metrics: List[ExtractedDataPoint]) -> str:
        """Format metrics as markdown table.

        Args:
            metrics: List of metric data points.

        Returns:
            Markdown table string.
        """
        if not metrics:
            return "No metrics extracted."

        lines = [
            "| Metric | Value | Source | Page |",
            "|--------|-------|--------|------|",
        ]
        for dp in metrics[:50]:  # Limit to 50
            lines.append(f"| {dp.context[:50]} | {dp.value} | {dp.source} | {dp.page} |")
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

    def stream_generate(
        self,
        report_type: str,
        query: str = "",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        custom_prompt: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """Stream generate a report (yield tokens).

        Args:
            report_type: Report type.
            query: Optional query.
            start_date: Optional start date.
            end_date: Optional end date.
            filters: Optional filters.
            custom_prompt: Optional custom prompt.

        Yields:
            Token strings.
        """
        report = self.generate(
            report_type=report_type,
            query=query,
            start_date=start_date,
            end_date=end_date,
            filters=filters,
            custom_prompt=custom_prompt,
        )
        # Yield the markdown
        yield report.to_markdown()
