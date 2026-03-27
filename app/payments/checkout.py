"""
Checkout — builds Stripe Checkout Session URLs for each plan.
Ensures the user has a Stripe Customer record before checkout.
"""

from __future__ import annotations

import os

from app.auth.db import update_user
from app.auth.models import User
from app.payments.plans import Plan
from app.payments.stripe_client import create_checkout_session, create_customer

_APP_URL = os.getenv("APP_URL", "http://localhost:3000")


def _ensure_stripe_customer(user: User) -> str:
    """Create a Stripe Customer for the user if one doesn't exist yet."""
    if user.stripe_customer_id:
        return user.stripe_customer_id
    customer_id = create_customer(user.email)
    user.stripe_customer_id = customer_id
    update_user(user)
    return customer_id


def get_checkout_url(user: User, plan: Plan) -> str:
    """
    Return a Stripe Checkout URL for the given plan.
    The success URL includes ?session_id={CHECKOUT_SESSION_ID} so the
    app can poll for payment confirmation.
    """
    customer_id = _ensure_stripe_customer(user)

    price_id = plan.stripe_price_id
    if not price_id:
        raise ValueError(
            f"Stripe Price ID not configured for plan '{plan.id}'. "
            f"Set {plan.stripe_price_env} in your .env file."
        )

    mode = "subscription" if plan.is_subscription else "payment"

    success_url = f"{_APP_URL}/?payment=success&session_id={{CHECKOUT_SESSION_ID}}&plan={plan.id}"
    cancel_url = f"{_APP_URL}/?payment=cancelled"

    return create_checkout_session(
        price_id=price_id,
        customer_id=customer_id,
        success_url=success_url,
        cancel_url=cancel_url,
        mode=mode,
        metadata={"user_id": str(user.id), "plan_id": plan.id},
    )
