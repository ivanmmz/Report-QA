"""Text chunker module for Windows RAG System."""
from dataclasses import dataclass
from typing import List
import re
from pathlib import Path

# Minimum number of meaningful characters a chunk must contain to be indexed.
# Chunks below this threshold are structural markers with no searchable content
# and would pollute the vector store, causing retrieval score distortion.
MIN_MEANINGFUL_CHUNK_LEN = 50


@dataclass
class TextChunk:
    """Represents a chunk of text with metadata."""
    content: str
    source: str
    page: int
    chunk_index: int
    total_chunks: int


class TextChunker:
    """Chunk text with overlap and semantic boundaries.

    Preserves table boundaries so that column headers and their data
    remain in the same chunk, preventing numeric values from being
    separated from their labels.
    """

    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 100):
        """Initialize chunker.

        Args:
            chunk_size: Target chunk size in characters.
            chunk_overlap: Overlap between chunks.
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def _split_text(self, text: str) -> List[str]:
        """Split text into initial chunks at semantic boundaries.

        Detects table regions (bounded by === TABLE DATA === and
        === DOCUMENT TEXT === markers) and keeps them intact as
        single chunks. Filters out near-empty structural-only chunks
        (e.g., bare === markers) that would pollute the vector store.

        Args:
            text: Full text to split.

        Returns:
            List of chunk strings, each containing meaningful content.
        """
        # Detect table regions to preserve them as atomic units
        table_regions = self._detect_table_regions(text)

        if table_regions:
            # Split only non-table text, keep tables intact
            raw = self._split_with_tables(text, table_regions)
        else:
            # No tables found, use paragraph-based splitting
            raw = self._split_paragraphs(text)

        # Filter out near-empty / structural-marker-only chunks that have no
        # real searchable content. These arise when pdf_loader emits section
        # headers like "=== TABLE DATA ===" or "=== DOCUMENT TEXT ===" as
        # their own paragraph, producing 18-character chunks that confuse the
        # embedding model and skew retrieval scores.
        return [
            c for c in raw
            if len(c.strip()) >= MIN_MEANINGFUL_CHUNK_LEN
            and not re.match(r'^===\s*[^=]+\s*===$', c.strip())
        ]

    def _detect_table_regions(self, text: str) -> List[tuple[int, int]]:
        """Find start/end positions of table data regions.

        Tables are bracketed by === TABLE DATA === headers.
        Data rows following COLUMNS: line and up to the next
        section marker are considered part of the table.

        Returns:
            List of (start, end) tuples for each table region.
        """
        regions = []
        lines = text.split('\n')
        in_table = False
        table_start = -1
        i = 0

        while i < len(lines):
            line = lines[i]
            # Table data section starts
            if '=== TABLE DATA ===' in line:
                in_table = True
                table_start = self._line_to_offset(text, lines, i)
                # Skip header marker
                i += 1
                continue

            # Track COLUMNS: as part of the same table
            if in_table and line.startswith('COLUMNS:'):
                i += 1
                continue

            # Table data rows (start with column_name: value)
            if in_table and ':' in line and not line.startswith('==='):
                i += 1
                continue

            # End of table: section marker only (NOT blank lines).
            # load_pdf.py joins sections with "\n\n", so blank lines
            # naturally appear between the marker and the data rows.
            # Terminating on blank lines would truncate the region to
            # just the "=== TABLE DATA ===" marker, discarding content.
            if in_table:
                if line.startswith('=== '):
                    end = self._line_to_offset(text, lines, i)
                    regions.append((table_start, end))
                    in_table = False
                    table_start = -1

            i += 1

        # Close any remaining open region
        if in_table and table_start >= 0:
            regions.append((table_start, len(text)))

        return regions

    def _line_to_offset(self, text: str, lines: List[str], line_idx: int) -> int:
        """Map a line index back to a character offset in the full text."""
        offset = 0
        for j in range(line_idx):
            offset += len(lines[j]) + 1  # +1 for newline
        return min(offset, len(text))

    def _split_with_tables(self, text: str, table_regions: List[tuple[int, int]]) -> List[str]:
        """Split text, keeping table regions intact."""
        chunks = []
        last_end = 0

        for t_start, t_end in sorted(table_regions):
            # Split text before this table
            if t_start > last_end:
                before = text[last_end:t_start].strip()
                if before:
                    chunks.extend(self._split_paragraphs(before))

            # Keep the entire table as one chunk
            table_text = text[t_start:t_end].strip()
            if table_text:
                chunks.append(table_text)

            last_end = t_end

        # Text after last table
        if last_end < len(text):
            after = text[last_end:].strip()
            if after:
                chunks.extend(self._split_paragraphs(after))

        return chunks

    def _split_paragraphs(self, text: str) -> List[str]:
        """Split text by paragraphs with size constraints."""
        paragraphs = re.split(r'\n\s*\n', text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        chunks = []
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 <= self.chunk_size:
                current_chunk += ("\n\n" + para if current_chunk else para)
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = para

        if current_chunk:
            chunks.append(current_chunk)

        # If chunks are still too large, split by sentences
        final_chunks = []
        for chunk in chunks:
            if len(chunk) > self.chunk_size * 1.5:
                sentences = re.split(r'(?<=[.!?])\s+', chunk)
                temp = ""
                for sent in sentences:
                    if len(temp) + len(sent) + 1 <= self.chunk_size:
                        temp += (" " + sent if temp else sent)
                    else:
                        if temp:
                            final_chunks.append(temp)
                        temp = sent
                if temp:
                    final_chunks.append(temp)
            else:
                final_chunks.append(chunk)

        return final_chunks

    def chunk_document(self, text: str, source: str, page: int = 1) -> List[TextChunk]:
        """Chunk a document into overlapping pieces.

        Args:
            text: Document text.
            source: Document source identifier.
            page: Page number.

        Returns:
            List of TextChunk objects.
        """
        # Normalize text before chunking
        # 1. Add source filename as a searchable prefix
        filename = Path(source).stem  # e.g. "202509"
        # 2. Normalize "Sept/" to "Sep/" so queries for "Sep 2025" match
        text = re.sub(r'\bSept/', 'Sep/', text)
        # 3. Prepend source info so the embedding can match on filename
        text = f"[File: {filename}] {text}"

        raw_chunks = self._split_text(text)

        chunks = []
        for i, chunk_text in enumerate(raw_chunks):
            # Add overlap from previous chunk
            if i > 0 and self.chunk_overlap > 0:
                prev_text = raw_chunks[i - 1]
                overlap = prev_text[-self.chunk_overlap:]
                chunk_text = overlap + "\n" + chunk_text

            chunks.append(TextChunk(
                content=chunk_text,
                source=source,
                page=page,
                chunk_index=i,
                total_chunks=len(raw_chunks),
            ))

        return chunks

    def chunk_documents(self, documents: List[tuple]) -> List[TextChunk]:
        """Chunk multiple documents.

        Args:
            documents: List of (text, source, page) tuples.

        Returns:
            Combined list of TextChunk objects.
        """
        all_chunks = []
        for text, source, page in documents:
            chunks = self.chunk_document(text, source, page)
            all_chunks.extend(chunks)
        return all_chunks
