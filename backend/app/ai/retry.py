import asyncio
from collections.abc import Awaitable, Callable

from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError


def is_retryable_provider_error(exc: Exception) -> bool:
    if isinstance(exc, (APIConnectionError, APITimeoutError, RateLimitError)):
        return True
    return isinstance(exc, APIStatusError) and exc.status_code >= 500


async def call_with_retry[T](
    operation: Callable[[], Awaitable[T]],
    *,
    max_retries: int = 2,
    base_delay_seconds: float = 0.05,
) -> T:
    for attempt in range(max_retries + 1):
        try:
            return await operation()
        except Exception as exc:
            if attempt >= max_retries or not is_retryable_provider_error(exc):
                raise
            await asyncio.sleep(base_delay_seconds * (2**attempt))
    raise AssertionError("unreachable")
