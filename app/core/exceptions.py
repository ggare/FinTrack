"""Domain exceptions and their FastAPI handler.

Services raise domain errors; a single exception handler converts them
into JSON responses with the proper status codes.
"""

from fastapi import Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    """Base class for business-logic errors."""

    status_code = 400

    def __init__(self, detail: str = "Request processing error") -> None:
        self.detail = detail
        super().__init__(detail)


class ValidationDomainError(DomainError):
    status_code = 400

    def __init__(self, detail: str = "Invalid data") -> None:
        super().__init__(detail)


class NotFoundError(DomainError):
    status_code = 404

    def __init__(self, detail: str = "Object not found") -> None:
        super().__init__(detail)


class AuthError(DomainError):
    status_code = 401

    def __init__(self, detail: str = "Authentication error") -> None:
        super().__init__(detail)


class ConflictError(DomainError):
    status_code = 409

    def __init__(self, detail: str = "Data conflict") -> None:
        super().__init__(detail)


async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
