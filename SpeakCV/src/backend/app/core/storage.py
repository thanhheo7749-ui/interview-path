import os
import uuid
from pathlib import Path


def _root() -> Path:
    return Path(os.environ.get("STORAGE_DIR", "./storage")).resolve()


def _resolve(path: str) -> Path:
    root = _root()
    full = (root / path).resolve()
    if root != full and root not in full.parents:
        raise ValueError("Path escapes the storage root")
    return full


def save_bytes(company_id: int, category: str, suffix: str, data: bytes) -> str:
    relative = f"{company_id}/{category}/{uuid.uuid4().hex}{suffix}"
    full = _resolve(relative)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(data)
    return relative


def read_bytes(path: str) -> bytes:
    return _resolve(path).read_bytes()


def delete(path: str) -> None:
    _resolve(path).unlink(missing_ok=True)
