from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.chunk import Chunk
from app.models.conversation import Conversation, Message, MessageSource
from app.models.document import Document, DocumentPage
from app.models.user import User
from app.schemas.conversation import (
    AnswerRead,
    CitationRead,
    ConversationCreate,
    ConversationDetail,
    ConversationRead,
    MessageRead,
    QuestionCreate,
)
from app.services.embeddings import EmbeddingConfigurationError, SearchQueryTooLong
from app.services.rag import AnswerProviderError, generate_answer, retrieve_evidence
from app.services.workspace_access import get_workspace_membership

router = APIRouter(prefix="/workspaces/{workspace_id}/conversations", tags=["conversations"])
CurrentDb = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def _conversation_or_404(
    db: Session, workspace_id: UUID, conversation_id: UUID, user_id: UUID
) -> Conversation:
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.workspace_id == workspace_id,
            Conversation.user_id == user_id,
        )
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    return conversation


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
def create_conversation(
    workspace_id: UUID,
    payload: ConversationCreate,
    db: CurrentDb,
    user: CurrentUser,
) -> Conversation:
    get_workspace_membership(db, workspace_id, user.id)
    conversation = Conversation(
        workspace_id=workspace_id,
        user_id=user.id,
        title=payload.title or "New conversation",
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("", response_model=list[ConversationRead])
def list_conversations(workspace_id: UUID, db: CurrentDb, user: CurrentUser) -> list[Conversation]:
    get_workspace_membership(db, workspace_id, user.id)
    return list(
        db.scalars(
            select(Conversation)
            .where(Conversation.workspace_id == workspace_id, Conversation.user_id == user.id)
            .order_by(Conversation.created_at.desc())
        )
    )


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    workspace_id: UUID,
    conversation_id: UUID,
    db: CurrentDb,
    user: CurrentUser,
) -> ConversationDetail:
    get_workspace_membership(db, workspace_id, user.id)
    conversation = _conversation_or_404(db, workspace_id, conversation_id, user.id)
    messages = list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at, Message.id)
        )
    )
    message_ids = [message.id for message in messages]
    source_rows = (
        db.execute(
            select(MessageSource, Chunk, Document, DocumentPage)
            .join(Chunk, Chunk.id == MessageSource.chunk_id)
            .join(Document, Document.id == Chunk.document_id)
            .join(DocumentPage, DocumentPage.id == Chunk.document_page_id)
            .where(
                MessageSource.message_id.in_(message_ids),
                Chunk.workspace_id == workspace_id,
                Document.workspace_id == workspace_id,
            )
        ).all()
        if message_ids
        else []
    )
    sources_by_message: dict[UUID, list[CitationRead]] = {}
    for source, chunk, document, page in source_rows:
        sources_by_message.setdefault(source.message_id, []).append(
            CitationRead(
                chunk_id=chunk.id,
                document_id=document.id,
                document_name=document.filename,
                page_number=page.page_number,
                source_index=page.source_index,
                relevance_score=source.relevance_score,
            )
        )
    return ConversationDetail(
        id=conversation.id,
        workspace_id=conversation.workspace_id,
        title=conversation.title,
        created_at=conversation.created_at,
        messages=[
            MessageRead(
                id=message.id,
                role=message.role,
                content=message.content,
                answer_status=message.answer_status,
                created_at=message.created_at,
                sources=sources_by_message.get(message.id, []),
            )
            for message in messages
        ],
    )


@router.post(
    "/{conversation_id}/messages", response_model=AnswerRead, status_code=status.HTTP_201_CREATED
)
def ask_question(
    workspace_id: UUID,
    conversation_id: UUID,
    payload: QuestionCreate,
    db: CurrentDb,
    user: CurrentUser,
) -> AnswerRead:
    get_workspace_membership(db, workspace_id, user.id)
    conversation = _conversation_or_404(db, workspace_id, conversation_id, user.id)
    try:
        evidence = retrieve_evidence(db, workspace_id, payload.content)
    except SearchQueryTooLong as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except EmbeddingConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding model is unavailable.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document retrieval is temporarily unavailable.",
        ) from exc

    evidence = [item for item in evidence if item["score"] >= settings.rag_min_relevance]
    history_rows = list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(8)
        )
    )
    history = [{"role": row.role, "content": row.content} for row in reversed(history_rows)]

    if not evidence:
        answer = (
            "I could not find enough relevant information in this workspace's processed documents "
            "to answer that question."
        )
        cited_ids: list[UUID] = []
        answer_status = "insufficient_evidence"
    else:
        try:
            answer, cited_ids = generate_answer(payload.content, evidence, history)
        except AnswerProviderError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The answer provider is unavailable or not configured.",
            ) from exc
        if not cited_ids:
            answer = "I could not produce an answer supported by the retrieved document passages."
            answer_status = "insufficient_evidence"
        else:
            answer_status = "answered"

    user_message = Message(conversation_id=conversation.id, role="user", content=payload.content)
    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=answer,
        answer_status=answer_status,
    )
    db.add_all([user_message, assistant_message])
    db.flush()
    evidence_by_id = {item["chunk"].id: item for item in evidence}
    for chunk_id in cited_ids:
        item = evidence_by_id[chunk_id]
        db.add(
            MessageSource(
                message_id=assistant_message.id,
                chunk_id=chunk_id,
                relevance_score=item["score"],
            )
        )
    if conversation.title == "New conversation":
        conversation.title = payload.content[:197].rstrip() + (
            "..." if len(payload.content) > 200 else ""
        )
    db.commit()
    db.refresh(assistant_message)

    citations = [
        CitationRead(
            chunk_id=chunk_id,
            document_id=evidence_by_id[chunk_id]["document"].id,
            document_name=evidence_by_id[chunk_id]["document"].filename,
            page_number=evidence_by_id[chunk_id]["page"].page_number,
            source_index=evidence_by_id[chunk_id]["page"].source_index,
            relevance_score=evidence_by_id[chunk_id]["score"],
        )
        for chunk_id in cited_ids
    ]
    return AnswerRead(
        id=assistant_message.id,
        role=assistant_message.role,
        content=assistant_message.content,
        answer_status=assistant_message.answer_status,
        created_at=assistant_message.created_at,
        sources=citations,
    )
