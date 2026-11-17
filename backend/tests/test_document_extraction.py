from io import BytesIO

import fitz
import pytest
from docx import Document as WordDocument

from app.core.config import settings
from app.services.document_extraction import DocumentProcessingError, extract_docx, extract_pdf


def _pdf_bytes(*pages: str, password: str | None = None) -> bytes:
    document = fitz.open()
    for text in pages:
        page = document.new_page()
        page.insert_text((72, 72), text)
    options = {"encryption": fitz.PDF_ENCRYPT_AES_256, "owner_pw": "owner"} if password else {}
    if password:
        options["user_pw"] = password
    return document.tobytes(**options)


def _docx_bytes() -> bytes:
    document = WordDocument()
    document.add_paragraph("Policy overview")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Leave"
    table.cell(0, 1).text = "12 days"
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_pdf_extraction_preserves_page_numbers_and_ignores_blank_pages() -> None:
    result = extract_pdf(_pdf_bytes("First page policy", "", "Third page policy"))

    assert result.page_count == 3
    assert [(unit.page_number, unit.text.strip()) for unit in result.units] == [
        (1, "First page policy"),
        (3, "Third page policy"),
    ]


def test_pdf_extraction_rejects_invalid_encrypted_and_scanned_documents() -> None:
    with pytest.raises(DocumentProcessingError, match="valid PDF"):
        extract_pdf(b"not a pdf")
    with pytest.raises(DocumentProcessingError, match="Password-protected"):
        extract_pdf(_pdf_bytes("Private policy", password="secret"))
    with pytest.raises(DocumentProcessingError, match="No selectable text"):
        extract_pdf(_pdf_bytes(""))


def test_pdf_extraction_enforces_page_and_extracted_text_limits(monkeypatch) -> None:
    monkeypatch.setattr(settings, "max_pdf_pages", 1)
    with pytest.raises(DocumentProcessingError, match="page processing limit"):
        extract_pdf(_pdf_bytes("One", "Two"))

    monkeypatch.setattr(settings, "max_pdf_pages", 10)
    monkeypatch.setattr(settings, "max_extracted_text_chars", 3)
    with pytest.raises(DocumentProcessingError, match="text is too large"):
        extract_pdf(_pdf_bytes("Longer policy"))


def test_docx_extraction_preserves_paragraphs_and_table_content() -> None:
    result = extract_docx(_docx_bytes())

    assert result.page_count is None
    assert len(result.units) == 1
    assert result.units[0].page_number is None
    assert "Policy overview" in result.units[0].text
    assert "Leave | 12 days" in result.units[0].text


def test_docx_extraction_rejects_invalid_empty_and_oversized_text(monkeypatch) -> None:
    with pytest.raises(DocumentProcessingError, match="valid"):
        extract_docx(b"not a docx")

    empty = WordDocument()
    buffer = BytesIO()
    empty.save(buffer)
    with pytest.raises(DocumentProcessingError, match="No text content"):
        extract_docx(buffer.getvalue())

    monkeypatch.setattr(settings, "max_extracted_text_chars", 3)
    with pytest.raises(DocumentProcessingError, match="text is too large"):
        extract_docx(_docx_bytes())
