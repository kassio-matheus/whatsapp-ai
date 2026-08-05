"""Token saver: prompt-engineering helpers that shrink LLM payloads.

The stack targets small (~8B) models with tight context windows. Feeding them
huge histories makes them slow, unfocused and prone to inventing data. These
helpers trim every part of the request (system prompt, history, user prompt)
down to explicit budgets before it reaches the failover chain, keeping only
what is essential to answer.

Character -> token approximation: ~1 token per 4 characters. This is only used
to *bound* the payload, never to bill anything, so the heuristic is fine.
"""

from __future__ import annotations

import re
import unicodedata

from app.core.config import settings

_CHARS_PER_TOKEN = 4.0

_WHITESPACE_RE = re.compile(r"[ \t]+")
_NEWLINES_RE = re.compile(r"\n{3,}")

#: Context-window budget (in tokens) per known model. Small models get tighter
#: budgets; unknown models fall back to a conservative default. Providers trim
#: their history with their own model's budget, so a failover to a different
#: model still gets a correctly sized payload.
MODEL_CONTEXT_BUDGETS: dict[str, int] = {
    "deepseek-v4-flash": 3000,
    "gpt-5.6-luna": 3500,
    "gemini-3.5-flash-lite": 3000,
    "llama-3.1-8b-instant": 2500,
}

DEFAULT_MODEL_CONTEXT_BUDGET = 3000


def model_context_budget(model: str | None) -> int:
    """Return the history + prompt token budget for a given model id."""
    if not model:
        return DEFAULT_MODEL_CONTEXT_BUDGET
    return MODEL_CONTEXT_BUDGETS.get(model, DEFAULT_MODEL_CONTEXT_BUDGET)


def estimate_tokens(text: str | None) -> int:
    """Approximate the number of tokens a string consumes."""
    if not text:
        return 0
    return max(1, round(len(text) / _CHARS_PER_TOKEN))


def compact_text(text: str | None) -> str:
    """Remove filler whitespace from a text block without changing meaning."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text)
    lines = [line.strip() for line in normalized.splitlines()]
    lines = [line for line in lines if line]
    joined = "\n".join(lines)
    joined = _NEWLINES_RE.sub("\n\n", joined)
    joined = _WHITESPACE_RE.sub(" ", joined)
    return joined.strip()


def _chars_budget(budget_tokens: int | None, default: int) -> int:
    budget = budget_tokens if budget_tokens is not None else default
    return max(1, round(budget * _CHARS_PER_TOKEN))


def _is_summary(item: dict[str, str]) -> bool:
    content = (item.get("content") or "").strip().lower()
    return "resumo da conversa" in content[:80]


def trim_context(
    context: list[dict[str, str]] | None,
    *,
    max_tokens: int | None = None,
    max_turns: int | None = None,
) -> list[dict[str, str]]:
    """Keep only the essential history for a small model.

    A conversation summary (when present) is always preserved because it is
    already a compressed form of the past. Everything else is reduced to the
    ``max_turns`` most recent messages, and the oldest of those are dropped
    until the whole history fits ``max_tokens``. Recent turns matter more than
    old ones for a chat agent.
    """
    if not context:
        return []

    budget_chars = _chars_budget(max_tokens, settings.AI_CONTEXT_BUDGET_TOKENS)
    turns = max_turns or settings.AI_MAX_CONTEXT_TURNS

    summary: list[dict[str, str]] = []
    history: list[dict[str, str]] = []
    for item in context:
        (summary if _is_summary(item) else history).append(item)

    kept = list(history[-turns:])
    base_cost = estimate_tokens(
        "".join(item.get("content", "") for item in summary)
    )

    while kept and estimate_tokens(
        "".join(item.get("content", "") for item in kept)
    ) + base_cost > budget_chars // _CHARS_PER_TOKEN:
        kept.pop(0)

    return summary + kept


def compact_prompt(prompt: str | None, *, max_tokens: int | None = None) -> str:
    """Normalize and cap the user prompt without touching its meaning."""
    cleaned = compact_text(prompt)
    if not cleaned:
        return ""
    budget_chars = _chars_budget(max_tokens, settings.AI_PROMPT_BUDGET_TOKENS)
    if len(cleaned) <= budget_chars:
        return cleaned
    return cleaned[: budget_chars - 3].rstrip() + "..."


def trim_system_prompt(
    system_prompt: str | None, *, max_tokens: int | None = None
) -> str | None:
    """Cap the system prompt, preserving the leading (most important) rules."""
    cleaned = compact_text(system_prompt)
    if not cleaned:
        return None
    budget_chars = _chars_budget(max_tokens, settings.AI_SYSTEM_BUDGET_TOKENS)
    if len(cleaned) <= budget_chars:
        return cleaned
    return cleaned[: budget_chars - 3].rstrip() + "..."
