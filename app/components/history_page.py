"""
History Page — shows persisted analysis history and usage insights.
"""

from __future__ import annotations

import csv
import io
from html import escape

import pandas as pd
import streamlit as st

from app.auth.db import (
    clear_analysis_history,
    delete_analysis_run,
    get_analysis_history,
    get_analysis_run,
    get_analysis_stats,
    get_analysis_stats_for_workspace,
    get_workspace,
)
from app.auth.models import User
from app.auth.session import get_active_workspace_id
from app.pipeline.report_generator import report_from_json, report_to_markdown
from app.project_types import PROJECT_TYPE_PROFILES, get_project_type_label
from app.utils.pdf_export import text_to_pdf_bytes


def _sort_rows(rows: list[dict], sort_by: str, ascending: bool) -> list[dict]:
    key_map = {
        "Date": lambda r: r.get("created_at", ""),
        "Score": lambda r: float(r.get("overall_score", 0)),
        "Grade": lambda r: r.get("grade", ""),
        "Findings": lambda r: int(r.get("rule_findings_count", 0)),
        "Project": lambda r: (r.get("source_name") or "").lower(),
        "Project type": lambda r: get_project_type_label(r.get("project_type", "general")).lower(),
    }
    return sorted(rows, key=key_map[sort_by], reverse=not ascending)


