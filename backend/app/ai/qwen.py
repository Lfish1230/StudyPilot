import logging
from time import perf_counter
from typing import Any, cast

from openai import AsyncOpenAI

from app.ai.retry import call_with_retry
from app.ai.types import (
    ChatMessage,
    ChatResult,
    ChatUnavailableError,
    EmbeddingUnavailableError,
    TokenUsage,
)
from app.core.config import Settings
from app.core.middleware import get_request_id

logger = logging.getLogger("studypilot.ai")


def _error_category(exc: Exception) -> str:
    status_code = getattr(exc, "status_code", None)
    if status_code == 429:
        return "rate_limit"
    if isinstance(status_code, int) and status_code >= 500:
        return "provider_server"
    if status_code in {401, 403}:
        return "authentication"
    if status_code == 400:
        return "validation"
    return "transport"


class QwenEmbeddingClient:
    def __init__(self, client: Any, model: str, dimensions: int) -> None:
        self._client = client
        self._model = model
        self._dimensions = dimensions

    @classmethod
    def from_settings(cls, settings: Settings) -> "QwenEmbeddingClient":
        client = AsyncOpenAI(
            api_key=settings.dashscope_api_key or "not-configured",
            base_url=settings.dashscope_base_url,
            timeout=settings.request_timeout_seconds,
        )
        return cls(client, settings.embedding_model, settings.embedding_dimension)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        started_at = perf_counter()
        try:
            response = await call_with_retry(
                lambda: self._client.embeddings.create(
                    model=self._model,
                    input=texts,
                    dimensions=self._dimensions,
                    encoding_format="float",
                )
            )
            embeddings = [list(item.embedding) for item in response.data]
            if len(embeddings) != len(texts) or any(
                len(embedding) != self._dimensions for embedding in embeddings
            ):
                raise EmbeddingUnavailableError("invalid embedding dimensions")
        except EmbeddingUnavailableError:
            self._log_call(started_at, 0, 0, "invalid_response")
            raise
        except Exception as exc:
            self._log_call(started_at, 0, 0, _error_category(exc))
            raise EmbeddingUnavailableError("embedding provider unavailable") from exc
        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        self._log_call(started_at, input_tokens, 0, None)
        return embeddings

    def _log_call(
        self,
        started_at: float,
        input_tokens: int,
        output_tokens: int,
        error_category: str | None,
    ) -> None:
        logger.info(
            "provider_call request_id=%s provider=dashscope model=%s "
            "latency_ms=%.2f input_tokens=%d output_tokens=%d error_category=%s",
            get_request_id(),
            self._model,
            (perf_counter() - started_at) * 1000,
            input_tokens,
            output_tokens,
            error_category or "none",
        )


class QwenChatClient:
    def __init__(self, client: Any, model: str) -> None:
        self._client = client
        self._model = model

    @classmethod
    def from_settings(cls, settings: Settings) -> "QwenChatClient":
        client = AsyncOpenAI(
            api_key=settings.dashscope_api_key or "not-configured",
            base_url=settings.dashscope_base_url,
            timeout=settings.request_timeout_seconds,
        )
        return cls(client, settings.chat_model)

    async def complete(
        self,
        messages: list[ChatMessage],
        response_format: dict[str, object] | None = None,
    ) -> ChatResult:
        started_at = perf_counter()
        request_messages = [
            {"role": message.role, "content": message.content} for message in messages
        ]
        kwargs: dict[str, object] = {
            "model": self._model,
            "messages": request_messages,
        }
        if response_format is not None:
            kwargs["response_format"] = response_format
        try:
            response = await call_with_retry(
                lambda: self._client.chat.completions.create(**kwargs)
            )
            content = response.choices[0].message.content
            if not isinstance(content, str):
                raise ChatUnavailableError("chat response has no text")
        except ChatUnavailableError:
            self._log_call(started_at, 0, 0, "invalid_response")
            raise
        except Exception as exc:
            self._log_call(started_at, 0, 0, _error_category(exc))
            raise ChatUnavailableError("chat provider unavailable") from exc
        usage = response.usage
        token_usage = TokenUsage(
            input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
        )
        self._log_call(
            started_at,
            token_usage.input_tokens,
            token_usage.output_tokens,
            None,
        )
        return ChatResult(
            content=content,
            model=cast(str, getattr(response, "model", self._model)),
            usage=token_usage,
        )

    def _log_call(
        self,
        started_at: float,
        input_tokens: int,
        output_tokens: int,
        error_category: str | None,
    ) -> None:
        logger.info(
            "provider_call request_id=%s provider=dashscope model=%s "
            "latency_ms=%.2f input_tokens=%d output_tokens=%d error_category=%s",
            get_request_id(),
            self._model,
            (perf_counter() - started_at) * 1000,
            input_tokens,
            output_tokens,
            error_category or "none",
        )
