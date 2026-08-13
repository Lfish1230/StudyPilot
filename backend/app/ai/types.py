from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TokenUsage:
    input_tokens: int
    output_tokens: int


class EmbeddingUnavailableError(Exception):
    """Raised when an embedding provider cannot complete a request."""
