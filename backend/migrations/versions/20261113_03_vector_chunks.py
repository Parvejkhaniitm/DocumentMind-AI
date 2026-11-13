"""Add semantic-search chunks and pgvector embeddings.

Revision ID: 20261113_03
Revises: 20261113_02
Create Date: 2026-11-13
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision: str = "20261113_03"
down_revision: str | None = "20261113_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("document_page_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_page_id"], ["document_pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "ordinal", name="uq_chunk_document_ordinal"),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.create_index("ix_chunks_workspace_id", "chunks", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_chunks_workspace_id", table_name="chunks")
    op.drop_index("ix_chunks_document_id", table_name="chunks")
    op.drop_table("chunks")
    # Keep the vector extension; other applications may use it in the same database.
