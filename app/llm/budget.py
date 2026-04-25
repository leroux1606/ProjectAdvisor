"""
Token Budget — per-user monthly LLM token cap.

Free / Credits / Pro tiers each have a monthly token allowance. Tokens are
counted across every LLM call (insights, plan generation, chat). The budget
window resets on the same day as the analysis-quota reset (`usage_reset_date`).

Default limits can be overridden via env vars:
    TOKEN_BUDGET_FREE      (default 20_000)
    TOKEN_BUDGET_CREDITS   (default 200_000)
    TOKEN_BUDGET_PRO       (default 2_000_000)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from app.auth.db import (
    get_token_usage_for_period,
    record_llm_usage,
)
from app.auth.models import Tier, User, payment_bypass_enabled

logger = logging.getLogger(__name__)


_DEFAULT_BUDGETS = {
    Tier.FREE: 20_000,
    Tier.CREDITS: 200_000,
    Tier.PRO: 2_000_000,
}


class BudgetExceeded(Exception):
    """Raised when an LLM call would exceed the user's monthly token budget."""


@dataclass
class BudgetStatus:
    tier: Tier
    monthly_limit: int
    used: int
    remaining: int


def _budget_for_tier(tier: Tier) -> int:
    env_keys = {
        Tier.FREE: "TOKEN_BUDGET_FREE",
        Tier.CREDITS: "TOKEN_BUDGET_CREDITS",
        Tier.PRO: "TOKEN_BUDGET_PRO",
    }
    raw = os.getenv(env_keys[tier])
    if raw:
        try:
            return max(0, int(raw))
        except ValueError:
            logger.warning("Invalid %s value: %r — using default", env_keys[tier], raw)
    return _DEFAULT_BUDGETS[tier]


def _period_start_iso(user: User) -> str:
    """
    Tokens are counted for the current billing period — from one month before
    the next reset date to that date. We approximate by using the user's
    current `usage_reset_date` (a date string YYYY-MM-DD): the period started
    on the first day of *that* month.
    """
    reset = (user.usage_reset_date or "")[:10]
    if len(reset) >= 7:
        # reset is the 1st of next month, so the current period started the
        # 1st of the previous month.
        year = int(reset[:4])
        month = int(reset[5:7])
        period_year = year if month > 1 else year - 1
        period_month = month - 1 if month > 1 else 12
        return f"{period_year:04d}-{period_month:02d}-01"
    # Fallback: count all-time. Acceptable on first run before reset_date is set.
    return "0000-01-01"


def get_status(user: User) -> BudgetStatus:
    limit = _budget_for_tier(user.tier)
    used = get_token_usage_for_period(user.id, since=_period_start_iso(user))
    return BudgetStatus(
        tier=user.tier,
        monthly_limit=limit,
        used=used,
        remaining=max(0, limit - used),
    )


def assert_can_spend(user: User, estimated_tokens: int) -> None:
    """
    Raise BudgetExceeded if processing this request would push the user over
    their monthly budget. Bypassed when BYPASS_PAYMENT is enabled.
    """
    if payment_bypass_enabled():
        return
    status = get_status(user)
    if status.used + estimated_tokens > status.monthly_limit:
        raise BudgetExceeded(
            f"Monthly AI token budget reached "
            f"({status.used:,}/{status.monthly_limit:,} tokens used). "
            f"Resets with your next analysis quota."
        )


def record_spend(
    user: User,
    *,
    purpose: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> None:
    """Record a completed LLM call against the user's account."""
    record_llm_usage(
        user_id=user.id,
        purpose=purpose,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )


def estimate_tokens(text: str) -> int:
    """Rough pre-call estimate: ~4 chars per token. Used for budget gating."""
    return max(1, len(text) // 4)
