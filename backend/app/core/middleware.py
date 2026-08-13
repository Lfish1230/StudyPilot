import logging
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from time import perf_counter
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("studypilot.http")
request_id_context: ContextVar[str] = ContextVar("request_id", default="background")


def get_request_id() -> str:
    return request_id_context.get()


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        context_token = request_id_context.set(request_id)
        started_at = perf_counter()
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id

            logger.info(
                "request_complete method=%s path=%s status=%s "
                "duration_ms=%.2f request_id=%s",
                request.method,
                request.url.path,
                response.status_code,
                (perf_counter() - started_at) * 1000,
                request_id,
            )
            return response
        finally:
            request_id_context.reset(context_token)
