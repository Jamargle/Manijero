"""HTTP entry point for the Manijero backend.

The health endpoint deliberately has no dependency on the answer pipeline. It answers
whether this HTTP service is alive, rather than claiming that external providers or the
knowledge corpus are available. ``/ready`` is the separate, explicit readiness check:
an operator routes pilot traffic only when the configured campaign and the reviewed
corpus can serve answers.

The application is built by :func:`create_app` so the hosted pilot profile can disable
interactive API docs, register the request guard, and enable operational logging without
changing the local workflow.
"""

from __future__ import annotations

from datetime import date
from typing import Literal, Union

from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.ask_api import (
    CorpusDocuments,
    get_as_of_date,
    get_corpus_documents,
    router as ask_router,
    sanitize_request_validation,
)
from app.pilot_config import PilotConfig, load_config
from app.pilot_guard import PilotGuardMiddleware
from app.pilot_logging import configure_operational_logging, operational_log
from app.readiness import evaluate_readiness, get_configured_campaign
from app.retention import RetentionError, RetentionStore, load_retention_store

SERVICE_NAME = "manijero-backend"


class HealthResponse(BaseModel):
    """Health payload: liveness only."""

    status: str
    service: str


class ReadinessResponse(BaseModel):
    """Readiness verdict without any corpus value or request content."""

    status: Literal["ready", "unavailable"]
    service: str


_RETENTION_FROM_ENV = object()


def create_app(
    config: PilotConfig | None = None,
    retention_store: RetentionStore | None | object = _RETENTION_FROM_ENV,
) -> FastAPI:
    """Build the FastAPI application for the configured service profile.

    Product-improvement retention stays off unless ``MANIJERO_RETENTION_DB`` names a safe
    store (or a test passes one). A configured but unsafe store also leaves retention off;
    the pilot preflight reports it as a problem before traffic.
    """

    resolved = config or load_config()
    pilot = resolved.pilot
    application = FastAPI(
        title="Manijero backend",
        description="Backend service for the Manijero olive-grove assistant.",
        version="0.1.0",
        docs_url=None if pilot else "/docs",
        redoc_url=None if pilot else "/redoc",
        openapi_url=None if pilot else "/openapi.json",
    )
    application.add_middleware(PilotGuardMiddleware, config=resolved)
    application.include_router(ask_router)
    application.add_exception_handler(RequestValidationError, sanitize_request_validation)
    application.add_exception_handler(Exception, unhandled_exception)
    if resolved.operational_logging:
        configure_operational_logging()
    if retention_store is _RETENTION_FROM_ENV:
        try:
            retention_store = load_retention_store()
        except RetentionError as error:
            operational_log("retention_disabled", reason=error.code)
            retention_store = None
    application.state.retention_store = retention_store

    @application.get("/health", response_model=HealthResponse, summary="Check service health")
    def health() -> HealthResponse:
        """Return a successful response when the HTTP service can handle requests."""

        return HealthResponse(status="ok", service=SERVICE_NAME)

    @application.get(
        "/ready",
        response_model=ReadinessResponse,
        summary="Check answer-service readiness",
        responses={
            503: {
                "description": (
                    "The configured campaign or the reviewed corpus cannot serve answers. "
                    "The response carries no corpus detail."
                )
            }
        },
    )
    def ready(
        corpus_documents: CorpusDocuments = Depends(get_corpus_documents),
        as_of: date = Depends(get_as_of_date),
        active_campaign: Union[str, None] = Depends(get_configured_campaign),
    ) -> Union[ReadinessResponse, JSONResponse]:
        """Report whether the explicit campaign and the reviewed corpus can answer."""

        verdict = evaluate_readiness(corpus_documents, as_of, active_campaign)
        payload = {
            "status": "ready" if verdict.ready else "unavailable",
            "service": SERVICE_NAME,
        }
        if not verdict.ready:
            return JSONResponse(status_code=503, content=payload)
        return ReadinessResponse(**payload)

    return application


async def unhandled_exception(request: object, exc: Exception) -> JSONResponse:
    """Log the failure type only and return a detail-free generic server error."""

    operational_log("internal_error", error_type=type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


app = create_app()
