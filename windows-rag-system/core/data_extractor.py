"""Data extractor module for Windows RAG System.

Extracts structured data (dates, numbers, metrics) from document chunks
using regex patterns and LLM-based extraction.
"""
import re
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

from utils.logger import setup_logger

logger = setup_logger("data_extractor")


@dataclass
class ExtractedDataPoint:
    """Represents a single extracted data point."""
    type: str  # 'date', 'number', 'metric', 'text'
    value: str
    context: str
    source: str
    page: int
    confidence: float = 1.0


class DataExtractor:
    """Extract structured data from document content."""

    # Common patterns
    DATE_PATTERNS = [
        # ISO dates: 2024-01-15, 2024/01/15
        r'\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b',
        # US dates: 01/15/2024, 01-15-2024
        r'\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b',
        # Month names: January 15, 2024; Jan 15, 2024; 15 Jan 2024
        r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[\.\s]+(\d{1,2})[,.\s]+(\d{4})\b',
        # Quarter: Q1 2024, Q2 2024
        r'\b(Q[1-4])\s+(\d{4})\b',
        # Year only: 2024
        r'\b(20\d{2})\b',
    ]

    NUMBER_PATTERNS = [
        # Percentages: 45.5%, 100%
        r'\b(\d+(?:\.\d+)?)\s*%\b',
        # Currency: $1,234.56, €100, ¥5000
        r'[\$\€\¥\£]\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)',
        # Large numbers with units: 1,234 kWh, 500 tons, 1000 MW
        r'\b(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\s*(kWh|MWh|MW|GW|tons?|kg|metric tons?|kWh|BTU|CO2|°C|°F|m³|m3|GJ|MJ)\b',
        # Simple numbers with context: 1234, 12.34
        r'\b(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\b',
    ]

    METRIC_KEYWORDS = [
        "COP", "efficiency", "power", "consumption", "energy", "cost",
        "temperature", "pressure", "flow", "capacity", "load", "output",
        "input", "savings", "reduction", "increase", "decrease", "change",
        "performance", "rating", "index", "score", "level", "amount",
        "percentage", "ratio", "rate", "factor", "coefficient",
    ]

    def __init__(self):
        """Initialize data extractor."""
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for performance."""
        self._date_regexes = [re.compile(p, re.IGNORECASE) for p in self.DATE_PATTERNS]
        self._number_regexes = [re.compile(p, re.IGNORECASE) for p in self.NUMBER_PATTERNS]

    def extract_dates(self, text: str, source: str = "", page: int = 1) -> List[ExtractedDataPoint]:
        """Extract date mentions from text.

        Args:
            text: Document text.
            source: Document source.
            page: Page number.

        Returns:
            List of extracted date data points.
        """
        results = []
        for regex in self._date_regexes:
            for match in regex.finditer(text):
                # Get surrounding context (50 chars before and after)
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                context = text[start:end]

                results.append(ExtractedDataPoint(
                    type="date",
                    value=match.group(0),
                    context=context.strip(),
                    source=source,
                    page=page,
                    confidence=0.9,
                ))
        return results

    def extract_numbers(self, text: str, source: str = "", page: int = 1) -> List[ExtractedDataPoint]:
        """Extract numeric values with context from text.

        Args:
            text: Document text.
            source: Document source.
            page: Page number.

        Returns:
            List of extracted number data points.
        """
        results = []
        for regex in self._number_regexes:
            for match in regex.finditer(text):
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                context = text[start:end]

                # Determine if this is a metric
                is_metric = any(kw.lower() in context.lower() for kw in self.METRIC_KEYWORDS)
                dp_type = "metric" if is_metric else "number"

                results.append(ExtractedDataPoint(
                    type=dp_type,
                    value=match.group(0),
                    context=context.strip(),
                    source=source,
                    page=page,
                    confidence=0.85 if is_metric else 0.7,
                ))
        return results

    def extract_metrics(self, text: str, source: str = "", page: int = 1) -> List[ExtractedDataPoint]:
        """Extract metric data points (keyword + number combinations).

        Args:
            text: Document text.
            source: Document source.
            page: Page number.

        Returns:
            List of extracted metric data points.
        """
        results = []
        # Pattern: metric_keyword followed by number within 10 words
        for keyword in self.METRIC_KEYWORDS:
            # Look for keyword followed by number
            pattern = rf'\b{keyword}\b[^.\n]{{0,30}}?(\d+(?:\.\d+)?(?:\s*%|\s*(?:kWh|MWh|MW|tons?|kg|°C|°F|m³|m3|GJ|MJ))?)'
            for match in re.finditer(pattern, text, re.IGNORECASE):
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                context = text[start:end]

                results.append(ExtractedDataPoint(
                    type="metric",
                    value=match.group(0),
                    context=context.strip(),
                    source=source,
                    page=page,
                    confidence=0.95,
                ))
        return results

    def extract_from_chunks(self, chunks: List[Dict[str, Any]]) -> List[ExtractedDataPoint]:
        """Extract all data points from a list of document chunks.

        Args:
            chunks: List of chunk dicts with 'content', 'source', 'page'.

        Returns:
            Combined list of all extracted data points.
        """
        all_results = []
        for chunk in chunks:
            text = chunk.get("content", "")
            source = chunk.get("source", "")
            page = chunk.get("page", 1)

            all_results.extend(self.extract_dates(text, source, page))
            all_results.extend(self.extract_numbers(text, source, page))
            all_results.extend(self.extract_metrics(text, source, page))

        # Remove duplicates (same value, same source, within 10 chars)
        seen = set()
        unique = []
        for dp in all_results:
            key = (dp.value, dp.source, dp.page)
            if key not in seen:
                seen.add(key)
                unique.append(dp)

        logger.info(f"Extracted {len(unique)} unique data points from {len(chunks)} chunks")
        return unique

    def filter_by_date_range(
        self,
        data_points: List[ExtractedDataPoint],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[ExtractedDataPoint]:
        """Filter data points by date range.

        Preserves ALL data point types (dates, metrics, numbers, text).
        Only date-type points are checked against the range filter;
        non-date points are always kept since their temporal context
        cannot be determined from the value alone.

        Args:
            data_points: List of data points.
            start_date: Start date string (YYYY-MM-DD) or None.
            end_date: End date string (YYYY-MM-DD) or None.

        Returns:
            Filtered data points.
        """
        if not start_date and not end_date:
            return data_points

        # Parse the range boundaries
        parsed_start = self._parse_date(start_date) if start_date else None
        parsed_end = self._parse_date(end_date) if end_date else None

        filtered = []
        for dp in data_points:
            if dp.type == "date":
                date_val = self._parse_date(dp.value)
                if date_val is None:
                    # Date-typed point we can't parse — keep it
                    filtered.append(dp)
                    continue
                if parsed_start and date_val < parsed_start:
                    continue
                if parsed_end and date_val > parsed_end:
                    continue
                filtered.append(dp)
            else:
                # Keep ALL non-date points (metrics, numbers, text)
                filtered.append(dp)

        return filtered

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse a date string into datetime.

        Args:
            date_str: Date string.

        Returns:
            datetime or None if unparsable.
        """
        formats = [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%m/%d/%Y",
            "%m-%d-%Y",
            "%B %d, %Y",
            "%b %d, %Y",
            "%Y",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None

    def get_unique_dates(self, data_points: List[ExtractedDataPoint]) -> List[str]:
        """Get sorted unique dates from data points.

        Args:
            data_points: List of data points.

        Returns:
            Sorted list of unique date strings.
        """
        dates = []
        for dp in data_points:
            if dp.type == "date":
                parsed = self._parse_date(dp.value)
                if parsed:
                    dates.append(parsed)
        dates = sorted(set(dates))
        return [d.strftime("%Y-%m-%d") for d in dates]

    def to_dict(self, data_points: List[ExtractedDataPoint]) -> List[Dict[str, Any]]:
        """Convert data points to dicts.

        Args:
            data_points: List of data points.

        Returns:
            List of dicts.
        """
        return [asdict(dp) for dp in data_points]

    def extract_with_llm(
        self,
        llm,
        text: str,
        extraction_type: str = "all",
    ) -> List[Dict[str, Any]]:
        """Use LLM to extract structured data from text.

        Args:
            llm: LLM gateway instance.
            text: Text to analyze.
            extraction_type: 'all', 'dates', 'metrics', 'entities'.

        Returns:
            List of extracted dicts.
        """
        system_prompt = """You are a data extraction specialist. Extract structured data from the provided text.

Return ONLY a JSON array in this format:
[
  {"type": "date", "value": "2024-01-15", "context": "surrounding text", "label": "optional label"},
  {"type": "metric", "value": "45.2", "unit": "%", "context": "surrounding text", "label": "efficiency"},
  {"type": "entity", "value": "HVAC System A", "category": "equipment", "context": "surrounding text"}
]

Types: date, metric, entity, number, text
Be precise and extract only factual data present in the text."""

        user_prompt = f"""Extract all {extraction_type} data from the following text:

{text[:3000]}"""

        try:
            response = llm.chat(user_prompt, "", system_prompt)
            # Try to parse JSON from response
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            data = json.loads(response)
            if isinstance(data, list):
                return data
            return [data] if isinstance(data, dict) else []
        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}")
            return []

    def summarize_data(self, data_points: List[ExtractedDataPoint]) -> Dict[str, Any]:
        """Generate a summary of extracted data.

        Args:
            data_points: List of data points.

        Returns:
            Summary dict with counts, date ranges, key metrics.
        """
        dates = [dp for dp in data_points if dp.type == "date"]
        metrics = [dp for dp in data_points if dp.type == "metric"]
        numbers = [dp for dp in data_points if dp.type == "number"]

        unique_dates = self.get_unique_dates(data_points)
        date_range = None
        if unique_dates:
            date_range = {
                "start": unique_dates[0],
                "end": unique_dates[-1],
                "count": len(unique_dates),
            }

        return {
            "total": len(data_points),
            "dates": {"count": len(dates), "unique": len(unique_dates), "range": date_range},
            "metrics": {"count": len(metrics)},
            "numbers": {"count": len(numbers)},
            "sources": list(set(dp.source for dp in data_points)),
        }
