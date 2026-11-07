"""Privacy-minimal HTTP boundary for ``POST /feedback``.

The only accepted field is a fixed two-value rating. The route takes no question, answer,
land context, answer id, land/client/device identifier, or free text; it reads no corpus,
campaign, retention store, or trace and starts no answer work. An accepted rating increments
one in-memory, per-process counter and returns ``204`` with no body. Nothing is persisted and
no feedback-specific log line is written.
"""

from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel, ConfigDict

from app import health_metrics


class FeedbackRequest(BaseModel):
    """Exactly one rating; unknown keys and non-string values are rejected."""

    model_config = ConfigDict(extra="forbid", strict=True)

    rating: Literal["useful", "not_useful"]


router = APIRouter()


@router.post(
    "/feedback",
    operation_id="submitAnswerFeedback",
    summary="Report whether an answer was useful",
    response_model=None,
    status_code=204,
    responses={
        400: {"description": "Malformed JSON request."},
        401: {
            "description": (
                "Pilot profile only. The per-client bearer token is missing or unknown; the "
                "response is generic and carries no credential detail."
            )
        },
        413: {
            "description": (
                "The request body exceeds the service bound; the response is generic and "
                "echoes no request value."
            )
        },
        422: {
            "description": (
                "The request is not exactly one allowed rating; the response echoes no "
                "submitted value."
            )
        },
        429: {
            "description": (
                "Pilot profile only. This client exceeded its per-minute feedback allowance. "
                "Limits are enforced per service process."
            )
        },
    },
)
def submit_feedback(payload: FeedbackRequest) -> Response:
    """Count the rating as an aggregate and return ``204`` with no body."""

    health_metrics.note_feedback(payload.rating)
    return Response(status_code=204)
