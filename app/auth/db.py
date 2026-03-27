"""
Auth DB — SQLite persistence for users and transactions.
Uses stdlib sqlite3 only. DB file lives at data/app.db.
"""

from __future__ import annotations

import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
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


def _ensure_column(con: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    existing = {
        row["name"] for row in con.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in existing:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


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
                display_name            TEXT,
                organization            TEXT,
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

            CREATE TABLE IF NOT EXISTS analysis_runs (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id                 INTEGER NOT NULL REFERENCES users(id),
                workspace_id            INTEGER REFERENCES workspaces(id),
                source_name             TEXT,
                source_type             TEXT    NOT NULL,
                overall_score           REAL    NOT NULL,
                grade                   TEXT    NOT NULL,
                word_count              INTEGER NOT NULL DEFAULT 0,
                sections_found_count    INTEGER NOT NULL DEFAULT 0,
                rule_findings_count     INTEGER NOT NULL DEFAULT 0,
                ai_insights_count       INTEGER NOT NULL DEFAULT 0,
                llm_enabled             INTEGER NOT NULL DEFAULT 0,
                summary                 TEXT,
                report_json             TEXT,
                created_at              TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS workspaces (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                name                TEXT    NOT NULL,
                join_code           TEXT    NOT NULL UNIQUE,
                created_by          INTEGER NOT NULL REFERENCES users(id),
                created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS workspace_members (
                workspace_id        INTEGER NOT NULL REFERENCES workspaces(id),
                user_id             INTEGER NOT NULL REFERENCES users(id),
                role                TEXT    NOT NULL DEFAULT 'member',
                created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
                UNIQUE(workspace_id, user_id)
            );
        """)
        _ensure_column(con, "users", "display_name", "TEXT")
        _ensure_column(con, "users", "organization", "TEXT")
        _ensure_column(con, "analysis_runs", "workspace_id", "INTEGER REFERENCES workspaces(id)")
        _ensure_column(con, "analysis_runs", "report_json", "TEXT")


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
        display_name=row["display_name"] if "display_name" in row.keys() else None,
        organization=row["organization"] if "organization" in row.keys() else None,
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
                stripe_customer_id = ?, stripe_subscription_id = ?,
                display_name = ?, organization = ?
               WHERE id = ?""",
            (
                user.tier.value,
                user.credits,
                user.monthly_usage,
                user.usage_reset_date,
                user.stripe_customer_id,
                user.stripe_subscription_id,
                user.display_name,
                user.organization,
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


def record_analysis_run(
    user_id: int,
    workspace_id: Optional[int],
    source_name: Optional[str],
    source_type: str,
    overall_score: float,
    grade: str,
    word_count: int,
    sections_found_count: int,
    rule_findings_count: int,
    ai_insights_count: int,
    llm_enabled: bool,
    summary: str,
    report_json: Optional[str] = None,
) -> None:
    with _conn() as con:
        con.execute(
            """INSERT INTO analysis_runs (
                user_id, workspace_id, source_name, source_type, overall_score, grade, word_count,
                sections_found_count, rule_findings_count, ai_insights_count,
                llm_enabled, summary, report_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                workspace_id,
                source_name,
                source_type,
                overall_score,
                grade,
                word_count,
                sections_found_count,
                rule_findings_count,
                ai_insights_count,
                int(llm_enabled),
                summary,
                report_json,
            ),
        )


def get_analysis_history(
    user_id: int,
    limit: int = 50,
    workspace_id: Optional[int] = None,
) -> list[dict]:
    with _conn() as con:
        if workspace_id is None:
            rows = con.execute(
                """SELECT analysis_runs.*, workspaces.name AS workspace_name
                   FROM analysis_runs
                   LEFT JOIN workspaces ON workspaces.id = analysis_runs.workspace_id
                   WHERE analysis_runs.user_id = ? AND analysis_runs.workspace_id IS NULL
                   ORDER BY analysis_runs.created_at DESC, analysis_runs.id DESC
                   LIMIT ?""",
                (user_id, limit),
            ).fetchall()
        else:
            rows = con.execute(
                """SELECT analysis_runs.*, workspaces.name AS workspace_name
                   FROM analysis_runs
                   JOIN workspace_members ON workspace_members.workspace_id = analysis_runs.workspace_id
                   LEFT JOIN workspaces ON workspaces.id = analysis_runs.workspace_id
                   WHERE workspace_members.user_id = ? AND analysis_runs.workspace_id = ?
                   ORDER BY analysis_runs.created_at DESC, analysis_runs.id DESC
                   LIMIT ?""",
                (user_id, workspace_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]


def get_analysis_run(run_id: int, user_id: int) -> Optional[dict]:
    with _conn() as con:
        row = con.execute(
            """SELECT analysis_runs.*, workspaces.name AS workspace_name
               FROM analysis_runs
               LEFT JOIN workspace_members
                 ON workspace_members.workspace_id = analysis_runs.workspace_id
                 AND workspace_members.user_id = ?
               LEFT JOIN workspaces ON workspaces.id = analysis_runs.workspace_id
               WHERE analysis_runs.id = ?
                 AND (analysis_runs.user_id = ? OR workspace_members.user_id = ?)""",
            (user_id, run_id, user_id, user_id),
        ).fetchone()
        return dict(row) if row else None


def delete_analysis_run(run_id: int, user_id: int) -> None:
    with _conn() as con:
        con.execute(
            "DELETE FROM analysis_runs WHERE id = ? AND user_id = ?",
            (run_id, user_id),
        )


def clear_analysis_history(user_id: int) -> None:
    with _conn() as con:
        con.execute("DELETE FROM analysis_runs WHERE user_id = ?", (user_id,))


def export_user_data(user_id: int) -> dict:
    user = get_user_by_id(user_id)
    if not user:
        return {}
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "tier": user.tier.value,
            "credits": user.credits,
            "monthly_usage": user.monthly_usage,
            "usage_reset_date": user.usage_reset_date,
            "display_name": user.display_name,
            "organization": user.organization,
            "created_at": user.created_at,
        },
        "transactions": get_user_transactions(user_id),
        "analysis_history": get_analysis_history(user_id, limit=1000),
        "workspaces": get_user_workspaces(user_id),
    }


def delete_user_account(user_id: int) -> None:
    with _conn() as con:
        con.execute("DELETE FROM analysis_runs WHERE user_id = ?", (user_id,))
        con.execute("DELETE FROM transactions WHERE user_id = ?", (user_id,))
        con.execute("DELETE FROM users WHERE id = ?", (user_id,))


def get_analysis_stats(user_id: int) -> dict:
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    with _conn() as con:
        total_row = con.execute(
            """SELECT
                   COUNT(*) AS total_runs,
                   COALESCE(AVG(overall_score), 0) AS average_score,
                   COALESCE(MAX(overall_score), 0) AS best_score,
                   MAX(created_at) AS last_analysis_at
               FROM analysis_runs
               WHERE user_id = ?""",
            (user_id,),
        ).fetchone()

        month_row = con.execute(
            """SELECT COUNT(*) AS runs_this_month
               FROM analysis_runs
               WHERE user_id = ? AND substr(created_at, 1, 7) = ?""",
            (user_id, current_month),
        ).fetchone()

    return {
        "total_runs": int(total_row["total_runs"]) if total_row else 0,
        "runs_this_month": int(month_row["runs_this_month"]) if month_row else 0,
        "average_score": round(float(total_row["average_score"]), 1) if total_row else 0.0,
        "best_score": round(float(total_row["best_score"]), 1) if total_row else 0.0,
        "last_analysis_at": total_row["last_analysis_at"] if total_row else None,
    }


def get_analysis_stats_for_workspace(user_id: int, workspace_id: int) -> dict:
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    with _conn() as con:
        total_row = con.execute(
            """SELECT
                   COUNT(*) AS total_runs,
                   COALESCE(AVG(overall_score), 0) AS average_score,
                   COALESCE(MAX(overall_score), 0) AS best_score,
                   MAX(created_at) AS last_analysis_at
               FROM analysis_runs
               WHERE workspace_id = ?
                 AND EXISTS (
                     SELECT 1 FROM workspace_members
                     WHERE workspace_members.workspace_id = analysis_runs.workspace_id
                       AND workspace_members.user_id = ?
                 )""",
            (workspace_id, user_id),
        ).fetchone()
        month_row = con.execute(
            """SELECT COUNT(*) AS runs_this_month
               FROM analysis_runs
               WHERE workspace_id = ?
                 AND substr(created_at, 1, 7) = ?
                 AND EXISTS (
                     SELECT 1 FROM workspace_members
                     WHERE workspace_members.workspace_id = analysis_runs.workspace_id
                       AND workspace_members.user_id = ?
                 )""",
            (workspace_id, current_month, user_id),
        ).fetchone()
    return {
        "total_runs": int(total_row["total_runs"]) if total_row else 0,
        "runs_this_month": int(month_row["runs_this_month"]) if month_row else 0,
        "average_score": round(float(total_row["average_score"]), 1) if total_row else 0.0,
        "best_score": round(float(total_row["best_score"]), 1) if total_row else 0.0,
        "last_analysis_at": total_row["last_analysis_at"] if total_row else None,
    }


def _generate_join_code() -> str:
    return secrets.token_hex(4).upper()


def create_workspace(name: str, user_id: int) -> dict:
    workspace_name = name.strip()
    if not workspace_name:
        raise ValueError("Workspace name is required.")
    join_code = _generate_join_code()
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO workspaces (name, join_code, created_by) VALUES (?, ?, ?)",
            (workspace_name, join_code, user_id),
        )
        workspace_id = cur.lastrowid
        con.execute(
            "INSERT INTO workspace_members (workspace_id, user_id, role) VALUES (?, ?, 'owner')",
            (workspace_id, user_id),
        )
    return get_workspace(workspace_id)


def join_workspace(user_id: int, join_code: str) -> dict:
    code = join_code.strip().upper()
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM workspaces WHERE join_code = ?",
            (code,),
        ).fetchone()
        if row is None:
            raise ValueError("Workspace join code not found.")
        con.execute(
            "INSERT OR IGNORE INTO workspace_members (workspace_id, user_id, role) VALUES (?, ?, 'member')",
            (row["id"], user_id),
        )
    return get_workspace(row["id"])


def get_workspace(workspace_id: int) -> Optional[dict]:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM workspaces WHERE id = ?",
            (workspace_id,),
        ).fetchone()
        return dict(row) if row else None


def get_user_workspaces(user_id: int) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            """SELECT workspaces.*, workspace_members.role
               FROM workspaces
               JOIN workspace_members ON workspace_members.workspace_id = workspaces.id
               WHERE workspace_members.user_id = ?
               ORDER BY workspaces.name""",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
