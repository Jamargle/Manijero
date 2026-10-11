"""HTTP entry point for the Manijero backend.

The health endpoint deliberately has no dependency on the answer pipeline. It
answers whether this HTTP service is alive, rather than claiming that external
providers or the knowledge corpus are available.
"""

from fastapi import FastAPI
from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Stable response returned by the service health check."""

    status: str
    service: str


app = FastAPI(
    title="Manijero backend",
    description="Backend service for the Manijero olive-grove assistant.",
    version="0.1.0",
)


@app.get("/health", response_model=HealthResponse, summary="Check service health")
def health() -> HealthResponse:
    """Return a successful response when the HTTP service can handle requests."""

    return HealthResponse(status="ok", service="manijero-backend")
