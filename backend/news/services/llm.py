"""Multi-provider chat-completion client for NewsHub.

Provider order is Gemini (primary), then Groq (fallback). The previous
OpenAI-compatible LLM_* configuration remains available only when neither
Gemini nor Groq is configured, or when LLM_ENABLE_LEGACY_FALLBACK=true.
No provider key is ever logged or returned to the frontend.
"""
from __future__ import annotations

import logging
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

import requests
from django.conf import settings

from news.exceptions import AIServiceError

logger = logging.getLogger("newshub.llm")
_provider_trace: ContextVar[tuple[str, ...]] = ContextVar("newshub_llm_provider_trace", default=())


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    api_key: str
    base_url: str
    model: str
    timeout: float


def reset_llm_provider_trace() -> None:
    """Start a fresh provider trace for the current request/task."""
    _provider_trace.set(())


def _record_provider(name: str, model: str) -> None:
    label = f"{name}:{model}"
    current = _provider_trace.get()
    if label not in current:
        _provider_trace.set(current + (label,))


def llm_provider_label() -> str:
    """Return the actual provider/model labels used by the current operation."""
    trace = _provider_trace.get()
    return ",".join(trace) if trace else llm_model_name()


def _provider_configs() -> list[ProviderConfig]:
    config = settings.NEWSHUB
    providers: list[ProviderConfig] = []
    gemini_key = str(config.get("GEMINI_API_KEY") or "").strip()
    groq_key = str(config.get("GROQ_API_KEY") or "").strip()

    if gemini_key:
        providers.append(ProviderConfig(
            name="gemini",
            api_key=gemini_key,
            base_url=str(config.get(
                "GEMINI_BASE_URL",
                "https://generativelanguage.googleapis.com/v1beta/openai",
            )).strip(),
            model=str(config.get("GEMINI_MODEL", "gemini-3.8-flash")).strip(),
            timeout=float(config.get("GEMINI_TIMEOUT", 18)),
        ))

    if groq_key:
        providers.append(ProviderConfig(
            name="groq",
            api_key=groq_key,
            base_url=str(config.get(
                "GROQ_BASE_URL", "https://api.groq.com/openai/v1"
            )).strip(),
            model=str(config.get("GROQ_MODEL", "openai/gpt-oss-20b")).strip(),
            timeout=float(config.get("GROQ_TIMEOUT", 18)),
        ))

    # Backward compatibility: use the old provider if no new provider is set.
    # When Gemini/Groq are configured, use OpenAI only if explicitly enabled.
    legacy_key = str(config.get("LLM_API_KEY") or "").strip()
    allow_legacy_fallback = bool(config.get("LLM_ENABLE_LEGACY_FALLBACK", False))
    if legacy_key and (not providers or allow_legacy_fallback):
        providers.append(ProviderConfig(
            name="legacy",
            api_key=legacy_key,
            base_url=str(config.get("LLM_BASE_URL", "https://api.openai.com/v1")).strip(),
            model=str(config.get("LLM_MODEL", "gpt-4o-mini")).strip(),
            timeout=float(config.get("LLM_TIMEOUT", 25)),
        ))

    return [p for p in providers if p.api_key and p.base_url and p.model]


def is_llm_enabled() -> bool:
    return bool(_provider_configs())


def llm_model_name() -> str:
    """Return configured provider/model identity for backward compatibility."""
    providers = _provider_configs()
    return providers[0].model if providers else ""


def llm_cache_identity() -> str:
    """Include all configured providers/models in summary cache versioning."""
    providers = _provider_configs()
    return "|".join(f"{p.name}:{p.model}" for p in providers) or "no-ai-provider"


def _provider_error(response: requests.Response) -> tuple[str, str, str]:
    message = ""
    code = ""
    try:
        payload = response.json()
        error = payload.get("error", payload) if isinstance(payload, dict) else {}
        if isinstance(error, dict):
            message = str(error.get("message") or "")[:350]
            code = str(error.get("code") or error.get("type") or "")[:100]
    except (ValueError, TypeError):
        pass
    request_id = str(
        response.headers.get("x-request-id")
        or response.headers.get("request-id")
        or response.headers.get("x-goog-request-id")
        or ""
    )[:120]
    return message, code, request_id


