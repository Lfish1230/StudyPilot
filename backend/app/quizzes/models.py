from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class QuestionType(StrEnum):
    MULTIPLE_CHOICE = "multiple_choice"
    SHORT_ANSWER = "short_answer"


class QuestionDifficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class Quiz(Base):
    __tablename__ = "quizzes"
    __table_args__ = (
        Index("ix_quizzes_user_created", "user_id", "created_at"),
        Index("ix_quizzes_course_created", "course_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    course_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    questions: Mapped[list["Question"]] = relationship(
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Question.position",
    )


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (
        Index("ix_questions_quiz_position", "quiz_id", "position", unique=True),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    quiz_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[QuestionType] = mapped_column(
        Enum(
            QuestionType,
            name="quiz_question_type",
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[str] | None] = mapped_column(JSON)
    standard_answer: Mapped[str] = mapped_column(Text, nullable=False)
    rubric_points: Mapped[list[str] | None] = mapped_column(JSON)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    knowledge_point: Mapped[str] = mapped_column(String(200), nullable=False)
    difficulty: Mapped[QuestionDifficulty] = mapped_column(
        Enum(
            QuestionDifficulty,
            name="quiz_question_difficulty",
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=False,
    )
    source_document_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    source_document_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_page: Mapped[int] = mapped_column(Integer, nullable=False)
