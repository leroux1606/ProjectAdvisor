"""
Dashboard Page — shows usage stats, current plan, billing portal link, transaction history.
"""

from __future__ import annotations

from html import escape

import streamlit as st

from app.auth.db import get_analysis_history, get_analysis_stats, get_analysis_stats_for_workspace, get_user_transactions, get_workspace, update_user
from app.auth.models import Tier, User
from app.auth.session import get_active_workspace_id, logout, refresh_user
from app.payments.plans import FREE_MONTHLY_LIMIT


def render_dashboard(user: User) -> None:
    # Refresh user from DB in case webhook updated their tier
    fresh = refresh_user()
    if fresh:
        user = fresh
    workspace_id = get_active_workspace_id()
    workspace = get_workspace(workspace_id) if workspace_id else None

    st.markdown(
        f'<h2 style="color:#f1f5f9;font-size:1.3rem;font-weight:700;margin-bottom:1.5rem;">'
        f'Account Dashboard</h2>',
        unsafe_allow_html=True,
    )
    if workspace:
        st.info(f'Active workspace: {workspace["name"]}. New analyses are currently saved to this shared workspace.')

    col_info, col_actions = st.columns([2, 1], gap="large")

    with col_info:
        _render_plan_status(user)
        _render_profile_editor(user)
        _render_analysis_stats(user, workspace_id)
        _render_usage(user)
        _render_recent_analyses(user, workspace_id)
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
            <div style="color:#cbd5e1;font-size:0.78rem;margin-bottom:4px;">Current Plan</div>
            <div style="display:flex;align-items:center;gap:0.75rem;">
                <span style="
                    background:{color}22;color:{color};border:1px solid {color};
                    padding:3px 10px;border-radius:4px;font-size:0.85rem;font-weight:700;
                ">{label}</span>
                <span style="color:#94a3b8;font-size:0.88rem;">{escape(user.access_label())}</span>
            </div>
            <div style="color:#cbd5e1;font-size:0.75rem;margin-top:6px;">
                Account: {escape(user.email)}
            </div>
            {f'<div style="color:#94a3b8;font-size:0.75rem;margin-top:4px;">Name: {escape(user.display_name)}</div>' if user.display_name else ''}
            {f'<div style="color:#94a3b8;font-size:0.75rem;margin-top:4px;">Organisation: {escape(user.organization)}</div>' if user.organization else ''}
            <div style="color:#94a3b8;font-size:0.75rem;margin-top:4px;">
                Member since: {user.created_at[:10] if user.created_at else "Recently"}
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
                <div style="color:#cbd5e1;font-size:0.78rem;margin-bottom:8px;">Monthly Usage</div>
                <div style="color:#f1f5f9;font-size:0.9rem;margin-bottom:6px;">
                    {used} / {FREE_MONTHLY_LIMIT} analyses used
                </div>
                <div style="background:#334155;border-radius:4px;height:6px;overflow:hidden;">
                    <div style="background:{bar_color};height:100%;width:{pct}%;"></div>
                </div>
                <div style="color:#cbd5e1;font-size:0.75rem;margin-top:6px;">
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
                <div style="color:#cbd5e1;font-size:0.78rem;margin-bottom:4px;">Credit Balance</div>
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


def _render_profile_editor(user: User) -> None:
    with st.expander("Profile Details", expanded=False):
        with st.form("profile_form"):
            display_name = st.text_input(
                "Display name",
                value=user.display_name or "",
                placeholder="How should we refer to you?",
            )
            organization = st.text_input(
                "Organisation",
                value=user.organization or "",
                placeholder="Optional company or team name",
            )
            submitted = st.form_submit_button("Save Profile", use_container_width=True)

        if submitted:
            user.display_name = display_name.strip() or None
            user.organization = organization.strip() or None
            update_user(user)
            st.success("Profile updated.")
            st.rerun()


