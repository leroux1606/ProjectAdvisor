"""
Structure Rules — deterministic checks for project plan completeness.
No LLM. Every rule is explicit, testable, and self-documenting.
"""

from __future__ import annotations

import re

from app.pipeline.section_extractor import ExtractedSections
from app.rule_engine.models import RuleFinding, Severity

# Minimum word counts per core section to be considered substantive
_MIN_WORDS: dict[str, int] = {
    "objectives":  20,
    "scope":       30,
    "deliverables": 25,
    "timeline":    20,
    "resources":   15,
    "risks":       20,
}

_CORE_SECTIONS = list(_MIN_WORDS.keys())

# SMART objective keyword signals
_SMART_MEASURABLE = re.compile(
    r"\b(\d+%|\d+ percent|kpi|metric|measur|quantif|target|benchmark)\b", re.IGNORECASE
)
_SMART_TIME_BOUND = re.compile(
    r"\b(by |deadline|due date|end of|q[1-4]|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{4})\b",
    re.IGNORECASE,
)

# Acceptance criteria signals
_ACCEPTANCE_CRITERIA = re.compile(
    r"\b(accept|criteria|done when|definition of done|sign.?off|approved by|verified)\b",
    re.IGNORECASE,
)


def check_structure(sections: ExtractedSections) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    counter = 1

    def _id() -> str:
        nonlocal counter
        fid = f"STR-{counter:03d}"
        counter += 1
        return fid

    # STR — Missing core sections
    for section in _CORE_SECTIONS:
        value = getattr(sections, section)
        if not value:
            findings.append(RuleFinding(
                rule_id=_id(),
                category="structure",
                severity=Severity.CRITICAL,
                title=f"Missing section: {section.capitalize()}",
                explanation=f"The '{section}' section is entirely absent from the project plan.",
                suggested_fix=f"Add a dedicated '{section.capitalize()}' section with substantive content.",
                rule_name="REQUIRED_SECTION_PRESENT",
            ))

    # STR — Sections below minimum word count
    for section, min_words in _MIN_WORDS.items():
        value = getattr(sections, section)
        if not value:
            continue  # already flagged as missing above
        word_count = len(value.split())
        if word_count < min_words:
            findings.append(RuleFinding(
                rule_id=_id(),
                category="structure",
                severity=Severity.HIGH,
                title=f"Thin section: {section.capitalize()} ({word_count} words)",
                explanation=(
                    f"The '{section}' section contains only {word_count} words, "
                    f"below the minimum of {min_words} expected for a substantive entry."
                ),
                suggested_fix=f"Expand the '{section.capitalize()}' section with more detail and specificity.",
                rule_name="SECTION_MINIMUM_CONTENT",
            ))

    # STR — Objectives not SMART: missing measurable element
    if sections.objectives:
        if not _SMART_MEASURABLE.search(sections.objectives):
            findings.append(RuleFinding(
                rule_id=_id(),
                category="structure",
                severity=Severity.MEDIUM,
                title="Objectives lack measurable success criteria",
                explanation=(
                    "No KPIs, metrics, percentages, or quantifiable targets were detected "
                    "in the Objectives section. SMART objectives require measurability."
                ),
                suggested_fix=(
                    "Add specific, measurable targets to each objective "
                    "(e.g. 'reduce processing time by 30%', 'achieve 99.9% uptime')."
                ),
                rule_name="SMART_OBJECTIVES_MEASURABLE",
            ))
        if not _SMART_TIME_BOUND.search(sections.objectives):
            findings.append(RuleFinding(
                rule_id=_id(),
                category="structure",
                severity=Severity.MEDIUM,
                title="Objectives are not time-bound",
                explanation=(
                    "No dates, quarters, or deadlines were detected in the Objectives section. "
                    "SMART objectives must specify when they will be achieved."
                ),
                suggested_fix="Add target dates or completion quarters to each objective.",
                rule_name="SMART_OBJECTIVES_TIME_BOUND",
            ))

    # STR — Deliverables missing acceptance criteria
    if sections.deliverables:
        if not _ACCEPTANCE_CRITERIA.search(sections.deliverables):
            findings.append(RuleFinding(
                rule_id=_id(),
                category="structure",
                severity=Severity.MEDIUM,
                title="Deliverables lack acceptance criteria",
                explanation=(
                    "No acceptance criteria, sign-off conditions, or 'definition of done' "
                    "language was detected in the Deliverables section."
                ),
                suggested_fix=(
                    "For each deliverable, define who approves it and what conditions "
                    "must be met before it is considered complete."
                ),
                rule_name="DELIVERABLES_ACCEPTANCE_CRITERIA",
            ))

    # STR — No budget section
    if not sections.budget:
        findings.append(RuleFinding(
            rule_id=_id(),
            category="structure",
            severity=Severity.LOW,
            title="No budget section present",
            explanation="The plan does not include a budget or cost estimate section.",
            suggested_fix="Add a Budget section with estimated costs, contingency, and approval authority.",
            rule_name="BUDGET_SECTION_PRESENT",
        ))

    # STR — No assumptions section
    if not sections.assumptions:
        findings.append(RuleFinding(
            rule_id=_id(),
            category="structure",
            severity=Severity.LOW,
            title="No assumptions documented",
            explanation=(
                "The plan does not list assumptions. Undocumented assumptions are a leading "
                "cause of scope creep and stakeholder misalignment."
            ),
            suggested_fix="Add an Assumptions section listing all conditions taken as true for planning purposes.",
            rule_name="ASSUMPTIONS_DOCUMENTED",
        ))

    return findings
