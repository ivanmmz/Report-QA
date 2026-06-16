"""Text chunker module for Windows RAG System."""
from dataclasses import dataclass
from typing import List
import re


@dataclass
class TextChunk:
    """Represents a chunk of text with metadata."""
    content: str
    source: str
    page: int
    chunk_index: int
    total_chunks: int


class TextChunker:
    """Chunk text with overlap and semantic boundaries."""

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

        Args:
            text: Full text to split.

        Returns:
            List of chunk strings.
        """
        # Split by paragraphs first
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
