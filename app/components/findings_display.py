"""
Findings Display Component — renders grouped findings with severity badges.
"""

from __future__ import annotations

import streamlit as st

from app.analysis.models import Finding, Severity
from app.pipeline.report_generator import FindingsGroup


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
        f'<span style="'
        f'background:{bg};color:{color};border:1px solid {color};'
        f'padding:2px 8px;border-radius:4px;font-size:0.72rem;font-weight:700;'
        f'letter-spacing:0.05em;">{label}</span>'
    )


def render_finding_card(finding: Finding) -> None:
    color, bg = _SEVERITY_STYLES.get(finding.severity, ("#94a3b8", "#1e293b"))
    st.markdown(
        f"""
        <div style="
            background: #1e293b;
            border: 1px solid #334155;
            border-left: 4px solid {color};
            border-radius: 8px;
            padding: 1rem 1.2rem;
            margin-bottom: 0.75rem;
        ">
            <div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.5rem;">
                {_severity_badge(finding.severity)}
                <span style="color:#f1f5f9;font-weight:600;font-size:0.95rem;">{finding.title}</span>
                <span style="color:#475569;font-size:0.78rem;margin-left:auto;">{finding.id}</span>
            </div>
            <div style="color:#94a3b8;font-size:0.88rem;margin-bottom:0.5rem;">{finding.description}</div>
            <div style="
                background:#0f172a;
                border-radius:6px;
                padding:0.6rem 0.8rem;
                color:#7dd3fc;
                font-size:0.85rem;
            ">
                <span style="color:#38bdf8;font-weight:600;">Recommendation: </span>{finding.recommendation}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_findings_group(group: FindingsGroup) -> None:
    if not group.findings:
        st.markdown(
            '<div style="color:#4ade80;padding:0.5rem 0;font-size:0.9rem;">✓ No issues found in this category.</div>',
            unsafe_allow_html=True,
        )
        return

    icon = _CATEGORY_ICONS.get(group.category, "•")
    critical = group.critical_count
    high = group.high_count

    summary_parts = []
    if critical:
        summary_parts.append(f'<span style="color:#ef4444">{critical} critical</span>')
    if high:
        summary_parts.append(f'<span style="color:#f97316">{high} high</span>')
    remaining = len(group.findings) - critical - high
    if remaining:
        summary_parts.append(f'<span style="color:#94a3b8">{remaining} other</span>')

    summary_html = " · ".join(summary_parts) if summary_parts else ""

    st.markdown(
        f'<div style="color:#64748b;font-size:0.82rem;margin-bottom:0.75rem;">'
        f'{len(group.findings)} finding(s) — {summary_html}</div>',
        unsafe_allow_html=True,
    )

    for finding in group.findings:
        render_finding_card(finding)


def render_all_findings(groups: list[FindingsGroup]) -> None:
    for group in groups:
        icon = _CATEGORY_ICONS.get(group.category, "•")
        count = len(group.findings)
        label = f"{icon} {group.label}"
        if count:
            label += f"  ({count})"

        with st.expander(label, expanded=(group.critical_count > 0)):
            render_findings_group(group)