def _extract_response_text(response: requests.Response, provider: ProviderConfig) -> str:
    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        request_id = str(response.headers.get("x-request-id", ""))[:120]
        logger.warning(
            "AI provider returned unexpected response: provider=%s model=%s request_id=%s",
            provider.name, provider.model, request_id or "not_returned",
        )
        raise AIServiceError("The AI provider returned an unexpected response format.") from exc

    if isinstance(content, list):
        content = " ".join(
            str(item.get("text", "")) for item in content if isinstance(item, dict)
        )
    if not content or not str(content).strip():
        raise AIServiceError("The AI provider returned an empty response.")
    return str(content).strip()


def _request_provider(
    provider: ProviderConfig,
    messages: list[dict],
    max_tokens: int,
    temperature: float,
) -> str:
    url = f"{provider.base_url.rstrip('/')}/chat/completions"
    payload: dict[str, Any] = {"model": provider.model, "messages": messages}

    if provider.name == "gemini":
        # Google documents this OpenAI-compatible Chat Completions endpoint.
        payload["max_tokens"] = max_tokens
        payload["reasoning_effort"] = "low"
    elif provider.name == "groq":
        # Groq recommends max_completion_tokens; it accepts chat-completion
        # messages and reasoning_effort for GPT-OSS models.
        payload["max_completion_tokens"] = max_tokens
        payload["temperature"] = temperature
        if provider.model.startswith("openai/gpt-oss"):
            payload["reasoning_effort"] = "low"
    else:
        model_lower = provider.model.lower()
        if model_lower.startswith(("gpt-5", "gpt-6", "o1", "o3", "o4")):
            payload["max_completion_tokens"] = max_tokens
            if model_lower.startswith(("gpt-5", "gpt-6")):
                payload["reasoning_effort"] = "none"
        else:
            payload["max_tokens"] = max_tokens
            payload["temperature"] = temperature

    try:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {provider.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=provider.timeout,
        )
    except requests.Timeout as exc:
        logger.warning("AI provider timeout: provider=%s model=%s", provider.name, provider.model)
        raise AIServiceError(f"{provider.name.title()} request timed out.") from exc
    except requests.RequestException as exc:
        logger.warning(
            "AI provider connection failed: provider=%s model=%s error=%s",
            provider.name, provider.model, exc.__class__.__name__,
        )
        raise AIServiceError(f"{provider.name.title()} could not be reached.") from exc

    if response.status_code >= 400:
        message, code, request_id = _provider_error(response)
        logger.warning(
            "AI provider rejected request: provider=%s model=%s status=%s code=%s request_id=%s message=%s",
            provider.name, provider.model, response.status_code,
            code or "not_returned", request_id or "not_returned",
            message or "no provider message",
        )
        if response.status_code in {401, 403}:
            reason = "authentication/permission rejected"
        elif response.status_code == 429:
            reason = "rate/quota limit reached"
        elif response.status_code == 400:
            reason = f"request rejected ({code or 'invalid_request'})"
        elif response.status_code == 404:
            reason = f"model or endpoint not found ({code or 'not_found'})"
        else:
            reason = f"HTTP {response.status_code} ({code or 'provider_error'})"
        raise AIServiceError(f"{provider.name.title()}: {reason}.")

    text = _extract_response_text(response, provider)
    _record_provider(provider.name, provider.model)
    return text


def chat_completion(
    messages: list[dict],
    max_tokens: int = 350,
    temperature: float = 0.2,
) -> str:
    """Try Gemini first, then Groq, then an explicitly enabled legacy provider."""
    providers = _provider_configs()
    if not providers:
        raise AIServiceError(
            "No AI provider is configured. Set GEMINI_API_KEY and/or GROQ_API_KEY in backend/.env."
        )

    failures: list[str] = []
    for provider in providers:
        try:
            result = _request_provider(provider, messages, max_tokens, temperature)
            logger.info("AI completion succeeded: provider=%s model=%s", provider.name, provider.model)
            return result
        except AIServiceError as exc:
            failures.append(str(exc))
            logger.warning("AI provider failed; trying next configured provider: %s", str(exc))

    raise AIServiceError(
        "All configured AI providers failed (" + " ; ".join(failures)
        + "). Check provider keys, model access and rate limits."
    )
