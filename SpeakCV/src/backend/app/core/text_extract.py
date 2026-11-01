import io

import docx
import pdfplumber
from docx.table import Table


class NoExtractableText(Exception):
    """The file holds no text this system can read. Its message is shown to HR, and retrying will not help."""


EMPTY = "This file has no extractable text."
NO_PDF_TEXT = "This PDF has no extractable text. Scanned documents are not supported."
NOT_UTF8 = "This file is not UTF-8 text. Save it as UTF-8 and upload it again."
UNREADABLE = "This file cannot be read. It may be damaged or password protected. Upload a new copy."


def _table_lines(table: Table) -> list[str]:
    lines = []
    for row in table.rows:
        seen = set()
        cells = []
        for cell in row.cells:
            # A merged cell appears once per grid column it spans.
            if cell._tc not in seen:
                seen.add(cell._tc)
                cells.append(" ".join(cell.text.split()))
        if any(cells):
            lines.append(" | ".join(cells))
    return lines


def _docx_text(data: bytes) -> str:
    lines: list[str] = []
    for block in docx.Document(io.BytesIO(data)).iter_inner_content():
        if isinstance(block, Table):
            lines.extend(_table_lines(block))
        else:
            lines.append(block.text)
    return "\n".join(lines)


def _pdf_pages(data: bytes) -> list[tuple[int, str]]:
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        pages = [(index, (page.extract_text() or "").strip()) for index, page in enumerate(pdf.pages, 1)]
    return [(number, text) for number, text in pages if text]


def _plain_text(data: bytes) -> str:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise NoExtractableText(NOT_UTF8) from exc
    if "\x00" in text:
        raise NoExtractableText(NOT_UTF8)
    return text


def extract_pages(data: bytes, suffix: str) -> list[tuple[int | None, str]]:
    suffix = suffix.lower()
    if suffix == ".pdf":
        try:
            pages = _pdf_pages(data)
        except Exception as exc:  # noqa: BLE001 - the PDF libraries raise many unrelated types on a bad file
            raise NoExtractableText(UNREADABLE) from exc
        if not pages:
            raise NoExtractableText(NO_PDF_TEXT)
        return pages
    if suffix == ".docx":
        try:
            text = _docx_text(data)
        except Exception as exc:  # noqa: BLE001 - python-docx and zipfile raise many unrelated types on a bad file
            raise NoExtractableText(UNREADABLE) from exc
    elif suffix in {".txt", ".md"}:
        text = _plain_text(data)
    else:
        raise ValueError(f"Unsupported document type: {suffix}")
    if not text.strip():
        raise NoExtractableText(EMPTY)
    return [(None, text)]
