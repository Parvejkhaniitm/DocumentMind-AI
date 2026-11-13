from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.workspace import WorkspaceMember


def get_workspace_membership(db: Session, workspace_id: UUID, user_id: UUID) -> WorkspaceMember:
    membership = db.get(WorkspaceMember, (workspace_id, user_id))
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    return membership


def require_workspace_owner(db: Session, workspace_id: UUID, user_id: UUID) -> WorkspaceMember:
    membership = get_workspace_membership(db, workspace_id, user_id)
    if membership.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workspace owner role required.",
        )
    return membership
