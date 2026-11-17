from io import BytesIO

import fitz
import pytest
from docx import Document as WordDocument
from fastapi import HTTPException, UploadFile

from app.api.v1.routes.documents import _read_upload, _safe_filename, _validate_docx
from app.core.config import settings


def _valid_docx() -> bytes:
    document = WordDocument()
    document.add_paragraph("Valid content")
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _upload(filename: str, content: bytes) -> UploadFile:
    return UploadFile(filename=filename, file=BytesIO(content))


def test_safe_filename_strips_paths_and_rejects_empty_or_long_names() -> None:
    assert _safe_filename(r"C:\private\policy.pdf") == "policy.pdf"
    with pytest.raises(HTTPException) as empty:
        _safe_filename("../")
    assert empty.value.status_code == 400
    with pytest.raises(HTTPException, match="too long"):
        _safe_filename(f"{'x' * 256}.pdf")


def test_upload_accepts_pdf_only_when_extension_and_signature_match() -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Policy")
    pdf = document.tobytes()

    filename, content_type, content = _read_upload(_upload("policy.pdf", pdf))

    assert filename == "policy.pdf"
    assert content_type == "application/pdf"
    assert content == pdf
    with pytest.raises(HTTPException) as mismatch:
        _read_upload(_upload("policy.pdf", b"not a PDF"))
    assert mismatch.value.status_code == 415


def test_upload_validates_docx_archive_and_rejects_unsupported_type() -> None:
    content = _valid_docx()
    assert _read_upload(_upload("policy.docx", content))[2] == content

    with pytest.raises(HTTPException) as invalid:
        _validate_docx(b"not a zip archive")
    assert invalid.value.status_code == 415

    with pytest.raises(HTTPException) as unsupported:
        _read_upload(_upload("notes.txt", b"plain text"))
    assert unsupported.value.status_code == 415


def test_upload_enforces_configured_size_and_docx_expansion_limits(monkeypatch) -> None:
    monkeypatch.setattr(settings, "max_upload_bytes", 8)
    with pytest.raises(HTTPException) as upload_size:
        _read_upload(_upload("policy.pdf", b"%PDF-" + b"x" * 10))
    assert upload_size.value.status_code == 413

    monkeypatch.setattr(settings, "max_docx_uncompressed_bytes", 1)
    with pytest.raises(HTTPException) as expansion_size:
        _validate_docx(_valid_docx())
    assert expansion_size.value.status_code == 413
