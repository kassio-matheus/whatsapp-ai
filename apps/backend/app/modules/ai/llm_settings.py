"""Global and per-company LLM configuration.

The AI module is global: a single set of provider API keys, models and
thinking power backs the AI Chat and acts as the platform default. Companies
can optionally override it (for example per-channel assistants) by storing
their own keys; companies without an override fall back to the global row,
then to the environment-configured chain.

Keys are encrypted at rest using the app SECRET_KEY and are never returned by
the API. The failover chain always follows the global order (DeepSeek ->
OpenAI -> Gemini); a selected provider moves to the front, and only providers
with a configured key are included.
"""

import base64
import hashlib
import uuid
from datetime import UTC, datetime

from cryptography.fernet import Fernet
from sqlmodel import Session

from app.core.config import settings
from app.modules.ai.llm.deepseek_llm import DeepSeek
from app.modules.ai.llm.failover import FailoverLLM
from app.modules.ai.llm.gemini_llm import Gemini
from app.modules.ai.llm.groq_llm import Groq
from app.modules.ai.llm.openai_llm import OpenAI
from app.modules.ai.models import (
    AIGlobalSettings,
    AIGlobalSettingsResponse,
    AIGlobalSettingsUpdate,
    AIPlatform,
    CompanyLLMSettings,
    CompanyLLMSettingsResponse,
    CompanyLLMSettingsUpdate,
    LLMProvider,
    LLMProviderConfig,
    ReasoningLevel,
)
from app.modules.auth.models import User

PROVIDER_ORDER: list[LLMProvider] = [
    LLMProvider.DEEPSEEK,
    LLMProvider.OPENAI,
    LLMProvider.GEMINI,
    LLMProvider.GROQ,
]

PROVIDER_MODELS: dict[LLMProvider, str] = {
    LLMProvider.DEEPSEEK: "deepseek-v4-flash",
    LLMProvider.OPENAI: "gpt-5.6-luna",
    LLMProvider.GEMINI: "gemini-3.5-flash-lite",
    LLMProvider.GROQ: "llama-3.1-8b-instant",
}

PROVIDER_LABELS: dict[LLMProvider, str] = {
    LLMProvider.DEEPSEEK: "DeepSeek",
    LLMProvider.OPENAI: "OpenAI",
    LLMProvider.GEMINI: "Gemini",
    LLMProvider.GROQ: "Groq",
}

_PROVIDER_KEY_ATTR = {
    LLMProvider.DEEPSEEK: "deepseek_api_key_enc",
    LLMProvider.OPENAI: "openai_api_key_enc",
    LLMProvider.GEMINI: "gemini_api_key_enc",
    LLMProvider.GROQ: "groq_api_key_enc",
}

_PROVIDER_MODEL_ATTR = {
    LLMProvider.DEEPSEEK: "deepseek_model",
    LLMProvider.OPENAI: "openai_model",
    LLMProvider.GEMINI: "gemini_model",
    LLMProvider.GROQ: "groq_model",
}

_PROVIDER_REASONING_ATTR = {
    LLMProvider.DEEPSEEK: "deepseek_reasoning_effort",
    LLMProvider.OPENAI: "openai_reasoning_effort",
    LLMProvider.GEMINI: "gemini_reasoning_effort",
    LLMProvider.GROQ: "groq_reasoning_effort",
}

_PROVIDER_THINKING_ATTR = {
    LLMProvider.DEEPSEEK: "deepseek_supports_thinking",
    LLMProvider.OPENAI: "openai_supports_thinking",
    LLMProvider.GEMINI: "gemini_supports_thinking",
    LLMProvider.GROQ: "groq_supports_thinking",
}

_ENV_KEY_ATTR = {
    LLMProvider.DEEPSEEK: "DEEPSEEK_API_KEY",
    LLMProvider.OPENAI: "OPENAI_API_KEY",
    LLMProvider.GEMINI: "GEMINI_API_KEY",
    LLMProvider.GROQ: "GROQ_API_KEY",
}

