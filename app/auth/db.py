"""
Auth DB — SQLite persistence for users and transactions.
Uses stdlib sqlite3 only. DB file lives at data/app.db.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from typing import Optional

from app.auth.models import Tier, User

_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "app.db")


def _ensure_data_dir() -> None:
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)


@contextmanager
def _conn():
    _ensure_data_dir()
    con = sqlite3.connect(_DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    """Create tables if they don't exist."""
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                email                   TEXT    NOT NULL UNIQUE,
                password_hash           TEXT    NOT NULL,
                tier                    TEXT    NOT NULL DEFAULT 'free',
                credits                 INTEGER NOT NULL DEFAULT 0,
                monthly_usage           INTEGER NOT NULL DEFAULT 0,
                usage_reset_date        TEXT    NOT NULL DEFAULT '',
                stripe_customer_id      TEXT,
                stripe_subscription_id  TEXT,
                created_at              TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id             INTEGER NOT NULL REFERENCES users(id),
                stripe_session_id   TEXT,
                type                TEXT    NOT NULL,
                amount_pence        INTEGER NOT NULL DEFAULT 0,
                credits_added       INTEGER NOT NULL DEFAULT 0,
                created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
            );
        """)


def _row_to_user(row: sqlite3.Row) -> User:
    return User(
        id=row["id"],
        email=row["email"],
        password_hash=row["password_hash"],
        tier=Tier(row["tier"]),
        credits=row["credits"],
        monthly_usage=row["monthly_usage"],
        usage_reset_date=row["usage_reset_date"],
        stripe_customer_id=row["stripe_customer_id"],
        stripe_subscription_id=row["stripe_subscription_id"],
        created_at=row["created_at"],
    )


def get_user_by_email(email: str) -> Optional[User]:
    with _conn() as con:
        row = con.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()
        return _row_to_user(row) if row else None


def get_user_by_id(user_id: int) -> Optional[User]:
    with _conn() as con:
        row = con.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return _row_to_user(row) if row else None


def get_user_by_stripe_customer(stripe_customer_id: str) -> Optional[User]:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM users WHERE stripe_customer_id = ?", (stripe_customer_id,)
        ).fetchone()
        return _row_to_user(row) if row else None


def create_user(email: str, password_hash: str, usage_reset_date: str) -> User:
    with _conn() as con:
        cur = con.execute(
            """INSERT INTO users (email, password_hash, tier, credits, monthly_usage, usage_reset_date)
               VALUES (?, ?, 'free', 0, 0, ?)""",
            (email.lower(), password_hash, usage_reset_date),
        )
        user_id = cur.lastrowid
    return get_user_by_id(user_id)


def update_user(user: User) -> None:
    with _conn() as con:
        con.execute(
            """UPDATE users SET
                tier = ?, credits = ?, monthly_usage = ?, usage_reset_date = ?,
                stripe_customer_id = ?, stripe_subscription_id = ?
               WHERE id = ?""",
            (
                user.tier.value,
                user.credits,
                user.monthly_usage,
                user.usage_reset_date,
                user.stripe_customer_id,
                user.stripe_subscription_id,
                user.id,
            ),
        )


def record_transaction(
    user_id: int,
    tx_type: str,
    amount_pence: int,
    credits_added: int = 0,
    stripe_session_id: Optional[str] = None,
) -> None:
    with _conn() as con:
        con.execute(
            """INSERT INTO transactions (user_id, stripe_session_id, type, amount_pence, credits_added)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, stripe_session_id, tx_type, amount_pence, credits_added),
        )


def get_user_transactions(user_id: int) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT 20",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
