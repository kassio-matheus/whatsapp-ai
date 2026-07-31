import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings


@dataclass(frozen=True)
class RateLimitRule:
    requests: int
    window_seconds: int


_GENERAL_RULE = RateLimitRule(requests=120, window_seconds=60)
_RULES = {
    "/auth/login": RateLimitRule(requests=5, window_seconds=60),
    "/auth/register": RateLimitRule(requests=5, window_seconds=3600),
    "/auth/recover-password": RateLimitRule(requests=5, window_seconds=3600),
    "/auth/resend-verification-email": RateLimitRule(
        requests=5, window_seconds=3600
    ),
    "/auth/reset-password": RateLimitRule(requests=5, window_seconds=3600),
}
_CHAT_RULE = RateLimitRule(requests=20, window_seconds=60)


def _client_key(request: Request) -> str:
    # Do not trust X-Forwarded-For unless a trusted proxy is configured.
    return request.client.host if request.client else "unknown"


class RequestProtectionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > settings.MAX_REQUEST_BYTES:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Request body is too large"},
                    )
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length header"},
                )

        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            path = request.url.path.rstrip("/")
            rule = _RULES.get(path)
            if path.startswith(f"{settings.API_V1_PREFIX}/ai/sessions/") and path.endswith(
                "/chat"
            ):
                rule = _CHAT_RULE
            if rule is None and path.startswith(settings.API_V1_PREFIX):
                rule = _GENERAL_RULE
            if rule is not None:
                key = f"{_client_key(request)}:{request.method}:{path}"
                now = time.monotonic()
                with self._lock:
                    timestamps = self._requests[key]
                    cutoff = now - rule.window_seconds
                    while timestamps and timestamps[0] <= cutoff:
                        timestamps.popleft()
                    if len(timestamps) >= rule.requests:
                        retry_after = max(
                            1, int(timestamps[0] + rule.window_seconds - now)
                        )
                        return JSONResponse(
                            status_code=429,
                            content={"detail": "Too many requests"},
                            headers={"Retry-After": str(retry_after)},
                        )
                    timestamps.append(now)

        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        if settings.ENVIRONMENT.lower() == "production":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=63072000; includeSubDomains",
            )
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
            )
        return response
