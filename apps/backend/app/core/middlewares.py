import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import console

_METHOD_COLORS = {
    "GET": "cyan",
    "POST": "green",
    "PUT": "yellow",
    "PATCH": "magenta",
    "DELETE": "red",
}


def _method_color(method: str) -> str:
    return _METHOD_COLORS.get(method.upper(), "white")


def _status_color(code: int) -> str:
    if code < 300:
        return "green"
    if code < 400:
        return "yellow"
    return "red"


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.perf_counter()

        response = await call_next(request)

        elapsed = time.perf_counter() - start
        request_id = getattr(request.state, "request_id", "-")

        console.print(f"[dim]{'-' * 70}[/]")
        console.print(
            f"[{_method_color(request.method)}]{request.method}[/] "
            f"[bold]{request.url.path}[/] "
            f"[{_status_color(response.status_code)}]{response.status_code}[/] "
            f"[dim]{(elapsed * 1000):.1f}ms[/] [dim]#{request_id[:8]}[/]"
        )

        return response
