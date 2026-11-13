from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.schemas.workspace import (
    MemberCreate,
    MemberRead,
    MemberRoleUpdate,
    WorkspaceCreate,
    WorkspaceRead,
)
from app.services.workspace_access import get_workspace_membership, require_workspace_owner

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
CurrentDb = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post("", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
def create_workspace(payload: WorkspaceCreate, db: CurrentDb, user: CurrentUser) -> WorkspaceRead:
    workspace = Workspace(name=payload.name.strip(), created_by=user.id)
    db.add(workspace)
    db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
    db.commit()
    db.refresh(workspace)
    return WorkspaceRead(
        id=workspace.id,
        name=workspace.name,
        created_by=workspace.created_by,
        created_at=workspace.created_at,
        role="owner",
    )


@router.get("", response_model=list[WorkspaceRead])
def list_workspaces(db: CurrentDb, user: CurrentUser) -> list[WorkspaceRead]:
    rows = db.execute(
        select(Workspace, WorkspaceMember.role)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user.id)
        .order_by(Workspace.created_at.desc())
    )
    return [
        WorkspaceRead(
            id=workspace.id,
            name=workspace.name,
            created_by=workspace.created_by,
            created_at=workspace.created_at,
            role=role,
        )
        for workspace, role in rows
    ]


@router.get("/{workspace_id}", response_model=WorkspaceRead)
def get_workspace(workspace_id: UUID, db: CurrentDb, user: CurrentUser) -> WorkspaceRead:
    membership = get_workspace_membership(db, workspace_id, user.id)
    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    return WorkspaceRead(
        id=workspace.id,
        name=workspace.name,
        created_by=workspace.created_by,
        created_at=workspace.created_at,
        role=membership.role,
    )


@router.get("/{workspace_id}/members", response_model=list[MemberRead])
def list_members(workspace_id: UUID, db: CurrentDb, user: CurrentUser) -> list[MemberRead]:
    get_workspace_membership(db, workspace_id, user.id)
    rows = db.execute(
        select(User.id, User.email, User.display_name, WorkspaceMember.role, WorkspaceMember.joined_at)
        .join(WorkspaceMember, WorkspaceMember.user_id == User.id)
        .where(WorkspaceMember.workspace_id == workspace_id)
        .order_by(WorkspaceMember.joined_at.asc())
    )
    return [
        MemberRead(
            user_id=user_id,
            email=email,
            display_name=display_name,
            role=role,
            joined_at=joined_at,
        )
        for user_id, email, display_name, role, joined_at in rows
    ]


@router.post("/{workspace_id}/members", response_model=MemberRead, status_code=status.HTTP_201_CREATED)
def add_member(
    workspace_id: UUID,
    payload: MemberCreate,
    db: CurrentDb,
    user: CurrentUser,
) -> MemberRead:
    require_workspace_owner(db, workspace_id, user.id)
    target_user = db.scalar(select(User).where(User.id == payload.user_id))
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    member = WorkspaceMember(workspace_id=workspace_id, user_id=target_user.id, role=payload.role)
    db.add(member)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That user is already a workspace member.",
        ) from exc
    db.refresh(member)
    return MemberRead(
        user_id=target_user.id,
        email=target_user.email,
        display_name=target_user.display_name,
        role=member.role,
        joined_at=member.joined_at,
    )


@router.patch("/{workspace_id}/members/{member_user_id}", response_model=MemberRead)
def update_member_role(
    workspace_id: UUID,
    member_user_id: UUID,
    payload: MemberRoleUpdate,
    db: CurrentDb,
    user: CurrentUser,
) -> MemberRead:
    require_workspace_owner(db, workspace_id, user.id)
    member = get_workspace_membership(db, workspace_id, member_user_id)
    if member.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transfer workspace ownership before changing an owner's role.",
        )
    member.role = payload.role
    db.commit()
    db.refresh(member)
    target_user = db.get(User, member_user_id)
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return MemberRead(
        user_id=target_user.id,
        email=target_user.email,
        display_name=target_user.display_name,
        role=member.role,
        joined_at=member.joined_at,
    )


@router.delete(
    "/{workspace_id}/members/{member_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def remove_member(
    workspace_id: UUID,
    member_user_id: UUID,
    db: CurrentDb,
    user: CurrentUser,
) -> Response:
    require_workspace_owner(db, workspace_id, user.id)
    member = get_workspace_membership(db, workspace_id, member_user_id)
    if member.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transfer workspace ownership before removing an owner.",
        )
    db.delete(member)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
