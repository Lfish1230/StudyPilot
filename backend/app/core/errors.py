from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    code: str
    message: str
    request_id: str


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    payload = ErrorResponse(
        code=exc.code,
        message=exc.message,
        request_id=getattr(request.state, "request_id", "unknown"),
    )
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump())


def error_response_schema() -> dict[str, Any]:
    return ErrorResponse.model_json_schema()

