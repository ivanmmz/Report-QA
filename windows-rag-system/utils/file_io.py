"""File I/O utilities for Windows RAG System."""
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from utils.logger import setup_logger

logger = setup_logger("file_io")


def ensure_dir(path: str | Path) -> Path:
    """Ensure directory exists and return Path object.

    Args:
        path: Directory path.

    Returns:
        Path object for the directory.
    """
    p = Path(path) if isinstance(path, str) else path
    p.mkdir(parents=True, exist_ok=True)
    return p


def read_json(path: str | Path) -> dict[str, Any]:
    """Read JSON file safely with logging.

    Args:
        path: Path to JSON file.

    Returns:
        Parsed JSON content. Returns empty dict if file missing or invalid.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"File not found: {path}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error in {path}: {e}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error reading {path}: {e}")
        return {}


def write_json(path: str | Path, data: dict[str, Any], indent: int = 2) -> None:
    """Write data to JSON file atomically.

    Writes to a temporary file first, then atomically renames to the
    target path. This prevents data corruption on crash during write.

    Args:
        path: Target file path.
        data: Data to serialize.
        indent: JSON indentation.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    # Write to temp file in same directory, then rename atomically
    try:
        fd, tmp_path = tempfile.mkstemp(
            dir=str(p.parent),
            prefix="." + p.name + ".",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=indent, ensure_ascii=False, default=str)
            # Atomic rename on same filesystem
            os.replace(tmp_path, str(p))
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except Exception as e:
        logger.error(f"Failed to write {path}: {e}")
        raise


def file_hash(path: str | Path) -> str:
    """Compute MD5 hash of file content.

    Args:
        path: File path.

    Returns:
        Hex digest of MD5 hash.

    Raises:
        FileNotFoundError: If file does not exist.
    """
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def list_files(directory: str | Path, extensions: list[str] | None = None) -> list[Path]:
    """List files in directory, optionally filtered by extension.

    Args:
        directory: Directory to scan.
        extensions: List of extensions (e.g., [".pdf"]). None means all files.

    Returns:
        List of Path objects.
    """
    p = Path(directory)
    if not p.exists():
        return []

    files = [f for f in p.iterdir() if f.is_file()]
    if extensions:
        files = [f for f in files if f.suffix.lower() in [e.lower() for e in extensions]]
    return files