def _render_analysis_stats(user: User, workspace_id: int | None) -> None:
    stats = get_analysis_stats_for_workspace(user.id, workspace_id) if workspace_id else get_analysis_stats(user.id)
    last_run = stats.get("last_analysis_at") or "No analyses yet"
    if last_run != "No analyses yet":
        last_run = last_run[:16].replace("T", " ")

    st.markdown("**Analysis Activity**")
    col1, col2, col3, col4 = st.columns(4, gap="small")
    cards = [
        ("Total analyses", str(stats["total_runs"])),
        ("This month", str(stats["runs_this_month"])),
        ("Average score", f'{stats["average_score"]:.1f}' if stats["total_runs"] else "—"),
        ("Best score", f'{stats["best_score"]:.1f}' if stats["total_runs"] else "—"),
    ]
    for col, (label, value) in zip((col1, col2, col3, col4), cards):
        with col:
            st.markdown(
                f"""
                <div style="background:#1e293b;border:1px solid #334155;border-radius:8px;
                            padding:0.9rem 1rem;margin-bottom:1rem;">
                    <div style="color:#cbd5e1;font-size:0.76rem;margin-bottom:0.25rem;">{label}</div>
                    <div style="color:#f1f5f9;font-size:1.35rem;font-weight:700;">{value}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown(
        f'<div style="color:#cbd5e1;font-size:0.8rem;margin:-0.35rem 0 1rem;">'
        f'Last analysis: <strong style="color:#f1f5f9;">{last_run}</strong></div>',
        unsafe_allow_html=True,
    )


def _render_recent_analyses(user: User, workspace_id: int | None) -> None:
    rows = get_analysis_history(user.id, limit=5, workspace_id=workspace_id)
    if not rows:
        st.info("No analysis history yet. Run your first project check to build your dashboard history.")
        return

    st.markdown("**Recent Analyses**")
    for row in rows:
        source_name = escape(row.get("source_name") or "Pasted project plan")
        created = (row.get("created_at") or "")[:16].replace("T", " ")
        ai_label = "AI insights" if row.get("llm_enabled") else "Rule-based only"
        findings = row.get("rule_findings_count", 0)
        summary = escape(row.get("summary", ""))
        workspace_name = escape(row.get("workspace_name") or "Personal")
        st.markdown(
            f"""
            <div style="background:#1e293b;border:1px solid #334155;border-radius:8px;
                        padding:0.9rem 1rem;margin-bottom:0.65rem;">
                <div style="display:flex;justify-content:space-between;gap:1rem;align-items:flex-start;">
                    <div>
                        <div style="color:#f1f5f9;font-size:0.92rem;font-weight:600;">{source_name}</div>
                        <div style="color:#cbd5e1;font-size:0.78rem;margin-top:0.15rem;">
                            {created} · {row.get("source_type", "unknown").title()} · {ai_label} · {workspace_name}
                        </div>
                    </div>
                    <div style="text-align:right;">
                        <div style="color:#60a5fa;font-size:1.05rem;font-weight:700;">{row.get("overall_score", 0):.1f}</div>
                        <div style="color:#cbd5e1;font-size:0.75rem;">Grade {row.get("grade", "—")}</div>
                    </div>
                </div>
                <div style="color:#cbd5e1;font-size:0.78rem;margin-top:0.45rem;">
                    {findings} rule findings · {row.get("word_count", 0):,} words
                </div>
                <div style="color:#94a3b8;font-size:0.78rem;margin-top:0.3rem;">{summary}</div>
            </div>
            """,
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

    if st.button("Back to Analyzer", use_container_width=True):
        st.session_state["page"] = "main"
        st.rerun()

    if st.button("View Analysis History", use_container_width=True):
        st.session_state["page"] = "history"
        st.rerun()

    if st.button("Manage Workspaces", use_container_width=True):
        st.session_state["page"] = "workspaces"
        st.rerun()

    if st.button("Privacy and Data", use_container_width=True):
        st.session_state["page"] = "privacy"
        st.rerun()

    if user.tier != Tier.PRO:
        if st.button("Upgrade Plan", use_container_width=True):
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
