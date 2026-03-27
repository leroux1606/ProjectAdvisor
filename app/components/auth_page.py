"""
Auth Page — login and registration forms.
"""

from __future__ import annotations

import streamlit as st

from app.auth.db import init_db
from app.auth.service import AuthError, login, register
from app.auth.session import set_current_user


def render_auth_page() -> None:
    init_db()

    st.markdown(
        """
        <div style="max-width:420px;margin:3rem auto 0;">
            <h1 style="color:#f1f5f9;font-size:1.6rem;font-weight:800;text-align:center;margin-bottom:0.25rem;">
                🔍 Project Plan Scrutinizer
            </h1>
            <p style="color:#64748b;font-size:0.88rem;text-align:center;margin-bottom:2rem;">
                Professional project audit tool
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col = st.columns([1, 2, 1])[1]

    with col:
        tab_login, tab_register = st.tabs(["Sign In", "Create Account"])

        with tab_login:
            _render_login()

        with tab_register:
            _render_register()

        st.markdown(
            '<div style="color:#334155;font-size:0.75rem;text-align:center;margin-top:2rem;">'
            'Free tier: 2 analyses/month · No credit card required to start'
            '</div>',
            unsafe_allow_html=True,
        )


def _render_login() -> None:
    with st.form("login_form"):
        st.markdown("#### Sign In")
        email = st.text_input("Email", placeholder="you@example.com")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign In", use_container_width=True)

    if submitted:
        if not email or not password:
            st.error("Please enter your email and password.")
            return
        try:
            user = login(email, password)
            set_current_user(user)
            st.rerun()
        except AuthError as e:
            st.error(str(e))


def _render_register() -> None:
    with st.form("register_form"):
        st.markdown("#### Create Account")
        email = st.text_input("Email", placeholder="you@example.com", key="reg_email")
        password = st.text_input("Password (min 8 chars)", type="password", key="reg_pass")
        confirm = st.text_input("Confirm Password", type="password", key="reg_confirm")
        submitted = st.form_submit_button("Create Account", use_container_width=True)

    if submitted:
        if not email or not password or not confirm:
            st.error("Please fill in all fields.")
            return
        if password != confirm:
            st.error("Passwords do not match.")
            return
        try:
            user = register(email, password)
            set_current_user(user)
            st.success("Account created! Welcome.")
            st.rerun()
        except AuthError as e:
            st.error(str(e))
