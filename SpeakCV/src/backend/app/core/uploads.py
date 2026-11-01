import mimetypes
import os

from fastapi import HTTPException, UploadFile

from app.core.settings import max_upload_bytes

CHUNK_SIZE = 1024 * 1024
CV_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
CV_UPLOAD_TYPES = set(CV_TYPES)
DOCUMENT_TYPES = CV_TYPES | {"text/plain", "text/markdown"}
AUDIO_TYPES = {"audio/webm", "audio/ogg", "audio/mpeg", "audio/mp4", "audio/wav", "audio/x-wav"}
# mimetypes maps some audio containers to video types, so name the ones we accept explicitly.
EXTENSION_TYPES = {".webm": "audio/webm", ".ogg": "audio/ogg", ".md": "text/markdown", ".mp4": "audio/mp4", ".m4a": "audio/mp4"}


def _guess_type(filename: str) -> str:
    extension = os.path.splitext(filename)[1].lower()
    return EXTENSION_TYPES.get(extension) or (mimetypes.guess_type(filename)[0] or "").lower()


async def read_upload(file: UploadFile, allowed_types: set[str]) -> bytes:
    """Read an upload into memory, enforcing type and size. Never uses the client's filename."""
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type in ("", "application/octet-stream"):
        content_type = _guess_type(file.filename or "")
    if content_type not in allowed_types:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {content_type or 'unknown'}")
    limit = max_upload_bytes()
    chunks, total = [], 0
    while chunk := await file.read(CHUNK_SIZE):
        total += len(chunk)
        if total > limit:
            raise HTTPException(status_code=413, detail=f"File is larger than the {limit // (1024 * 1024)} MB limit")
        chunks.append(chunk)
    return b"".join(chunks)
