from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

Difficulty = Literal["easy", "medium", "hard"]


class MultipleChoiceQuestion(BaseModel):
    type: Literal["multiple_choice"]
    prompt: str = Field(min_length=1, max_length=1000)
    options: list[str] = Field(min_length=4, max_length=4)
    standard_answer: str = Field(min_length=1, max_length=500)
    explanation: str = Field(min_length=1, max_length=2000)
    knowledge_point: str = Field(min_length=1, max_length=200)
    difficulty: Difficulty
    source_document_id: UUID
    source_page: int = Field(gt=0)

    @field_validator("prompt", "standard_answer", "explanation", "knowledge_point")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return value

    @field_validator("options")
    @classmethod
    def validate_options(cls, options: list[str]) -> list[str]:
        normalized = [option.strip() for option in options]
        if any(not option for option in normalized):
            raise ValueError("options must not be blank")
        if len(set(normalized)) != 4:
            raise ValueError("options must be unique")
        return normalized

    @model_validator(mode="after")
    def answer_must_be_an_option(self) -> "MultipleChoiceQuestion":
        if self.standard_answer not in self.options:
            raise ValueError("standard answer must be one of the options")
        return self


class ShortAnswerQuestion(BaseModel):
    type: Literal["short_answer"]
    prompt: str = Field(min_length=1, max_length=1000)
    standard_answer: str = Field(min_length=1, max_length=3000)
    rubric_points: list[str] = Field(min_length=1, max_length=10)
    explanation: str = Field(min_length=1, max_length=2000)
    knowledge_point: str = Field(min_length=1, max_length=200)
    difficulty: Difficulty
    source_document_id: UUID
    source_page: int = Field(gt=0)

    @field_validator("prompt", "standard_answer", "explanation", "knowledge_point")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return value

    @field_validator("rubric_points")
    @classmethod
    def validate_rubric_points(cls, points: list[str]) -> list[str]:
        normalized = [point.strip() for point in points]
        if any(not point for point in normalized):
            raise ValueError("rubric points must not be blank")
        return normalized


GeneratedQuestion = Annotated[
    MultipleChoiceQuestion | ShortAnswerQuestion,
    Field(discriminator="type"),
]


class GeneratedQuiz(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    questions: list[GeneratedQuestion] = Field(min_length=1, max_length=10)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value


class QuizCreate(BaseModel):
    document_ids: list[UUID] = Field(min_length=1, max_length=20)
    multiple_choice_count: int = Field(ge=1, le=10)
    short_answer_count: int = Field(default=0, ge=0, le=5)

    @field_validator("document_ids")
    @classmethod
    def document_ids_must_be_unique(cls, values: list[UUID]) -> list[UUID]:
        if len(set(values)) != len(values):
            raise ValueError("document ids must be unique")
        return values

    @model_validator(mode="after")
    def total_count_must_not_exceed_ten(self) -> "QuizCreate":
        if self.multiple_choice_count + self.short_answer_count > 10:
            raise ValueError("question count must not exceed 10")
        return self


class QuizSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    course_id: UUID
    title: str
    question_count: int
    created_at: datetime


class QuizQuestionResponse(BaseModel):
    id: UUID
    type: str
    position: int
    prompt: str
    options: list[str] | None
    knowledge_point: str
    difficulty: str
    source_document_id: UUID
    source_document_name: str
    source_page: int


class QuizDetailResponse(QuizSummaryResponse):
    questions: list[QuizQuestionResponse]


class SubmittedAnswer(BaseModel):
    question_id: UUID
    answer: str = Field(min_length=1, max_length=5000)

    @field_validator("answer")
    @classmethod
    def normalize_answer(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("answer must not be blank")
        return value


class QuizSubmission(BaseModel):
    answers: list[SubmittedAnswer] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def question_ids_must_be_unique(self) -> "QuizSubmission":
        question_ids = [answer.question_id for answer in self.answers]
        if len(set(question_ids)) != len(question_ids):
            raise ValueError("question ids must be unique")
        return self


class AnswerResultResponse(BaseModel):
    question_id: UUID
    type: str
    prompt: str
    user_answer: str
    standard_answer: str
    explanation: str
    score: int
    is_correct: bool
    feedback: str
    missing_points: list[str]
    knowledge_point: str
    source_document_id: UUID
    source_document_name: str
    source_page: int


class QuizAttemptResponse(BaseModel):
    id: UUID
    quiz_id: UUID
    total_score: int
    max_score: int
    percentage: float
    submitted_at: datetime
    answers: list[AnswerResultResponse]
