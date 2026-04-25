"""
Tests for token budget enforcement.
Uses an isolated SQLite database via a tmp DB path.
"""

from __future__ import annotations

import os

import pytest

from app.auth import db as auth_db
from app.auth.models import Tier, User
from app.llm import budget


@pytest.fixture
def tmp_db(monkeypatch, tmp_path):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr(auth_db, "_DB_PATH", str(db_file))
    monkeypatch.delenv("BYPASS_PAYMENT", raising=False)
    monkeypatch.delenv("TOKEN_BUDGET_FREE", raising=False)
    monkeypatch.delenv("TOKEN_BUDGET_CREDITS", raising=False)
    monkeypatch.delenv("TOKEN_BUDGET_PRO", raising=False)
    auth_db.init_db()
    yield db_file


def _make_user(tier: Tier = Tier.FREE, reset_date: str = "2026-05-01") -> User:
    user = auth_db.create_user(
        email=f"test+{os.urandom(4).hex()}@example.com",
        password_hash="x",
        usage_reset_date=reset_date,
    )
    if tier != Tier.FREE:
        user.tier = tier
        auth_db.update_user(user)
    return user


def test_default_budgets(tmp_db):
    user = _make_user(Tier.FREE)
    assert budget.get_status(user).monthly_limit == 20_000

    user_credits = _make_user(Tier.CREDITS)
    assert budget.get_status(user_credits).monthly_limit == 200_000

    user_pro = _make_user(Tier.PRO)
    assert budget.get_status(user_pro).monthly_limit == 2_000_000


def test_env_overrides_budget(tmp_db, monkeypatch):
    monkeypatch.setenv("TOKEN_BUDGET_FREE", "1000")
    user = _make_user(Tier.FREE)
    assert budget.get_status(user).monthly_limit == 1000


def test_invalid_env_falls_back_to_default(tmp_db, monkeypatch):
    monkeypatch.setenv("TOKEN_BUDGET_FREE", "not-a-number")
    user = _make_user(Tier.FREE)
    assert budget.get_status(user).monthly_limit == 20_000


def test_record_spend_increments_used(tmp_db):
    user = _make_user(Tier.FREE)
    budget.record_spend(
        user,
        purpose="chat_turn",
        model="anthropic/claude-haiku-4-5",
        prompt_tokens=100,
        completion_tokens=50,
    )
    status = budget.get_status(user)
    assert status.used == 150
    assert status.remaining == 20_000 - 150


def test_assert_can_spend_blocks_when_over_budget(tmp_db, monkeypatch):
    monkeypatch.setenv("TOKEN_BUDGET_FREE", "100")
    user = _make_user(Tier.FREE)
    budget.record_spend(
        user,
        purpose="chat_turn",
        model="x",
        prompt_tokens=80,
        completion_tokens=10,
    )
    # 90 used; an estimate of 20 more would push to 110 > 100.
    with pytest.raises(budget.BudgetExceeded):
        budget.assert_can_spend(user, estimated_tokens=20)


def test_assert_can_spend_allows_when_under_budget(tmp_db):
    user = _make_user(Tier.FREE)
    # Should not raise.
    budget.assert_can_spend(user, estimated_tokens=5_000)


def test_bypass_payment_skips_budget(tmp_db, monkeypatch):
    monkeypatch.setenv("BYPASS_PAYMENT", "true")
    monkeypatch.setenv("TOKEN_BUDGET_FREE", "10")
    user = _make_user(Tier.FREE)
    budget.record_spend(
        user, purpose="x", model="x", prompt_tokens=999, completion_tokens=999,
    )
    # Way over the 10-token cap, but bypass means no check.
    budget.assert_can_spend(user, estimated_tokens=10_000)


def test_estimate_tokens_rough_chars_over_4():
    assert budget.estimate_tokens("a" * 100) == 25
    assert budget.estimate_tokens("") == 1
