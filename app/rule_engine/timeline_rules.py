"""
Timeline Rules — deterministic checks for schedule realism and completeness.
Parses timeline text for task/duration patterns without an LLM.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.pipeline.section_extractor import ExtractedSections
from app.rule_engine.models import RuleFinding, Severity


# Matches lines like: "Task name - 1 day", "Phase 1: 2 weeks", "Step 3 (3 hours)"
_TASK_DURATION_RE = re.compile(
    r"(?P<task>[^\n:–\-]{5,60})"          # task name
    r"[\s:–\-–—]+?"
    r"(?P<qty>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>hour|day|week|month|sprint)s?",
    re.IGNORECASE,
)

# Dependency signal words
_DEPENDENCY_RE = re.compile(
    r"\b(depends on|after|following|preceded by|blocked by|requires completion|upon completion of)\b",
    re.IGNORECASE,
)

# Milestone signal words
_MILESTONE_RE = re.compile(
    r"\b(milestone|gate|go.?live|launch|release|sign.?off|go/no.?go|phase.?complete)\b",
    re.IGNORECASE,
)

# Contingency / buffer signal
_BUFFER_RE = re.compile(
    r"\b(buffer|contingency|float|slack|reserve|padding)\b",
    re.IGNORECASE,
)

# Review / testing signal
_REVIEW_RE = re.compile(
    r"\b(review|test|uat|qa|quality assurance|sign.?off|approval|pilot)\b",
    re.IGNORECASE,
)

# Duration thresholds in days considered unrealistically short per task type
_COMPLEX_TASK_KEYWORDS = re.compile(
    r"\b(architecture|design|migration|integration|deployment|infrastructure|security|"
    r"development|implement|build|creat|develop|deliver)\b",
    re.IGNORECASE,
)
_MIN_DAYS_COMPLEX = 3  # below this is suspicious for a complex task


@dataclass
class _ParsedTask:
    name: str
    duration_days: float
    line: str


def _to_days(qty: float, unit: str) -> float:
    unit = unit.lower()
    if "hour" in unit:
        return qty / 8
    if "week" in unit:
        return qty * 5
    if "month" in unit:
        return qty * 20
    if "sprint" in unit:
        return qty * 10
    return qty  # days


def _parse_tasks(text: str) -> list[_ParsedTask]:
    tasks = []
    for match in _TASK_DURATION_RE.finditer(text):
        qty = float(match.group("qty"))
        unit = match.group("unit")
        days = _to_days(qty, unit)
        tasks.append(_ParsedTask(
            name=match.group("task").strip(),
            duration_days=days,
            line=match.group(0),
        ))
    return tasks


def check_timeline(sections: ExtractedSections) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    counter = 1

    def _id() -> str:
        nonlocal counter
        fid = f"TML-{counter:03d}"
        counter += 1
        return fid

    # TML — No timeline section
    if not sections.timeline:
        findings.append(RuleFinding(
            rule_id=_id(),
            category="timeline",
            severity=Severity.CRITICAL,
            title="No timeline section present",
            explanation="The plan contains no timeline, schedule, or phasing information.",
            suggested_fix="Add a Timeline section with phases, tasks, durations, and target dates.",
            rule_name="TIMELINE_SECTION_PRESENT",
        ))
        return findings

    text = sections.timeline

    # TML — No milestones
    if not _MILESTONE_RE.search(text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="timeline",
            severity=Severity.HIGH,
            title="No milestones defined",
            explanation=(
                "The timeline contains no milestones, phase gates, or key decision points. "
                "Without milestones, progress cannot be formally tracked."
            ),
            suggested_fix="Define at least 3 milestones with target dates and completion criteria.",
            rule_name="MILESTONES_DEFINED",
        ))

    # TML — No task dependencies
    if not _DEPENDENCY_RE.search(text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="timeline",
            severity=Severity.HIGH,
            title="No task dependencies documented",
            explanation=(
                "No dependency language was found in the timeline. Tasks without explicit "
                "dependencies cannot be sequenced correctly, risking parallel work conflicts."
            ),
            suggested_fix=(
                "Document predecessor/successor relationships for all tasks. "
                "Consider producing a Gantt chart or network diagram."
            ),
            rule_name="TASK_DEPENDENCIES_DOCUMENTED",
        ))

    # TML — No contingency buffer
    if not _BUFFER_RE.search(text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="timeline",
            severity=Severity.MEDIUM,
            title="No schedule contingency or buffer",
            explanation=(
                "The timeline does not mention buffer time, float, or contingency. "
                "Plans without schedule reserve routinely overrun."
            ),
            suggested_fix="Add 10–20% schedule buffer for each phase, documented explicitly.",
            rule_name="SCHEDULE_BUFFER_PRESENT",
        ))

    # TML — No review/testing time
    if not _REVIEW_RE.search(text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="timeline",
            severity=Severity.MEDIUM,
            title="No review, testing, or UAT time allocated",
            explanation=(
                "The timeline does not include review, QA, UAT, or sign-off activities. "
                "These are non-negotiable for professional delivery."
            ),
            suggested_fix=(
                "Explicitly schedule review and testing phases. "
                "Allow at least 10–15% of total project time for QA and acceptance."
            ),
            rule_name="REVIEW_TIME_ALLOCATED",
        ))

    # TML — Parse tasks and check for unrealistically short durations
    tasks = _parse_tasks(text)
    for task in tasks:
        if (
            task.duration_days < _MIN_DAYS_COMPLEX
            and _COMPLEX_TASK_KEYWORDS.search(task.name)
        ):
            findings.append(RuleFinding(
                rule_id=_id(),
                category="timeline",
                severity=Severity.HIGH,
                title=f"Unrealistic duration: '{task.name[:50]}'",
                explanation=(
                    f"Task '{task.name[:60]}' is assigned {task.duration_days:.1f} day(s), "
                    f"which is unrealistically short for a complex technical activity."
                ),
                suggested_fix=(
                    f"Re-estimate '{task.name[:40]}'. Complex tasks rarely complete in under "
                    f"{_MIN_DAYS_COMPLEX} days. Include design, build, and test cycles."
                ),
                rule_name="UNREALISTIC_TASK_DURATION",
            ))

    # TML — Single-day timeline for entire project
    if tasks:
        total_days = sum(t.duration_days for t in tasks)
        if total_days < 5:
            findings.append(RuleFinding(
                rule_id=_id(),
                category="timeline",
                severity=Severity.CRITICAL,
                title=f"Total scheduled effort is only {total_days:.1f} day(s)",
                explanation=(
                    f"The sum of all detected task durations is {total_days:.1f} days, "
                    "which is implausibly short for a complete project."
                ),
                suggested_fix="Review all task estimates. The total schedule appears incomplete or incorrect.",
                rule_name="TOTAL_DURATION_PLAUSIBLE",
            ))

    return findings
