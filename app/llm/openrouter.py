"""
OpenRouter Client — single entry point for all LLM calls.

Reads configuration from the environment:
    OPENROUTER_API_KEY      required
    OPENROUTER_MODEL        default model (default: anthropic/claude-haiku-4-5)
    OPENROUTER_APP_URL      sent as HTTP-Referer (recommended by OpenRouter)
    OPENROUTER_APP_NAME     sent as X-Title

Backward compatibility:
    If OPENROUTER_API_KEY is unset but OPENAI_API_KEY is set, calls fall back
    to OpenAI directly. This lets the existing AI Insights layer keep working
    until the migration is complete.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_OPENAI_URL = "https://api.openai.com/v1/chat/completions"

DEFAULT_MODEL = "anthropic/claude-haiku-4-5"
_DEFAULT_TIMEOUT_SECONDS = 60


class LLMError(Exception):
    """Raised when an LLM call fails for a reason the caller can surface."""


class LLMNotConfigured(LLMError):
    """Raised when no LLM provider is configured."""


@dataclass
class ChatResult:
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


def _provider() -> str:
    """Return 'openrouter' if configured, else 'openai' if configured, else raise."""
    if os.getenv("OPENROUTER_API_KEY"):
        return "openrouter"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    raise LLMNotConfigured(
        "No LLM provider configured. Set OPENROUTER_API_KEY (preferred) "
        "or OPENAI_API_KEY in your .env file."
    )


def llm_available() -> bool:
    """True when at least one provider key is set."""
    return bool(os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"))


def _resolve_model(model: Optional[str], provider: str) -> str:
    if model:
        return model
    if provider == "openrouter":
        return os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL)
    # openai legacy
    return os.getenv("OPENAI_MODEL", "gpt-4o")


def _headers(provider: str) -> dict[str, str]:
    if provider == "openrouter":
        headers = {
            "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
            "Content-Type": "application/json",
        }
        # Optional but recommended by OpenRouter for app attribution.
        app_url = os.getenv("OPENROUTER_APP_URL")
        app_name = os.getenv("OPENROUTER_APP_NAME")
        if app_url:
            headers["HTTP-Referer"] = app_url
        if app_name:
            headers["X-Title"] = app_name
        return headers
    # openai legacy
    return {
        "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
        "Content-Type": "application/json",
    }


def _endpoint(provider: str) -> str:
    return _OPENROUTER_URL if provider == "openrouter" else _OPENAI_URL


def call_chat(
    messages: list[dict],
    *,
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 2048,
    response_format: Optional[dict] = None,
    timeout: int = _DEFAULT_TIMEOUT_SECONDS,
) -> ChatResult:
    """
    Send a chat-completion request and return a ChatResult.

    `messages` is the standard OpenAI-format list of {role, content}.
    `response_format` is passed through (e.g. {"type": "json_object"}) but is
    only honoured by some models; callers that need JSON must also instruct
    the model in the prompt.
    """
    provider = _provider()
    resolved_model = _resolve_model(model, provider)

    payload: dict = {
        "model": resolved_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format is not None:
        payload["response_format"] = response_format

    try:
        response = requests.post(
            _endpoint(provider),
            headers=_headers(provider),
            json=payload,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise LLMError(f"LLM request failed: {exc}") from exc

    if response.status_code >= 400:
        # Try to surface the provider's error message if present.
        detail = response.text[:500]
        try:
            err = response.json().get("error", {})
            if isinstance(err, dict):
                detail = err.get("message", detail)
            elif isinstance(err, str):
                detail = err
        except (ValueError, AttributeError):
            pass
        raise LLMError(
            f"LLM provider returned HTTP {response.status_code}: {detail}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise LLMError(f"LLM returned non-JSON body: {response.text[:200]}") from exc

    choices = data.get("choices") or []
    if not choices:
        raise LLMError("LLM response had no choices.")
    content = choices[0].get("message", {}).get("content")
    if not content:
        raise LLMError("LLM returned an empty message.")

    usage = data.get("usage") or {}
    return ChatResult(
        text=content,
        model=data.get("model", resolved_model),
        prompt_tokens=int(usage.get("prompt_tokens", 0)),
        completion_tokens=int(usage.get("completion_tokens", 0)),
        total_tokens=int(usage.get("total_tokens", 0)),
    )


def call_json(
    system_prompt: str,
    user_prompt: str,
    *,
    model: Optional[str] = None,
    max_tokens: int = 2048,
    timeout: int = _DEFAULT_TIMEOUT_SECONDS,
) -> tuple[dict, ChatResult]:
    """
    Convenience wrapper that asks the model to respond with a JSON object,
    parses the result, and returns (parsed_dict, ChatResult).

    Raises LLMError if the response cannot be parsed as JSON.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    result = call_chat(
        messages,
        model=model,
        temperature=0.0,
        max_tokens=max_tokens,
        # Some providers/models honour this; others ignore it. The system prompt
        # should also instruct the model to return JSON.
        response_format={"type": "json_object"},
        timeout=timeout,
    )

    text = result.text.strip()
    try:
        return json.loads(text), result
    except json.JSONDecodeError:
        # Tolerate leading/trailing prose by extracting the first {...} object.
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise LLMError(f"LLM did not return JSON: {text[:200]}")
        return json.loads(match.group()), result
