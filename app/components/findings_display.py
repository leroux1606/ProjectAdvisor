"""
Findings Display Component — renders rule-based findings and AI insights per category.
"""

from __future__ import annotations

import streamlit as st

from app.rule_engine.models import AIInsight, CategoryResult, RuleFinding, Severity


_SEVERITY_STYLES: dict[Severity, tuple[str, str]] = {
    Severity.CRITICAL: ("#ef4444", "#450a0a"),
    Severity.HIGH:     ("#f97316", "#431407"),
    Severity.MEDIUM:   ("#f59e0b", "#451a03"),
    Severity.LOW:      ("#3b82f6", "#172554"),
    Severity.INFO:     ("#94a3b8", "#1e293b"),
}

_CATEGORY_ICONS: dict[str, str] = {
    "structure":   "🏗",
    "consistency": "🔗",
    "timeline":    "📅",
    "risk":        "⚠️",
    "resource":    "👥",
    "governance":  "🏛",
}


def _severity_badge(severity: Severity) -> str:
    color, bg = _SEVERITY_STYLES.get(severity, ("#94a3b8", "#1e293b"))
    label = severity.value.upper()
    return (
        f'<span style="background:{bg};color:{color};border:1px solid {color};'
        f'padding:2px 8px;border-radius:4px;font-size:0.72rem;font-weight:700;'
        f'letter-spacing:0.05em;">{label}</span>'
    )


def render_rule_finding(finding: RuleFinding) -> None:
    color, bg = _SEVERITY_STYLES.get(finding.severity, ("#94a3b8", "#1e293b"))
    st.markdown(
        f"""
        <div style="
            background:#1e293b;
            border:1px solid #334155;
            border-left:4px solid {color};
            border-radius:8px;
            padding:1rem 1.2rem;
            margin-bottom:0.75rem;
        ">
            <div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.4rem;">
                {_severity_badge(finding.severity)}
                <span style="color:#f1f5f9;font-weight:600;font-size:0.95rem;">{finding.title}</span>
                <span style="color:#475569;font-size:0.75rem;margin-left:auto;">{finding.rule_id}</span>
            </div>
            <div style="color:#94a3b8;font-size:0.87rem;margin-bottom:0.5rem;">{finding.explanation}</div>
            <div style="background:#0f172a;border-radius:6px;padding:0.6rem 0.8rem;color:#7dd3fc;font-size:0.85rem;">
                <span style="color:#38bdf8;font-weight:600;">Fix: </span>{finding.suggested_fix}
            </div>
            <div style="color:#334155;font-size:0.72rem;margin-top:0.4rem;">
                Rule: <code style="color:#475569;">{finding.rule_name}</code>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_ai_insight(insight: AIInsight) -> None:
    st.markdown(
        f"""
        <div style="
            background:#0f172a;
            border:1px solid #1e3a5f;
            border-left:4px solid #3b82f6;
            border-radius:8px;
            padding:0.9rem 1.2rem;
            margin-bottom:0.6rem;
        ">
            <div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.4rem;">
                <span style="
                    background:#1e3a5f;color:#93c5fd;border:1px solid #3b82f6;
                    padding:2px 8px;border-radius:4px;font-size:0.7rem;font-weight:700;
                ">AI INSIGHT</span>
                <span style="color:#e2e8f0;font-weight:600;font-size:0.92rem;">{insight.title}</span>
            </div>
            <div style="color:#94a3b8;font-size:0.86rem;margin-bottom:0.5rem;">{insight.insight}</div>
            <div style="background:#172554;border-radius:6px;padding:0.5rem 0.8rem;color:#93c5fd;font-size:0.84rem;">
                <span style="color:#60a5fa;font-weight:600;">Suggestion: </span>{insight.suggestion}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_category_result(result: CategoryResult) -> None:
    if not result.rule_findings and not result.ai_insights:
        st.markdown(
            '<div style="color:#4ade80;padding:0.5rem 0;font-size:0.9rem;">✓ No issues found.</div>',
            unsafe_allow_html=True,
        )
        return

    if result.rule_findings:
        critical = result.critical_count
        high = result.high_count
        other = len(result.rule_findings) - critical - high

        parts = []
        if critical:
            parts.append(f'<span style="color:#ef4444">{critical} critical</span>')
        if high:
            parts.append(f'<span style="color:#f97316">{high} high</span>')
        if other:
            parts.append(f'<span style="color:#94a3b8">{other} other</span>')

        st.markdown(
            f'<div style="color:#64748b;font-size:0.8rem;margin-bottom:0.75rem;">'
            f'<strong style="color:#94a3b8">Rule findings:</strong> '
            f'{len(result.rule_findings)} — {" · ".join(parts)}</div>',
            unsafe_allow_html=True,
        )
        for finding in result.rule_findings:
            render_rule_finding(finding)

    if result.ai_insights:
        st.markdown(
            '<div style="color:#64748b;font-size:0.8rem;margin:0.75rem 0 0.5rem;">'
            '<strong style="color:#60a5fa">AI Insights</strong> (supplementary)</div>',
            unsafe_allow_html=True,
        )
        for insight in result.ai_insights:
            render_ai_insight(insight)


def render_all_findings(category_results: list[CategoryResult]) -> None:
    for result in category_results:
        icon = _CATEGORY_ICONS.get(result.category, "•")
        rule_count = len(result.rule_findings)
        ai_count = len(result.ai_insights)

        label = f"{icon} {result.label}"
        if rule_count:
            label += f"  ({rule_count} findings"
            if ai_count:
                label += f" + {ai_count} AI insights"
            label += ")"

        with st.expander(label, expanded=(result.critical_count > 0)):
            render_category_result(result)
