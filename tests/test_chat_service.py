"""
Tests for the read-only chat service. LLM is mocked.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.auth import db as auth_db
from app.auth.models import Tier
from app.llm import budget
from app.llm.chat_service import ChatError, chat_turn
from app.llm.openrouter import ChatResult, LLMError
from app.pipeline.scoring_engine import ScoreBreakdown
from app.pipeline.report_generator import AuditReport
from app.rule_engine.models import (
    CategoryResult,
    RuleFinding,
    Severity,
)


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


def _report() -> AuditReport:
    finding = RuleFinding(
        rule_id="STR-001",
        category="structure",
        severity=Severity.HIGH,
        title="Missing objectives section",
        explanation="The plan does not contain an objectives section.",
        suggested_fix="Add an Objectives section.",
        rule_name="STRUCTURE_OBJECTIVES_PRESENT",
    )
    cat = CategoryResult(
        category="structure",
        label="Structure",
        rule_findings=[finding],
        ai_insights=[],
    )
    scores = ScoreBreakdown(
        structure=4.0,
        consistency=8.0,
        timeline=7.0,
        risk=6.0,
        resource=5.0,
        governance=5.0,
        overall=5.5,
        grade="C",
        top_issues=[finding],
    )
    return AuditReport(
        generated_at="2026-04-25",
        source_name="test.txt",
        project_type="general",
        word_count=500,
        sections_found=["scope", "timeline"],
        sections_missing=["objectives"],
        overall_score=5.5,
        grade="C",
        score_breakdown=scores,
        top_issues=[finding],
        category_results=[cat],
        recommendations=[],
        ai_insights=[],
        llm_enabled=False,
    )


def test_empty_message_rejected(tmp_db):
    user = _user()
    with pytest.raises(ChatError):
        chat_turn(user, None, "plan text", _report(), [], "")


def test_too_long_message_rejected(tmp_db):
    user = _user()
    with pytest.raises(ChatError, match="too long"):
        chat_turn(user, None, "plan text", _report(), [], "x" * 9999)


def test_chat_turn_persists_messages(tmp_db):
    user = _user()
    fake = ChatResult(
        text="Sure — your plan lacks objectives.",
        model="anthropic/claude-haiku-4-5",
        prompt_tokens=200,
        completion_tokens=50,
        total_tokens=250,
    )
    with patch("app.llm.chat_service.call_chat", return_value=fake):
        result = chat_turn(
            user,
            analysis_run_id=None,
            plan_text="A short plan body.",
            report=_report(),
            history=[],
            user_message="What's missing?",
        )

    assert "objectives" in result.reply.lower()
    rows = auth_db.get_chat_messages(user.id, None)
    assert len(rows) == 2
    assert rows[0]["role"] == "user"
    assert rows[1]["role"] == "assistant"
    assert budget.get_status(user).used == 250


def test_chat_turn_blocked_by_budget(tmp_db, monkeypatch):
    monkeypatch.setenv("TOKEN_BUDGET_FREE", "10")
    user = _user(Tier.FREE)
    with patch("app.llm.chat_service.call_chat") as mock_call:
        with pytest.raises(budget.BudgetExceeded):
            chat_turn(
                user,
                analysis_run_id=None,
                plan_text="A short plan body.",
                report=_report(),
                history=[],
                user_message="What's missing?",
            )
        mock_call.assert_not_called()


def test_chat_turn_handles_llm_error(tmp_db):
    user = _user()
    with patch(
        "app.llm.chat_service.call_chat",
        side_effect=LLMError("upstream offline"),
    ):
        with pytest.raises(ChatError, match="Could not reply"):
            chat_turn(
                user,
                analysis_run_id=None,
                plan_text="A plan.",
                report=_report(),
                history=[],
                user_message="hi",
            )


def test_history_is_trimmed(tmp_db):
    user = _user()
    fake = ChatResult(
        text="ok",
        model="m",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
    )
    long_history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"}
        for i in range(60)
    ]
    with patch("app.llm.chat_service.call_chat", return_value=fake) as mock:
        chat_turn(
            user,
            analysis_run_id=None,
            plan_text="A plan.",
            report=_report(),
            history=long_history,
            user_message="next",
        )
    sent_messages = mock.call_args.kwargs["messages"]
    # 2 system + at most 24 trimmed history + 1 new user
    assert len(sent_messages) <= 2 + 24 + 1
