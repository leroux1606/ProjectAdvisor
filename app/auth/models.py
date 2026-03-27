"""
Auth Models — User dataclass and tier definitions.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


class Tier(str, Enum):
    FREE = "free"
    CREDITS = "credits"   # has a credit balance, no subscription
    PRO = "pro"           # active subscription (monthly or annual)


def payment_bypass_enabled() -> bool:
    value = os.getenv("BYPASS_PAYMENT", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


@dataclass
class User:
    id: int
    email: str
    password_hash: str
    tier: Tier
    credits: int                      # remaining one-time analysis credits
    monthly_usage: int                # analyses run this calendar month (free tier)
    usage_reset_date: str             # ISO date string — when monthly_usage resets
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    display_name: Optional[str] = None
    organization: Optional[str] = None
    created_at: str = ""

    def can_analyse(self) -> bool:
        """Return True if the user is allowed to run an analysis right now."""
        if payment_bypass_enabled():
            return True
        if self.tier == Tier.PRO:
            return True
        if self.tier == Tier.CREDITS and self.credits > 0:
            return True
        if self.tier == Tier.FREE:
            from app.auth.service import reset_monthly_usage_if_needed  # noqa: PLC0415
            reset_monthly_usage_if_needed(self)
            return self.monthly_usage < 2
        return False

    def access_label(self) -> str:
        if payment_bypass_enabled():
            return "Testing mode — payment bypass enabled"
        if self.tier == Tier.PRO:
            return "Pro — unlimited"
        if self.tier == Tier.CREDITS:
            return f"{self.credits} credit(s) remaining"
        reset_date = self.usage_reset_date or ""
        used = self.monthly_usage
        return f"Free — {max(0, 2 - used)} of 2 free analyses remaining (resets {reset_date})"
