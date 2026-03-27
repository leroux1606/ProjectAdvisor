"""
Pricing Page — displays plan cards and redirects to Stripe Checkout.
"""

from __future__ import annotations

import streamlit as st

from app.auth.models import User
from app.payments.checkout import get_checkout_url
from app.payments.plans import FREE_MONTHLY_LIMIT, PLANS, Plan


_BADGE_STYLE = (
    "background:#1e3a5f;color:#93c5fd;border:1px solid #3b82f6;"
    "padding:2px 8px;border-radius:4px;font-size:0.7rem;font-weight:700;"
    "letter-spacing:0.05em;"
)

_CARD_STYLE = (
    "background:#1e293b;border:1px solid #334155;border-radius:12px;"
    "padding:1.5rem;text-align:center;height:100%;"
)

_CARD_HIGHLIGHT = (
    "background:#1e293b;border:2px solid #3b82f6;border-radius:12px;"
    "padding:1.5rem;text-align:center;height:100%;"
)


def render_pricing_page(user: User) -> None:
    st.markdown(
        """
        <div style="text-align:center;margin-bottom:2rem;">
            <h2 style="color:#f1f5f9;font-size:1.5rem;font-weight:800;">Upgrade Your Plan</h2>
            <p style="color:#cbd5e1;font-size:0.9rem;">
                Choose the option that fits your needs. All payments processed securely by Stripe.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Free tier reminder
    st.markdown(
        f'<div style="background:#0f172a;border:1px solid #334155;border-radius:8px;'
        f'padding:0.75rem 1rem;color:#94a3b8;font-size:0.85rem;margin-bottom:1.5rem;text-align:center;">'
        f'You are on the <strong style="color:#f1f5f9;">Free tier</strong> — '
        f'{FREE_MONTHLY_LIMIT} analyses per month included at no cost.</div>',
        unsafe_allow_html=True,
    )

    cols = st.columns(len(PLANS), gap="medium")

    for col, plan in zip(cols, PLANS):
        with col:
            _render_plan_card(plan, user)

    st.markdown(
        '<div style="color:#cbd5e1;font-size:0.75rem;text-align:center;margin-top:2rem;">'
        'Payments processed by Stripe · Subscriptions can be cancelled anytime from your dashboard'
        '</div>',
        unsafe_allow_html=True,
    )


def _render_plan_card(plan: Plan, user: User) -> None:
    highlight = plan.badge in ("POPULAR", "BEST VALUE")
    card_css = _CARD_HIGHLIGHT if highlight else _CARD_STYLE

    badge_html = (
        f'<div style="margin-bottom:0.5rem;">'
        f'<span style="{_BADGE_STYLE}">{plan.badge}</span></div>'
        if plan.badge else '<div style="margin-bottom:1.2rem;"></div>'
    )

    st.markdown(
        f"""
        <div style="{card_css}">
            {badge_html}
            <div style="color:#f1f5f9;font-size:1rem;font-weight:700;margin-bottom:0.3rem;">
                {plan.name}
            </div>
            <div style="color:#3b82f6;font-size:1.6rem;font-weight:800;margin-bottom:0.5rem;">
                {plan.price_display}
            </div>
            <div style="color:#94a3b8;font-size:0.82rem;margin-bottom:1rem;">
                {plan.description}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    price_id = plan.stripe_price_id
    if not price_id:
        st.markdown(
            '<div style="color:#f59e0b;font-size:0.75rem;text-align:center;margin-top:0.5rem;">'
            'Not yet configured</div>',
            unsafe_allow_html=True,
        )
        return

    if st.button(f"Buy — {plan.price_display}", key=f"buy_{plan.id}", use_container_width=True):
        try:
            url = get_checkout_url(user, plan)
            st.markdown(
                f'<meta http-equiv="refresh" content="0;url={url}">',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div style="color:#94a3b8;font-size:0.85rem;text-align:center;">'
                f'Redirecting to Stripe… <a href="{url}" style="color:#3b82f6;">click here</a> if not redirected.</div>',
                unsafe_allow_html=True,
            )
        except Exception as e:
            st.error(f"Could not create checkout session: {e}")
