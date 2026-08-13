from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from openai import APIStatusError, APITimeoutError, RateLimitError

from app.ai.qwen import QwenChatClient, QwenEmbeddingClient
from app.ai.types import ChatMessage, ChatUnavailableError, EmbeddingUnavailableError


def api_error(status_code: int) -> APIStatusError:
    request = httpx.Request("POST", "https://example.com/v1/test")
    response = httpx.Response(status_code, request=request)
    return APIStatusError("provider error", response=response, body=None)


def rate_limit_error() -> RateLimitError:
    request = httpx.Request("POST", "https://example.com/v1/test")
    response = httpx.Response(429, request=request)
    return RateLimitError("rate limited", response=response, body=None)


class FakeEmbeddingsResource:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> Any:
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeChatCompletions:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> Any:
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def embedding_response(count: int, dimensions: int = 1024) -> object:
    return SimpleNamespace(
        data=[SimpleNamespace(embedding=[0.1] * dimensions) for _ in range(count)],
        usage=SimpleNamespace(prompt_tokens=17),
    )


def chat_response() -> object:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="回答"))],
        usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7),
        model="qwen-plus",
    )


@pytest.mark.asyncio
async def test_embedding_gateway_uses_batch_model_and_dimensions() -> None:
    resource = FakeEmbeddingsResource([embedding_response(2)])
    client = SimpleNamespace(embeddings=resource)
    gateway = QwenEmbeddingClient(client, "text-embedding-v4", 1024)

    embeddings = await gateway.embed(["第一段", "第二段"])
    assert len(embeddings) == 2
    assert resource.calls == [
        {
            "model": "text-embedding-v4",
            "input": ["第一段", "第二段"],
            "dimensions": 1024,
            "encoding_format": "float",
        }
    ]


@pytest.mark.asyncio
async def test_embedding_gateway_retries_server_errors_twice() -> None:
    resource = FakeEmbeddingsResource(
        [api_error(500), api_error(503), embedding_response(1)]
    )
    gateway = QwenEmbeddingClient(SimpleNamespace(embeddings=resource), "embed", 1024)
    await gateway.embed(["text"])
    assert len(resource.calls) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "transient_error",
    [
        APITimeoutError(httpx.Request("POST", "https://example.com/v1/test")),
        rate_limit_error(),
    ],
)
async def test_embedding_gateway_retries_timeout_and_rate_limit(
    transient_error: Exception,
) -> None:
    resource = FakeEmbeddingsResource([transient_error, embedding_response(1)])
    gateway = QwenEmbeddingClient(SimpleNamespace(embeddings=resource), "embed", 1024)
    await gateway.embed(["text"])
    assert len(resource.calls) == 2


@pytest.mark.asyncio
async def test_embedding_gateway_does_not_retry_validation_errors() -> None:
    resource = FakeEmbeddingsResource([api_error(400)])
    gateway = QwenEmbeddingClient(SimpleNamespace(embeddings=resource), "embed", 1024)
    with pytest.raises(EmbeddingUnavailableError):
        await gateway.embed(["text"])
    assert len(resource.calls) == 1


@pytest.mark.asyncio
async def test_embedding_gateway_rejects_wrong_dimensions() -> None:
    resource = FakeEmbeddingsResource([embedding_response(1, dimensions=3)])
    gateway = QwenEmbeddingClient(SimpleNamespace(embeddings=resource), "embed", 1024)
    with pytest.raises(EmbeddingUnavailableError):
        await gateway.embed(["text"])


@pytest.mark.asyncio
async def test_chat_gateway_normalizes_usage_and_response_format() -> None:
    completions = FakeChatCompletions([chat_response()])
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    gateway = QwenChatClient(client, "qwen-plus")
    result = await gateway.complete(
        [ChatMessage(role="user", content="问题")],
        response_format={"type": "json_object"},
    )
    assert result.content == "回答"
    assert result.usage.input_tokens == 11
    assert result.usage.output_tokens == 7
    assert completions.calls[0]["model"] == "qwen-plus"
    assert completions.calls[0]["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_chat_gateway_sanitizes_provider_failure() -> None:
    completions = FakeChatCompletions([api_error(401)])
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    gateway = QwenChatClient(client, "qwen-plus")
    with pytest.raises(ChatUnavailableError):
        await gateway.complete([ChatMessage(role="user", content="secret prompt")])
    assert len(completions.calls) == 1
