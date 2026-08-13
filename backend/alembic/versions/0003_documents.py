"""Create private course documents.

Revision ID: 0003_documents
Revises: 0002_courses
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_documents"
down_revision: str | None = "0002_courses"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    document_status = postgresql.ENUM(
        "uploaded",
        "processing",
        "ready",
        "failed",
        name="document_status",
        create_type=False,
    )
    postgresql.ENUM(
        "uploaded", "processing", "ready", "failed", name="document_status"
    ).create(op.get_bind(), checkfirst=True)
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("object_key", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("status", document_status, nullable=False),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
    )
    op.create_index(
        "ix_documents_course_created",
        "documents",
        ["course_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_documents_course_created", table_name="documents")
    op.drop_table("documents")
    sa.Enum(name="document_status").drop(op.get_bind(), checkfirst=True)
