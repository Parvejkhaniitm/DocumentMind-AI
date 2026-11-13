from hashlib import sha256
import logging
from pathlib import PurePosixPath
from typing import Annotated
from unicodedata import category
from uuid import UUID, uuid4
from zipfile import BadZipFile, ZipFile
from io import BytesIO

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.document import Document
from app.models.user import User
from app.schemas.document import DocumentRead
from app.services.object_storage import delete_object, put_object
from app.services.workspace_access import get_workspace_membership
from app.tasks.document_ingestion import process_document

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workspaces/{workspace_id}/documents", tags=["documents"])
CurrentDb = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
PDF_TYPE = "application/pdf"
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _safe_filename(original: str | None) -> str:
    name = PurePosixPath((original or "").replace("\\", "/")).name
    name = "".join(character for character in name if category(character) != "Cc").strip()
    if not name or name in {".", ".."}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A valid filename is required.")
    if len(name) > 255:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is too long.")
    return name


def _validate_docx(content: bytes) -> None:
    try:
        with ZipFile(BytesIO(content)) as archive:
            names = set(archive.namelist())
            total_uncompressed_bytes = sum(item.file_size for item in archive.infolist())
    except (BadZipFile, OSError) as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="File is not a valid DOCX.") from exc

    if "[Content_Types].xml" not in names or "word/document.xml" not in names:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="File is not a valid DOCX.")
    if total_uncompressed_bytes > settings.max_docx_uncompressed_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="DOCX expands beyond the processing limit.")


def _read_upload(upload: UploadFile) -> tuple[str, str, bytes]:
    filename = _safe_filename(upload.filename)
    extension = PurePosixPath(filename).suffix.lower()
    content = upload.file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File exceeds the upload size limit.")

    if extension == ".pdf" and b"%PDF-" in content[:1024]:
        return filename, PDF_TYPE, content
    if extension == ".docx":
        _validate_docx(content)
        return filename, DOCX_TYPE, content
    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail="Only valid PDF and DOCX files are supported.",
    )


def _require_editor_role(db: Session, workspace_id: UUID, user_id: UUID) -> None:
    membership = get_workspace_membership(db, workspace_id, user_id)
    if membership.role not in {"owner", "editor"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workspace editor role required.",
        )


@router.post("", response_model=DocumentRead, status_code=status.HTTP_202_ACCEPTED)
def upload_document(
    workspace_id: UUID,
    db: CurrentDb,
    user: CurrentUser,
    upload: Annotated[UploadFile, File(description="PDF or DOCX document")],
) -> Document:
    _require_editor_role(db, workspace_id, user.id)
    filename, content_type, content = _read_upload(upload)
    document_id = uuid4()
    object_key = f"workspaces/{workspace_id}/documents/{document_id}/{uuid4().hex}"

    try:
        put_object(object_key=object_key, content=content, content_type=content_type)
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document storage is temporarily unavailable.",
        ) from exc

    document = Document(
        id=document_id,
        workspace_id=workspace_id,
        uploaded_by=user.id,
        filename=filename,
        content_type=content_type,
        size_bytes=len(content),
        sha256=sha256(content).hexdigest(),
        object_key=object_key,
        status="queued",
    )
    db.add(document)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        try:
            delete_object(object_key=object_key)
        except (BotoCoreError, ClientError):
            logger.warning("Could not clean up an untracked document object after a database error.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document metadata could not be saved.",
        ) from exc

    try:
        process_document.delay(str(document.id))
    except Exception as exc:
        document.status = "failed"
        document.error_summary = "Processing could not be queued. Check the worker service and upload again."
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document was stored, but processing could not be queued.",
        ) from exc

    db.refresh(document)
    return document


@router.get("", response_model=list[DocumentRead])
def list_documents(workspace_id: UUID, db: CurrentDb, user: CurrentUser) -> list[Document]:
    get_workspace_membership(db, workspace_id, user.id)
    return list(
        db.scalars(
            select(Document)
            .where(Document.workspace_id == workspace_id)
            .order_by(Document.created_at.desc())
        )
    )


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(document_id: UUID, workspace_id: UUID, db: CurrentDb, user: CurrentUser) -> Document:
    get_workspace_membership(db, workspace_id, user.id)
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.workspace_id == workspace_id,
        )
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_document(
    document_id: UUID,
    workspace_id: UUID,
    db: CurrentDb,
    user: CurrentUser,
) -> Response:
    _require_editor_role(db, workspace_id, user.id)
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.workspace_id == workspace_id,
        )
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    document.status = "deleting"
    db.commit()
    try:
        delete_object(object_key=document.object_key)
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document storage is temporarily unavailable. Retry deletion later.",
        ) from exc
    db.delete(document)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{document_id}/reprocess", response_model=DocumentRead, status_code=status.HTTP_202_ACCEPTED)
def reprocess_document(
    document_id: UUID,
    workspace_id: UUID,
    db: CurrentDb,
    user: CurrentUser,
) -> Document:
    _require_editor_role(db, workspace_id, user.id)
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.workspace_id == workspace_id,
        )
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    if document.status in {"queued", "processing", "deleting"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document cannot be reprocessed while another job is active.",
        )

    document.status = "queued"
    document.error_summary = None
    db.commit()
    try:
        process_document.delay(str(document.id))
    except Exception as exc:
        document.status = "failed"
        document.error_summary = "Processing could not be queued. Check the worker service and retry."
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document was saved, but processing could not be queued.",
        ) from exc
    db.refresh(document)
    return document
