from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.chunk import Chunk
from app.models.document import Document, DocumentPage
from app.models.user import User
from app.schemas.search import SearchRequest, SearchResponse, SearchResult
from app.services.embeddings import EmbeddingConfigurationError, SearchQueryTooLong, embed_query
from app.services.workspace_access import get_workspace_membership

router = APIRouter(prefix="/workspaces/{workspace_id}/search", tags=["search"])
CurrentDb = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post("", response_model=SearchResponse)
def search_workspace(
    workspace_id: UUID,
    payload: SearchRequest,
    db: CurrentDb,
    user: CurrentUser,
) -> SearchResponse:
    get_workspace_membership(db, workspace_id, user.id)
    try:
        query_vector = embed_query(payload.query)
    except EmbeddingConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The embedding model is not configured correctly.",
        ) from exc
    except SearchQueryTooLong as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Semantic search is temporarily unavailable.",
        ) from exc

    distance = Chunk.embedding.cosine_distance(query_vector)
    statement = (
        select(Chunk, Document, DocumentPage, distance.label("distance"))
        .join(Document, Document.id == Chunk.document_id)
        .join(DocumentPage, DocumentPage.id == Chunk.document_page_id)
        .where(
            Chunk.workspace_id == workspace_id,
            Document.workspace_id == workspace_id,
            Document.status == "ready",
            Chunk.embedding_model == settings.embedding_model,
        )
    )
    if payload.document_ids:
        statement = statement.where(Document.id.in_(payload.document_ids))

    rows = db.execute(statement.order_by(distance).limit(payload.limit))
    items = [
        SearchResult(
            chunk_id=chunk.id,
            document_id=document.id,
            document_name=document.filename,
            source_index=page.source_index,
            page_number=page.page_number,
            content=chunk.content,
            score=max(-1.0, min(1.0, 1.0 - float(distance_value))),
        )
        for chunk, document, page, distance_value in rows
    ]
    return SearchResponse(query=payload.query, items=items)
