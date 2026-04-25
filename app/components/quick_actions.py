"""
Quick Actions Panel — button-driven write verbs for the loaded plan.

Each verb produces a *proposal*: the model's revised plan text. The user
sees a diff and explicitly accepts before any state changes. On accept,
the plan is replaced in session_state and the audit pipeline is re-run
against the new text.
"""

from __future__ import annotations

import difflib
from html import escape
from typing import Callable, Optional

import streamlit as st

from app.auth.db import record_analysis_run
from app.auth.models import User
from app.auth.session import get_active_workspace_id
from app.llm import budget as llm_budget
from app.llm.openrouter import llm_available
from app.llm.verbs import (
    ALLOWED_SECTIONS,
    VerbError,
    VerbProposal,
    add_section,
    regenerate_timeline,
    rewrite_section,
)
from app.pipeline.orchestrator import PipelineError, run_pipeline_full
from app.pipeline.report_generator import (
    AuditReport,
    report_to_json,
)


_PROPOSAL_KEY = "verb_proposal"
_VERB_LABELS = {
    "rewrite_section": "Rewrite a section",
    "add_section": "Add or expand a section",
    "regenerate_timeline": "Regenerate timeline",
}


def render_quick_actions(
    user: User,
    plan_text: Optional[str],
    report: Optional[AuditReport],
) -> None:
    if report is None or not plan_text:
        return
    if not llm_available():
        return

    st.markdown("---")
    st.markdown("### Quick Actions")
    st.markdown(
        '<div style="color:#94a3b8;font-size:0.78rem;margin-bottom:0.6rem;">'
        "Ask the AI to revise a section. You'll see the change as a diff and "
        "can accept or reject it before anything is overwritten. Accepted "
        "changes are scored by the deterministic audit, not the AI."
        "</div>",
        unsafe_allow_html=True,
    )

    proposal: Optional[VerbProposal] = st.session_state.get(_PROPOSAL_KEY)

    if proposal is None:
        _render_action_form(user, plan_text)
    else:
        _render_proposal_diff(user, plan_text, report, proposal)


def _render_action_form(user: User, plan_text: str) -> None:
    col_verb, col_section = st.columns([2, 2], gap="small")

    with col_verb:
        verb = st.selectbox(
            "Action",
            options=list(_VERB_LABELS.keys()),
            format_func=lambda v: _VERB_LABELS[v],
            key="verb_selector",
        )

    with col_section:
        if verb == "regenerate_timeline":
            section = "Timeline"
            st.text_input(
                "Section",
                value="Timeline",
                disabled=True,
                key="verb_section_locked",
            )
        else:
            section = st.selectbox(
                "Section",
                options=ALLOWED_SECTIONS,
                key="verb_section_selector",
            )

    instructions = st.text_area(
        "Instructions (optional)",
        placeholder=(
            "e.g. Tighten phasing, add quarterly milestones for 2026, and "
            "name the project sponsor as Jane Doe."
        ),
        height=80,
        key="verb_instructions",
    )

    status = llm_budget.get_status(user)
    if status.remaining <= 0:
        st.warning(
            f"Monthly AI token budget reached "
            f"({status.used:,}/{status.monthly_limit:,}). "
            "Quick Actions are disabled until your usage resets."
        )

    generate_clicked = st.button(
        "Generate proposal",
        use_container_width=True,
        disabled=status.remaining <= 0,
        key="verb_generate_btn",
    )

    if not generate_clicked:
        return

    handler: Callable[[], VerbProposal]
    if verb == "rewrite_section":
        handler = lambda: rewrite_section(user, plan_text, section, instructions)
    elif verb == "add_section":
        handler = lambda: add_section(user, plan_text, section, instructions)
    elif verb == "regenerate_timeline":
        handler = lambda: regenerate_timeline(user, plan_text, instructions)
    else:
        st.error(f"Unknown action: {verb}")
        return

    with st.spinner("Drafting proposal…"):
        try:
            proposal = handler()
        except llm_budget.BudgetExceeded as exc:
            st.error(str(exc))
            return
        except VerbError as exc:
            st.error(str(exc))
            return
        except Exception as exc:
            st.error(f"Action failed: {exc}")
            return

    st.session_state[_PROPOSAL_KEY] = proposal
    st.rerun()