def render_history_page(user: User) -> None:
    workspace_id = get_active_workspace_id()
    workspace = get_workspace(workspace_id) if workspace_id else None
    stats = get_analysis_stats_for_workspace(user.id, workspace_id) if workspace_id else get_analysis_stats(user.id)
    rows = get_analysis_history(user.id, limit=500, workspace_id=workspace_id)

    st.markdown(
        """
        <div style="margin-bottom:1.5rem;">
            <h2 style="color:#f1f5f9;font-size:1.35rem;font-weight:800;margin-bottom:0.25rem;">
                Analysis History
            </h2>
            <p style="color:#cbd5e1;font-size:0.9rem;margin:0;">
                Review previously analysed projects, scores, and usage trends.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if workspace:
        st.info(
            f'Viewing shared history for workspace "{escape(workspace["name"])}". '
            "Switch to Personal workspace in Workspaces to see only your private reports."
        )
    else:
        st.info(
            "Viewing your private history. Switch to a shared workspace to see team analyses."
        )

    c1, c2, c3, c4 = st.columns(4, gap="small")
    stats_cards = [
        ("Total analyses", str(stats["total_runs"])),
        ("This month", str(stats["runs_this_month"])),
        ("Average score", f'{stats["average_score"]:.1f}' if stats["total_runs"] else "—"),
        ("Best score", f'{stats["best_score"]:.1f}' if stats["total_runs"] else "—"),
    ]
    for col, (label, value) in zip((c1, c2, c3, c4), stats_cards):
        with col:
            st.markdown(
                f"""
                <div style="background:#1e293b;border:1px solid #334155;border-radius:8px;
                            padding:1rem;margin-bottom:1rem;">
                    <div style="color:#cbd5e1;font-size:0.76rem;margin-bottom:0.25rem;">{label}</div>
                    <div style="color:#f1f5f9;font-size:1.4rem;font-weight:700;">{value}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if not rows:
        st.info("No projects have been analysed yet.")
        return

    filter_col1, filter_col2, filter_col3, filter_col4, filter_col5 = st.columns(5, gap="small")
    with filter_col1:
        search_text = st.text_input("Search", placeholder="Project name or summary")
    with filter_col2:
        source_filter = st.selectbox("Source type", ["All", "Upload", "Text"])
    with filter_col3:
        ai_filter = st.selectbox("AI mode", ["All", "AI enabled", "Rule-based only"])
    with filter_col4:
        project_type_filter = st.selectbox(
            "Project type",
            ["All"] + [profile.label for profile in PROJECT_TYPE_PROFILES],
        )
    with filter_col5:
        sort_by = st.selectbox("Sort by", ["Date", "Score", "Grade", "Findings", "Project", "Project type"])
        ascending = st.toggle("Ascending", value=False)

    filtered_rows = rows
    if search_text.strip():
        needle = search_text.strip().lower()
        filtered_rows = [
            row for row in filtered_rows
            if needle in (row.get("source_name") or "").lower()
            or needle in (row.get("summary") or "").lower()
        ]
    if source_filter != "All":
        wanted = source_filter.lower()
        filtered_rows = [row for row in filtered_rows if row.get("source_type") == wanted]
    if ai_filter == "AI enabled":
        filtered_rows = [row for row in filtered_rows if row.get("llm_enabled")]
    elif ai_filter == "Rule-based only":
        filtered_rows = [row for row in filtered_rows if not row.get("llm_enabled")]
    if project_type_filter != "All":
        filtered_rows = [
            row for row in filtered_rows
            if get_project_type_label(row.get("project_type", "general")) == project_type_filter
        ]

    filtered_rows = _sort_rows(filtered_rows, sort_by, ascending)
    if not filtered_rows:
        st.info("No reports matched your current filters.")
        return

    export_buffer = io.StringIO()
    writer = csv.DictWriter(
        export_buffer,
        fieldnames=["Date", "Project", "Project type", "Workspace", "Source", "Score", "Grade", "Findings", "AI", "Summary"],
    )
    export_fields = set(writer.fieldnames or [])
    writer.writeheader()

    table_rows = []
    for row in filtered_rows:
        entry = {
            "Select": False,
            "ID": row["id"],
            "Date": (row.get("created_at") or "")[:16].replace("T", " "),
            "Project": row.get("source_name") or "Pasted project plan",
            "Project type": get_project_type_label(row.get("project_type", "general")),
            "Workspace": row.get("workspace_name") or "Personal",
            "Ownership": "Mine" if row.get("user_id") == user.id else "Shared",
            "Source": row.get("source_type", "unknown").title(),
            "Score": f'{row.get("overall_score", 0):.1f}',
            "Grade": row.get("grade", ""),
            "Findings": row.get("rule_findings_count", 0),
            "AI": "Yes" if row.get("llm_enabled") else "No",
            "Summary": row.get("summary", ""),
        }
        table_rows.append(entry)
        writer.writerow({k: v for k, v in entry.items() if k in export_fields})

    st.markdown("### Checked Projects")
    df = pd.DataFrame(table_rows)
    edited_df = st.data_editor(
        df,
        hide_index=True,
        use_container_width=True,
        disabled=[col for col in df.columns if col != "Select"],
        column_config={
            "Select": st.column_config.CheckboxColumn("Select", help="Select rows for actions"),
            "ID": st.column_config.NumberColumn("ID", disabled=True, width="small"),
        },
        key="history_editor",
    )
    selected_rows = edited_df[edited_df["Select"]]
    selected_ids = selected_rows["ID"].tolist()
    selected_owned_ids = selected_rows[selected_rows["Ownership"] == "Mine"]["ID"].tolist()

    action_col1, action_col2, action_col3 = st.columns(3, gap="medium")
    with action_col1:
        st.download_button(
            "Download History CSV",
            data=export_buffer.getvalue(),
            file_name="analysis-history.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with action_col2:
        if st.button("Delete Selected", use_container_width=True, type="secondary", disabled=not selected_owned_ids):
            for run_id in selected_owned_ids:
                delete_analysis_run(int(run_id), user.id)
            st.success(f"Deleted {len(selected_owned_ids)} selected report(s) that belong to you.")
            st.rerun()
    with action_col3:
        if st.button("Clear My Saved History", use_container_width=True, type="secondary"):
            clear_analysis_history(user.id, workspace_id=workspace_id)
            st.success("Your saved history in the current scope was cleared.")
            st.rerun()

    if len(selected_ids) == 1:
        selected_run = get_analysis_run(int(selected_ids[0]), user.id)
        if selected_run:
            report_json = selected_run.get("report_json")
            st.markdown("### Selected Report")
            if report_json:
                saved_report = report_from_json(report_json)
                col_open, col_md, col_pdf = st.columns(3, gap="medium")
                with col_open:
                    if st.button("Open Saved Report", use_container_width=True):
                        st.session_state["report"] = saved_report
                        st.session_state["page"] = "main"
                        st.rerun()
                with col_md:
                    md = report_to_markdown(saved_report)
                    st.download_button(
                        "Download Markdown",
                        data=md,
                        file_name=f"report-{selected_run['id']}.md",
                        mime="text/markdown",
                        use_container_width=True,
                    )
                with col_pdf:
                    md = report_to_markdown(saved_report)
                    st.download_button(
                        "Download PDF",
                        data=text_to_pdf_bytes(md, title=f"Report {selected_run['id']}"),
                        file_name=f"report-{selected_run['id']}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
            else:
                st.info("This older run does not have a fully saved report attached yet.")

    if len(selected_ids) == 2:
        left_run = get_analysis_run(int(selected_ids[0]), user.id)
        right_run = get_analysis_run(int(selected_ids[1]), user.id)
        if left_run and right_run and left_run.get("report_json") and right_run.get("report_json"):
            left_report = report_from_json(left_run["report_json"])
            right_report = report_from_json(right_run["report_json"])
            comparison = [
                {
                    "Metric": "Source",
                    "First report": left_report.source_name or "Pasted project plan",
                    "Second report": right_report.source_name or "Pasted project plan",
                },
                {
                    "Metric": "Project type",
                    "First report": get_project_type_label(left_report.project_type),
                    "Second report": get_project_type_label(right_report.project_type),
                },
                {
                    "Metric": "Overall score",
                    "First report": f"{left_report.overall_score:.1f}",
                    "Second report": f"{right_report.overall_score:.1f}",
                },
                {
                    "Metric": "Grade",
                    "First report": left_report.grade,
                    "Second report": right_report.grade,
                },
                {
                    "Metric": "Word count",
                    "First report": f"{left_report.word_count:,}",
                    "Second report": f"{right_report.word_count:,}",
                },
                {
                    "Metric": "Rule findings",
                    "First report": str(sum(len(r.rule_findings) for r in left_report.category_results)),
                    "Second report": str(sum(len(r.rule_findings) for r in right_report.category_results)),
                },
                {
                    "Metric": "AI insights",
                    "First report": str(len(left_report.ai_insights)),
                    "Second report": str(len(right_report.ai_insights)),
                },
            ]
            st.markdown("### Compare Selected Reports")
            st.dataframe(comparison, use_container_width=True, hide_index=True)
        else:
            st.info("Both selected reports must have saved report data to be compared.")
    elif len(selected_ids) > 2:
        st.info("Select at most two reports to compare them side by side.")

