"""
Chat Service — read-only conversational interface scoped to a loaded plan.

Each turn:
1. Build messages: system prompt + plan/findings context + persisted history + new user msg.
2. Enforce per-user token budget.
3. Call the LLM via OpenRouter.
4. Persist user + assistant messages to `chat_messages`.
5. Record token spend.

Write actions (rewrite_section, regenerate_timeline) are handled separately by
the verb dispatcher and do NOT route through this function.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from app.auth.db import append_chat_message
from app.auth.models import User
from app.llm import budget
from app.llm.openrouter import LLMError, LLMNotConfigured, call_chat
from app.llm.prompts.chat_assistant import SYSTEM_PROMPT, build_context_message
from app.pipeline.report_generator import AuditReport

logger = logging.getLogger(__name__)


_MAX_USER_MESSAGE_CHARS = 4000
_MAX_HISTORY_TURNS = 12       # last 12 user/assistant pairs
_MAX_OUTPUT_TOKENS = 1024


class ChatError(Exception):
    """Raised when a chat turn cannot complete."""


@dataclass
class ChatTurnResult:
    reply: str
    model: str
    prompt_tokens: int
    completion_tokens: int


def _trim_history(history: list[dict]) -> list[dict]:
    """Keep only the last N turns to bound prompt size."""
    if len(history) <= _MAX_HISTORY_TURNS * 2:
        return history
    return history[-_MAX_HISTORY_TURNS * 2:]


def chat_turn(
    user: User,
    analysis_run_id: Optional[int],
    plan_text: str,
    report: AuditReport,
    history: list[dict],
    user_message: str,
) -> ChatTurnResult:
    """
    Run a single chat turn and persist both messages.
    `history` is a list of {"role": "user"|"assistant", "content": str}.
    """
    if not user_message or not user_message.strip():
        raise ChatError("Empty message.")

    cleaned = user_message.strip()
    if len(cleaned) > _MAX_USER_MESSAGE_CHARS:
        raise ChatError(
            f"Message is too long ({len(cleaned):,} chars). "
            f"Keep it under {_MAX_USER_MESSAGE_CHARS:,} characters."
        )

    context_block = build_context_message(plan_text, report)

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": context_block},
    ]
    messages.extend(_trim_history(history))
    messages.append({"role": "user", "content": cleaned})

    estimated = (
        budget.estimate_tokens(SYSTEM_PROMPT)
        + budget.estimate_tokens(context_block)
        + sum(budget.estimate_tokens(m["content"]) for m in messages[2:])
        + _MAX_OUTPUT_TOKENS
    )
    budget.assert_can_spend(user, estimated_tokens=estimated)

    try:
        result = call_chat(
            messages=messages,
            temperature=0.3,
            max_tokens=_MAX_OUTPUT_TOKENS,
        )
    except LLMNotConfigured as exc:
        raise ChatError(str(exc)) from exc
    except LLMError as exc:
        logger.warning("Chat LLM call failed: %s", exc)
        raise ChatError(f"Could not reply: {exc}") from exc

    budget.record_spend(
        user,
        purpose="chat_turn",
        model=result.model,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )

    # Persist both messages so reloading the report restores the conversation.
    append_chat_message(
        user_id=user.id,
        analysis_run_id=analysis_run_id,
        role="user",
        content=cleaned,
        tokens_used=result.prompt_tokens,
    )
    append_chat_message(
        user_id=user.id,
        analysis_run_id=analysis_run_id,
        role="assistant",
        content=result.text,
        tokens_used=result.completion_tokens,
    )

    return ChatTurnResult(
        reply=result.text,
        model=result.model,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )
