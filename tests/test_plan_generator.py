"""
Tests for the plan generator. LLM is mocked.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.auth import db as auth_db
from app.auth.models import Tier
from app.llm import budget
from app.llm.openrouter import ChatResult, LLMNotConfigured
from app.pipeline.plan_generator import (
    PlanGenerationError,
    generate_plan,
)


@pytest.fixture
def tmp_db(monkeypatch, tmp_path):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr(auth_db, "_DB_PATH", str(db_file))
    monkeypatch.delenv("BYPASS_PAYMENT", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    auth_db.init_db()
    yield db_file


def _user(tier: Tier = Tier.PRO):
    user = auth_db.create_user(
        email="user@example.com",
        password_hash="x",
        usage_reset_date="2026-05-01",
    )
    if tier != Tier.FREE:
        user.tier = tier
        auth_db.update_user(user)
    return user


_FAKE_PLAN = (
    "## Objectives\nDeliver A.\n\n"
    "## Scope\nIn: X. Out: Y.\n\n"
    "## Deliverables\n1. Foo.\n\n"
    "## Timeline\nPhase 1 Apr–Jun 2026.\n\n"
    "## Resources\nPM, 2 engineers.\n\n"
    "## Risks\nRisk 1: high impact, mitigated by Z.\n\n"
    "## Governance\nWeekly steering with sponsor.\n\n"
    "## Assumptions\nA1.\n\n"
    "## Constraints\nC1.\n\n"
    "## Budget\n£100,000 across phases.\n"
)


def test_empty_prompt_rejected(tmp_db):
    user = _user()
    with pytest.raises(PlanGenerationError, match="describe the project"):
        generate_plan("", "general", user)


def test_too_long_prompt_rejected(tmp_db):
    user = _user()
    with pytest.raises(PlanGenerationError, match="too long"):
        generate_plan("x" * 10_000, "general", user)


def test_generate_plan_success(tmp_db, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    user = _user(Tier.PRO)

    fake_result = ChatResult(
        text=_FAKE_PLAN,
        model="anthropic/claude-haiku-4-5",
        prompt_tokens=400,
        completion_tokens=900,
        total_tokens=1300,
    )
    with patch("app.pipeline.plan_generator.call_chat", return_value=fake_result):
        plan = generate_plan(
            "A clear project description with enough detail.",
            "software_it",
            user,
        )

    assert "## Objectives" in plan.text
    assert plan.project_type == "software_it"
    assert plan.completion_tokens == 900
    # Budget should reflect the spend.
    status = budget.get_status(user)
    assert status.used == 1300


def test_generate_plan_blocked_by_budget(tmp_db, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("TOKEN_BUDGET_FREE", "10")
    user = _user(Tier.FREE)

    # Should raise before any LLM call.
    with patch("app.pipeline.plan_generator.call_chat") as mock_call:
        with pytest.raises(budget.BudgetExceeded):
            generate_plan("Build a thing.", "general", user)
        mock_call.assert_not_called()


def test_generate_plan_handles_unconfigured_provider(tmp_db):
    user = _user()
    with patch(
        "app.pipeline.plan_generator.call_chat",
        side_effect=LLMNotConfigured("no key"),
    ):
        with pytest.raises(PlanGenerationError, match="no key"):
            generate_plan("Build a thing.", "general", user)


def test_generate_plan_rejects_short_output(tmp_db, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    user = _user()
    short = ChatResult(
        text="oops",
        model="anthropic/claude-haiku-4-5",
        prompt_tokens=10,
        completion_tokens=2,
        total_tokens=12,
    )
    with patch("app.pipeline.plan_generator.call_chat", return_value=short):
        with pytest.raises(PlanGenerationError, match="unusably short"):
            generate_plan("Build a thing.", "general", user)
