"""Document manager with folder watching and persistence."""
import json
import time
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, asdict

from utils.logger import setup_logger
from utils.file_io import read_json, write_json, file_hash, list_files, ensure_dir
from utils.paths import DOC_INDEX_PATH, VECTOR_DIR
from core.pdf_loader import load_pdf
from core.chunker import TextChunker, TextChunk
from core.embedder import APIEmbedder
from vectorstore.faiss_store import FAISSStore

logger = setup_logger("document_manager")


@dataclass
class DocumentEntry:
    """Represents an indexed document entry."""
    file: str
    hash: str
    status: str  # 'indexed', 'modified', 'deleted'
    timestamp: float
    chunks: int


class DocumentManager:
    """Manages document folder, indexing, and persistence."""

    def __init__(
        self,
        index_path=DOC_INDEX_PATH,
        vector_dir=VECTOR_DIR,
        settings: dict | None = None,
    ):
        """Initialize document manager.

        Args:
            index_path: Path to document index JSON.
            vector_dir: Directory for vector storage.
            settings: App settings dict.
        """
        self.index_path = Path(index_path)
        self.vector_dir = Path(vector_dir)
        self.settings = settings or {}
        self.selected_folders: List[str] = []
        self.selected_folder: str | None = None
        self.documents: Dict[str, DocumentEntry] = {}
        self.chunker = TextChunker(
            chunk_size=self.settings.get("chunk_size", 800),
            chunk_overlap=self.settings.get("chunk_overlap", 100),
        )
        self.embedder: APIEmbedder | None = None
        self.vector_store: FAISSStore | None = None
        self._load_index()

    def _load_index(self) -> None:
        """Load document index from disk."""
        data = read_json(self.index_path)
        self.selected_folders = data.get("selected_folders", [])
        self.selected_folder = data.get("selected_folder")
        if not self.selected_folders and self.selected_folder:
            self.selected_folders = [self.selected_folder]
        self.selected_folders = list(dict.fromkeys(filter(None, self.selected_folders)))
        self.selected_folder = self.selected_folders[0] if self.selected_folders else None
        
        self.documents = {
            k: DocumentEntry(**v)
            for k, v in data.get("files", {}).items()
        }

    def _save_index(self) -> None:
        """Save document index to disk."""
        data = {
            "selected_folder": self.selected_folder,
            "selected_folders": self.selected_folders,
            "files": {k: asdict(v) for k, v in self.documents.items()},
        }
        write_json(self.index_path, data)
        logger.info(f"Saved index with {len(self.documents)} documents across {len(self.selected_folders)} folders")

    def set_folder(self, folder_path: str) -> None:
        """Set selected folder (delegates to add_folder for compatibility)."""
        self.add_folder(folder_path)

    def add_folder(self, folder_path: str) -> None:
        """Add a folder path to the index.

        Args:
            folder_path: Absolute path to folder.
        """
        path = Path(folder_path)
        if not path.exists() or not path.is_dir():
            raise ValueError(f"Invalid folder path: {folder_path}")
        
        resolved = str(path.resolve())
        if resolved not in self.selected_folders:
            self.selected_folders.append(resolved)
        self.selected_folder = self.selected_folders[0] if self.selected_folders else None
        self._save_index()
        logger.info(f"Added folder: {resolved}")

    def remove_folder(self, folder_path: str) -> None:
        """Remove a folder path and clear its files from the index.

        Args:
            folder_path: Folder path to remove.
        """
        resolved = str(Path(folder_path).resolve())
        if resolved in self.selected_folders:
            self.selected_folders.remove(resolved)
        self.selected_folder = self.selected_folders[0] if self.selected_folders else None
        
        # Find all files belonging to this folder
        to_remove = [k for k in self.documents if k.startswith(resolved)]
        for k in to_remove:
            del self.documents[k]
            
        self._save_index()
        self._rebuild_from_index()
        logger.info(f"Removed folder and rebuilt index: {resolved}")

    def _rebuild_from_index(self) -> None:
        """Rebuild vector store index using currently indexed active documents."""
        if not self.embedder or not self.vector_store:
            return
        logger.info("Rebuilding vector store from index...")
        self.vector_store.clear()
        active_files = [f for f, doc in self.documents.items() if doc.status == "indexed"]
        self.documents = {}
        for f in active_files:
            if Path(f).exists():
                self.index_file(f)
        self._save_index()

    def scan_folder(self, folder_path: str | None = None) -> List[str]:
        """Scan all selected folders (or a specific one) for PDF files.

        Returns:
            List of PDF file paths.
        """
        all_files = []
        folders_to_scan = [folder_path] if folder_path else self.selected_folders
        for folder in folders_to_scan:
            if folder and Path(folder).is_dir():
                files = list_files(folder, extensions=[".pdf"])
                all_files.extend([str(f) for f in files])
        return list(dict.fromkeys(all_files))

    def detect_changes(self, folder_path: str | None = None) -> Dict[str, List[str]]:
        """Detect new, modified, and deleted files.

        Returns:
            Dict with keys 'new', 'modified', 'deleted'.
        """
        current_files = set(self.scan_folder(folder_path))
        
        if folder_path:
            resolved_folder = str(Path(folder_path).resolve())
            indexed_files = set(k for k in self.documents.keys() if k.startswith(resolved_folder))
        else:
            indexed_files = set(self.documents.keys())
        
        new_files = []
        modified_files = []
        
        for f in current_files:
            if f not in indexed_files:
                new_files.append(f)
            else:
                current_hash = file_hash(f)
                if current_hash != self.documents[f].hash or (self.embedder and self.documents[f].status == "pending"):
                    modified_files.append(f)
        
        deleted_files = list(indexed_files - current_files)
        
        return {
            "new": new_files,
            "modified": modified_files,
            "deleted": deleted_files,
        }

    def initialize_stores(self, embedder: APIEmbedder, vector_store: FAISSStore) -> None:
        """Bind embedding and vector store.

        Args:
            embedder: APIEmbedder instance.
            vector_store: FAISSStore instance.
        """
        self.embedder = embedder
        self.vector_store = vector_store

    def index_file(self, file_path: str) -> int:
        """Index a single PDF file.

        Args:
            file_path: Path to PDF file.

        Returns:
            Number of chunks indexed.
        """
        logger.info(f"Indexing: {file_path}")
        
        try:
            doc = load_pdf(file_path)
            chunks = self.chunker.chunk_document(doc.text, source=file_path)
            
            if not chunks:
                # Track the file even with 0 chunks so it shows in the UI
                self.documents[file_path] = DocumentEntry(
                    file=file_path,
                    hash=file_hash(file_path),
                    status="empty",
                    timestamp=time.time(),
                    chunks=0,
                )
                self._save_index()
                return 0
            
            # If embedder not available, just track the file with chunk count
            if not self.embedder or not self.vector_store:
                self.documents[file_path] = DocumentEntry(
                    file=file_path,
                    hash=file_hash(file_path),
                    status="pending",  # tracked but not embedded
                    timestamp=time.time(),
                    chunks=len(chunks),
                )
                self._save_index()
                logger.info(f"Tracked {len(chunks)} chunks from {file_path} (embedder not available)")
                return len(chunks)
            
            # Prepare metadata
            chunk_texts = [c.content for c in chunks]
            embeddings = self.embedder.embed_chunks(chunk_texts)
            
            metadatas = []
            for i, chunk in enumerate(chunks):
                metadatas.append({
                    "id": f"{file_path}::{i}",
                    "content": chunk.content,
                    "source": file_path,
                    "page": chunk.page,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                })
            
            self.vector_store.add(embeddings, metadatas)
            
            # Update index
            self.documents[file_path] = DocumentEntry(
                file=file_path,
                hash=file_hash(file_path),
                status="indexed",
                timestamp=time.time(),
                chunks=len(chunks),
            )
            
            self._save_index()
            self.vector_store.save()
            
            logger.info(f"Indexed {len(chunks)} chunks from {file_path}")
            return len(chunks)
            
        except Exception as e:
            logger.error(f"Failed to index {file_path}: {e}")
            return 0

    def index_all(self, force_reindex: bool = False, folder_path: str | None = None) -> Dict[str, Any]:
        """Index all files in selected folder.

        Args:
            force_reindex: Reindex even if already indexed.
            folder_path: Limit to this folder if specified.

        Returns:
            Dict with keys:
              "results"       — dict mapping file paths to chunk counts (0 = failed)
              "failed_files"  — list of file paths that failed to index
              "total_indexed" — total chunks indexed across all files
              "total_files"   — number of files with at least 1 chunk indexed
        """
        results = {}
        failed_files = []

        if folder_path:
            if not Path(folder_path).is_dir():
                return {"results": {}, "failed_files": [], "total_indexed": 0, "total_files": 0}
        elif not self.selected_folder:
            return {"results": {}, "failed_files": [], "total_indexed": 0, "total_files": 0}

        changes = self.detect_changes(folder_path)
        files_to_index = changes["new"] + changes["modified"]

        if force_reindex:
            files_to_index = self.scan_folder(folder_path)
            if folder_path:
                resolved_folder = str(Path(folder_path).resolve())
                to_remove = [k for k in self.documents if k.startswith(resolved_folder)]
                for k in to_remove:
                    del self.documents[k]
                self._rebuild_from_index()
            else:
                self.vector_store.clear()
                self.documents = {}

        for f in files_to_index:
            count = self.index_file(f)
            results[f] = count
            if count == 0:
                failed_files.append(f)

        for f in changes["deleted"]:
            self.documents[f].status = "deleted"

        if changes["deleted"]:
            self._save_index()

        total_indexed = sum(results.values())
        total_files = len([v for v in results.values() if v > 0])

        return {
            "results": results,
            "failed_files": failed_files,
            "total_indexed": total_indexed,
            "total_files": total_files,
        }

    def sync(self, folder_path: str | None = None) -> Dict[str, Any]:
        """Full sync: detect changes and index.

        Returns:
            Summary dict with status, indexed counts, and failed file list.
        """
        if folder_path:
            if not Path(folder_path).is_dir():
                return {"status": "no_folder", "indexed": 0, "failed_files": []}
        elif not self.selected_folder:
            return {"status": "no_folder", "indexed": 0, "failed_files": []}

        changes = self.detect_changes(folder_path)
        result = self.index_all(folder_path=folder_path)

        return {
            "status": "success" if not result["failed_files"] else "partial",
            "indexed": result["total_indexed"],
            "files": result["total_files"],
            "failed_files": result["failed_files"],
            "changes": changes,
        }

    def get_status(self) -> Dict[str, Any]:
        """Get current document status.

        Returns:
            Status dict with folders, document count, vector count.
        """
        return {
            "selected_folder": self.selected_folder,
            "selected_folders": self.selected_folders,
            "document_count": len([d for d in self.documents.values() if d.status == "indexed"]),
            "vector_count": self.vector_store.count() if self.vector_store else 0,
            "documents": [
                {"file": d.file, "status": d.status, "chunks": d.chunks}
                for d in self.documents.values()
            ],
        }

    def handle_upload(self, file_path: str) -> int:
        """Handle a single uploaded file.

        Args:
            file_path: Path to uploaded file.

        Returns:
            Number of chunks indexed.
        """
        return self.index_file(file_path)
