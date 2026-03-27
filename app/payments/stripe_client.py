"""
Stripe Client — thin wrapper around the Stripe SDK.
All Stripe API calls go through this module.
"""

from __future__ import annotations

import os
from typing import Optional

import stripe
from dotenv import load_dotenv

load_dotenv()


def _get_stripe():
    key = os.getenv("STRIPE_SECRET_KEY")
    if not key:
        raise EnvironmentError(
            "STRIPE_SECRET_KEY is not set. Add it to your .env file."
        )
    stripe.api_key = key
    return stripe


def create_customer(email: str) -> str:
    """Create a Stripe Customer and return the customer ID."""
    s = _get_stripe()
    customer = s.Customer.create(email=email)
    return customer.id


def create_checkout_session(
    price_id: str,
    customer_id: str,
    success_url: str,
    cancel_url: str,
    mode: str,                    # "payment" or "subscription"
    metadata: Optional[dict] = None,
) -> str:
    """Create a Stripe Checkout Session and return the session URL."""
    s = _get_stripe()
    params = {
        "customer": customer_id,
        "line_items": [{"price": price_id, "quantity": 1}],
        "mode": mode,
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": metadata or {},
    }
    session = s.checkout.Session.create(**params)
    return session.url


def create_billing_portal_session(customer_id: str, return_url: str) -> str:
    """Create a Stripe Billing Portal session URL for subscription management."""
    s = _get_stripe()
    session = s.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return session.url


def construct_webhook_event(payload: bytes, sig_header: str) -> stripe.Event:
    """Verify and parse an incoming Stripe webhook event."""
    secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise EnvironmentError("STRIPE_WEBHOOK_SECRET is not set.")
    return stripe.Webhook.construct_event(payload, sig_header, secret)


def cancel_subscription(subscription_id: str) -> None:
    s = _get_stripe()
    s.Subscription.cancel(subscription_id)
