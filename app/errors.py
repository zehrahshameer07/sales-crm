"""One error type for every business/permission problem, so status codes stay consistent.

401 not logged in      403 not allowed        404 not found / not yours
409 conflict (duplicate, invalid status move)  422 invalid data   429 too many attempts
"""
import logging
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, status_code: int, detail: str, *, code: Optional[str] = None,
                 headers: Optional[dict] = None) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.code = code
        self.headers = headers or {}


def not_found(what: str = "Not found") -> AppError:
    return AppError(404, what)


def forbidden(detail: str = "You don't have permission to do that.") -> AppError:
    return AppError(403, detail)


def conflict(detail: str) -> AppError:
    return AppError(409, detail)


def invalid(detail: str) -> AppError:
    return AppError(422, detail)


def too_many(detail: str, retry_after: int) -> AppError:
    return AppError(429, detail, headers={"Retry-After": str(max(1, int(retry_after)))})


log = logging.getLogger("sales_crm")


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        body = {"detail": exc.detail}
        if exc.code:
            body["code"] = exc.code
        return JSONResponse(body, status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Log the details for developers, but never show them to the user (no stack traces in responses)
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse({"detail": "Something went wrong on our side. Please try again."}, status_code=500)
