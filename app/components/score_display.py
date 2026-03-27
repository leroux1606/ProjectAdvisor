"""
Score Display Component — renders the overall score and per-category breakdown.
Scores are 100% deterministic from rule findings.
"""

from __future__ import annotations

import streamlit as st

from app.pipeline.scoring_engine import ScoreBreakdown


_GRADE_COLORS = {
    "A": "#22c55e",
    "B": "#84cc16",
    "C": "#f59e0b",
    "D": "#f97316",
    "F": "#ef4444",
}

_SCORE_CATEGORIES = [
    ("structure",   "Structure & Completeness"),
    ("consistency", "Internal Consistency"),
    ("timeline",    "Timeline & Scheduling"),
    ("risk",        "Risk Management"),
    ("resource",    "Resource Planning"),
    ("governance",  "Governance & Oversight"),
]


def _score_color(score: float) -> str:
    if score >= 8.0:
        return "#22c55e"
    if score >= 6.0:
        return "#84cc16"
    if score >= 4.0:
        return "#f59e0b"
    if score >= 2.0:
        return "#f97316"
    return "#ef4444"


def _overall_label(score: float) -> str:
    if score >= 8.5:
        return "Excellent — plan is well-structured and comprehensive."
    if score >= 7.0:
        return "Good — plan is solid with minor gaps to address."
    if score >= 5.5:
        return "Adequate — plan has notable weaknesses requiring attention."
    if score >= 4.0:
        return "Weak — significant issues identified across multiple areas."
    return "Poor — plan requires substantial rework before proceeding."


def render_score_header(scores: ScoreBreakdown, llm_enabled: bool = False) -> None:
    grade_color = _GRADE_COLORS.get(scores.grade, "#94a3b8")
    score_color = _score_color(scores.overall)
    mode_badge = (
        '<span style="background:#1e3a5f;color:#93c5fd;border:1px solid #3b82f6;'
        'padding:2px 8px;border-radius:4px;font-size:0.72rem;font-weight:600;">'
        'Rule-based + AI Insights</span>'
        if llm_enabled else
        '<span style="background:#1e293b;color:#94a3b8;border:1px solid #334155;'
        'padding:2px 8px;border-radius:4px;font-size:0.72rem;font-weight:600;">'
        'Rule-based Only</span>'
    )

    st.markdown(
        f"""
        <div style="
            display:flex;align-items:center;gap:2rem;
            padding:1.5rem 2rem;background:#1e293b;
            border-radius:12px;border:1px solid #334155;margin-bottom:1.5rem;
        ">
            <div style="text-align:center;min-width:100px;">
                <div style="font-size:4rem;font-weight:800;color:{score_color};line-height:1;">{scores.overall}</div>
                <div style="color:#94a3b8;font-size:0.85rem;margin-top:4px;">out of 10</div>
            </div>
            <div style="width:2px;height:70px;background:#334155;"></div>
            <div style="text-align:center;min-width:80px;">
                <div style="font-size:3.5rem;font-weight:800;color:{grade_color};line-height:1;">{scores.grade}</div>
                <div style="color:#94a3b8;font-size:0.85rem;margin-top:4px;">Grade</div>
            </div>
            <div style="width:2px;height:70px;background:#334155;"></div>
            <div style="flex:1;">
                <div style="color:#cbd5e1;font-size:1rem;font-weight:600;margin-bottom:0.4rem;">
                    Overall Assessment
                </div>
                <div style="color:#94a3b8;font-size:0.9rem;margin-bottom:0.5rem;">
                    {_overall_label(scores.overall)}
                </div>
                {mode_badge}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_score_breakdown(scores: ScoreBreakdown) -> None:
    st.markdown("#### Score Breakdown")
    st.markdown(
        '<div style="color:#cbd5e1;font-size:0.78rem;margin-bottom:0.75rem;">'
        'Scores are deterministic — computed from rule findings only.</div>',
        unsafe_allow_html=True,
    )

    cols = st.columns(3)
    for idx, (attr, label) in enumerate(_SCORE_CATEGORIES):
        score = getattr(scores, attr)
        color = _score_color(score)
        col = cols[idx % 3]
        with col:
            st.markdown(
                f"""
                <div style="
                    background:#1e293b;border:1px solid #334155;
                    border-radius:8px;padding:1rem;margin-bottom:0.75rem;text-align:center;
                ">
                    <div style="color:#94a3b8;font-size:0.78rem;margin-bottom:6px;">{label}</div>
                    <div style="color:{color};font-size:1.8rem;font-weight:700;">{score}</div>
                    <div style="background:#334155;border-radius:4px;height:4px;margin-top:8px;overflow:hidden;">
                        <div style="background:{color};height:100%;width:{score * 10}%;"></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
