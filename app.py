"""
Project Plan Scrutinizer — Streamlit UI Entry Point
Hybrid engine: deterministic rules (primary) + LLM insights (secondary, optional).
Auth gate: login required. Freemium + credits + subscription via Stripe.
"""

from __future__ import annotations

from html import escape
import os

import streamlit as st

from app.auth.db import get_workspace, init_db, record_analysis_run
from app.auth.models import Tier
from app.auth.service import AuthError, consume_analysis
from app.auth.session import get_active_workspace_id, get_current_user, init, is_authenticated
from app.components.auth_page import render_auth_page
from app.components.dashboard_page import render_dashboard
from app.components.findings_display import render_all_findings
from app.components.history_page import render_history_page
from app.components.privacy_page import render_privacy_page
from app.components.pricing_page import render_pricing_page
from app.components.recommendations_display import render_recommendations
from app.components.score_display import render_score_breakdown, render_score_header
from app.components.top_issues import render_top_issues
from app.components.workspace_page import render_workspace_page
from app.pipeline.orchestrator import PipelineError, run_pipeline
from app.pipeline.report_generator import AuditReport, report_to_json, report_to_markdown
from app.utils.pdf_export import text_to_pdf_bytes

st.set_page_config(
    page_title="Project Plan Scrutinizer",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .stApp { background-color: #0f172a; color: #e2e8f0; }
    .stApp header { background-color: #0f172a; }
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    .stTextArea label, .stFileUploader label, .stToggle label {
        color: #e2e8f0 !important;
        font-weight: 600 !important;
    }
    .streamlit-expanderHeader {
        background-color: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
        color: #e2e8f0 !important;
        font-weight: 600 !important;
    }
    .streamlit-expanderContent {
        background-color: #0f172a !important;
        border: 1px solid #334155 !important;
        border-top: none !important;
    }
    .stButton > button {
        background: #1d4ed8; color: white; border: none;
        border-radius: 8px; padding: 0.6rem 2rem;
        font-size: 1rem; font-weight: 600; width: 100%;
    }
    .stButton > button:hover { background: #1e40af; }
    .stTabs [data-baseweb="tab-list"] { background: #1e293b; border-radius: 8px; padding: 4px; }
    .stTabs [data-baseweb="tab"] { color: #cbd5e1; border-radius: 6px; }
    .stTabs [aria-selected="true"] { background: #334155 !important; color: #f1f5f9 !important; }
    .stTextArea textarea {
        background: #1e293b; color: #e2e8f0; border: 1px solid #475569;
        caret-color: #f8fafc !important;
    }
    .stTextArea textarea::placeholder { color: #94a3b8 !important; opacity: 1 !important; }
    .stTextArea textarea::selection,
    .stTextInput input::selection {
        background: #2563eb !important;
        color: #ffffff !important;
    }
    .stFileUploader { background: #1e293b; border: 1px dashed #334155; border-radius: 8px; }
    .stButton > button:focus-visible,
    .stTextArea textarea:focus-visible,
    .stTextInput input:focus-visible,
    .stFileUploader [role="button"]:focus-visible,
    .stTabs [data-baseweb="tab"]:focus-visible,
    .stToggle input:focus-visible + div {
        outline: 3px solid #f8fafc !important;
        outline-offset: 2px !important;
        box-shadow: 0 0 0 2px #1d4ed8 !important;
    }
    hr { border-color: #1e293b; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Bootstrap ─────────────────────────────────────────────────────────────────
init_db()
init()

# ── Page routing ──────────────────────────────────────────────────────────────
if not is_authenticated():
    render_auth_page()
    st.stop()

user = get_current_user()
if user is None:
    render_auth_page()
    st.stop()

# Handle post-payment redirect from Stripe
query_params = st.query_params
payment_status = query_params.get("payment")
if payment_status == "success":
    st.success("Payment successful! Your account has been updated.")
    st.query_params.clear()
elif payment_status == "cancelled":
    st.info("Payment cancelled — no charge was made.")
    st.query_params.clear()

# Page state
page = st.session_state.get("page", "main")

if page == "dashboard":
    render_dashboard(user)
    st.stop()

if page == "history":
    render_history_page(user)
    if st.button("Back to Analyzer", key="back_from_history"):
        st.session_state["page"] = "main"
        st.rerun()
    st.stop()

if page == "privacy":
    render_privacy_page(user)
    if st.button("Back to Analyzer", key="back_from_privacy"):
        st.session_state["page"] = "main"
        st.rerun()
    st.stop()

if page == "workspaces":
    render_workspace_page(user)
    if st.button("Back to Analyzer", key="back_from_workspaces"):
        st.session_state["page"] = "main"
        st.rerun()
    st.stop()

if page == "pricing":
    render_pricing_page(user)
    if st.button("← Back", key="back_from_pricing"):
        st.session_state["page"] = "main"
        st.rerun()
    st.stop()

# ── Main App ──────────────────────────────────────────────────────────────────

# Header
active_workspace_id = get_active_workspace_id()
active_workspace = get_workspace(active_workspace_id) if active_workspace_id else None
header_col, nav_col = st.columns([4, 2], gap="medium")
with header_col:
    st.markdown(
        """
        <div style="margin-bottom:1.5rem;">
            <h1 style="color:#f1f5f9;font-size:1.8rem;font-weight:800;margin-bottom:0.25rem;">
                Project Plan Scrutinizer
            </h1>
            <p style="color:#cbd5e1;font-size:0.92rem;margin:0;">
                Hybrid audit engine · Deterministic rules (primary) + AI insights (secondary)
                · PRINCE2 &amp; PMBOK aligned
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
with nav_col:
    account_label = escape(user.display_name or user.email)
    workspace_label = escape(active_workspace["name"]) if active_workspace else "Personal workspace"
    st.markdown(
        f'<div style="color:#cbd5e1;font-size:0.82rem;text-align:right;margin-bottom:0.45rem;">'
        f'Signed in as <strong style="color:#f1f5f9;">{account_label}</strong></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="color:#94a3b8;font-size:0.78rem;text-align:right;margin-bottom:0.45rem;">'
        f'Workspace: <strong style="color:#cbd5e1;">{workspace_label}</strong></div>',
        unsafe_allow_html=True,
    )
    nav_a, nav_b, nav_c, nav_d = st.columns(4, gap="small")
    with nav_a:
        if st.button("Analysis History", use_container_width=True):
            st.session_state["page"] = "history"
            st.rerun()
    with nav_b:
        if st.button("My Account", use_container_width=True):
            st.session_state["page"] = "dashboard"
            st.rerun()
    with nav_c:
        if st.button("Privacy", use_container_width=True):
            st.session_state["page"] = "privacy"
            st.rerun()
    with nav_d:
        if st.button("Workspaces", use_container_width=True):
            st.session_state["page"] = "workspaces"
            st.rerun()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Account")
    st.markdown(
        f'<div style="color:#94a3b8;font-size:0.82rem;margin-bottom:0.5rem;">{escape(user.display_name or user.email)}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="color:#cbd5e1;font-size:0.8rem;margin-bottom:1rem;">{user.access_label()}</div>',
        unsafe_allow_html=True,
    )

    col_dash, col_priv = st.columns(2)
    with col_dash:
        if st.button("My Account", use_container_width=True):
            st.session_state["page"] = "dashboard"
            st.rerun()
    with col_priv:
        if st.button("Privacy", use_container_width=True):
            st.session_state["page"] = "privacy"
            st.rerun()

    if st.button("Workspaces", use_container_width=True):
        st.session_state["page"] = "workspaces"
        st.rerun()

    if user.tier != Tier.PRO:
        if st.button("Upgrade Plan", use_container_width=True):
            st.session_state["page"] = "pricing"
            st.rerun()

    st.markdown("---")
    st.markdown("### Settings")

    llm_available = bool(os.getenv("OPENAI_API_KEY"))
    if llm_available:
        enable_llm = st.toggle("Enable AI Insights", value=True, help=(
            "LLM adds soft quality insights on top of rule findings. "
            "Rule-based scores are unaffected."
        ))
        st.markdown(
            '<div style="color:#4ade80;font-size:0.8rem;">✓ OpenAI API key detected</div>',
            unsafe_allow_html=True,
        )
    else:
        enable_llm = False
        st.markdown(
            '<div style="color:#f59e0b;font-size:0.8rem;">⚠ No API key — deterministic mode</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown(
        """
        <div style="color:#cbd5e1;font-size:0.78rem;">
        <strong style="color:#f1f5f9;">Scoring weights</strong><br>
        Structure: 25% &nbsp;|&nbsp; Timeline: 20%<br>
        Risk: 20% &nbsp;|&nbsp; Consistency: 15%<br>
        Resource: 12% &nbsp;|&nbsp; Governance: 8%<br>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ── Access check banner ───────────────────────────────────────────────────────
if not user.can_analyse():
    st.warning(
        "You have used all your free analyses this month. "
        "Upgrade to continue.",
        icon="⚠️",
    )
    render_pricing_page(user)
    st.stop()

# ── Input ─────────────────────────────────────────────────────────────────────
st.markdown("### Submit Project Plan")

input_tab, upload_tab = st.tabs(["📝 Paste Text", "📁 Upload File"])

text_input: str = ""
uploaded_filename: str | None = None
uploaded_bytes: bytes | None = None

with input_tab:
    st.markdown(
        '<div style="color:#cbd5e1;font-size:0.84rem;margin-bottom:0.5rem;">'
        "Paste the full project plan text. Include objectives, scope, deliverables, "
        "timeline, resources, risks, and governance where possible."
        "</div>",
        unsafe_allow_html=True,
    )
    text_input = st.text_area(
        label="Paste project plan text",
        placeholder=(
            "Paste the full project plan — objectives, scope, deliverables, "
            "timeline, resources, risks, governance..."
        ),
        height=280,
    )

with upload_tab:
    st.markdown(
        '<div style="color:#cbd5e1;font-size:0.84rem;margin-bottom:0.5rem;">'
        "Accepted file types: PDF, DOCX, TXT, and MD."
        "</div>",
        unsafe_allow_html=True,
    )
    uploaded_file = st.file_uploader(
        "Upload a project plan file",
        type=["pdf", "docx", "txt", "md"],
    )
    if uploaded_file:
        uploaded_filename = uploaded_file.name
        uploaded_bytes = uploaded_file.read()
        st.success(f"Loaded: **{uploaded_filename}** ({len(uploaded_bytes):,} bytes)")

st.markdown("<br>", unsafe_allow_html=True)
analyze_clicked = st.button("Analyze Project Plan", use_container_width=True)

# ── Analysis ──────────────────────────────────────────────────────────────────
if analyze_clicked:
    has_file = uploaded_bytes is not None and uploaded_filename is not None
    has_text = bool(text_input and text_input.strip())

    if not has_file and not has_text:
        st.error("Please paste a project plan or upload a file before analysing.")
        st.stop()

    # Access check — consume one unit before running (atomic check+deduct)
    try:
        consume_analysis(user)
    except AuthError as exc:
        st.error(str(exc))
        st.session_state["page"] = "pricing"
        st.rerun()

    progress_bar = st.progress(0)
    status_text = st.empty()

    def update_progress(stage: str, pct: int) -> None:
        progress_bar.progress(pct)
        status_text.markdown(
            f'<div style="color:#94a3b8;font-size:0.85rem;">⚙ {stage}...</div>',
            unsafe_allow_html=True,
        )

    try:
        report: AuditReport = run_pipeline(
            text=text_input if has_text and not has_file else None,
            filename=uploaded_filename,
            file_bytes=uploaded_bytes,
            enable_llm=enable_llm,
            progress_callback=update_progress,
        )
    except PipelineError as exc:
        progress_bar.empty()
        status_text.empty()
        st.error(f"Analysis failed: {exc}")
        st.stop()
    except Exception as exc:
        progress_bar.empty()
        status_text.empty()
        st.error(f"Unexpected error: {exc}")
        st.stop()

    progress_bar.empty()
    status_text.empty()
    st.session_state["report"] = report
    total_findings = sum(len(r.rule_findings) for r in report.category_results)
    summary = ", ".join(issue.title for issue in report.top_issues[:2]) or "Analysis completed successfully."
    record_analysis_run(
        user_id=user.id,
        workspace_id=active_workspace_id,
        source_name=report.source_name,
        source_type="upload" if has_file else "text",
        overall_score=report.overall_score,
        grade=report.grade,
        word_count=report.word_count,
        sections_found_count=len(report.sections_found),
        rule_findings_count=total_findings,
        ai_insights_count=len(report.ai_insights),
        llm_enabled=report.llm_enabled,
        summary=summary,
        report_json=report_to_json(report),
    )

# ── Report ────────────────────────────────────────────────────────────────────
if "report" in st.session_state:
    report: AuditReport = st.session_state["report"]
    escaped_source_name = escape(report.source_name) if report.source_name else ""

    st.markdown("---")

    col_title, col_meta = st.columns([3, 2])
    with col_title:
        st.markdown(
            '<h2 style="color:#f1f5f9;font-size:1.3rem;font-weight:700;margin:0;">Audit Report</h2>',
            unsafe_allow_html=True,
        )
    with col_meta:
        st.markdown(
            f'<div style="color:#475569;font-size:0.8rem;text-align:right;">'
            f'{report.generated_at}'
            f'{"&nbsp;· " + escaped_source_name if report.source_name else ""}'
            f'&nbsp;· {report.word_count:,} words'
            f'</div>',
            unsafe_allow_html=True,
        )

    export_col, clear_col = st.columns([1, 1])
    with export_col:
        markdown_report = report_to_markdown(report)
        st.download_button(
            "Download This Report",
            data=markdown_report,
            file_name=f"{(report.source_name or 'project-plan-report').replace(' ', '-').lower()}.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with clear_col:
        if st.button("Clear Current Report", use_container_width=True):
            st.session_state.pop("report", None)
            st.rerun()
    st.download_button(
        "Download Report as PDF",
        data=text_to_pdf_bytes(markdown_report, title=report.source_name or "Project Plan Scrutinizer Report"),
        file_name=f"{(report.source_name or 'project-plan-report').replace(' ', '-').lower()}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)
    render_score_header(report.score_breakdown, llm_enabled=report.llm_enabled)

    col_summary, col_scores = st.columns([1, 1], gap="large")

    with col_summary:
        st.markdown("#### Summary")

        if report.sections_found:
            found_html = " ".join(
                f'<span style="background:#166534;color:#86efac;padding:2px 8px;'
                f'border-radius:4px;font-size:0.78rem;margin:2px;">{s}</span>'
                for s in report.sections_found
            )
            st.markdown(
                f'<div style="margin-bottom:0.5rem;"><span style="color:#64748b;font-size:0.82rem;">Sections detected: </span>{found_html}</div>',
                unsafe_allow_html=True,
            )

        if report.sections_missing:
            missing_html = " ".join(
                f'<span style="background:#450a0a;color:#fca5a5;padding:2px 8px;'
                f'border-radius:4px;font-size:0.78rem;margin:2px;">{s}</span>'
                for s in report.sections_missing
            )
            st.markdown(
                f'<div style="margin-bottom:1rem;"><span style="color:#64748b;font-size:0.82rem;">Missing sections: </span>{missing_html}</div>',
                unsafe_allow_html=True,
            )

        total_findings = sum(len(r.rule_findings) for r in report.category_results)
        total_ai = len(report.ai_insights)
        st.markdown(
            f'<div style="color:#64748b;font-size:0.82rem;margin-bottom:0.75rem;">'
            f'<strong style="color:#94a3b8">{total_findings}</strong> rule findings &nbsp;·&nbsp; '
            f'<strong style="color:#60a5fa">{total_ai}</strong> AI insights</div>',
            unsafe_allow_html=True,
        )

        st.markdown("**Top Issues** (by severity)")
        render_top_issues(report.top_issues)

    with col_scores:
        render_score_breakdown(report.score_breakdown)

    st.markdown("---")
    st.markdown("### Detailed Findings")
    st.markdown(
        '<div style="color:#64748b;font-size:0.83rem;margin-bottom:1rem;">'
        'Rule findings are deterministic — each shows the rule ID and name that triggered it. '
        'AI insights (if present) are supplementary and do not affect scores.</div>',
        unsafe_allow_html=True,
    )
    render_all_findings(report.category_results)

    st.markdown("---")
    st.markdown("### Recommendations")
    st.markdown(
        '<div style="color:#64748b;font-size:0.83rem;margin-bottom:1rem;">'
        'Prioritised by severity. Each recommendation is traceable to its triggering rule.</div>',
        unsafe_allow_html=True,
    )
    render_recommendations(report.recommendations)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<div style="color:#334155;font-size:0.75rem;text-align:center;">'
        'Project Plan Scrutinizer · Hybrid rule + AI engine · PRINCE2 &amp; PMBOK aligned · '
        'All findings should be reviewed by a qualified project manager.'
        '</div>',
        unsafe_allow_html=True,
    )
