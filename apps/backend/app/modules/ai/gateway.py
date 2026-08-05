"""AI gateway: the single entry point for every feature that calls the LLM.

All AI features (dashboard chat, WhatsApp auto-reply, WhatsApp /ai draft, …)
must go through :func:`generate`. It enforces the same pipeline everywhere:

    Function -> AI gateway -> Failover chain -> Provider LLM

so the stack can be corrected in one place:

1. resolve the right provider chain (user company, explicit company or global);
2. inject the authoritative facts (user/company ids) into the system prompt so
   the model never needs a lookup call for data it already owns;
3. apply the token saver (trim history, compact the prompt) before the request
   leaves the process, because the ~8B models degrade with fat contexts;
4. delegate to the failover chain, which tries providers until one answers.

``generate_*`` variants are thin conveniences that pre-fill the facts for a
user, a company or neither.
"""

from __future__ import annotations

import uuid

from sqlmodel import Session

from app.modules.ai.llm.failover import FailoverLLM
from app.modules.ai.llm_settings import (
    build_global_llm,
    build_llm_for_company,
    build_llm_for_user,
)
from app.modules.ai.models import AIPlatform, ChatResponseStructure
from app.modules.auth.models import User
from app.modules.companies.models import Company

from .context import company_facts, inject_facts, user_facts
from .token_saver import compact_prompt, trim_context


def _resolve_llm(
    *,
    session: Session,
    user: User | None,
    company: Company | None,
) -> AIPlatform:
    if company is not None:
        return build_llm_for_company(session=session, company_id=company.id)
    if user is not None:
        return build_llm_for_user(session=session, user=user)
    return build_global_llm(session=session)


def generate(
    *,
    session: Session,
    prompt: str,
    context: list[dict[str, str]] | None = None,
    system_prompt: str | None = None,
    actor_user_id: str | None = None,
    allowed_tools: list[str] | None = None,
    user: User | None = None,
    company: Company | None = None,
    facts: dict[str, str] | None = None,
    token_budget: int | None = None,
) -> ChatResponseStructure:
    """Run one LLM turn through the shared pipeline (see module docstring)."""
    llm = _resolve_llm(session=session, user=user, company=company)

    merged_facts: dict[str, str] = {}
    if user is not None:
        merged_facts.update(user_facts(user))
    if company is not None:
        merged_facts.update(company_facts(company))
    if facts:
        merged_facts.update(facts)

    system_prompt = inject_facts(system_prompt, facts=merged_facts)
    context = trim_context(context, max_tokens=token_budget)
    prompt = compact_prompt(prompt)

    return llm.generate(
        prompt=prompt,
        context=context,
        system_prompt=system_prompt,
        actor_user_id=actor_user_id,
        allowed_tools=allowed_tools,
    )


def generate_for_user(
    *,
    session: Session,
    user: User | None,
    prompt: str,
    context: list[dict[str, str]] | None = None,
    system_prompt: str | None = None,
    actor_user_id: str | None = None,
    allowed_tools: list[str] | None = None,
    token_budget: int | None = None,
) -> ChatResponseStructure:
    """Generate as ``user`` (their company chain, their facts)."""
    return generate(
        session=session,
        prompt=prompt,
        context=context,
        system_prompt=system_prompt,
        actor_user_id=actor_user_id or (str(user.id) if user else None),
        allowed_tools=allowed_tools,
        user=user,
        token_budget=token_budget,
    )


def generate_for_company(
    *,
    session: Session,
    company: Company,
    owner: User | None,
    prompt: str,
    context: list[dict[str, str]] | None = None,
    system_prompt: str | None = None,
    actor_user_id: str | None = None,
    allowed_tools: list[str] | None = None,
    facts: dict[str, str] | None = None,
    token_budget: int | None = None,
) -> ChatResponseStructure:
    """Generate for a company (owner company chain, company + owner facts)."""
    return generate(
        session=session,
        prompt=prompt,
        context=context,
        system_prompt=system_prompt,
        actor_user_id=actor_user_id or (str(owner.id) if owner else None),
        allowed_tools=allowed_tools,
        user=owner,
        company=company,
        facts=facts,
        token_budget=token_budget,
    )


def resolve_failover_chain(*, session: Session, company_id: uuid.UUID) -> FailoverLLM:
    """Return the failover chain for a company (for inspection/testing)."""
    chain = _resolve_llm(session=session, user=None, company=Company(id=company_id))
    return chain if isinstance(chain, FailoverLLM) else FailoverLLM([chain])
