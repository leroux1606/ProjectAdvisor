"""
Recommendations Display Component — renders prioritised, rule-driven recommendations.
Each item shows which rule triggered it for full transparency.
"""

from __future__ import annotations

import streamlit as st

from app.pipeline.report_generator import RecommendationItem
from app.rule_engine.models import Severity


_SEVERITY_COLOR: dict[Severity, str] = {
    Severity.CRITICAL: "#ef4444",
    Severity.HIGH:     "#f97316",
    Severity.MEDIUM:   "#f59e0b",
    Severity.LOW:      "#3b82f6",
    Severity.INFO:     "#94a3b8",
}

_CATEGORY_ICONS: dict[str, str] = {
    "structure":   "🏗",
    "consistency": "🔗",
    "timeline":    "📅",
    "risk":        "⚠️",
    "resource":    "👥",
    "governance":  "🏛",
}


def render_recommendations(recommendations: list[RecommendationItem]) -> None:
    if not recommendations:
        st.info("No recommendations generated.")
        return

    for item in recommendations:
        color = _SEVERITY_COLOR.get(item.severity, "#94a3b8")
        icon = _CATEGORY_ICONS.get(item.category, "•")

        st.markdown(
            f"""
            <div style="
                display:flex;gap:1rem;
                background:#1e293b;border:1px solid #334155;
                border-radius:8px;padding:1rem 1.2rem;margin-bottom:0.6rem;
                align-items:flex-start;
            ">
                <div style="
                    min-width:32px;height:32px;
                    background:{color}22;border:1px solid {color};
                    border-radius:50%;display:flex;align-items:center;
                    justify-content:center;color:{color};
                    font-weight:700;font-size:0.85rem;flex-shrink:0;
                ">{item.priority}</div>
                <div style="flex:1;">
                    <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.3rem;">
                        <span style="font-size:0.9rem;">{icon}</span>
                        <span style="color:#f1f5f9;font-weight:600;font-size:0.92rem;">{item.title}</span>
                        <span style="
                            color:{color};font-size:0.7rem;font-weight:600;
                            background:{color}22;padding:1px 6px;border-radius:3px;
                            margin-left:auto;
                        ">{item.severity.value.upper()}</span>
                    </div>
                    <div style="color:#94a3b8;font-size:0.87rem;margin-bottom:0.4rem;">{item.action}</div>
                    <div style="color:#334155;font-size:0.72rem;">
                        Triggered by rule: <code style="color:#475569;">{item.rule_id} · {item.rule_name}</code>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
