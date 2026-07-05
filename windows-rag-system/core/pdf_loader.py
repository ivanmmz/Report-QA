"""PDF loader module for Windows RAG System.

Extracts text from PDFs with smart table reconstruction.
Handles both structured reports and free-text documents.
"""
import re
import fitz  # PyMuPDF
from pathlib import Path
from dataclasses import dataclass
from typing import List

from utils.logger import setup_logger

logger = setup_logger("pdf_loader")


@dataclass
class PDFDocument:
    """Represents a parsed PDF document."""
    source: str
    text: str
    pages: int
    metadata: dict


def _reconstruct_tables(text: str) -> str:
    """Reconstruct broken table rows from line-by-line extracted text.

    Many PDF extractors (including PyMuPDF) break table cells into
    separate lines. This function detects that pattern and reassembles
    the rows so that each table row becomes a single line with
    cell values joined by meaningful separators.

    Detection heuristic: if many consecutive short lines (< 25 chars)
    appear without blank-line separators, they are likely table cells
    that should be merged.

    Args:
        text: Raw extracted text.

    Returns:
        Text with table rows reconstructed.
    """
    lines = text.split('\n')
    if not lines:
        return text

    result_lines = []
    buffer = []
    buffer_len = 0

    def flush_buffer():
        if not buffer:
            return
        # Join short fragments into a meaningful line
        merged = ' | '.join(buffer)
        result_lines.append(merged)
        buffer.clear()

    for line in lines:
        stripped = line.strip()

        # Blank line = paragraph boundary → flush
        if not stripped:
            flush_buffer()
            result_lines.append('')
            buffer_len = 0
            continue

        # Long line (> 60 chars) = prose paragraph → flush buffer, keep as-is
        if len(stripped) > 60:
            flush_buffer()
            result_lines.append(stripped)
            buffer_len = 0
            continue

        # Short line: likely a table cell value
        # If we already have fragments in buffer and total is getting long,
        # flush to start a new row
        if buffer and buffer_len + len(stripped) > 120:
            flush_buffer()

        buffer.append(stripped)
        buffer_len += len(stripped)

    flush_buffer()
    return '\n'.join(result_lines)


def _extract_page_tables(page) -> List[str]:
    """Extract tables from a PDF page using PyMuPDF's table detection.

    Falls back to text extraction if table extraction is not available.

    Args:
        page: PyMuPDF page object.

    Returns:
        List of table strings (markdown formatted).
    """
    tables = []

    # Try PyMuPDF's built-in table extraction (available in fitz >= 1.23)
    try:
        tab = page.find_tables()
        if tab and hasattr(tab, 'tables'):
            for table in tab.tables:
                rows = table.extract()
                if rows:
                    table_str = _format_table_rows(rows)
                    tables.append(table_str)
    except Exception:
        pass

    return tables


def _format_table_rows(rows: List[List[str]]) -> str:
    """Format table rows as a readable text block with column headers preserved.

    Preserves the header row as a labeled structure so downstream processing
    can associate values with their column names.

    Returns empty string if the table contains no actual data rows, so that
    the caller can safely skip empty/header-only tables.

    Args:
        rows: List of rows, each row is a list of cell strings.

    Returns:
        Formatted table string with column labels, or empty string if no data.
    """
    if not rows:
        return ""

    header = rows[0]
    lines = []
    data_lines = []

    # Emit column index labels for structured access
    col_labels = []
    for i, cell in enumerate(header):
        label = str(cell).strip() if cell else f"COL_{i}"
        col_labels.append(label)

    # Format each data row with column context
    for row in rows[1:]:
        cells = [str(cell).strip() if cell else "" for cell in row]
        if any(cells):  # Skip completely empty rows
            labeled_cells = []
            for i, cell in enumerate(cells):
                if cell and i < len(col_labels):
                    labeled_cells.append(f"{col_labels[i]}: {cell}")
                elif cell:
                    labeled_cells.append(cell)
            data_lines.append(" | ".join(labeled_cells))

    # Only return a formatted table if there are actual data rows.
    # A table with ONLY a header and no data rows is useless and causes
    # empty chunks in the vector store.
    if not data_lines:
        return ""

    lines.append("COLUMNS: " + " | ".join(col_labels))
    lines.append("---")
    lines.extend(data_lines)

    return "\n".join(lines)


def load_pdf(path: str | Path) -> PDFDocument:
    """Load and extract text from a PDF file.

    Uses multiple extraction strategies:
    1. PyMuPDF table detection for structured data
    2. Text extraction with table reconstruction
    3. Merges both into a comprehensive text output

    Args:
        path: Path to PDF file.

    Returns:
        PDFDocument with extracted text and metadata.
    """
    path = Path(path)
    doc = fitz.open(str(path))

    text_parts = []
    table_parts = []
    page_count = len(doc)

    for page_num, page in enumerate(doc):
        # Strategy 1: Extract tables via PyMuPDF's find_tables
        page_tables = _extract_page_tables(page)
        if page_tables:
            table_parts.extend(page_tables)

        # Strategy 2: Regular text extraction
        page_text = page.get_text()
        if page_text and page_text.strip():
            # Reconstruct broken table rows
            reconstructed = _reconstruct_tables(page_text)
            text_parts.append(reconstructed)

    # Merge text and table content
    # Only include TABLE DATA section if tables have actual meaningful content.
    # Filter out any empty table strings (header-only tables with no data rows)
    # to prevent polluting the vector store with near-empty chunks.
    non_empty_tables = [t for t in table_parts if t and t.strip()]
    full_parts = []
    if non_empty_tables:
        for t in non_empty_tables:
            full_parts.append("=== TABLE DATA ===")
            full_parts.append(t)
        full_parts.append("=== DOCUMENT TEXT ===")
    full_parts.extend(text_parts)

    full_text = "\n\n".join(full_parts)

    # If we got very little text, try extracting text blocks directly
    if len(full_text.strip()) < 100:
        for page in doc:
            blocks = page.get_text("blocks")
            if blocks:
                block_texts = []
                for b in blocks:
                    # b[4] is the text content for text blocks
                    if len(b) > 4 and b[4].strip():
                        block_texts.append(b[4].strip())
                if block_texts:
                    full_text += "\n\n" + "\n".join(block_texts)

    metadata = {
        "title": doc.metadata.get("title", "") or path.stem,
        "author": doc.metadata.get("author", ""),
        "page_count": page_count,
        "source": str(path),
    }

    doc.close()

    logger.info(f"Loaded {path.name}: {len(full_text)} chars, {page_count} pages, {len(table_parts)} tables")

    return PDFDocument(
        source=str(path),
        text=full_text,
        pages=page_count,
        metadata=metadata,
    )