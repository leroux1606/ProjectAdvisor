"""
Governance Rules — deterministic checks for oversight, change control, and reporting.
"""

from __future__ import annotations

import re

from app.pipeline.section_extractor import ExtractedSections
from app.rule_engine.models import RuleFinding, Severity


_SPONSOR_RE = re.compile(
    r"\b(sponsor|executive sponsor|business owner|steering|project board|senior responsible)\b",
    re.IGNORECASE,
)
_CHANGE_CONTROL_RE = re.compile(
    r"\b(change control|change request|change management|change board|change log|change register|ccb)\b",
    re.IGNORECASE,
)
_ESCALATION_RE = re.compile(
    r"\b(escalat|escalation path|escalation process|issue log|issue register|raise.*issue)\b",
    re.IGNORECASE,
)
_REPORTING_RE = re.compile(
    r"\b(status report|progress report|dashboard|weekly|monthly|reporting|highlight report|checkpoint)\b",
    re.IGNORECASE,
)
_STAGE_GATE_RE = re.compile(
    r"\b(stage gate|phase review|go.?no.?go|tollgate|phase.?end|end stage|project board review)\b",
    re.IGNORECASE,
)
_LESSONS_RE = re.compile(
    r"\b(lessons learned|lessons learnt|retrospective|post.?project|post.?implementation review|pir)\b",
    re.IGNORECASE,
)


def _check_section(text: str | None) -> str:
    """Return governance text from either dedicated section or fallback to full plan."""
    return text or ""


def check_governance(sections: ExtractedSections) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    counter = 1

    def _id() -> str:
        nonlocal counter
        fid = f"GOV-{counter:03d}"
        counter += 1
        return fid

    # Governance evidence may appear in the governance section OR elsewhere in the plan
    gov_text = sections.governance or ""
    full_text = " ".join(filter(None, [
        sections.objectives, sections.scope, sections.deliverables,
        sections.timeline, sections.resources, sections.risks,
        sections.governance, sections.assumptions, sections.constraints,
    ]))

    # GOV — No sponsor / executive ownership
    if not _SPONSOR_RE.search(full_text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="governance",
            severity=Severity.CRITICAL,
            title="No project sponsor or executive owner identified",
            explanation=(
                "No sponsor, project board, or senior responsible owner was identified anywhere "
                "in the plan. Without executive ownership, the project lacks authority to proceed "
                "and has no escalation path."
            ),
            suggested_fix=(
                "Name the project sponsor and define their responsibilities. "
                "Establish a project board or steering committee with named members."
            ),
            rule_name="SPONSOR_IDENTIFIED",
        ))

    # GOV — No change control process
    if not _CHANGE_CONTROL_RE.search(full_text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="governance",
            severity=Severity.HIGH,
            title="No change control process defined",
            explanation=(
                "The plan does not define a change control process. Without this, scope changes "
                "are uncontrolled, leading to scope creep, budget overruns, and delayed delivery."
            ),
            suggested_fix=(
                "Define a change control process: how changes are requested, assessed, "
                "approved, and communicated. Assign a Change Authority."
            ),
            rule_name="CHANGE_CONTROL_DEFINED",
        ))

    # GOV — No escalation path
    if not _ESCALATION_RE.search(full_text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="governance",
            severity=Severity.HIGH,
            title="No escalation path or issue management process",
            explanation=(
                "No escalation path or issue management process was detected. "
                "Issues that cannot be resolved at team level need a defined route to management."
            ),
            suggested_fix=(
                "Document the escalation hierarchy and issue management process. "
                "Maintain an Issue Log with owners and resolution dates."
            ),
            rule_name="ESCALATION_PATH_DEFINED",
        ))

    # GOV — No reporting cadence
    if not _REPORTING_RE.search(full_text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="governance",
            severity=Severity.MEDIUM,
            title="No reporting cadence defined",
            explanation=(
                "The plan does not define how and when project status will be reported "
                "to stakeholders. This makes it impossible to track progress formally."
            ),
            suggested_fix=(
                "Define a reporting cadence: weekly status reports to the team, "
                "monthly highlight reports to the sponsor, dashboard updates for stakeholders."
            ),
            rule_name="REPORTING_CADENCE_DEFINED",
        ))

    # GOV — No stage gates or phase reviews
    if not _STAGE_GATE_RE.search(full_text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="governance",
            severity=Severity.MEDIUM,
            title="No stage gates or phase review points",
            explanation=(
                "The plan does not define formal phase reviews or stage gates. "
                "Without these checkpoints, the project proceeds without formal authorisation "
                "between phases, a core PRINCE2 requirement."
            ),
            suggested_fix=(
                "Define stage gates at major phase transitions with go/no-go criteria. "
                "Require project board sign-off before proceeding to the next phase."
            ),
            rule_name="STAGE_GATES_DEFINED",
        ))

    # GOV — No lessons learned
    if not _LESSONS_RE.search(full_text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="governance",
            severity=Severity.LOW,
            title="No lessons learned or post-project review planned",
            explanation=(
                "The plan does not include a lessons learned session or post-implementation review. "
                "This is standard practice in PRINCE2 and PMBOK."
            ),
            suggested_fix=(
                "Schedule a post-project review or retrospective. "
                "Document lessons learned and feed them back into organisational standards."
            ),
            rule_name="LESSONS_LEARNED_PLANNED",
        ))

    return findings
