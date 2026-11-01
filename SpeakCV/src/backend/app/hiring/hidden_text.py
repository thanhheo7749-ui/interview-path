"""Extracts CV text without what a reader could not see. Best effort; the flag it sets draws no conclusion on intent."""
import io
from dataclasses import dataclass

import docx
import pdfplumber
from docx.table import Table
from docx.text.hyperlink import Hyperlink

from app.core.text_extract import NoExtractableText, extract_pages

MIN_VISIBLE_SIZE = 2
NEAR_WHITE = 0.95
UNREADABLE = "We could not read this file. Please upload a PDF or DOCX that opens normally."
NO_TEXT = "This file has no extractable text. Scanned documents are not supported."


@dataclass(frozen=True)
class CvText:
    text: str
    hidden_detected: bool


def _near_white_colour(color) -> bool:
    if color is None:
        return False
    components = color if isinstance(color, (tuple, list)) else (color,)
    if not components or not all(isinstance(part, (int, float)) for part in components):
        return False
    if len(components) == 4:  # CMYK: white is no ink at all, and full ink is black
        return all(part <= 1 - NEAR_WHITE for part in components)
    return all(part >= NEAR_WHITE for part in components)


def _keep_pdf_object(obj: dict) -> bool:
    if obj.get("object_type") != "char":
        return True
    return obj.get("size", MIN_VISIBLE_SIZE) >= MIN_VISIBLE_SIZE and not _near_white_colour(obj.get("non_stroking_color"))


def _without_whitespace(text: str) -> str:
    return "".join(text.split())


def _extract_pdf(data: bytes) -> CvText:
    unfiltered = "\n".join(text for _, text in extract_pages(data, ".pdf"))
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        pages = [(page.filter(_keep_pdf_object).extract_text() or "").strip() for page in pdf.pages]
    text = "\n".join(page for page in pages if page)
    return CvText(text=text, hidden_detected=_without_whitespace(text) != _without_whitespace(unfiltered))


def _run_is_hidden(run) -> bool:
    font = run.font
    if font.hidden:
        return True
    if font.size is not None and font.size.pt < MIN_VISIBLE_SIZE:
        return True
    rgb = font.color.rgb if font.color is not None else None
    return rgb is not None and all(part >= NEAR_WHITE * 255 for part in rgb)


def _docx_block_lines(container, flags: list[bool]) -> list[str]:
    lines: list[str] = []
    for block in container.iter_inner_content():
        if isinstance(block, Table):
            seen = set()
            for row in block.rows:
                for cell in row.cells:
                    if cell._tc not in seen:  # a merged cell is returned once per grid position
                        seen.add(cell._tc)
                        lines.extend(_docx_block_lines(cell, flags))
            continue
        parts: list[str] = []
        for item in block.iter_inner_content():
            for run in item.runs if isinstance(item, Hyperlink) else (item,):
                if _run_is_hidden(run):
                    flags.append(True)
                else:
                    parts.append(run.text)
        lines.append("".join(parts))
    return lines


def _extract_docx(data: bytes) -> CvText:
    flags: list[bool] = []
    lines = _docx_block_lines(docx.Document(io.BytesIO(data)), flags)
    return CvText(text="\n".join(line for line in lines if line.strip()), hidden_detected=bool(flags))


def extract_cv(data: bytes, suffix: str) -> CvText:
    suffix = suffix.lower()
    if suffix not in {".pdf", ".docx"}:
        raise ValueError(f"Unsupported CV type: {suffix}")
    try:
        result = _extract_pdf(data) if suffix == ".pdf" else _extract_docx(data)
    except NoExtractableText:
        raise
    except Exception as exc:
        # The parsers fail in many ways on a damaged or hostile file. Their messages are not for candidates.
        raise NoExtractableText(UNREADABLE) from exc
    if not result.text.strip():
        raise NoExtractableText(NO_TEXT)
    return result
