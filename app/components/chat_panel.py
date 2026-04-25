"""
Chat Panel — conversational assistant scoped to the loaded plan + report.

Renders below the report when one is loaded. Uses Streamlit's built-in
`st.chat_message` and `st.chat_input` primitives, which escape content for us.
History is persisted in `chat_messages` keyed by analysis_run_id.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

from app.auth.db import (
    append_chat_message,
    clear_chat_messages,
    get_chat_messages,
)
from app.auth.models import User
from app.llm import budget as llm_budget
from app.llm.chat_service import ChatError, chat_turn
from app.llm.openrouter import llm_available
from app.pipeline.report_generator import AuditReport


def render_chat_panel(
    user: User,
    plan_text: Optional[str],
    report: Optional[AuditReport],
    analysis_run_id: Optional[int],
) -> None:
    if report is None or not plan_text:
        return

    st.markdown("---")
    st.markdown("### Ask the assistant")

    if not llm_available():
        st.info(
            "AI chat requires an LLM provider. Add OPENROUTER_API_KEY to your "
            ".env file to enable this feature."
        )
        return

    status = llm_budget.get_status(user)
    if status.remaining <= 0:
        st.warning(
            f"Monthly AI token budget reached "
            f"({status.used:,}/{status.monthly_limit:,}). "
            "The chat will resume when your usage resets."
        )
        # Still render history below for review.

    st.markdown(
        '<div style="color:#94a3b8;font-size:0.78rem;margin-bottom:0.5rem;">'
        "Ask about the plan, request explanations of findings, or get a summary. "
        "The assistant cannot modify the plan or the score — those remain deterministic."
        "</div>",
        unsafe_allow_html=True,
    )

    history = get_chat_messages(user.id, analysis_run_id)

    # Render existing history.
    for row in history:
        role = row["role"]
        if role not in ("user", "assistant"):
            continue
        with st.chat_message(role):
            st.markdown(row["content"])

    # Optional: clear-history control.
    if history:
        if st.button("Clear conversation", key=f"clear_chat_{analysis_run_id or 'session'}"):
            clear_chat_messages(user.id, analysis_run_id)
            st.rerun()

    user_message = st.chat_input(
        "Ask about this plan…",
        disabled=status.remaining <= 0,
        key=f"chat_input_{analysis_run_id or 'session'}",
    )

    if not user_message:
        return

    # Show the user message immediately.
    with st.chat_message("user"):
        st.markdown(user_message)

    # Build history payload for the service.
    history_payload = [
        {"role": row["role"], "content": row["content"]}
        for row in history
        if row["role"] in ("user", "assistant")
    ]

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                result = chat_turn(
                    user=user,
                    analysis_run_id=analysis_run_id,
                    plan_text=plan_text,
                    report=report,
                    history=history_payload,
                    user_message=user_message,
                )
            except llm_budget.BudgetExceeded as exc:
                # Persist the user message so it's not lost.
                append_chat_message(
                    user_id=user.id,
                    analysis_run_id=analysis_run_id,
                    role="user",
                    content=user_message,
                )
                st.error(str(exc))
                return
            except ChatError as exc:
                st.error(str(exc))
                return
            except Exception as exc:
                st.error(f"Chat failed: {exc}")
                return
        st.markdown(result.reply)

    # Force a rerun so the new history is shown via the standard render path
    # on the next pass (avoids duplicating the just-shown message).
    st.rerun()
