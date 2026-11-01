import io

import docx
import pdfplumber


class NoExtractableText(Exception):
    """A PDF with no text layer. OCR is out of scope."""


def extract_pages(data: bytes, suffix: str) -> list[tuple[int | None, str]]:
    suffix = suffix.lower()
    if suffix == ".pdf":
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = [(index, (page.extract_text() or "").strip()) for index, page in enumerate(pdf.pages, 1)]
        pages = [(number, text) for number, text in pages if text]
        if not pages:
            raise NoExtractableText("This PDF has no extractable text. Scanned documents are not supported.")
        return pages
    if suffix == ".docx":
        text = "\n".join(paragraph.text for paragraph in docx.Document(io.BytesIO(data)).paragraphs)
        return [(None, text)]
    if suffix in {".txt", ".md"}:
        return [(None, data.decode("utf-8", errors="replace"))]
    raise ValueError(f"Unsupported document type: {suffix}")
