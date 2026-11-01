"""Answer audio on disk, under RECORDINGS_DIR. Paths are relative to that root, and nothing here logs content."""
import os
import uuid
from pathlib import Path


def _root() -> Path:
    return Path(os.environ.get("RECORDINGS_DIR", "./recordings")).resolve()


def _resolve(path: str) -> Path:
    root = _root()
    full = (root / path).resolve()
    if root != full and root not in full.parents:
        raise ValueError("Path escapes the recordings root")
    return full


def save_turn_audio(company_id: int, owner_key, position: int, data: bytes, suffix: str) -> str:
    """Write the file whole or not at all, so a reader never sees half an answer."""
    relative = f"{company_id}/{owner_key}/{position}{suffix}"
    full = _resolve(relative)
    full.parent.mkdir(parents=True, exist_ok=True)
    temporary = full.with_name(f".{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_bytes(data)
        os.replace(temporary, full)
    finally:
        temporary.unlink(missing_ok=True)
    return relative


def read(path: str) -> bytes:
    return _resolve(path).read_bytes()


def delete(path: str) -> None:
    _resolve(path).unlink(missing_ok=True)
