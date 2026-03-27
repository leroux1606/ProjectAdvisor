"""
Pricing Plans — single source of truth for all tiers, prices, and limits.
Price IDs are read from environment variables (set in .env).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    description: str
    price_display: str       # human-readable, e.g. "£15 one-time"
    price_pence: int         # for display only
    credits: int             # 0 = unlimited (subscription)
    is_subscription: bool
    stripe_price_env: str    # env var name holding the Stripe Price ID
    badge: str               # e.g. "POPULAR"

    @property
    def stripe_price_id(self) -> Optional[str]:
        return os.getenv(self.stripe_price_env)


PLANS: list[Plan] = [
    Plan(
        id="credits_10",
        name="Starter Pack",
        description="10 project plan analyses. Never expires.",
        price_display="£15",
        price_pence=1500,
        credits=10,
        is_subscription=False,
        stripe_price_env="STRIPE_PRICE_CREDITS_10",
        badge="",
    ),
    Plan(
        id="credits_50",
        name="Team Pack",
        description="50 project plan analyses. Never expires.",
        price_display="£50",
        price_pence=5000,
        credits=50,
        is_subscription=False,
        stripe_price_env="STRIPE_PRICE_CREDITS_50",
        badge="BEST VALUE",
    ),
    Plan(
        id="pro_monthly",
        name="Pro Monthly",
        description="Unlimited analyses. Cancel anytime.",
        price_display="£29 / month",
        price_pence=2900,
        credits=0,
        is_subscription=True,
        stripe_price_env="STRIPE_PRICE_PRO_MONTHLY",
        badge="POPULAR",
    ),
    Plan(
        id="pro_annual",
        name="Pro Annual",
        description="Unlimited analyses. Save 28% vs monthly.",
        price_display="£249 / year",
        price_pence=24900,
        credits=0,
        is_subscription=True,
        stripe_price_env="STRIPE_PRICE_PRO_ANNUAL",
        badge="SAVE 28%",
    ),
]

FREE_MONTHLY_LIMIT = 2


def get_plan(plan_id: str) -> Optional[Plan]:
    return next((p for p in PLANS if p.id == plan_id), None)
