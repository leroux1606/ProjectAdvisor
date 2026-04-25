"""
Plan Generator — produces a draft project plan from a free-form prompt.

The output is plain markdown text. It is NOT scored here. The caller is
expected to feed the result through `run_pipeline()` so the deterministic
audit applies to the generated plan exactly as it would for any uploaded
plan. This keeps the scoring contract intact.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.auth.models import User
from app.llm import budget
from app.llm.openrouter import LLMError, LLMNotConfigured, call_chat
from app.llm.prompts.generate_plan import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)


_MAX_USER_PROMPT_CHARS = 4000
_MAX_OUTPUT_TOKENS = 4096


class PlanGenerationError(Exception):
    """Raised when plan generation cannot complete."""


@dataclass
class GeneratedPlan:
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    project_type: str


def generate_plan(
    user_prompt: str,
    project_type: str,
    user: User,
) -> GeneratedPlan:
    """
    Generate a draft project plan from a free-form prompt.

    Raises:
        PlanGenerationError — for input validation failures or LLM errors
                              with messages safe to surface to the user.
        budget.BudgetExceeded — when the user's monthly token budget would
                                be exceeded.
    """
    if not user_prompt or not user_prompt.strip():
        raise PlanGenerationError("Please describe the project you want to plan.")

    cleaned = user_prompt.strip()
    if len(cleaned) > _MAX_USER_PROMPT_CHARS:
        raise PlanGenerationError(
            f"Prompt is too long ({len(cleaned):,} chars). "
            f"Please keep it under {_MAX_USER_PROMPT_CHARS:,} characters."
        )

    user_message = build_user_prompt(cleaned, project_type)

    # Pre-flight budget check based on a rough estimate. Output is bounded by
    # max_tokens; we add a generous buffer to cover the actual completion.
    estimated = budget.estimate_tokens(SYSTEM_PROMPT + user_message) + _MAX_OUTPUT_TOKENS
    budget.assert_can_spend(user, estimated_tokens=estimated)

    try:
        result = call_chat(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.4,
            max_tokens=_MAX_OUTPUT_TOKENS,
        )
    except LLMNotConfigured as exc:
        raise PlanGenerationError(str(exc)) from exc
    except LLMError as exc:
        logger.warning("Plan generation LLM call failed: %s", exc)
        raise PlanGenerationError(f"Could not generate plan: {exc}") from exc

    budget.record_spend(
        user,
        purpose="generate_plan",
        model=result.model,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )

    text = result.text.strip()
    if len(text) < 200:
        raise PlanGenerationError(
            "The model produced an unusably short plan. Please try again "
            "with a more detailed prompt."
        )

    return GeneratedPlan(
        text=text,
        model=result.model,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        project_type=project_type,
    )
