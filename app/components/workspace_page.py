"""
Workspace Page — create, join, and switch team workspaces.
"""

from __future__ import annotations

from html import escape

import streamlit as st

from app.auth.db import create_workspace, get_user_workspaces, join_workspace
from app.auth.models import User
from app.auth.session import get_active_workspace_id, set_active_workspace_id


def render_workspace_page(user: User) -> None:
    st.markdown(
        """
        <div style="margin-bottom:1.5rem;">
            <h2 style="color:#f1f5f9;font-size:1.35rem;font-weight:800;margin-bottom:0.25rem;">
                Workspaces
            </h2>
            <p style="color:#cbd5e1;font-size:0.9rem;margin:0;">
                Create a shared workspace, join a team using a code, and choose where new analyses are saved.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    workspaces = get_user_workspaces(user.id)
    active_workspace_id = get_active_workspace_id()

    if workspaces:
        options = {"Personal workspace (private)": None}
        for ws in workspaces:
            label = f'{ws["name"]} · {ws["role"]} · code {ws["join_code"]}'
            options[label] = ws["id"]

        current_label = next(
            (label for label, ws_id in options.items() if ws_id == active_workspace_id),
            "Personal workspace (private)",
        )
        selected_label = st.selectbox(
            "Save new analyses to",
            list(options.keys()),
            index=list(options.keys()).index(current_label),
        )
        selected_id = options[selected_label]
        if selected_id != active_workspace_id:
            set_active_workspace_id(selected_id)
            st.success("Active workspace updated.")
            st.rerun()
    else:
        st.info("You are currently using only your private personal workspace.")

    create_col, join_col = st.columns(2, gap="large")
    with create_col:
        with st.form("create_workspace_form"):
            st.markdown("### Create workspace")
            workspace_name = st.text_input(
                "Workspace name",
                placeholder="e.g. PMO Team or Client Delivery",
            )
            create_submitted = st.form_submit_button("Create Workspace", use_container_width=True)
        if create_submitted:
            try:
                workspace = create_workspace(workspace_name, user.id)
                set_active_workspace_id(workspace["id"])
                st.success(f'Workspace "{workspace["name"]}" created. Share code `{workspace["join_code"]}` with teammates.')
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    with join_col:
        with st.form("join_workspace_form"):
            st.markdown("### Join workspace")
            join_code = st.text_input(
                "Workspace join code",
                placeholder="Paste the team join code",
            )
            join_submitted = st.form_submit_button("Join Workspace", use_container_width=True)
        if join_submitted:
            try:
                workspace = join_workspace(user.id, join_code)
                set_active_workspace_id(workspace["id"])
                st.success(f'Joined workspace "{workspace["name"]}".')
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    if workspaces:
        st.markdown("### Your workspaces")
        for ws in workspaces:
            name = escape(ws["name"])
            role = escape(ws["role"])
            join_code = escape(ws["join_code"])
            active_label = "Active" if ws["id"] == active_workspace_id else "Available"
            st.markdown(
                f"""
                <div style="background:#1e293b;border:1px solid #334155;border-radius:8px;
                            padding:0.9rem 1rem;margin-bottom:0.65rem;">
                    <div style="display:flex;justify-content:space-between;gap:1rem;">
                        <div>
                            <div style="color:#f1f5f9;font-size:0.92rem;font-weight:600;">{name}</div>
                            <div style="color:#cbd5e1;font-size:0.78rem;margin-top:0.15rem;">
                                Role: {role} · Join code: {join_code}
                            </div>
                        </div>
                        <div style="color:#60a5fa;font-size:0.8rem;font-weight:600;">{active_label}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
