"""
Webhook Handler — processes Stripe events and updates the database.
Called by webhook_server.py (Flask).
"""

from __future__ import annotations

import logging

import stripe

from app.auth.db import (
    get_user_by_id,
    get_user_by_stripe_customer,
    record_transaction,
    update_user,
)
from app.auth.models import Tier
from app.payments.plans import get_plan

logger = logging.getLogger(__name__)


def handle_event(event: stripe.Event) -> None:
    """Dispatch a Stripe event to the appropriate handler."""
    handlers = {
        "checkout.session.completed":           _on_checkout_completed,
        "customer.subscription.updated":        _on_subscription_updated,
        "customer.subscription.deleted":        _on_subscription_deleted,
        "invoice.payment_failed":               _on_payment_failed,
    }
    handler = handlers.get(event["type"])
    if handler:
        handler(event["data"]["object"])
    else:
        logger.debug("Unhandled Stripe event type: %s", event["type"])


def _on_checkout_completed(session: dict) -> None:
    user_id = int(session.get("metadata", {}).get("user_id", 0))
    plan_id = session.get("metadata", {}).get("plan_id", "")
    stripe_session_id = session.get("id", "")

    if not user_id or not plan_id:
        logger.warning("checkout.session.completed missing metadata: %s", session.get("id"))
        return

    user = get_user_by_id(user_id)
    if not user:
        logger.error("User %s not found for checkout session %s", user_id, stripe_session_id)
        return

    plan = get_plan(plan_id)
    if not plan:
        logger.error("Plan %s not found for checkout session %s", plan_id, stripe_session_id)
        return

    amount_pence = session.get("amount_total", 0) or 0

    if plan.is_subscription:
        # Subscription — upgrade to Pro
        subscription_id = session.get("subscription")
        user.tier = Tier.PRO
        user.stripe_subscription_id = subscription_id
        record_transaction(
            user_id=user.id,
            tx_type="subscription_start",
            amount_pence=amount_pence,
            credits_added=0,
            stripe_session_id=stripe_session_id,
        )
        logger.info("User %s upgraded to Pro (subscription %s)", user.id, subscription_id)
    else:
        # One-time credit pack
        user.credits += plan.credits
        if user.tier == Tier.FREE:
            user.tier = Tier.CREDITS
        record_transaction(
            user_id=user.id,
            tx_type="credit_purchase",
            amount_pence=amount_pence,
            credits_added=plan.credits,
            stripe_session_id=stripe_session_id,
        )
        logger.info("User %s purchased %d credits (plan %s)", user.id, plan.credits, plan_id)

    update_user(user)


def _on_subscription_updated(subscription: dict) -> None:
    customer_id = subscription.get("customer")
    status = subscription.get("status")

    user = get_user_by_stripe_customer(customer_id)
    if not user:
        return

    if status == "active":
        user.tier = Tier.PRO
        user.stripe_subscription_id = subscription.get("id")
    elif status in ("past_due", "unpaid", "canceled", "incomplete_expired"):
        user.tier = Tier.FREE
        user.stripe_subscription_id = None

    update_user(user)
    logger.info("User %s subscription status: %s → tier: %s", user.id, status, user.tier)


def _on_subscription_deleted(subscription: dict) -> None:
    customer_id = subscription.get("customer")
    user = get_user_by_stripe_customer(customer_id)
    if not user:
        return
    user.tier = Tier.FREE
    user.stripe_subscription_id = None
    update_user(user)
    logger.info("User %s subscription cancelled — reverted to Free tier", user.id)


def _on_payment_failed(invoice: dict) -> None:
    customer_id = invoice.get("customer")
    user = get_user_by_stripe_customer(customer_id)
    if not user:
        return
    logger.warning("Payment failed for user %s (customer %s)", user.id if user else "?", customer_id)