_CLASS_BY_PROVIDER = {
    LLMProvider.DEEPSEEK: DeepSeek,
    LLMProvider.OPENAI: OpenAI,
    LLMProvider.GEMINI: Gemini,
    LLMProvider.GROQ: Groq,
}

GLOBAL_SETTINGS_ID = 1


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(
        hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    )
    return Fernet(key)


def encrypt_value(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_value(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except Exception:  # noqa: BLE001 - tolerate keys encrypted with a stale secret
        return None


def _selected_provider(row: object | None) -> LLMProvider | None:
    value = getattr(row, "selected_provider",
                    None) if row is not None else None
    if not value:
        return None
    try:
        return LLMProvider(value)
    except ValueError:
        return None


def _provider_reasoning(
    provider: LLMProvider, level: ReasoningLevel
) -> str:
    """Map the unified thinking power to each provider's vocabulary.

    Gemini understands ``MINIMAL|LOW|MEDIUM|HIGH``; OpenAI accepts
    ``minimal|low|medium|high``; DeepSeek only accepts ``low|high|max``.
    """
    if provider == LLMProvider.GEMINI:
        return level.value.upper()
    if provider == LLMProvider.DEEPSEEK:
        return {
            ReasoningLevel.MINIMAL: "low",
            ReasoningLevel.LOW: "low",
            ReasoningLevel.MEDIUM: "high",
            ReasoningLevel.HIGH: "max",
        }[level]
    return level.value


def _reasoning_by_provider(
    row: object | None,
) -> dict[LLMProvider, ReasoningLevel]:
    """Per-provider thinking power, falling back to ``MEDIUM``."""
    levels: dict[LLMProvider, ReasoningLevel] = {}
    for provider in PROVIDER_ORDER:
        value = getattr(row, _PROVIDER_REASONING_ATTR[provider],
                        None) if row is not None else None
        try:
            levels[provider] = ReasoningLevel(value) if value \
                else ReasoningLevel.MEDIUM
        except ValueError:
            levels[provider] = ReasoningLevel.MEDIUM
    return levels


def _supports_thinking_by_provider(
    row: object | None,
) -> dict[LLMProvider, bool]:
    """Per-provider thinking toggle, defaulting to ``True``."""
    flags: dict[LLMProvider, bool] = {}
    for provider in PROVIDER_ORDER:
        value = getattr(row, _PROVIDER_THINKING_ATTR[provider],
                        None) if row is not None else None
        flags[provider] = bool(value) if value is not None else True
    return flags


def _stored_keys(row: object | None) -> dict[LLMProvider, str]:
    keys: dict[LLMProvider, str] = {}
    if row is None:
        return keys
    for provider in PROVIDER_ORDER:
        api_key = decrypt_value(getattr(row, _PROVIDER_KEY_ATTR[provider]))
        if api_key:
            keys[provider] = api_key
    return keys


def _stored_models(row: object | None) -> dict[LLMProvider, str]:
    models: dict[LLMProvider, str] = {}
    if row is None:
        return models
    for provider in PROVIDER_ORDER:
        model = getattr(row, _PROVIDER_MODEL_ATTR[provider]) or ""
        if model.strip():
            models[provider] = model.strip()
    return models


def _env_keys() -> dict[LLMProvider, str]:
    keys: dict[LLMProvider, str] = {}
    for provider in PROVIDER_ORDER:
        api_key = getattr(settings, _ENV_KEY_ATTR[provider], "")
        if api_key:
            keys[provider] = api_key
    return keys


def _chain_from_row(
    *,
    row: object | None,
    keys: dict[LLMProvider, str],
) -> list[AIPlatform]:
    return _chain_from_keys(
        keys=keys,
        models=_stored_models(row),
        selected=_selected_provider(row),
        reasoning=_reasoning_by_provider(row),
        supports_thinking=_supports_thinking_by_provider(row),
    )


def _chain_from_keys(
    *,
    keys: dict[LLMProvider, str],
    models: dict[LLMProvider, str] | None = None,
    selected: LLMProvider | None = None,
    reasoning: dict[LLMProvider, ReasoningLevel] | None = None,
    supports_thinking: dict[LLMProvider, bool] | None = None,
) -> list[AIPlatform]:
    ordered = [selected] if selected is not None else []
    ordered += [p for p in PROVIDER_ORDER if p != selected]
    models = models or {}
    reasoning = reasoning or {}
    supports_thinking = supports_thinking or {}
    providers: list[AIPlatform] = []
    for provider in ordered:
        api_key = keys.get(provider)
        if not api_key:
            continue
        model = models.get(provider, PROVIDER_MODELS[provider])
        cls = _CLASS_BY_PROVIDER[provider]
        provider_reasoning = _provider_reasoning(
            provider,
            reasoning.get(provider, ReasoningLevel.MEDIUM),
        )
        provider_thinking = supports_thinking.get(provider, True)
        if provider == LLMProvider.GEMINI:
            providers.append(
                cls(
                    api_key=api_key,
                    model=model,
                    thinking_level=provider_reasoning,
                    supports_thinking=provider_thinking,
                )
            )
        else:
            providers.append(
                cls(
                    api_key=api_key,
                    model=model,
                    reasoning=provider_reasoning,
                    supports_thinking=provider_thinking,
                )
            )
    return providers


# ---------------------------------------------------------------------------
# Global AI settings (platform default)
# ---------------------------------------------------------------------------


def get_global_settings(*, session: Session) -> AIGlobalSettings:
    row = session.get(AIGlobalSettings, GLOBAL_SETTINGS_ID)
    if row is None:
        row = AIGlobalSettings(id=GLOBAL_SETTINGS_ID)
        session.add(row)
        session.commit()
        session.refresh(row)
    return row


def update_global_settings(
    *,
    session: Session,
    data: AIGlobalSettingsUpdate,
) -> AIGlobalSettings:
    row = session.get(AIGlobalSettings, GLOBAL_SETTINGS_ID)
    if row is None:
        row = AIGlobalSettings(id=GLOBAL_SETTINGS_ID)
        session.add(row)

    if data.selected_provider is not None:
        row.selected_provider = data.selected_provider.value
    else:
        row.selected_provider = None
    for provider in PROVIDER_ORDER:
        key_field = f"{provider.value}_api_key"
        api_key = getattr(data, key_field, None)
        if api_key is not None:
            setattr(
                row,
                _PROVIDER_KEY_ATTR[provider],
                encrypt_value(api_key) if api_key else None,
            )
        model_field = f"{provider.value}_model"
        model = getattr(data, model_field, None)
        if model is not None:
            setattr(
                row,
                _PROVIDER_MODEL_ATTR[provider],
                model.strip() or None,
            )
    for provider in PROVIDER_ORDER:
        reasoning_field = f"{provider.value}_reasoning_effort"
        reasoning_value = getattr(data, reasoning_field, None)
        if reasoning_value is not None:
            setattr(
                row,
                _PROVIDER_REASONING_ATTR[provider],
                reasoning_value.value,
            )
        thinking_field = f"{provider.value}_supports_thinking"
        thinking_value = getattr(data, thinking_field, None)
        if thinking_value is not None:
            setattr(
                row,
                _PROVIDER_THINKING_ATTR[provider],
                thinking_value,
            )
    row.updated_at = datetime.now(UTC).replace(tzinfo=None)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def global_settings_response(*, row: AIGlobalSettings) -> AIGlobalSettingsResponse:
    providers: dict[str, LLMProviderConfig] = {}
    for provider in PROVIDER_ORDER:
        configured = bool(decrypt_value(
            getattr(row, _PROVIDER_KEY_ATTR[provider])))
        model = (
            getattr(row, _PROVIDER_MODEL_ATTR[provider])
            or PROVIDER_MODELS[provider]
        )
        providers[provider.value] = LLMProviderConfig(
            configured=configured,
            model=model,
            supports_thinking=_supports_thinking_by_provider(row)[provider],
            reasoning_effort=_reasoning_by_provider(row)[provider],
        )
    return AIGlobalSettingsResponse(
        selected_provider=_selected_provider(row),
        providers=providers,
    )


def build_global_llm(*, session: Session | None = None) -> AIPlatform:
    """Build the platform default chain (global row, then environment keys)."""
    row = None
    if session is not None:
        row = session.get(AIGlobalSettings, GLOBAL_SETTINGS_ID)
    keys = _stored_keys(row)
    if not keys:
        keys = _env_keys()
    return FailoverLLM(providers=_chain_from_row(row=row, keys=keys))


# ---------------------------------------------------------------------------
# Per-company settings (optional override)
# ---------------------------------------------------------------------------


def get_company_llm_settings(
    *, session: Session, company_id: uuid.UUID
) -> CompanyLLMSettings | None:
    return session.get(CompanyLLMSettings, company_id)


def update_company_llm_settings(
    *,
    session: Session,
    company_id: uuid.UUID,
    data: CompanyLLMSettingsUpdate,
) -> CompanyLLMSettings:
    row = session.get(CompanyLLMSettings, company_id)
    if row is None:
        row = CompanyLLMSettings(company_id=company_id)
        session.add(row)

    if data.selected_provider is not None:
        row.selected_provider = data.selected_provider.value
    else:
        row.selected_provider = None
    for provider in PROVIDER_ORDER:
        key_field = f"{provider.value}_api_key"
        api_key = getattr(data, key_field, None)
        if api_key is not None:
            setattr(
                row,
                _PROVIDER_KEY_ATTR[provider],
                encrypt_value(api_key) if api_key else None,
            )
        model_field = f"{provider.value}_model"
        model = getattr(data, model_field, None)
        if model is not None:
            setattr(
                row,
                _PROVIDER_MODEL_ATTR[provider],
                model.strip() or None,
            )
    for provider in PROVIDER_ORDER:
        reasoning_field = f"{provider.value}_reasoning_effort"
        reasoning_value = getattr(data, reasoning_field, None)
        if reasoning_value is not None:
            setattr(
                row,
                _PROVIDER_REASONING_ATTR[provider],
                reasoning_value.value,
            )
        thinking_field = f"{provider.value}_supports_thinking"
        thinking_value = getattr(data, thinking_field, None)
        if thinking_value is not None:
            setattr(
                row,
                _PROVIDER_THINKING_ATTR[provider],
                thinking_value,
            )
    row.updated_at = datetime.now(UTC).replace(tzinfo=None)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def company_settings_response(
    *, company_id: uuid.UUID, row: CompanyLLMSettings | None
) -> CompanyLLMSettingsResponse:
    providers: dict[str, LLMProviderConfig] = {}
    for provider in PROVIDER_ORDER:
        configured = (
            bool(decrypt_value(getattr(row, _PROVIDER_KEY_ATTR[provider])))
            if row is not None
            else False
        )
        model = (
            (getattr(
                row, _PROVIDER_MODEL_ATTR[provider]) or PROVIDER_MODELS[provider])
            if row is not None
            else PROVIDER_MODELS[provider]
        )
        supports_thinking = (
            _supports_thinking_by_provider(row)[provider]
            if row is not None
            else True
        )
        reasoning_effort = (
            _reasoning_by_provider(row)[provider]
            if row is not None
            else ReasoningLevel.MEDIUM
        )
        providers[provider.value] = LLMProviderConfig(
            configured=configured,
            model=model,
            supports_thinking=supports_thinking,
            reasoning_effort=reasoning_effort,
        )
    return CompanyLLMSettingsResponse(
        company_id=company_id,
        selected_provider=_selected_provider(row),
        providers=providers,
    )


# Keep a backwards-compatible alias for callers using the old name.
settings_response = company_settings_response


def build_llm_for_company(
    *, session: Session, company_id: uuid.UUID
) -> AIPlatform:
    """Build the company chain, falling back to the global chain."""
    row = get_company_llm_settings(session=session, company_id=company_id)
    keys = _stored_keys(row)
    if not keys:
        return build_global_llm(session=session)
    return FailoverLLM(providers=_chain_from_row(row=row, keys=keys))


def build_llm_for_user(*, session: Session, user: User | None) -> AIPlatform:
    """Build the chain for a user's company, or the global chain."""
    if user is not None and user.company_id is not None:
        return build_llm_for_company(session=session, company_id=user.company_id)
    return build_global_llm(session=session)
