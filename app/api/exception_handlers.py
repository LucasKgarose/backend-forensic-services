"""FastAPI exception handlers mapping domain exceptions to HTTP responses."""

from fastapi import Request
from fastapi.responses import JSONResponse

from app.errors import (
    APKDowngradeError,
    CaseNotFoundError,
    ConfigurationError,
    CorruptedDatabaseError,
    DecryptionError,
    DeviceConnectionError,
    DeviceNotFoundError,
    FileNotFoundOnDeviceError,
    ForensicServiceError,
    KeyMismatchError,
    NotificationSourceUnavailableError,
    ReportGenerationError,
    ShellCommandError,
    TamperDetectedError,
)

# Exception -> HTTP status code mapping
EXCEPTION_STATUS_MAP: dict[type[ForensicServiceError], int] = {
    CaseNotFoundError: 404,
    DeviceNotFoundError: 404,
    FileNotFoundOnDeviceError: 404,
    NotificationSourceUnavailableError: 404,
    KeyMismatchError: 400,
    CorruptedDatabaseError: 400,
    DeviceConnectionError: 502,
    ShellCommandError: 502,
    APKDowngradeError: 500,
    DecryptionError: 500,
    TamperDetectedError: 409,
    ReportGenerationError: 500,
    ConfigurationError: 500,
    ForensicServiceError: 500,  # catch-all for base class
}


async def forensic_exception_handler(
    request: Request, exc: ForensicServiceError
) -> JSONResponse:
    """Handle any ForensicServiceError by looking up the appropriate HTTP status code."""
    status_code = EXCEPTION_STATUS_MAP.get(type(exc), 500)
    return JSONResponse(
        status_code=status_code,
        content={
            "detail": exc.message,
            "error_type": type(exc).__name__,
            "details": exc.details,
        },
    )


def register_exception_handlers(app) -> None:
    """Register all exception handlers on the FastAPI app."""
    app.add_exception_handler(ForensicServiceError, forensic_exception_handler)
