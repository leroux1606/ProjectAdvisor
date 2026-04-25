"""
Write-action verbs for the chat assistant.

Each verb takes the current plan text plus user-supplied parameters, calls
the LLM, and returns a *proposal* (the full revised plan). The caller is
responsible for:
  - Showing a diff of original vs proposal to the user.
  - Re-running the audit pipeline on the proposal if the user accepts.
  - Persisting the new state.

Verbs do NOT mutate state themselves. This keeps the contract auditable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from app.auth.models import User
from app.llm import budget
from app.llm.openrouter import LLMError, LLMNotConfigured, call_chat
from app.llm.prompts.write_verbs import (
    SYSTEM_PROMPT,
    build_add_section_prompt,
    build_regenerate_timeline_prompt,
    build_rewrite_prompt,
)

logger = logging.getLogger(__name__)


_MAX_INSTRUCTION_CHARS = 1000
_MAX_OUTPUT_TOKENS = 4096


class Verb(str, Enum):
    REWRITE_SECTION = "rewrite_section"
    ADD_SECTION = "add_section"
    REGENERATE_TIMELINE = "regenerate_timeline"


# The fixed canonical sections that the rewrite/add verbs may target. Mirrors
# the rule engine's `SECTION_NAMES` list — extending here without extending
# there would create a verb that the rule engine cannot evaluate.
ALLOWED_SECTIONS: tuple[str, ...] = (
    "Objectives",
    "Scope",
    "Deliverables",
    "Timeline",
    "Resources",
    "Risks",
    "Governance",
    "Assumptions",
    "Constraints",
    "Budget",
)


class VerbError(Exception):
    """Raised when a verb cannot complete with a user-facing message."""


@dataclass
class VerbProposal:
    verb: Verb
    section: str | None
    instructions: str
    proposed_plan_text: str
    model: str
    prompt_tokens: int
    completion_tokens: int


def _validate_section(section: str) -> str:
    normalised = section.strip().title()
    if normalised not in ALLOWED_SECTIONS:
        raise VerbError(
            f"Unknown section '{section}'. Allowed: {', '.join(ALLOWED_SECTIONS)}."
        )
    return normalised


def _validate_instructions(instructions: str) -> str:
    cleaned = (instructions or "").strip()
    if len(cleaned) > _MAX_INSTRUCTION_CHARS:
        raise VerbError(
            f"Instructions are too long ({len(cleaned):,} chars). "
            f"Keep them under {_MAX_INSTRUCTION_CHARS:,} characters."
        )
    return cleaned


def _run(
    user: User,
    purpose: str,
    user_prompt: str,
) -> tuple[str, str, int, int]:
    """Shared LLM-call path for all write verbs."""
    estimated = (
        budget.estimate_tokens(SYSTEM_PROMPT)
        + budget.estimate_tokens(user_prompt)
        + _MAX_OUTPUT_TOKENS
    )
    budget.assert_can_spend(user, estimated_tokens=estimated)

    try:
        result = call_chat(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=_MAX_OUTPUT_TOKENS,
        )
    except LLMNotConfigured as exc:
        raise VerbError(str(exc)) from exc
    except LLMError as exc:
        logger.warning("Write-verb LLM call failed: %s", exc)
        raise VerbError(f"Could not generate proposal: {exc}") from exc

    budget.record_spend(
        user,
        purpose=purpose,
        model=result.model,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )

    text = result.text.strip()
    if len(text) < 200:
        raise VerbError(
            "The model produced an unusably short proposal. Please try again "
            "with clearer instructions."
        )
    return text, result.model, result.prompt_tokens, result.completion_tokens


def rewrite_section(
    user: User,
    plan_text: str,
    section: str,
    instructions: str,
) -> VerbProposal:
    section = _validate_section(section)
    instructions = _validate_instructions(instructions)
    prompt = build_rewrite_prompt(plan_text, section, instructions)
    text, model, ptok, ctok = _run(user, "rewrite_section", prompt)
    return VerbProposal(
        verb=Verb.REWRITE_SECTION,
        section=section,
        instructions=instructions,
        proposed_plan_text=text,
        model=model,
        prompt_tokens=ptok,
        completion_tokens=ctok,
    )


def add_section(
    user: User,
    plan_text: str,
    section: str,
    instructions: str,
) -> VerbProposal:
    section = _validate_section(section)
    instructions = _validate_instructions(instructions)
    prompt = build_add_section_prompt(plan_text, section, instructions)
    text, model, ptok, ctok = _run(user, "add_section", prompt)
    return VerbProposal(
        verb=Verb.ADD_SECTION,
        section=section,
        instructions=instructions,
        proposed_plan_text=text,
        model=model,
        prompt_tokens=ptok,
        completion_tokens=ctok,
    )


def regenerate_timeline(
    user: User,
    plan_text: str,
    constraints: str,
) -> VerbProposal:
    constraints = _validate_instructions(constraints)
    prompt = build_regenerate_timeline_prompt(plan_text, constraints)
    text, model, ptok, ctok = _run(user, "regenerate_timeline", prompt)
    return VerbProposal(
        verb=Verb.REGENERATE_TIMELINE,
        section="Timeline",
        instructions=constraints,
        proposed_plan_text=text,
        model=model,
        prompt_tokens=ptok,
        completion_tokens=ctok,
    )
