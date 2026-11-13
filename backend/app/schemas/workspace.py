from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

WorkspaceRole = Literal["owner", "editor", "viewer"]


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def workspace_name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Workspace name cannot be blank.")
        return value


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    created_by: UUID
    created_at: datetime
    role: WorkspaceRole


class MemberCreate(BaseModel):
    user_id: UUID
    role: Literal["editor", "viewer"] = "viewer"


class MemberRoleUpdate(BaseModel):
    role: Literal["editor", "viewer"]


class MemberRead(BaseModel):
    user_id: UUID
    email: str
    display_name: str
    role: WorkspaceRole
    joined_at: datetime
