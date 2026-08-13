"""Create quizzes and validated questions.

Revision ID: 0006_quizzes
Revises: 0005_conversations
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006_quizzes"
down_revision: str | None = "0005_conversations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    question_type = postgresql.ENUM(
        "multiple_choice",
        "short_answer",
        name="quiz_question_type",
        create_type=False,
    )
    difficulty = postgresql.ENUM(
        "easy", "medium", "hard", name="quiz_question_difficulty", create_type=False
    )
    question_type.create(op.get_bind(), checkfirst=True)
    difficulty.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "quizzes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quizzes_user_created", "quizzes", ["user_id", "created_at"])
    op.create_index("ix_quizzes_course_created", "quizzes", ["course_id", "created_at"])
    op.create_table(
        "questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quiz_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", question_type, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("standard_answer", sa.Text(), nullable=False),
        sa.Column("rubric_points", sa.JSON(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("knowledge_point", sa.String(length=200), nullable=False),
        sa.Column("difficulty", difficulty, nullable=False),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_document_name", sa.String(length=255), nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["quiz_id"], ["quizzes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_questions_quiz_position",
        "questions",
        ["quiz_id", "position"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_questions_quiz_position", table_name="questions")
    op.drop_table("questions")
    op.drop_index("ix_quizzes_course_created", table_name="quizzes")
    op.drop_index("ix_quizzes_user_created", table_name="quizzes")
    op.drop_table("quizzes")
    postgresql.ENUM(name="quiz_question_difficulty").drop(
        op.get_bind(), checkfirst=True
    )
    postgresql.ENUM(name="quiz_question_type").drop(op.get_bind(), checkfirst=True)
