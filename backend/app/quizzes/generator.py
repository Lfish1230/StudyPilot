import json
from dataclasses import dataclass
from uuid import UUID

from pydantic import ValidationError

from app.ai.interfaces import ChatClient
from app.ai.types import ChatMessage, ChatUnavailableError, TokenUsage
from app.core.errors import ApiError, ServiceUnavailableError
from app.quizzes.prompts import build_quiz_messages
from app.quizzes.schemas import GeneratedQuiz
from app.rag.model import DocumentChunk


@dataclass(frozen=True, slots=True)
class QuizGenerationResult:
    quiz: GeneratedQuiz
    model: str
    usage: TokenUsage


def _response_format() -> dict[str, object]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "generated_quiz",
            "strict": True,
            "schema": GeneratedQuiz.model_json_schema(),
        },
    }


def _validate_generation(
    content: str,
    chunks: list[DocumentChunk],
    multiple_choice_count: int,
    short_answer_count: int,
) -> GeneratedQuiz:
    quiz = GeneratedQuiz.model_validate_json(content)
    actual_multiple_choice = sum(
        question.type == "multiple_choice" for question in quiz.questions
    )
    actual_short_answer = sum(
        question.type == "short_answer" for question in quiz.questions
    )
    if (
        actual_multiple_choice != multiple_choice_count
        or actual_short_answer != short_answer_count
    ):
        raise ValueError("generated question counts do not match the request")

    source_pages: dict[UUID, set[int]] = {}
    for chunk in chunks:
        source_pages.setdefault(chunk.document_id, set()).add(chunk.page_number)
    for question in quiz.questions:
        if question.source_page not in source_pages.get(
            question.source_document_id, set()
        ):
            raise ValueError("question source is not present in selected context")
    return quiz


async def generate_quiz(
    chat_client: ChatClient,
    chunks: list[DocumentChunk],
    multiple_choice_count: int,
    short_answer_count: int,
) -> QuizGenerationResult:
    messages = build_quiz_messages(chunks, multiple_choice_count, short_answer_count)
    total_usage = TokenUsage(0, 0)
    last_model = "unknown"
    for attempt in range(2):
        try:
            result = await chat_client.complete(
                messages, response_format=_response_format()
            )
        except ChatUnavailableError as exc:
            raise ServiceUnavailableError(
                "quiz_generation_unavailable",
                "测验生成服务暂时不可用，请稍后重试。",
            ) from exc
        total_usage = TokenUsage(
            total_usage.input_tokens + result.usage.input_tokens,
            total_usage.output_tokens + result.usage.output_tokens,
        )
        last_model = result.model
        try:
            quiz = _validate_generation(
                result.content,
                chunks,
                multiple_choice_count,
                short_answer_count,
            )
            return QuizGenerationResult(quiz, last_model, total_usage)
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            if attempt == 1:
                raise ApiError(
                    502,
                    "quiz_generation_invalid",
                    "模型未能生成有效测验，请重试。",
                ) from exc
            messages.extend(
                [
                    ChatMessage(role="assistant", content=result.content),
                    ChatMessage(
                        role="user",
                        content=(
                            "上一个 JSON 未通过校验。请只返回修正后的完整 JSON。"
                            f"校验错误：{str(exc)[:1000]}"
                        ),
                    ),
                ]
            )
    raise RuntimeError("unreachable")
