"""Request-boundary guards for the answer API.

Every profile bounds the request body size, so no caller can make the service buffer
unbounded input. The pilot profile additionally requires a per-client bearer token and
enforces that client's per-minute request allowance. A tunnel is transport only: these
checks belong to the application.

The middleware is a pure ASGI layer, so it sees the raw body before the route parses it,
replays the exact bytes to the application, and never logs the body or the query string.
Rejections use the same plain, detail-free JSON shape as the rest of the service.

Rate limiting is per process and in memory. With several worker processes a caller's
effective allowance is the configured limit times the worker count; this is stated in the
operator runbook and must not be described as a cluster-wide limit.
"""

from __future__ import annotations

from collections import deque
import json
import threading
import time
from typing import Callable, Deque, Dict, Iterable

from app.pilot_config import PilotConfig
from app.pilot_logging import log_request

REJECTION_DETAILS = {
    401: "Client credentials are required.",
    413: "Request body is too large.",
    429: "Too many requests.",
}

# Only the answer route can start work. Liveness and readiness probes stay open so an
# operator or the tunnel health check can observe the process without a client token.
GATED_PATHS = frozenset({"/ask"})

REJECTION_HEADERS = {
    401: ((b"www-authenticate", b"Bearer"),),
    429: ((b"retry-after", b"60"),),
}


class RateLimiter:
    """A per-client sliding-window request limiter in local memory."""

    def __init__(self, window_seconds: float = 60.0) -> None:
        self.window = window_seconds
        self._events: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, client_id: str, limit: int) -> bool:
        """Record a request for ``client_id`` when it fits the window."""

        now = time.monotonic()
        cutoff = now - self.window
        with self._lock:
            events = self._events.setdefault(client_id, deque())
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                return False
            events.append(now)
            return True


class PilotGuardMiddleware:
    """Bound the body, authenticate pilot callers, and log one operational line."""

    def __init__(
        self,
        app: object,
        config: PilotConfig,
        limiter: RateLimiter | None = None,
    ) -> None:
        self.app = app
        self.config = config
        self.limiter = limiter or RateLimiter()

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        method = str(scope.get("method", ""))
        path = str(scope.get("path", "/"))
        started = time.monotonic()

        try:
            body = await _read_bounded_body(scope, receive, self.config.max_request_bytes)
        except _BodyTooLarge:
            await self._reject(send, 413, started, method, path, "too_large")
            return
        if body is None:
            return  # the client disconnected while sending

        gate = "open"
        if self.config.authentication_required and path in GATED_PATHS:
            gate = "authenticated"
            rejection = self._rejection(scope)
            if rejection is not None:
                status, gate = rejection
                await self._reject(send, status, started, method, path, gate)
                return

        observed: dict[str, int] = {}
        replayed = _replay_receive(receive, body)

        async def capture_send(message: dict) -> None:
            if message.get("type") == "http.response.start":
                observed["status"] = int(message.get("status", 500))
            await send(message)

        try:
            await self.app(scope, replayed, capture_send)
        except Exception:
            log_request(
                self.config,
                method=method,
                path=path,
                status=500,
                duration_ms=_elapsed_ms(started),
                gate=gate,
            )
            raise
        log_request(
            self.config,
            method=method,
            path=path,
            status=observed.get("status", 500),
            duration_ms=_elapsed_ms(started),
            gate=gate,
        )

    def _rejection(self, scope: dict) -> tuple[int, str] | None:
        """Return the rejection status and gate, or ``None`` when the caller may proceed."""

        token = _bearer_token(scope.get("headers") or [])
        client = self.config.client_for_token(token)
        if client is None:
            return 401, "unauthenticated"
        if not self.limiter.allow(client.client_id, client.requests_per_minute):
            return 429, "rate_limited"
        return None

    async def _reject(
        self,
        send: Callable,
        status: int,
        started: float,
        method: str,
        path: str,
        gate: str,
    ) -> None:
        await _send_json(
            send,
            status,
            {"detail": REJECTION_DETAILS[status]},
            extra_headers=REJECTION_HEADERS.get(status, ()),
        )
        log_request(
            self.config,
            method=method,
            path=path,
            status=status,
            duration_ms=_elapsed_ms(started),
            gate=gate,
        )


class _BodyTooLarge(Exception):
    """Internal signal: the request body exceeds the configured bound."""


async def _read_bounded_body(scope: dict, receive: Callable, limit: int) -> bytes | None:
    declared = _content_length(scope.get("headers") or [])
    if declared is not None and declared > limit:
        raise _BodyTooLarge()
    chunks: list[bytes] = []
    size = 0
    while True:
        message = await receive()
        if message.get("type") == "http.disconnect":
            return None
        chunk = message.get("body", b"")
        if chunk:
            size += len(chunk)
            if size > limit:
                raise _BodyTooLarge()
            chunks.append(chunk)
        if not message.get("more_body", False):
            return b"".join(chunks)


def _replay_receive(receive: Callable, body: bytes) -> Callable:
    delivered = False

    async def replay() -> dict:
        nonlocal delivered
        if not delivered:
            delivered = True
            return {"type": "http.request", "body": body, "more_body": False}
        return await receive()

    return replay


def _content_length(headers: Iterable[tuple[bytes, bytes]]) -> int | None:
    for name, value in headers:
        if name.lower() == b"content-length":
            try:
                return int(value.decode("ascii"))
            except (UnicodeDecodeError, ValueError):
                return None
    return None


def _bearer_token(headers: Iterable[tuple[bytes, bytes]]) -> str | None:
    for name, value in headers:
        if name.lower() != b"authorization":
            continue
        try:
            raw = value.decode("latin-1").strip()
        except UnicodeDecodeError:
            return None
        scheme, _, token = raw.partition(" ")
        if scheme.lower() != "bearer":
            return None
        token = token.strip()
        return token or None
    return None


async def _send_json(
    send: Callable,
    status: int,
    payload: dict,
    extra_headers: tuple[tuple[bytes, bytes], ...] = (),
) -> None:
    body = json.dumps(payload).encode("utf-8")
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode("ascii")),
        *extra_headers,
    ]
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


def _elapsed_ms(started: float) -> int:
    return max(0, int((time.monotonic() - started) * 1000))
