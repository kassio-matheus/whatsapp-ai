"""Shared helpers for the AI platform implementations."""

from pydantic import ValidationError

from ..models import ChatResponseStructure


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
