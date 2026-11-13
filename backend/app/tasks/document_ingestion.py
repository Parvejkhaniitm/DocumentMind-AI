from uuid import UUID

from sqlalchemy import delete, select

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.chunk import Chunk
from app.models.document import Document, DocumentPage
from app.services.document_extraction import (
    DocumentProcessingError,
    extract_docx,
    extract_pdf,
)
from app.services.chunking import chunk_text
from app.services.embeddings import EmbeddingConfigurationError, embed_texts, get_tokenizer
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
            tokenizer = get_tokenizer()
            chunk_descriptors = []
            for unit in result.units:
                for text in chunk_text(unit.text, tokenizer):
                    chunk_descriptors.append((unit.source_index, text))
            if not chunk_descriptors:
                raise DocumentProcessingError("No searchable text could be produced from this document.")
            vectors = embed_texts([text for _, text in chunk_descriptors])
        except (DocumentProcessingError, EmbeddingConfigurationError) as exc:
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
        db.execute(delete(Chunk).where(Chunk.document_id == parsed_id))
        db.execute(delete(DocumentPage).where(DocumentPage.document_id == parsed_id))
        page_records = [
            DocumentPage(
                document_id=parsed_id,
                source_index=unit.source_index,
                page_number=unit.page_number,
                text=unit.text,
            )
            for unit in result.units
        ]
        db.add_all(page_records)
        db.flush()
        pages_by_source = {page.source_index: page for page in page_records}
        db.add_all(
            [
                Chunk(
                    document_id=parsed_id,
                    workspace_id=document.workspace_id,
                    document_page_id=pages_by_source[source_index].id,
                    ordinal=ordinal,
                    content=text,
                    embedding=vector,
                    embedding_model=settings.embedding_model,
                )
                for ordinal, ((source_index, text), vector) in enumerate(
                    zip(chunk_descriptors, vectors, strict=True), start=1
                )
            ]
        )
        document.page_count = result.page_count
        document.status = "ready"
        document.error_summary = None
        db.commit()