def _render_proposal_diff(
    user: User,
    plan_text: str,
    report: AuditReport,
    proposal: VerbProposal,
) -> None:
    label = _VERB_LABELS.get(proposal.verb.value, proposal.verb.value)
    section_label = escape(proposal.section or "—")
    st.markdown(
        f'<div style="background:#1e293b;border:1px solid #334155;border-radius:8px;'
        f'padding:0.75rem 1rem;margin-bottom:0.6rem;">'
        f'<div style="color:#cbd5e1;font-size:0.78rem;">Proposal</div>'
        f'<div style="color:#f1f5f9;font-size:0.95rem;font-weight:600;">'
        f'{escape(label)} · {section_label}</div>'
        f'<div style="color:#94a3b8;font-size:0.76rem;margin-top:0.25rem;">'
        f'{proposal.completion_tokens:,} tokens · model {escape(proposal.model)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if proposal.instructions:
        st.markdown(
            f'<div style="color:#cbd5e1;font-size:0.8rem;margin-bottom:0.5rem;">'
            f'Instructions: <em>{escape(proposal.instructions)}</em></div>',
            unsafe_allow_html=True,
        )

    diff_lines = list(difflib.unified_diff(
        plan_text.splitlines(),
        proposal.proposed_plan_text.splitlines(),
        fromfile="current",
        tofile="proposed",
        lineterm="",
        n=3,
    ))
    if not diff_lines:
        st.info("The model returned the plan unchanged. You can reject and try different instructions.")
    else:
        st.markdown("**Diff (current → proposed):**")
        st.code("\n".join(diff_lines), language="diff")

    with st.expander("Show full proposed plan"):
        st.markdown(proposal.proposed_plan_text)

    col_accept, col_reject = st.columns(2)
    with col_accept:
        accept_clicked = st.button(
            "Accept and re-audit",
            use_container_width=True,
            type="primary",
            key="verb_accept_btn",
            disabled=not diff_lines,
        )
    with col_reject:
        reject_clicked = st.button(
            "Reject",
            use_container_width=True,
            key="verb_reject_btn",
        )

    if reject_clicked:
        st.session_state.pop(_PROPOSAL_KEY, None)
        st.rerun()

    if accept_clicked:
        _accept_proposal(user, report, proposal)


def _accept_proposal(user: User, report: AuditReport, proposal: VerbProposal) -> None:
    """Replace plan + report with the accepted proposal and re-run the audit."""
    with st.spinner("Re-running audit on the revised plan…"):
        try:
            result = run_pipeline_full(
                text=proposal.proposed_plan_text,
                project_type=report.project_type,
                # Keep the same AI insights setting the user originally chose.
                enable_llm=report.llm_enabled,
            )
        except PipelineError as exc:
            st.error(f"Audit failed on the revised plan: {exc}")
            return
        except Exception as exc:
            st.error(f"Unexpected error during re-audit: {exc}")
            return

    new_report = result.report
    st.session_state["report"] = new_report
    st.session_state["plan_text"] = result.plan_text

    workspace_id = get_active_workspace_id()
    total_findings = sum(len(r.rule_findings) for r in new_report.category_results)
    summary = (
        ", ".join(issue.title for issue in new_report.top_issues[:2])
        or f"Re-audit after {proposal.verb.value} on {proposal.section or '—'}."
    )
    run_id = record_analysis_run(
        user_id=user.id,
        workspace_id=workspace_id,
        source_name=new_report.source_name or "Revised plan",
        project_type=new_report.project_type,
        source_type="ai_revision",
        overall_score=new_report.overall_score,
        grade=new_report.grade,
        word_count=new_report.word_count,
        sections_found_count=len(new_report.sections_found),
        rule_findings_count=total_findings,
        ai_insights_count=len(new_report.ai_insights),
        llm_enabled=new_report.llm_enabled,
        summary=summary,
        report_json=report_to_json(new_report),
    )
    st.session_state["analysis_run_id"] = run_id
    st.session_state.pop(_PROPOSAL_KEY, None)
    st.session_state["flash_success"] = (
        f"Plan updated. New score: {new_report.overall_score:.1f} (grade {new_report.grade})."
    )
    st.rerun()
