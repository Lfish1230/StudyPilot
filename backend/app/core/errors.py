from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
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


class ConflictError(ApiError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(409, code, message)


class UnauthorizedError(ApiError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(401, code, message)


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    payload = ErrorResponse(
        code=exc.code,
        message=exc.message,
        request_id=getattr(request.state, "request_id", "unknown"),
    )
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump())


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    del exc
    payload = ErrorResponse(
        code="validation_error",
        message="请求参数无效，请检查后重试。",
        request_id=getattr(request.state, "request_id", "unknown"),
    )
    return JSONResponse(status_code=422, content=payload.model_dump())


def error_response_schema() -> dict[str, Any]:
    return ErrorResponse.model_json_schema()
