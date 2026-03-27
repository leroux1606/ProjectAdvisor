"""
Privacy Page — data export, storage explanation, and account deletion controls.
"""

from __future__ import annotations

import json

import streamlit as st

from app.auth.db import delete_user_account, export_user_data
from app.auth.models import User
from app.auth.session import logout


def render_privacy_page(user: User) -> None:
    st.markdown(
        """
        <div style="margin-bottom:1.5rem;">
            <h2 style="color:#f1f5f9;font-size:1.35rem;font-weight:800;margin-bottom:0.25rem;">
                Privacy and Data Controls
            </h2>
            <p style="color:#cbd5e1;font-size:0.9rem;margin:0;">
                Review what data is stored, export your account data, or remove your account.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### What the app stores")
    st.markdown(
        """
        - Account details such as email, plan, usage counters, and optional profile fields.
        - Payment transaction metadata when billing is used.
        - Analysis history metadata and saved report outputs.
        - The app does not intentionally retain the raw uploaded project document by default.
        """
    )

    export_payload = export_user_data(user.id)
    export_json = json.dumps(export_payload, indent=2)
    st.download_button(
        "Export My Data",
        data=export_json,
        file_name="project-scrutinizer-account-export.json",
        mime="application/json",
        use_container_width=True,
    )

    st.markdown("### Delete account")
    st.warning(
        "Deleting your account removes your profile, analysis history, and transaction records from this local application. This action cannot be undone."
    )
    with st.form("delete_account_form"):
        confirm_email = st.text_input(
            "Type your email address to confirm deletion",
            placeholder=user.email,
        )
        confirm_delete = st.form_submit_button("Delete My Account", use_container_width=True)

    if confirm_delete:
        if confirm_email.strip().lower() != user.email.lower():
            st.error("Email confirmation did not match. Your account was not deleted.")
            return
        delete_user_account(user.id)
        logout()
        st.success("Your account and saved data have been deleted.")
        st.rerun()

