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


def _docx_with_table() -> bytes:
    document = docx.Document()
    document.add_paragraph("Before the table")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text, table.cell(0, 1).text = "Level", "Days"
    table.cell(1, 0).text, table.cell(1, 1).text = "Senior", "20"
    document.add_paragraph("After the table")
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_docx_tables_are_read_in_document_order():
    [(page, text)] = extract_pages(_docx_with_table(), ".docx")
    assert page is None
    assert text.splitlines() == ["Before the table", "Level | Days", "Senior | 20", "After the table"]


def test_docx_merged_cells_are_not_repeated():
    document = docx.Document()
    table = document.add_table(rows=1, cols=3)
    table.cell(0, 0).merge(table.cell(0, 1)).text = "Merged"
    table.cell(0, 2).text = "Other"
    buffer = io.BytesIO()
    document.save(buffer)
    assert extract_pages(buffer.getvalue(), ".docx") == [(None, "Merged | Other")]


@pytest.mark.parametrize("data,suffix", [(b"", ".txt"), (b"  \n\t ", ".md")])
def test_empty_text_files_have_no_extractable_text(data, suffix):
    with pytest.raises(NoExtractableText):
        extract_pages(data, suffix)


def test_empty_docx_has_no_extractable_text():
    buffer = io.BytesIO()
    docx.Document().save(buffer)
    with pytest.raises(NoExtractableText):
        extract_pages(buffer.getvalue(), ".docx")


@pytest.mark.parametrize("data", [b"\xff\xfe\x00\x01binary", "valid\x00with a NUL".encode()])
def test_binary_content_in_a_text_file_gets_a_clear_message(data):
    with pytest.raises(NoExtractableText) as caught:
        extract_pages(data, ".txt")
    assert "UTF-8" in str(caught.value)
    assert "retry" not in str(caught.value).lower()


def test_utf8_byte_order_mark_is_dropped():
    assert extract_pages("\ufeffhello".encode(), ".txt") == [(None, "hello")]


@pytest.mark.parametrize("suffix", [".pdf", ".docx"])
def test_corrupt_files_say_the_file_cannot_be_read(suffix):
    with pytest.raises(NoExtractableText) as caught:
        extract_pages(b"this is not really that format", suffix)
    assert "cannot be read" in str(caught.value)
    assert "retry" not in str(caught.value).lower()
