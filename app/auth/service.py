"""
Auth Service — register, login, password hashing, usage tracking.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import bcrypt

from app.auth.db import (
    create_user,
    get_user_by_email,
    update_user,
)
from app.auth.models import Tier, User, payment_bypass_enabled


class AuthError(Exception):
    pass


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _next_month_first() -> str:
    today = date.today()
    if today.month == 12:
        return date(today.year + 1, 1, 1).isoformat()
    return date(today.year, today.month + 1, 1).isoformat()


def register(email: str, password: str) -> User:
    email = email.strip().lower()
    if not email or "@" not in email:
        raise AuthError("Invalid email address.")
    if len(password) < 8:
        raise AuthError("Password must be at least 8 characters.")
    if get_user_by_email(email):
        raise AuthError("An account with this email already exists.")
    hashed = _hash_password(password)
    return create_user(email, hashed, _next_month_first())


def login(email: str, password: str) -> User:
    email = email.strip().lower()
    user = get_user_by_email(email)
    if not user or not _verify_password(password, user.password_hash):
        raise AuthError("Invalid email or password.")
    return user


def reset_monthly_usage_if_needed(user: User) -> None:
    """Reset monthly_usage counter if the reset date has passed."""
    today = date.today().isoformat()
    if user.usage_reset_date and today >= user.usage_reset_date:
        user.monthly_usage = 0
        user.usage_reset_date = _next_month_first()
        update_user(user)


def consume_analysis(user: User) -> None:
    """
    Deduct one analysis unit from the user's allowance and persist.
    Raises AuthError if the user has no remaining access.
    """
    if payment_bypass_enabled():
        return

    reset_monthly_usage_if_needed(user)

    if user.tier == Tier.PRO:
        return  # unlimited — nothing to deduct

    if user.tier == Tier.CREDITS:
        if user.credits <= 0:
            raise AuthError("No credits remaining. Please purchase more.")
        user.credits -= 1
        update_user(user)
        return

    # Free tier
    if user.monthly_usage >= 2:
        raise AuthError("Free tier limit reached (2/month). Please upgrade.")
    user.monthly_usage += 1
    update_user(user)
