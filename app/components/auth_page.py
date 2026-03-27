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
        <style>
        /* Input labels */
        .stTextInput label { color: #cbd5e1 !important; font-size: 0.88rem !important; font-weight: 500 !important; }
        /* Input boxes */
        .stTextInput input {
            background-color: #1e293b !important;
            color: #f1f5f9 !important;
            border: 1px solid #475569 !important;
            border-radius: 6px !important;
            font-size: 0.95rem !important;
        }
        /* Placeholder text */
        .stTextInput input::placeholder { color: #64748b !important; opacity: 1 !important; }
        /* Tab labels */
        .stTabs [data-baseweb="tab"] { color: #94a3b8 !important; font-weight: 600; font-size: 0.95rem; }
        .stTabs [aria-selected="true"] { color: #f1f5f9 !important; }
        /* Form submit button */
        .stFormSubmitButton > button {
            background: #3b82f6 !important; color: white !important;
            border: none !important; border-radius: 8px !important;
            padding: 0.6rem 2rem !important; font-size: 1rem !important;
            font-weight: 600 !important; width: 100% !important;
        }
        .stFormSubmitButton > button:hover { background: #2563eb !important; }
        </style>
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
        email = st.text_input("Email address", placeholder="e.g. john@company.com")
        password = st.text_input("Password", placeholder="Enter your password", type="password")
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
        st.markdown(
            '<div style="color:#64748b;font-size:0.82rem;margin-bottom:0.75rem;">'
            'Free tier included — 2 analyses per month, no credit card required.</div>',
            unsafe_allow_html=True,
        )
        email = st.text_input("Email address", placeholder="e.g. john@company.com", key="reg_email")
        password = st.text_input("Password", placeholder="At least 8 characters", type="password", key="reg_pass")
        confirm = st.text_input("Confirm password", placeholder="Re-enter your password", type="password", key="reg_confirm")
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
