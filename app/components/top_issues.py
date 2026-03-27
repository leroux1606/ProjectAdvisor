"""
Top Issues Component — renders the top 5 rule-based findings in the summary panel.
"""

from __future__ import annotations

from html import escape

import streamlit as st

from app.rule_engine.models import RuleFinding, Severity


_SEVERITY_COLOR: dict[Severity, str] = {
    Severity.CRITICAL: "#ef4444",
    Severity.HIGH:     "#f97316",
    Severity.MEDIUM:   "#f59e0b",
    Severity.LOW:      "#3b82f6",
    Severity.INFO:     "#94a3b8",
}


def render_top_issues(findings: list[RuleFinding]) -> None:
    if not findings:
        st.markdown(
            '<div style="color:#4ade80;font-size:0.9rem;">✓ No critical or high-severity issues found.</div>',
            unsafe_allow_html=True,
        )
        return

    for finding in findings:
        color = _SEVERITY_COLOR.get(finding.severity, "#94a3b8")
        title = escape(finding.title)
        rule_meta = escape(f"{finding.rule_id} · {finding.severity.value.upper()} · {finding.rule_name}")
        st.markdown(
            f"""
            <div style="
                display:flex;align-items:flex-start;gap:0.75rem;
                padding:0.65rem 0;border-bottom:1px solid #1e293b;
            ">
                <div style="
                    width:8px;height:8px;border-radius:50%;
                    background:{color};margin-top:6px;flex-shrink:0;
                "></div>
                <div>
                    <div style="color:#f1f5f9;font-size:0.9rem;font-weight:500;">{title}</div>
                    <div style="color:#cbd5e1;font-size:0.76rem;margin-top:2px;">
                        {rule_meta}
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
