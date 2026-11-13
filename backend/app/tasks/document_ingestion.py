from uuid import UUID

from sqlalchemy import delete, select

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.document import Document, DocumentPage
from app.services.document_extraction import (
    DocumentProcessingError,
    extract_docx,
    extract_pdf,
)
from app.services.object_storage import get_object


@celery_app.task(bind=True, name="documind.documents.process")
def process_document(self, document_id: str) -> None:
    try:
        parsed_id = UUID(document_id)
    except ValueError:
        return

    with SessionLocal() as db:
        document = db.scalar(
            select(Document)
            .where(Document.id == parsed_id)
            .execution_options(populate_existing=True)
        )
        if document is None or document.status == "deleting":
            return

        document.status = "processing"
        document.error_summary = None
        db.commit()

        try:
            content = get_object(object_key=document.object_key)
            result = (
                extract_pdf(content)
                if document.content_type == "application/pdf"
                else extract_docx(content)
            )
        except DocumentProcessingError as exc:
            current_document = db.scalar(
                select(Document)
                .where(Document.id == parsed_id)
                .execution_options(populate_existing=True)
            )
            if current_document is not None and current_document.status != "deleting":
                current_document.status = "failed"
                current_document.error_summary = str(exc)
                db.commit()
            return
        except Exception as exc:
            db.rollback()
            if self.request.retries < 3:
                raise self.retry(exc=exc, countdown=10 * (2**self.request.retries), max_retries=3)
            document = db.get(Document, parsed_id)
            if document is not None and document.status != "deleting":
                document.status = "failed"
                document.error_summary = "Processing could not finish after several attempts."
                db.commit()
            return

        document = db.scalar(
            select(Document)
            .where(Document.id == parsed_id)
            .execution_options(populate_existing=True)
        )
        if document is None or document.status == "deleting":
            return
        db.execute(delete(DocumentPage).where(DocumentPage.document_id == parsed_id))
        db.add_all(
            [
                DocumentPage(
                    document_id=parsed_id,
                    source_index=unit.source_index,
                    page_number=unit.page_number,
                    text=unit.text,
                )
                for unit in result.units
            ]
        )
        document.page_count = result.page_count
        document.status = "ready"
        document.error_summary = None
        db.commit()
