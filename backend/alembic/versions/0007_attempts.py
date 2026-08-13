"""Create quiz attempts and graded answers.

Revision ID: 0007_attempts
Revises: 0006_quizzes
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007_attempts"
down_revision: str | None = "0006_quizzes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quiz_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quiz_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("total_score", sa.Integer(), nullable=False),
        sa.Column("max_score", sa.Integer(), nullable=False),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["quiz_id"], ["quizzes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quiz_id", "user_id", name="uq_quiz_attempts_quiz_user"),
    )
    op.create_index(
        "ix_quiz_attempts_user_submitted",
        "quiz_attempts",
        ["user_id", "submitted_at"],
    )
    op.create_table(
        "attempt_answers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_answer", sa.Text(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("missing_points", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id"], ["quiz_attempts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "attempt_id",
            "question_id",
            name="uq_attempt_answers_attempt_question",
        ),
    )
    op.create_index(
        "ix_attempt_answers_question_id", "attempt_answers", ["question_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_attempt_answers_question_id", table_name="attempt_answers")
    op.drop_table("attempt_answers")
    op.drop_index("ix_quiz_attempts_user_submitted", table_name="quiz_attempts")
    op.drop_table("quiz_attempts")
