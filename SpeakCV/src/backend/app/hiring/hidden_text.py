"""Extracts CV text without what a reader could not see. Best effort; the flag it sets draws no conclusion on intent."""
import io
import re
import zipfile
from dataclasses import dataclass

import docx
import pdfplumber
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.hyperlink import Hyperlink

from app.core.text_extract import NoExtractableText, extract_pages

MIN_VISIBLE_SIZE = 2
NEAR_WHITE = 0.95
MAX_PDF_PAGES = 30
MAX_DOCX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
UNREADABLE = "We could not read this file. Please upload a PDF or DOCX that opens normally."
NO_TEXT = "This file has no extractable text. Scanned documents are not supported."


class CvTooLarge(Exception):
    """A file too big to parse safely. The message is fixed and written for the candidate."""


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


def _lies_on(obj: dict, area: dict) -> bool:
    x, y = (obj["x0"] + obj["x1"]) / 2, (obj["top"] + obj["bottom"]) / 2
    return area["x0"] <= x <= area["x1"] and area["top"] <= y <= area["bottom"]


def _visibility_filter(page):
    """White text on a coloured sidebar is real content. Near-white text is hidden only with nothing filled beneath it.

    pdfplumber gives no drawing order and a curve is judged by its bounding box, so this is an approximation."""
    backgrounds = [
        shape for shape in (*page.rects, *page.curves)
        if shape.get("fill") and not _near_white_colour(shape.get("non_stroking_color"))
    ] + list(page.images)

    def keep(obj: dict) -> bool:
        if obj.get("object_type") != "char":
            return True
        if obj.get("size", MIN_VISIBLE_SIZE) < MIN_VISIBLE_SIZE:
            return False
        if not _near_white_colour(obj.get("non_stroking_color")):
            return True
        return any(_lies_on(obj, area) for area in backgrounds)

    return keep


def _without_whitespace(text: str) -> str:
    return "".join(text.split())


def _extract_pdf(data: bytes) -> CvText:
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        if len(pdf.pages) > MAX_PDF_PAGES:
            raise CvTooLarge(f"This PDF has more than {MAX_PDF_PAGES} pages. Please upload a shorter CV.")
        unfiltered = "\n".join(text for _, text in extract_pages(data, ".pdf"))
        pages = [(page.filter(_visibility_filter(page)).extract_text() or "").strip() for page in pdf.pages]
    text = "\n".join(page for page in pages if page)
    return CvText(text=text, hidden_detected=_without_whitespace(text) != _without_whitespace(unfiltered))


def _has_visible_shading(properties) -> bool:
    shading = properties.find(qn("w:shd")) if properties is not None else None
    fill = shading.get(qn("w:fill")) if shading is not None else None
    if not fill or not re.fullmatch(r"[0-9A-Fa-f]{6}", fill):  # "auto" means no colour was set
        return False
    return not all(int(fill[index:index + 2], 16) >= NEAR_WHITE * 255 for index in (0, 2, 4))


def _run_is_hidden(run, shaded: bool) -> bool:
    font = run.font
    if font.hidden:
        return True
    if font.size is not None and font.size.pt < MIN_VISIBLE_SIZE:
        return True
    rgb = font.color.rgb if font.color is not None else None
    if rgb is None or not all(part >= NEAR_WHITE * 255 for part in rgb):
        return False
    return not (shaded or _has_visible_shading(run._r.rPr))


def _docx_block_lines(container, flags: list[bool], shaded: bool = False) -> list[str]:
    lines: list[str] = []
    for block in container.iter_inner_content():
        if isinstance(block, Table):
            seen = set()
            for row in block.rows:
                for cell in row.cells:
                    if cell._tc not in seen:  # a merged cell is returned once per grid position
                        seen.add(cell._tc)
                        lines.extend(_docx_block_lines(cell, flags, shaded or _has_visible_shading(cell._tc.tcPr)))
            continue
        parts: list[str] = []
        block_shaded = shaded or _has_visible_shading(block._p.pPr)
        for item in block.iter_inner_content():
            for run in item.runs if isinstance(item, Hyperlink) else (item,):
                if _run_is_hidden(run, block_shaded):
                    flags.append(True)
                else:
                    parts.append(run.text)
        lines.append("".join(parts))
    return lines


def _check_docx_size(data: bytes) -> None:
    """Checked before parsing. A size the zip understates does not help an attacker: zipfile stops reading at it."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        total = sum(info.file_size for info in archive.infolist())
    if total > MAX_DOCX_UNCOMPRESSED_BYTES:
        limit = MAX_DOCX_UNCOMPRESSED_BYTES // (1024 * 1024)
        raise CvTooLarge(f"This DOCX is larger than {limit} MB when unpacked. Please upload a smaller file.")


def _extract_docx(data: bytes) -> CvText:
    _check_docx_size(data)
    flags: list[bool] = []
    lines = _docx_block_lines(docx.Document(io.BytesIO(data)), flags)
    return CvText(text="\n".join(line for line in lines if line.strip()), hidden_detected=bool(flags))


def extract_cv(data: bytes, suffix: str) -> CvText:
    suffix = suffix.lower()
    if suffix not in {".pdf", ".docx"}:
        raise ValueError(f"Unsupported CV type: {suffix}")
    try:
        result = _extract_pdf(data) if suffix == ".pdf" else _extract_docx(data)
    except (NoExtractableText, CvTooLarge):
        raise
    except Exception as exc:
        # The parsers fail in many ways on a damaged or hostile file. Their messages are not for candidates.
        raise NoExtractableText(UNREADABLE) from exc
    if not result.text.strip():
        raise NoExtractableText(NO_TEXT)
    return result
