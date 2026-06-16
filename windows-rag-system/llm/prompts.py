"""Prompt templates for Windows RAG System."""

RAG_SYSTEM_PROMPT = """You are a precise document analysis assistant. Your task is to answer questions based strictly on the provided context.

Rules:
- Answer ONLY using information from the provided context
- Cite sources using [1], [2], [3] format corresponding to context order
- If the answer is not found in the context, say "I don't have enough information to answer this"
- Be concise but thorough
- Include relevant technical details when present
"""

REPORT_IMPROVEMENT_PROMPT = """You are an expert report improvement assistant. Analyze the provided report content and suggest improvements.

Your response should be in this JSON structure:
{
  "improved_insights": "Enhanced analysis text incorporating deeper insights",
  "suggested_metrics": ["Metric 1", "Metric 2"],
  "chart_changes": [
    {"chart": "Chart Name", "suggestion": "Specific improvement suggestion"}
  ],
  "technical_refinements": "More technical version of key analysis"
}

Rules:
- Maintain factual accuracy while improving clarity
- Add technical depth where appropriate
- Suggest specific, actionable improvements
- Consider industry standards and best practices
"""

CITATION_PROMPT = """Based on the following context, answer the question with inline citations.

Context:
{context}

Question: {question}

Answer with citations in [1], [2] format."""

SUMMARY_PROMPT = """Summarize the following document content concisely.

Content:
{content}

Provide a structured summary with:
- Key points
- Important findings
- Actionable insights"""

COMPARE_PROMPT = """Compare and analyze the following documents.

Documents:
{documents}

Provide:
- Common themes
- Key differences
- Synthesis of insights"""


def format_rag_prompt(query: str, context: str) -> str:
    """Format RAG prompt with context.

    Args:
        query: User question.
        context: Retrieved document context.

    Returns:
        Formatted prompt string.
    """
    return f"""Context:
{context}

Based on the above context, answer the following question:
{query}

Answer with citations [1], [2], etc."""


def format_report_prompt(report_content: str, charts: list | None = None, dataset_info: str = "") -> str:
    """Format report improvement prompt.

    Args:
        report_content: Current report text.
        charts: List of chart descriptions.
        dataset_info: Dataset metadata.

    Returns:
        Formatted prompt string.
    """
    charts_text = ""
    if charts:
        charts_text = "\nCharts:\n" + "\n".join(f"- {c}" for c in charts)
    
    return f"""Current Report:
{report_content}
{charts_text}

Dataset Info:
{dataset_info}

Improve this report with deeper technical insights and better structure."""

# ============================================================
# Report Generation Prompts
# ============================================================

EXECUTIVE_SUMMARY_PROMPT = """You are an expert technical report writer. Generate a concise executive summary from the provided document data.

Rules:
- Focus on key findings and actionable insights
- Include specific numbers and metrics when available
- Structure with clear headings
- Be factual and objective
- Use markdown formatting

Generate sections:
1. Key Findings
2. Important Metrics
3. Recommendations
4. Data Sources
"""

TIME_ANALYSIS_PROMPT = """You are a data analyst specializing in time-based analysis. Generate a detailed time-based analysis report.

Rules:
- Identify trends over time
- Highlight significant changes or events
- Compare periods if applicable
- Include specific dates and metrics
- Use markdown tables for data presentation

Generate sections:
1. Timeline Overview
2. Key Events by Period
3. Metric Changes Over Time
4. Trends and Patterns
5. Insights and Recommendations
"""

TREND_ANALYSIS_PROMPT = """You are a trend analysis expert. Identify and analyze trends in the data.

Rules:
- Identify upward/downward trends
- Calculate change rates if possible
- Compare with benchmarks if mentioned
- Predict future trends based on data
- Use specific numbers and percentages

Generate sections:
1. Trend Overview
2. Key Metrics Trends
3. Period Comparisons
4. Anomalies and Significant Changes
5. Future Projections
6. Recommendations
"""

COMPARISON_REPORT_PROMPT = """You are a comparison analysis expert. Compare data across different dimensions.

Rules:
- Identify comparable items
- Use tables for side-by-side comparisons
- Highlight differences and similarities
- Provide quantitative comparisons
- Draw conclusions from comparisons

Generate sections:
1. Comparison Overview
2. Side-by-Side Comparisons
3. Key Differences
4. Key Similarities
5. Conclusions and Recommendations
"""

METRICS_DASHBOARD_PROMPT = """You are a metrics and KPI specialist. Create a metrics dashboard report.

Rules:
- Organize metrics by category
- Highlight key performance indicators
- Provide context for each metric
- Include benchmarks if available
- Use tables for metric presentation

Generate sections:
1. KPI Overview
2. Performance Metrics by Category
3. Key Metrics Table
4. Benchmarks and Targets
5. Insights and Recommendations
"""

CUSTOM_REPORT_PROMPT = """You are a professional report writer. Generate a report based on the user's request.

Rules:
- Follow the user's instructions precisely
- Use markdown formatting
- Include specific data points and numbers
- Cite sources when possible
- Be thorough and structured
"""

def format_data_points_prompt(data_points: list) -> str:
    """Format extracted data points for prompt.

    Args:
        data_points: List of data point dicts.

    Returns:
        Formatted string.
    """
    lines = []
    for dp in data_points:
        lines.append(f"- [{dp.get('type', 'unknown')}] {dp.get('value', '')} (source: {dp.get('source', 'Unknown')}, page: {dp.get('page', 1)})")
    return "\n".join(lines)
