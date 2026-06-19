"""Centralized, absolute path constants for Windows RAG System.

All paths are resolved relative to this file's location so the project
works correctly regardless of the current working directory or where
the project folder is placed on disk.

Directory layout this file assumes:
    <project_root>/
        utils/
            paths.py        <- this file
        config/
        data/
            copilot_history/
            documents/
            metadata/
            reports/
            uploads/
            vectors/
        ...
"""
from pathlib import Path

# ---------------------------------------------------------------------------
# Project root
# ---------------------------------------------------------------------------
# utils/paths.py lives one level below the project root, so .parent.parent
# climbs up to the project root.
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Top-level directories
# ---------------------------------------------------------------------------
CONFIG_DIR: Path = PROJECT_ROOT / "config"
DATA_DIR: Path = PROJECT_ROOT / "data"

# ---------------------------------------------------------------------------
# Data sub-directories
# ---------------------------------------------------------------------------
VECTOR_DIR: Path = DATA_DIR / "vectors"
METADATA_DIR: Path = DATA_DIR / "metadata"
UPLOADS_DIR: Path = DATA_DIR / "uploads"
REPORTS_DIR: Path = DATA_DIR / "reports"
DOCUMENTS_DIR: Path = DATA_DIR / "documents"

# ---------------------------------------------------------------------------
# Config files
# ---------------------------------------------------------------------------
SETTINGS_PATH: Path = CONFIG_DIR / "settings.json"
API_KEYS_LOCAL_PATH: Path = CONFIG_DIR / "api_keys.local.json"
API_KEYS_PATH: Path = CONFIG_DIR / "api_keys.json"

# ---------------------------------------------------------------------------
# Data files
# ---------------------------------------------------------------------------
DOC_INDEX_PATH: Path = METADATA_DIR / "doc_index.json"
FAISS_INDEX_PATH: Path = VECTOR_DIR / "faiss.index"
FAISS_METADATA_PATH: Path = VECTOR_DIR / "metadata.pkl"
