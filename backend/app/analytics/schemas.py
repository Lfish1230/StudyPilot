from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class MistakeResponse(BaseModel):
    attempt_id: UUID
    quiz_id: UUID
    quiz_title: str
    question_id: UUID
    type: str
    prompt: str
    user_answer: str
    standard_answer: str
    explanation: str
    score: int
    feedback: str
    missing_points: list[str]
    knowledge_point: str
    source_document_id: UUID
    source_document_name: str
    source_page: int
    submitted_at: datetime


class WeakTopicResponse(BaseModel):
    knowledge_point: str
    answered_count: int
    wrong_count: int
    weak_score: float


class RecentAttemptResponse(BaseModel):
    attempt_id: UUID
    quiz_id: UUID
    quiz_title: str
    total_score: int
    max_score: int
    percentage: float
    submitted_at: datetime


class CourseAnalyticsResponse(BaseModel):
    total_questions: int
    total_attempts: int
    average_percent_score: float
    weak_topics: list[WeakTopicResponse]
    recent_attempts: list[RecentAttemptResponse]
