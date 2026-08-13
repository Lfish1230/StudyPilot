from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class TokenUsage:
    input_tokens: int
    output_tokens: int


class EmbeddingUnavailableError(Exception):
    """Raised when an embedding provider cannot complete a request."""


class ChatUnavailableError(Exception):
    """Raised when a chat provider cannot complete a request."""


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True, slots=True)
class ChatResult:
    content: str
    model: str
    usage: TokenUsage
