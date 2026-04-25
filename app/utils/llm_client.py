"""
LLM Client — thin compatibility shim over app.llm.openrouter.

Existing modules (insights, section_extractor) call `call_llm(...)`. This shim
preserves that interface while routing through the OpenRouter client. Once
those callers migrate to the typed `app.llm.openrouter` interface directly,
this module can be removed.
"""

from __future__ import annotations

from app.llm.openrouter import LLMError, call_chat


def call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.0,
    max_tokens: int = 2048,
) -> str:
    """
    Backward-compatible wrapper. Returns the raw response string.
    Callers are responsible for JSON parsing.
    """
    result = call_chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        # Honoured by OpenAI and some OpenRouter models. Ignored by others;
        # the existing callers' system prompts already enforce JSON.
        response_format={"type": "json_object"},
    )
    return result.text


__all__ = ["call_llm", "LLMError"]
