import io

import docx
import pytest
from reportlab.pdfgen import canvas

from app.core.text_extract import NoExtractableText, extract_pages


def _pdf(pages: list[str]) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    for text in pages:
        if text:
            pdf.drawString(72, 720, text)
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def test_txt_and_md_return_a_single_unnumbered_page():
    assert extract_pages(b"hello", ".txt") == [(None, "hello")]
    assert extract_pages("# Tiêu đề".encode(), ".MD") == [(None, "# Tiêu đề")]


def test_docx_paragraphs_are_joined():
    document = docx.Document()
    document.add_paragraph("First line")
    document.add_paragraph("Second line")
    buffer = io.BytesIO()
    document.save(buffer)
    assert extract_pages(buffer.getvalue(), ".docx") == [(None, "First line\nSecond line")]


def test_pdf_pages_are_numbered_from_one_and_blank_pages_skipped():
    pages = extract_pages(_pdf(["Alpha page", "", "Gamma page"]), ".pdf")
    assert pages == [(1, "Alpha page"), (3, "Gamma page")]


def test_pdf_without_text_raises():
    with pytest.raises(NoExtractableText):
        extract_pages(_pdf([""]), ".pdf")


def test_unsupported_suffix_raises():
    with pytest.raises(ValueError):
        extract_pages(b"x", ".exe")
