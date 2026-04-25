"""
Tests for write-action verbs. LLM is mocked.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.auth import db as auth_db
from app.auth.models import Tier
from app.llm import budget, verbs
from app.llm.openrouter import ChatResult, LLMError


@pytest.fixture
def tmp_db(monkeypatch, tmp_path):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr(auth_db, "_DB_PATH", str(db_file))
    monkeypatch.delenv("BYPASS_PAYMENT", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
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


_ORIGINAL_PLAN = (
    "## Objectives\nDeliver Project Alpha to the customer by end of Q3 2026 "
    "with full acceptance and signoff from the steering committee.\n\n"
    "## Scope\nIn-scope: backend migration, API rewrite, customer onboarding. "
    "Out-of-scope: legacy reporting layer.\n\n"
    "## Timeline\nPhase 1 Apr–Jun 2026: discovery and design. "
    "Phase 2 Jul–Sep 2026: build and test.\n\n"
    "## Risks\nRisk 1: customer schedule slippage. Mitigation: weekly checkpoint.\n\n"
    "## Governance\nWeekly steering with sponsor and PM. Monthly board update.\n"
)

_REVISED_PLAN = _ORIGINAL_PLAN.replace(
    "## Timeline\nPhase 1 Apr–Jun 2026: discovery and design. "
    "Phase 2 Jul–Sep 2026: build and test.",
    "## Timeline\nPhase 1 (April 2026): discovery and design with sponsor signoff. "
    "Phase 2 (May 2026): solution architecture frozen. "
    "Phase 3 (June 2026): build complete. "
    "Phase 4 (July 2026): UAT and go-live preparation.",
)


def _ok_result(text: str = _REVISED_PLAN) -> ChatResult:
    return ChatResult(
        text=text,
        model="anthropic/claude-haiku-4-5",
        prompt_tokens=300,
        completion_tokens=600,
        total_tokens=900,
    )


def test_rewrite_section_validates_section(tmp_db):
    user = _user()
    with pytest.raises(verbs.VerbError, match="Unknown section"):
        verbs.rewrite_section(user, _ORIGINAL_PLAN, "NotARealSection", "")


def test_rewrite_section_normalises_case(tmp_db):
    user = _user()
    with patch("app.llm.verbs.call_chat", return_value=_ok_result()):
        proposal = verbs.rewrite_section(user, _ORIGINAL_PLAN, "timeline", "tighten")
    assert proposal.section == "Timeline"


def test_rewrite_section_returns_proposal(tmp_db):
    user = _user()
    with patch("app.llm.verbs.call_chat", return_value=_ok_result()):
        proposal = verbs.rewrite_section(user, _ORIGINAL_PLAN, "Timeline", "tighten")

    assert proposal.verb == verbs.Verb.REWRITE_SECTION
    assert "## Timeline" in proposal.proposed_plan_text
    assert proposal.completion_tokens == 600
    assert budget.get_status(user).used == 900


def test_regenerate_timeline_records_under_correct_purpose(tmp_db):
    user = _user()
    with patch("app.llm.verbs.call_chat", return_value=_ok_result()):
        verbs.regenerate_timeline(user, _ORIGINAL_PLAN, "add quarterly milestones")

    breakdown = auth_db.get_llm_usage_breakdown(user.id, since="0000-01-01")
    purposes = {row["purpose"] for row in breakdown}
    assert "regenerate_timeline" in purposes


def test_add_section_uses_add_section_purpose(tmp_db):
    user = _user()
    with patch("app.llm.verbs.call_chat", return_value=_ok_result()):
        verbs.add_section(user, _ORIGINAL_PLAN, "Budget", "include contingency")

    breakdown = auth_db.get_llm_usage_breakdown(user.id, since="0000-01-01")
    purposes = {row["purpose"] for row in breakdown}
    assert "add_section" in purposes


def test_verb_blocked_by_budget(tmp_db, monkeypatch):
    monkeypatch.setenv("TOKEN_BUDGET_FREE", "10")
    user = _user(Tier.FREE)
    with patch("app.llm.verbs.call_chat") as mock_call:
        with pytest.raises(budget.BudgetExceeded):
            verbs.rewrite_section(user, _ORIGINAL_PLAN, "Timeline", "tighten")
        mock_call.assert_not_called()


def test_verb_handles_llm_error(tmp_db):
    user = _user()
    with patch(
        "app.llm.verbs.call_chat",
        side_effect=LLMError("upstream offline"),
    ):
        with pytest.raises(verbs.VerbError, match="Could not generate"):
            verbs.rewrite_section(user, _ORIGINAL_PLAN, "Timeline", "tighten")


def test_verb_rejects_short_output(tmp_db):
    user = _user()
    short = ChatResult(
        text="oops",
        model="m",
        prompt_tokens=10,
        completion_tokens=2,
        total_tokens=12,
    )
    with patch("app.llm.verbs.call_chat", return_value=short):
        with pytest.raises(verbs.VerbError, match="unusably short"):
            verbs.rewrite_section(user, _ORIGINAL_PLAN, "Timeline", "tighten")


def test_instructions_length_limit(tmp_db):
    user = _user()
    with pytest.raises(verbs.VerbError, match="too long"):
        verbs.rewrite_section(user, _ORIGINAL_PLAN, "Timeline", "x" * 5000)
