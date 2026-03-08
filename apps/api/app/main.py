from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.filters import router as filters_router
from app.api.routes.signals import router as signals_router
from app.core.config import settings
from app.schemas.api_response import ApiError, ApiMeta, ApiResponse, HealthPayload


LOCAL_DEV_ORIGIN_REGEX = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=LOCAL_DEV_ORIGIN_REGEX,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    error = exc.detail if isinstance(exc.detail, dict) else {}
    payload = ApiResponse[None](
        data=None,
        meta=ApiMeta(),
        error=ApiError(
            code=error.get("code", "http_error"),
            message=error.get("message", str(exc.detail)),
            details=error.get("details"),
        ),
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=payload.model_dump(mode="json"),
    )


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    _: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    payload = ApiResponse[None](
        data=None,
        meta=ApiMeta(),
        error=ApiError(
            code="validation_error",
            message="Request validation failed",
            details={"errors": exc.errors()},
        ),
    )
    return JSONResponse(
        status_code=422,
        content=payload.model_dump(mode="json"),
    )


app.include_router(filters_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(signals_router, prefix="/api/v1")


@app.get("/health", tags=["system"], response_model=ApiResponse[HealthPayload])
def health_check() -> ApiResponse[HealthPayload]:
    return ApiResponse(
        data=HealthPayload(status="ok"),
        meta=ApiMeta(),
    )
