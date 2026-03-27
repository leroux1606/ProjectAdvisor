"""
Auth Session — Streamlit session state helpers for current user.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

from app.auth.db import get_user_by_id, get_user_workspaces, init_db
from app.auth.models import User

_KEY = "auth_user_id"
_WORKSPACE_KEY = "active_workspace_id"


def init() -> None:
    """Initialise DB and session state on app startup."""
    init_db()
    if _KEY not in st.session_state:
        st.session_state[_KEY] = None
    if _WORKSPACE_KEY not in st.session_state:
        st.session_state[_WORKSPACE_KEY] = None


def get_current_user() -> Optional[User]:
    user_id = st.session_state.get(_KEY)
    if user_id is None:
        return None
    return get_user_by_id(user_id)


def set_current_user(user: User) -> None:
    st.session_state[_KEY] = user.id
    workspaces = get_user_workspaces(user.id)
    st.session_state[_WORKSPACE_KEY] = workspaces[0]["id"] if workspaces else None


def logout() -> None:
    st.session_state[_KEY] = None
    # Clear any cached report
    st.session_state.pop("report", None)
    st.session_state["page"] = "main"
    st.session_state[_WORKSPACE_KEY] = None


def is_authenticated() -> bool:
    return st.session_state.get(_KEY) is not None


def refresh_user() -> Optional[User]:
    """Re-fetch user from DB (e.g. after a payment webhook updates their tier)."""
    user_id = st.session_state.get(_KEY)
    if user_id is None:
        return None
    user = get_user_by_id(user_id)
    return user


def get_active_workspace_id() -> Optional[int]:
    return st.session_state.get(_WORKSPACE_KEY)


def set_active_workspace_id(workspace_id: Optional[int]) -> None:
    st.session_state[_WORKSPACE_KEY] = workspace_id
