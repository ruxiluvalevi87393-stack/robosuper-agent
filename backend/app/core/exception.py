from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppException(Exception):
    status_code: int = 500
    code: str = "internal_error"
    message: str = "Internal server error"

    def __init__(
        self,
        message: Optional[str] = None,
        *,
        code: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
    ):
        if message is not None:
            self.message = message
        if code is not None:
            self.code = code
        self.payload = payload or {}
        super().__init__(self.message)


class NotFoundException(AppException):
    status_code = 404
    code = "not_found"
    message = "Resource not found"


class AlreadyExistsException(AppException):
    status_code = 409
    code = "already_exists"
    message = "Resource already exists"


class ValidationException(AppException):
    status_code = 422
    code = "validation_error"
    message = "Validation failed"


class ConflictException(AppException):
    status_code = 409
    code = "conflict"
    message = "Resource conflict"


class UnauthorizedException(AppException):
    status_code = 401
    code = "unauthorized"
    message = "Unauthorized"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def _handle_app_exception(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "payload": exc.payload,
            },
        )
