"""
LLM Client — thin wrapper around the OpenAI Chat Completions API.
All analysis modules must use this function exclusively.
Returns raw string content; callers are responsible for JSON parsing.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "OPENAI_API_KEY is not set. "
                "Create a .env file from .env.example and add your key."
            )
        _client = OpenAI(api_key=api_key)
    return _client


def call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.0,
    max_tokens: int = 2048,
) -> str:
    """
    Call the configured OpenAI model and return the raw response string.
    temperature=0.0 is enforced for all analysis calls to ensure determinism.
    """
    model = os.getenv("OPENAI_MODEL", "gpt-4o")
    client = _get_client()

    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content
    if content is None:
        raise ValueError("LLM returned an empty response.")
    return content
