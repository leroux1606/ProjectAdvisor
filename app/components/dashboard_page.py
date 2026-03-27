"""
Dashboard Page — shows usage stats, current plan, billing portal link, transaction history.
"""

from __future__ import annotations

import streamlit as st

from app.auth.db import get_user_transactions
from app.auth.models import Tier, User
from app.auth.session import logout, refresh_user
from app.payments.plans import FREE_MONTHLY_LIMIT


def render_dashboard(user: User) -> None:
    # Refresh user from DB in case webhook updated their tier
    fresh = refresh_user()
    if fresh:
        user = fresh

    st.markdown(
        f'<h2 style="color:#f1f5f9;font-size:1.3rem;font-weight:700;margin-bottom:1.5rem;">'
        f'Account Dashboard</h2>',
        unsafe_allow_html=True,
    )

    col_info, col_actions = st.columns([2, 1], gap="large")

    with col_info:
        _render_plan_status(user)
        _render_usage(user)
        _render_transactions(user)

    with col_actions:
        _render_actions(user)


def _render_plan_status(user: User) -> None:
    tier_colors = {
        Tier.FREE: "#94a3b8",
        Tier.CREDITS: "#f59e0b",
        Tier.PRO: "#22c55e",
    }
    tier_labels = {
        Tier.FREE: "Free",
        Tier.CREDITS: "Credits",
        Tier.PRO: "Pro",
    }
    color = tier_colors.get(user.tier, "#94a3b8")
    label = tier_labels.get(user.tier, user.tier.value)

    st.markdown(
        f"""
        <div style="background:#1e293b;border:1px solid #334155;border-radius:8px;
                    padding:1rem 1.2rem;margin-bottom:1rem;">
            <div style="color:#64748b;font-size:0.78rem;margin-bottom:4px;">Current Plan</div>
            <div style="display:flex;align-items:center;gap:0.75rem;">
                <span style="
                    background:{color}22;color:{color};border:1px solid {color};
                    padding:3px 10px;border-radius:4px;font-size:0.85rem;font-weight:700;
                ">{label}</span>
                <span style="color:#94a3b8;font-size:0.88rem;">{user.access_label()}</span>
            </div>
            <div style="color:#475569;font-size:0.75rem;margin-top:6px;">
                Account: {user.email}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_usage(user: User) -> None:
    if user.tier == Tier.FREE:
        used = user.monthly_usage
        remaining = max(0, FREE_MONTHLY_LIMIT - used)
        pct = min(100, int((used / FREE_MONTHLY_LIMIT) * 100))
        bar_color = "#ef4444" if remaining == 0 else "#3b82f6"
        st.markdown(
            f"""
            <div style="background:#1e293b;border:1px solid #334155;border-radius:8px;
                        padding:1rem 1.2rem;margin-bottom:1rem;">
                <div style="color:#64748b;font-size:0.78rem;margin-bottom:8px;">Monthly Usage</div>
                <div style="color:#f1f5f9;font-size:0.9rem;margin-bottom:6px;">
                    {used} / {FREE_MONTHLY_LIMIT} analyses used
                </div>
                <div style="background:#334155;border-radius:4px;height:6px;overflow:hidden;">
                    <div style="background:{bar_color};height:100%;width:{pct}%;"></div>
                </div>
                <div style="color:#475569;font-size:0.75rem;margin-top:6px;">
                    Resets: {user.usage_reset_date or 'next month'}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    elif user.tier == Tier.CREDITS:
        st.markdown(
            f"""
            <div style="background:#1e293b;border:1px solid #334155;border-radius:8px;
                        padding:1rem 1.2rem;margin-bottom:1rem;">
                <div style="color:#64748b;font-size:0.78rem;margin-bottom:4px;">Credit Balance</div>
                <div style="color:#f59e0b;font-size:2rem;font-weight:700;">{user.credits}</div>
                <div style="color:#94a3b8;font-size:0.82rem;">analyses remaining</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="background:#1e293b;border:1px solid #334155;border-radius:8px;'
            'padding:1rem 1.2rem;margin-bottom:1rem;color:#22c55e;font-size:0.9rem;">'
            '✓ Pro plan — unlimited analyses</div>',
            unsafe_allow_html=True,
        )


def _render_transactions(user: User) -> None:
    txs = get_user_transactions(user.id)
    if not txs:
        return

    st.markdown("**Recent Transactions**")
    for tx in txs[:5]:
        tx_type = tx.get("type", "")
        amount = tx.get("amount_pence", 0)
        credits = tx.get("credits_added", 0)
        created = tx.get("created_at", "")[:10]

        label = {
            "credit_purchase": f"+{credits} credits",
            "subscription_start": "Pro subscription started",
        }.get(tx_type, tx_type)

        amount_str = f"£{amount / 100:.2f}" if amount else ""

        st.markdown(
            f'<div style="display:flex;justify-content:space-between;'
            f'padding:0.4rem 0;border-bottom:1px solid #1e293b;font-size:0.83rem;">'
            f'<span style="color:#94a3b8;">{created}</span>'
            f'<span style="color:#f1f5f9;">{label}</span>'
            f'<span style="color:#4ade80;">{amount_str}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )


def _render_actions(user: User) -> None:
    st.markdown("**Actions**")

    if st.button("🔍 Back to Analyser", use_container_width=True):
        st.session_state["page"] = "main"
        st.rerun()

    if user.tier != Tier.PRO:
        if st.button("⬆ Upgrade Plan", use_container_width=True):
            st.session_state["page"] = "pricing"
            st.rerun()

    if user.tier == Tier.PRO and user.stripe_customer_id:
        from app.payments.stripe_client import create_billing_portal_session  # noqa: PLC0415
        import os  # noqa: PLC0415
        app_url = os.getenv("APP_URL", "http://localhost:3000")
        try:
            portal_url = create_billing_portal_session(user.stripe_customer_id, app_url)
            st.markdown(
                f'<a href="{portal_url}" target="_blank" style="'
                f'display:block;background:#1e293b;border:1px solid #334155;border-radius:8px;'
                f'padding:0.5rem 1rem;color:#94a3b8;text-align:center;font-size:0.88rem;'
                f'text-decoration:none;margin-top:0.5rem;">'
                f'Manage Subscription ↗</a>',
                unsafe_allow_html=True,
            )
        except Exception:
            pass

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Sign Out", use_container_width=True):
        logout()
        st.rerun()
