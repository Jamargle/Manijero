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
import os
from typing import Literal, Union

from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from app import health_metrics
from app.answer_inspection import inspection_allowed
from app.answer_trace import AnswerTrace, load_answer_trace
from app.ask_api import (
    KNOWLEDGE_RELEASE_ROOT_ENV,
    CorpusDocuments,
    get_as_of_date,
    get_corpus_documents,
    last_release_outcome,
    router as ask_router,
    sanitize_request_validation,
)
from app.gemini_generation import GeminiTransport, GenerationClock
from app.local_generation import resolve_startup_generation
from app.health_metrics import HealthMetrics
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
_TRACE_FROM_ENV = object()
_INSPECTION_FROM_ENV = object()


def create_app(
    config: PilotConfig | None = None,
    retention_store: RetentionStore | None | object = _RETENTION_FROM_ENV,
    *,
    generation_transport: GeminiTransport | None = None,
    generation_clock: GenerationClock | None = None,
    local_transport: GeminiTransport | None = None,
    answer_trace: AnswerTrace | object = _TRACE_FROM_ENV,
    answer_inspection: bool | object = _INSPECTION_FROM_ENV,
) -> FastAPI:
    """Build the FastAPI application for the configured service profile.

    Product-improvement retention stays off unless ``MANIJERO_RETENTION_DB`` names a safe
    store (or a test passes one). A configured but unsafe store also leaves retention off;
    the pilot preflight reports it as a problem before traffic.

    The answer provider is resolved once here. No real Gemini transport exists in this
    repository, so ``generation_transport`` defaults to ``None`` (a gate blocker) and the
    provider stays ``extractive``; only tests inject a fake transport and clock.

    ``MANIJERO_GENERATION_PROVIDER=local`` selects the loopback Ollama provider instead
    (:mod:`app.local_generation`). It stays off unless both of its env keys match the
    committed model record, and in the pilot profile it also needs a passed pilot review.
    Resolution makes no network call; ``local_transport`` lets tests and the measurement
    script inject a transport in place of the default ``OllamaTransport``.
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
    registry = HealthMetrics()
    registry.set_service(resolved.profile, application.version)
    application.state.health_metrics = registry
    application.add_middleware(PilotGuardMiddleware, config=resolved, metrics=registry)
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
    if answer_trace is _TRACE_FROM_ENV:
        answer_trace = load_answer_trace(os.environ, resolved.profile)
    answer_trace.startup()
    application.state.answer_trace = answer_trace
    if answer_inspection is _INSPECTION_FROM_ENV:
        answer_inspection = inspection_allowed(resolved.profile, os.environ)
    application.state.answer_inspection = answer_inspection is True
    operational_log("answer_inspection", state="on" if answer_inspection is True else "off")
    generation = resolve_startup_generation(
        gemini_transport=generation_transport,
        local_transport=local_transport,
        clock=generation_clock,
        pilot=pilot,
    )
    operational_log(
        "generation_provider",
        provider=generation.provider,
        blockers=",".join(generation.blockers),
    )
    application.state.generation_provider = generation
    registry.set_provider(generation.provider)

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

    @application.get("/metrics", include_in_schema=False, response_class=Response)
    def metrics(
        corpus_documents: CorpusDocuments = Depends(get_corpus_documents),
        as_of: date = Depends(get_as_of_date),
        active_campaign: Union[str, None] = Depends(get_configured_campaign),
    ) -> Response:
        """Counts and timings only, in Prometheus text format; gated in the pilot profile."""

        verdict = evaluate_readiness(corpus_documents, as_of, active_campaign)
        body = registry.render(
            ready=verdict.ready,
            problems=verdict.problems,
            release=_release_label(),
            source_updates=health_metrics.read_source_updates(),
        )
        return Response(content=body, media_type=health_metrics.CONTENT_TYPE)

    return application


def _release_label() -> tuple[str, str]:
    """The served or refused release id, or ``none``/``repository`` without a release root."""

    if not os.environ.get(KNOWLEDGE_RELEASE_ROOT_ENV, "").strip():
        return "none", "repository"
    outcome = last_release_outcome()
    if outcome is None:
        return "none", "refused"
    release_id, state = outcome
    return (release_id or "none"), state


async def unhandled_exception(request: object, exc: Exception) -> JSONResponse:
    """Log the failure type only and return a detail-free generic server error."""

    operational_log("internal_error", error_type=type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


app = create_app()
