import json
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.ai.types import ChatMessage, ChatResult, TokenUsage
from app.core.errors import ApiError
from app.quizzes.generator import generate_quiz
from app.quizzes.schemas import GeneratedQuiz
from app.rag.model import DocumentChunk


class SequenceChatClient:
    def __init__(self, contents: list[str]) -> None:
        self.contents = contents
        self.calls: list[tuple[list[ChatMessage], dict[str, object] | None]] = []

    async def complete(
        self,
        messages: list[ChatMessage],
        response_format: dict[str, object] | None = None,
    ) -> ChatResult:
        self.calls.append((list(messages), response_format))
        return ChatResult(
            content=self.contents[len(self.calls) - 1],
            model="fake-quiz-model",
            usage=TokenUsage(10, 5),
        )


def source_chunk(document_id: UUID | None = None, page: int = 7) -> DocumentChunk:
    return DocumentChunk(
        id=uuid4(),
        document_id=document_id or uuid4(),
        course_id=uuid4(),
        page_number=page,
        content="TCP 使用三次握手确认通信双方的收发能力。",
        token_count=18,
        embedding=[1.0] + [0.0] * 1023,
    )


def valid_payload(document_id: UUID, page: int = 7) -> dict[str, object]:
    return {
        "title": "TCP 基础测验",
        "questions": [
            {
                "type": "multiple_choice",
                "prompt": "TCP 三次握手的主要作用是什么？",
                "options": ["确认双方收发能力", "压缩报文", "分配域名", "加密磁盘"],
                "standard_answer": "确认双方收发能力",
                "explanation": "资料明确说明三次握手用于确认双方能力。",
                "knowledge_point": "TCP 三次握手",
                "difficulty": "easy",
                "source_document_id": str(document_id),
                "source_page": page,
            },
            {
                "type": "short_answer",
                "prompt": "简述 TCP 三次握手的作用。",
                "standard_answer": "确认通信双方具备收发能力。",
                "rubric_points": ["确认发送能力", "确认接收能力"],
                "explanation": "需要同时说明双方的收发能力。",
                "knowledge_point": "TCP 三次握手",
                "difficulty": "medium",
                "source_document_id": str(document_id),
                "source_page": page,
            },
        ],
    }


def test_question_schema_rejects_invalid_options_answer_and_rubric() -> None:
    document_id = uuid4()
    payload = valid_payload(document_id)
    multiple_choice = payload["questions"][0]  # type: ignore[index]
    multiple_choice["options"] = ["A", "A", "C", "D"]  # type: ignore[index]
    multiple_choice["standard_answer"] = "B"  # type: ignore[index]
    short_answer = payload["questions"][1]  # type: ignore[index]
    short_answer["rubric_points"] = []  # type: ignore[index]

    with pytest.raises(ValidationError):
        GeneratedQuiz.model_validate(payload)


@pytest.mark.asyncio
async def test_invalid_generation_is_repaired_once() -> None:
    chunk = source_chunk()
    client = SequenceChatClient(
        ["not json", json.dumps(valid_payload(chunk.document_id), ensure_ascii=False)]
    )

    result = await generate_quiz(client, [chunk], 1, 1)

    assert result.quiz.title == "TCP 基础测验"
    assert len(client.calls) == 2
    assert client.calls[0][1] is not None
    assert "校验错误" in client.calls[1][0][-1].content
    assert result.usage == TokenUsage(20, 10)


@pytest.mark.asyncio
async def test_two_invalid_generations_raise_stable_error() -> None:
    chunk = source_chunk()
    wrong_page = json.dumps(valid_payload(chunk.document_id, page=999))
    client = SequenceChatClient([wrong_page, wrong_page])

    with pytest.raises(ApiError) as exc_info:
        await generate_quiz(client, [chunk], 1, 1)

    assert exc_info.value.code == "quiz_generation_invalid"
    assert len(client.calls) == 2


@pytest.mark.asyncio
async def test_generation_rejects_wrong_question_counts() -> None:
    chunk = source_chunk()
    payload = valid_payload(chunk.document_id)
    payload["questions"] = payload["questions"][:1]  # type: ignore[index]
    client = SequenceChatClient([json.dumps(payload), json.dumps(payload)])

    with pytest.raises(ApiError) as exc_info:
        await generate_quiz(client, [chunk], 1, 1)
    assert exc_info.value.code == "quiz_generation_invalid"
