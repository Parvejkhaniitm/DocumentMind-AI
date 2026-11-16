from dataclasses import dataclass
from io import BytesIO

import fitz
from docx import Document as WordDocument
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.core.config import settings


class DocumentProcessingError(ValueError):
    """A permanent input error that should be shown as a safe document status."""


@dataclass(frozen=True)
class ExtractedUnit:
    source_index: int
    page_number: int | None
    text: str


@dataclass(frozen=True)
class ExtractionResult:
    units: list[ExtractedUnit]
    page_count: int | None


def _check_text_limit(units: list[ExtractedUnit]) -> None:
    if sum(len(unit.text) for unit in units) > settings.max_extracted_text_chars:
        raise DocumentProcessingError("The extracted document text is too large to process.")


def extract_pdf(content: bytes) -> ExtractionResult:
    try:
        with fitz.open(stream=content, filetype="pdf") as pdf:
            if pdf.is_encrypted:
                raise DocumentProcessingError("Password-protected PDFs are not supported yet.")
            if pdf.page_count > settings.max_pdf_pages:
                raise DocumentProcessingError(
                    f"PDF exceeds the {settings.max_pdf_pages}-page processing limit."
                )
            units = []
            for index, page in enumerate(pdf, start=1):
                text = page.get_text("text")
                if text.strip():
                    units.append(ExtractedUnit(source_index=index, page_number=index, text=text))
            page_count = pdf.page_count
    except DocumentProcessingError:
        raise
    except Exception as exc:
        raise DocumentProcessingError(
            "The PDF could not be read. Check that it is a valid PDF."
        ) from exc

    _check_text_limit(units)
    if not units:
        raise DocumentProcessingError(
            "No selectable text was found. Scanned-document OCR is not available yet."
        )
    return ExtractionResult(units=units, page_count=page_count)


def extract_docx(content: bytes) -> ExtractionResult:
    try:
        document = WordDocument(BytesIO(content))
        blocks: list[str] = []
        for child in document.element.body.iterchildren():
            if isinstance(child, CT_P):
                text = Paragraph(child, document).text.strip()
                if text:
                    blocks.append(text)
            elif isinstance(child, CT_Tbl):
                table = Table(child, document)
                for row in table.rows:
                    cells = [cell.text.strip() for cell in row.cells]
                    row_text = " | ".join(value for value in cells if value)
                    if row_text:
                        blocks.append(row_text)
    except Exception as exc:
        raise DocumentProcessingError(
            "The DOCX file could not be read. Check that it is valid."
        ) from exc

    text = "\n".join(blocks).strip()
    unit = ExtractedUnit(source_index=1, page_number=None, text=text)
    _check_text_limit([unit])
    if not text:
        raise DocumentProcessingError("No text content was found in the DOCX file.")
    return ExtractionResult(units=[unit], page_count=None)
