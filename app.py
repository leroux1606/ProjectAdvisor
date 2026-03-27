"""
Project Plan Scrutinizer — Streamlit UI Entry Point
"""

from __future__ import annotations

import streamlit as st

from app.components.findings_display import render_all_findings
from app.components.recommendations_display import render_recommendations
from app.components.score_display import render_score_breakdown, render_score_header
from app.components.top_issues import render_top_issues
from app.pipeline.orchestrator import PipelineError, run_pipeline
from app.pipeline.report_generator import AuditReport

st.set_page_config(
    page_title="Project Plan Scrutinizer",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global styles ─────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* Dark background */
    .stApp { background-color: #0f172a; color: #e2e8f0; }
    .stApp header { background-color: #0f172a; }

    /* Remove default Streamlit padding */
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }

    /* Expander styling */
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

    /* Button */
    .stButton > button {
        background: #3b82f6;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.6rem 2rem;
        font-size: 1rem;
        font-weight: 600;
        width: 100%;
        transition: background 0.2s;
    }
    .stButton > button:hover { background: #2563eb; }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { background: #1e293b; border-radius: 8px; padding: 4px; }
    .stTabs [data-baseweb="tab"] { color: #94a3b8; border-radius: 6px; }
    .stTabs [aria-selected="true"] { background: #334155 !important; color: #f1f5f9 !important; }

    /* Text area / file uploader */
    .stTextArea textarea { background: #1e293b; color: #e2e8f0; border: 1px solid #334155; }
    .stFileUploader { background: #1e293b; border: 1px dashed #334155; border-radius: 8px; }

    /* Divider */
    hr { border-color: #1e293b; }

    /* Info / warning boxes */
    .stAlert { border-radius: 8px; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div style="margin-bottom: 2rem;">
        <h1 style="
            color: #f1f5f9;
            font-size: 1.8rem;
            font-weight: 800;
            margin-bottom: 0.25rem;
        ">🔍 Project Plan Scrutinizer</h1>
        <p style="color: #64748b; font-size: 0.95rem; margin: 0;">
            Structured audit tool — PRINCE2 &amp; PMBOK aligned · Not a chatbot
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ── Input Section ─────────────────────────────────────────────────────────────
st.markdown("### Submit Project Plan")

input_tab, upload_tab = st.tabs(["📝 Paste Text", "📁 Upload File"])

text_input: str = ""
uploaded_filename: str | None = None
uploaded_bytes: bytes | None = None

with input_tab:
    text_input = st.text_area(
        label="Paste your project plan here",
        placeholder=(
            "Paste the full project plan text — objectives, scope, deliverables, "
            "timeline, resources, risks, governance..."
        ),
        height=280,
        label_visibility="collapsed",
    )

with upload_tab:
    uploaded_file = st.file_uploader(
        "Upload project plan document",
        type=["pdf", "docx", "txt", "md"],
        label_visibility="collapsed",
    )
    if uploaded_file:
        uploaded_filename = uploaded_file.name
        uploaded_bytes = uploaded_file.read()
        st.success(f"Loaded: **{uploaded_filename}** ({len(uploaded_bytes):,} bytes)")

st.markdown("<br>", unsafe_allow_html=True)
analyze_clicked = st.button("🔍 Analyse Project Plan", use_container_width=True)


# ── Analysis ──────────────────────────────────────────────────────────────────
if analyze_clicked:
    has_file = uploaded_bytes is not None and uploaded_filename is not None
    has_text = bool(text_input and text_input.strip())

    if not has_file and not has_text:
        st.error("Please paste a project plan or upload a file before analysing.")
        st.stop()

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

    # ── Store in session state so report persists across reruns ──────────────
    st.session_state["report"] = report


# ── Report Display ────────────────────────────────────────────────────────────
if "report" in st.session_state:
    report: AuditReport = st.session_state["report"]

    st.markdown("---")
    st.markdown(
        f"""
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;">
            <h2 style="color:#f1f5f9;font-size:1.3rem;font-weight:700;margin:0;">
                Audit Report
            </h2>
            <div style="color:#475569;font-size:0.8rem;">
                {report.generated_at}
                {"· " + report.source_name if report.source_name else ""}
                · {report.word_count:,} words
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Score header
    render_score_header(report.score_breakdown)

    # Two-column layout: summary left, score breakdown right
    col_summary, col_scores = st.columns([1, 1], gap="large")

    with col_summary:
        st.markdown("#### Summary")

        # Sections detected
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

        st.markdown("**Top Issues**")
        render_top_issues(report.top_issues)

    with col_scores:
        render_score_breakdown(report.score_breakdown)

    st.markdown("---")

    # Findings
    st.markdown("### Detailed Findings")
    render_all_findings(report.findings_groups)

    st.markdown("---")

    # Recommendations
    st.markdown("### Recommendations")
    st.markdown(
        '<div style="color:#64748b;font-size:0.85rem;margin-bottom:1rem;">'
        'Prioritised by severity — address items in order.</div>',
        unsafe_allow_html=True,
    )
    render_recommendations(report.recommendations)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<div style="color:#334155;font-size:0.75rem;text-align:center;">'
        'Project Plan Scrutinizer · PRINCE2 &amp; PMBOK aligned · '
        'All findings are AI-generated and should be reviewed by a qualified project manager.'
        '</div>',
        unsafe_allow_html=True,
    )
