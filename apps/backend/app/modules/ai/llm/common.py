"""Shared helpers for the AI platform implementations."""

import json
import re

from pydantic import ValidationError

from ..models import ChatResponseStructure

_STATUS_MESSAGES: dict[int, str] = {
    400: "Invalid request sent to the AI provider",
    401: "Invalid API key",
    402: "Insufficient balance",
    403: "Access denied by the AI provider",
    404: "Model or resource not found",
    408: "Timed out waiting for the AI provider",
    429: "Rate limit exceeded, try again shortly",
    500: "Internal error in the AI provider",
    502: "AI provider unavailable",
    503: "AI provider unavailable, try again",
}


def _unwrap_error(exc: BaseException) -> BaseException:
    """Descend through exception groups to the first meaningful cause."""
    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        exc = exc.exceptions[0]
    return exc


def _status_code(exc: BaseException) -> int | None:
    code = getattr(exc, "status_code", None)
    if isinstance(code, int):
        return code
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        return code
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    return status if isinstance(status, int) else None


def _raw_message(exc: BaseException) -> str:
    message = getattr(exc, "message", None)
    if isinstance(message, str) and message.strip():
        return message.strip()
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            error_message = error.get("message")
            if isinstance(error_message, str) and error_message.strip():
                return error_message.strip()
        elif isinstance(error, str) and error.strip():
            return error.strip()
    return str(exc)


def _provider_name(exc: BaseException) -> str:
    module = type(exc).__module__
    if "gemini" in module or "genai" in module:
        return "Gemini"
    if "openai" in module:
        return "OpenAI"
    if "deepseek" in module or "anthropic" in module:
        return type(exc).__module__.rsplit(".", 1)[0].rsplit("_", 1)[0]
    return "AI provider"


def friendly_provider_error(exc: BaseException) -> str:
    """Translate a provider exception into a human-friendly message.

    Unwraps exception groups (raised by the MCP tool runner) and maps HTTP
    status codes and message hints to short, actionable English messages,
    for example 402 -> "Insufficient balance".
    """
    root = _unwrap_error(exc)

    failures = getattr(root, "failures", None)
    if isinstance(failures, list):
        return str(root)

    code = _status_code(root)

    message = _raw_message(root).lower()
    hints: list[tuple[tuple[str, ...], str]] = [
        (("insufficient balance", "payment required", "billing"), "Insufficient balance"),
        (("invalid api key", "incorrect api key", "authentication"), "Invalid API key"),
        (("rate limit", "resource exhausted", "quota", "too many requests"), "Rate limit exceeded, try again shortly"),
        (("timeout", "timed out", "deadline"), "Timed out waiting for the AI provider"),
        (("not found", "unknown model"), "Model or resource not found"),
        (("permission", "forbidden", "denied"), "Access denied by the AI provider"),
    ]

    for keywords, friendly in hints:
        if any(keyword in message for keyword in keywords):
            return friendly

    if code in _STATUS_MESSAGES:
        return _STATUS_MESSAGES[code]

    raw = _raw_message(root)
    if raw:
        return f"{_provider_name(root)} failed: {raw[:200]}"
    return f"{_provider_name(root)} failed"


def tool_name_from_validation_error(exc: BaseException) -> str | None:
    """Extract the offending tool name from a tool-validation 400.

    Providers reject requests whose output references a tool that was not
    declared in ``request.tools``. Groq reports the failed generation verbatim
    (``{"name": ..., "arguments": ...}``) inside the error body; fall back to
    scanning the message when that is missing. Returns ``None`` when the error
    is not a tool-validation failure.
    """
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            generation = error.get("failed_generation")
            if isinstance(generation, str) and generation.strip():
                try:
                    parsed = json.loads(generation)
                except (json.JSONDecodeError, ValueError):
                    pass
                else:
                    if isinstance(parsed, dict):
                        name = parsed.get("name")
                        if isinstance(name, str) and name.strip():
                            return name.strip()

    message = _raw_message(exc)
    match = re.search(r"tool '([^']+)' which was not in request\.tools", message)
    if match:
        return match.group(1)
    match = re.search(r"function '([^']+)'", message)
    if match:
        return match.group(1)
    return None


def parse_chat_response(text: str) -> ChatResponseStructure:
    """Parse the model output into the structured chat response.

    Providers differ in how strictly they enforce JSON output. This helper
    tries the strict schema first, then the first JSON object found in the
    text, and finally falls back to treating the whole output as the response
    text.
    """
    cleaned = (text or "").strip()
    if cleaned:
        try:
            return ChatResponseStructure.model_validate_json(cleaned)
        except (ValidationError, ValueError):
            pass
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end > start:
            try:
                return ChatResponseStructure.model_validate_json(
                    cleaned[start : end + 1]
                )
            except (ValidationError, ValueError):
                pass
    return ChatResponseStructure(response=cleaned)
