"""Automatic context facts injection.

Small models cannot be trusted to "remember" identifiers across tool calls,
and forcing them to look every id up costs latency and tokens. This module
injects the stable identifiers of the current actor (user id, company id,
company name, owner id) straight into the system prompt, so the model never
needs a lookup tool for data it already owns. The injected block doubles as a
guardrail: it tells the model those values are authoritative and must never be
guessed or replaced.
"""

from __future__ import annotations

import uuid

from app.modules.auth.models import User
from app.modules.companies.models import Company

from .token_saver import compact_text, trim_system_prompt

_FACTS_HEADER = "Authoritative context (real values, never guess or change them):"


def user_facts(user: User | None) -> dict[str, str]:
    """Stable identifiers of the acting user."""
    if user is None:
        return {}
    facts: dict[str, str] = {
        "user_id": str(user.id),
        "user_email": str(user.email),
        "is_super_admin": "true" if user.is_super_admin else "false",
    }
    if user.company_id is not None:
        facts["company_id"] = str(user.company_id)
    return facts


def company_facts(company: Company | None) -> dict[str, str]:
    """Stable identifiers of the company the AI acts for."""
    if company is None:
        return {}
    return {
        "company_id": str(company.id),
        "company_name": company.name,
        "company_owner_id": str(company.owner_id),
    }


def facts_block(facts: dict[str, str] | None) -> str:
    """Render the facts dict as a compact, copyable block."""
    if not facts:
        return ""
    lines = [_FACTS_HEADER]
    for key in sorted(facts):
        lines.append(f"- {key}: {facts[key]}")
    return "\n".join(lines)


def inject_facts(
    system_prompt: str | None,
    *,
    facts: dict[str, str] | None = None,
    max_tokens: int | None = None,
) -> str | None:
    """Merge authoritative facts into the system prompt.

    The facts block is placed before any user-written rules so a small model
    sees the identifiers first. The combined prompt is then trimmed to the
    system budget so it never bloats the request.
    """
    block = facts_block(facts)
    if not block:
        return trim_system_prompt(system_prompt, max_tokens=max_tokens)

    base = compact_text(system_prompt)
    combined = f"{block}\n\n{base}" if base else block
    return trim_system_prompt(combined, max_tokens=max_tokens)


def as_uuid(value: str | uuid.UUID | None) -> uuid.UUID | None:
    """Coerce a raw id to a UUID, returning ``None`` when malformed."""
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError):
        return None
