"""
Consistency Rules — deterministic cross-section coherence checks.
Looks for keyword mismatches and structural gaps across sections.
"""

from __future__ import annotations

import re

from app.pipeline.section_extractor import ExtractedSections
from app.rule_engine.models import RuleFinding, Severity


def _word_set(text: str | None) -> set[str]:
    """Return lowercase word tokens from text, min 4 chars, no stopwords."""
    if not text:
        return set()
    stopwords = {
        "this", "that", "with", "from", "will", "have", "been", "they",
        "their", "into", "each", "which", "also", "would", "should",
        "project", "plan", "team", "work", "task", "phase",
    }
    tokens = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
    return {t for t in tokens if t not in stopwords}


def _overlap_ratio(set_a: set[str], set_b: set[str]) -> float:
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / min(len(set_a), len(set_b))


# Duration / effort signals in timeline
_EFFORT_RE = re.compile(
    r"\b(\d+)\s*(day|week|month|sprint|hour)s?\b", re.IGNORECASE
)

# Team size signals in resources
_TEAM_SIZE_RE = re.compile(
    r"\b(\d+)\s*(developer|engineer|analyst|tester|person|people|member|staff|fte)\b",
    re.IGNORECASE,
)


def check_consistency(sections: ExtractedSections) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    counter = 1

    def _id() -> str:
        nonlocal counter
        fid = f"CON-{counter:03d}"
        counter += 1
        return fid

    # CON — Scope vs Deliverables vocabulary overlap
    scope_words = _word_set(sections.scope)
    deliverable_words = _word_set(sections.deliverables)
    if scope_words and deliverable_words:
        ratio = _overlap_ratio(scope_words, deliverable_words)
        if ratio < 0.15:
            findings.append(RuleFinding(
                rule_id=_id(),
                category="consistency",
                severity=Severity.HIGH,
                title="Low vocabulary overlap between Scope and Deliverables",
                explanation=(
                    f"Scope and Deliverables share only {ratio:.0%} of their key terms. "
                    "This suggests deliverables may not fully address what is in scope, "
                    "or scope items exist with no corresponding deliverable."
                ),
                suggested_fix=(
                    "Review each scope item and ensure at least one deliverable corresponds to it. "
                    "Remove deliverables that fall outside the defined scope."
                ),
                rule_name="SCOPE_DELIVERABLE_ALIGNMENT",
            ))

    # CON — Objectives vs Deliverables vocabulary overlap
    objective_words = _word_set(sections.objectives)
    if objective_words and deliverable_words:
        ratio = _overlap_ratio(objective_words, deliverable_words)
        if ratio < 0.10:
            findings.append(RuleFinding(
                rule_id=_id(),
                category="consistency",
                severity=Severity.MEDIUM,
                title="Deliverables appear misaligned with Objectives",
                explanation=(
                    f"Objectives and Deliverables share only {ratio:.0%} of key terms. "
                    "Deliverables should directly enable the stated objectives."
                ),
                suggested_fix=(
                    "Map each deliverable back to at least one objective. "
                    "Remove or revise deliverables that do not contribute to objectives."
                ),
                rule_name="OBJECTIVES_DELIVERABLE_ALIGNMENT",
            ))

    # CON — Timeline references tasks not in scope or deliverables
    timeline_words = _word_set(sections.timeline)
    scope_and_deliverable_words = scope_words | deliverable_words
    if timeline_words and scope_and_deliverable_words:
        ratio = _overlap_ratio(timeline_words, scope_and_deliverable_words)
        if ratio < 0.12:
            findings.append(RuleFinding(
                rule_id=_id(),
                category="consistency",
                severity=Severity.MEDIUM,
                title="Timeline tasks appear disconnected from scope and deliverables",
                explanation=(
                    f"Only {ratio:.0%} key term overlap between Timeline and Scope+Deliverables. "
                    "Timeline tasks should directly correspond to in-scope work and deliverables."
                ),
                suggested_fix=(
                    "Ensure every task in the timeline maps to a deliverable or scope item. "
                    "Remove tasks that are not reflected in scope, or update scope accordingly."
                ),
                rule_name="TIMELINE_SCOPE_ALIGNMENT",
            ))

    # CON — Large team but short timeline (rough effort check)
    if sections.resources and sections.timeline:
        effort_matches = _EFFORT_RE.findall(sections.timeline)
        team_matches = _TEAM_SIZE_RE.findall(sections.resources)

        # Estimate total person-days in timeline
        unit_map = {"hour": 0.125, "day": 1, "week": 5, "month": 20, "sprint": 10}
        total_effort = sum(
            int(qty) * unit_map.get(unit.lower().rstrip("s"), 1)
            for qty, unit in effort_matches
        )

        # Estimate team size
        team_size = max((int(qty) for qty, _ in team_matches), default=0)

        if team_size >= 5 and total_effort > 0 and total_effort < team_size * 5:
            findings.append(RuleFinding(
                rule_id=_id(),
                category="consistency",
                severity=Severity.HIGH,
                title="Team size is large relative to scheduled effort",
                explanation=(
                    f"The resource plan suggests ~{team_size} people, but the timeline "
                    f"totals only ~{total_effort:.0f} person-days. "
                    "This either indicates tasks are missing from the timeline or "
                    "resources are over-provisioned."
                ),
                suggested_fix=(
                    "Reconcile the timeline with the resource plan. "
                    "Ensure all work packages are scheduled and assigned."
                ),
                rule_name="EFFORT_RESOURCE_BALANCE",
            ))

    # CON — Risks reference technologies/systems not in scope
    if sections.risks and sections.scope:
        risk_words = _word_set(sections.risks)
        # Flag if risks section is much larger vocabulary than scope (signs of out-of-scope risks)
        if len(risk_words) > len(scope_words) * 2 and scope_words:
            findings.append(RuleFinding(
                rule_id=_id(),
                category="consistency",
                severity=Severity.LOW,
                title="Risk register vocabulary significantly exceeds scope",
                explanation=(
                    "The risks section references significantly more domain terms than the scope, "
                    "which may indicate risks are documented for out-of-scope areas."
                ),
                suggested_fix=(
                    "Review the risk register and confirm each risk is relevant to the defined scope. "
                    "Remove or annotate risks relating to out-of-scope systems."
                ),
                rule_name="RISK_SCOPE_ALIGNMENT",
            ))

    return findings
