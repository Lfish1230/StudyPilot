"""Deterministic, network-free AI adapters used by the end-to-end test suite."""

import json
from typing import Any

from app.ai.types import ChatMessage, ChatResult, TokenUsage


class FakeEmbeddingClient:
    """Return the same valid vector so every fixture chunk is retrievable."""

    def __init__(self, dimensions: int) -> None:
        if dimensions < 1:
            raise ValueError("embedding dimensions must be positive")
        self._vector = [1.0] + [0.0] * (dimensions - 1)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector.copy() for _ in texts]


class FakeChatClient:
    """Produce schema-valid Chinese responses without calling a model provider."""

    model = "studypilot-fake-v1"

    async def complete(
        self,
        messages: list[ChatMessage],
        response_format: dict[str, object] | None = None,
    ) -> ChatResult:
        if response_format is None:
            content = (
                "传输控制协议（TCP）通过三次握手确认双方的发送与接收能力，"
                "并同步建立连接所需的初始序列信息。[S1]"
            )
        else:
            schema_name = self._schema_name(response_format)
            if schema_name == "generated_quiz":
                content = self._quiz(messages)
            elif schema_name == "short_answer_grade":
                content = json.dumps(
                    {
                        "score": 8,
                        "feedback": "核心思路正确，可以补充连接参数同步的作用。",
                        "missing_points": ["初始序列信息"],
                    },
                    ensure_ascii=False,
                )
            else:
                raise ValueError(f"unsupported fake response schema: {schema_name}")
        return ChatResult(
            content=content,
            model=self.model,
            usage=TokenUsage(input_tokens=32, output_tokens=24),
        )

    @staticmethod
    def _schema_name(response_format: dict[str, object]) -> str:
        json_schema = response_format.get("json_schema")
        if not isinstance(json_schema, dict):
            return ""
        return str(json_schema.get("name", ""))

    @staticmethod
    def _quiz(messages: list[ChatMessage]) -> str:
        request: dict[str, Any] = json.loads(messages[1].content)
        sources = request["SOURCE_DATA"]
        if not sources:
            raise ValueError("fake quiz provider requires source data")
        source = sources[0]
        document_id = source["document_id"]
        page_number = source["page_number"]
        questions: list[dict[str, object]] = []
        multiple_choice_count = int(request["multiple_choice_count"])
        short_answer_count = int(request["short_answer_count"])

        for index in range(multiple_choice_count):
            if index % 2 == 0:
                prompt = "TCP 建立连接通常使用几次握手？"
                options = ["一次", "两次", "三次", "四次"]
                answer = "三次"
                point = "TCP 三次握手"
            else:
                prompt = "TCP 三次握手的主要作用是什么？"
                options = [
                    "确认双方收发能力并同步连接信息",
                    "加密全部应用数据",
                    "替代 IP 地址分配",
                    "压缩网络报文",
                ]
                answer = "确认双方收发能力并同步连接信息"
                point = "连接建立"
            questions.append(
                {
                    "type": "multiple_choice",
                    "prompt": prompt,
                    "options": options,
                    "standard_answer": answer,
                    "explanation": "三次握手用于可靠地建立 TCP 连接。",
                    "knowledge_point": point,
                    "difficulty": "easy" if index == 0 else "medium",
                    "source_document_id": document_id,
                    "source_page": page_number,
                }
            )

        for _ in range(short_answer_count):
            questions.append(
                {
                    "type": "short_answer",
                    "prompt": "简述 TCP 三次握手的作用。",
                    "standard_answer": "确认双方收发能力并同步建立连接所需的信息。",
                    "rubric_points": ["确认收发能力", "同步连接信息"],
                    "explanation": "握手让通信双方在传输数据前确认连接状态。",
                    "knowledge_point": "TCP 三次握手",
                    "difficulty": "medium",
                    "source_document_id": document_id,
                    "source_page": page_number,
                }
            )
        return json.dumps(
            {"title": "TCP 连接基础测验", "questions": questions},
            ensure_ascii=False,
        )
