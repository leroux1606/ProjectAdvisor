"""
Risk Rules — deterministic checks for risk management completeness.
"""

from __future__ import annotations

import re

from app.pipeline.section_extractor import ExtractedSections
from app.rule_engine.models import RuleFinding, Severity


# Risk register signals
_REGISTER_RE = re.compile(
    r"\b(risk register|risk log|risk matrix|risk table|risk id)\b", re.IGNORECASE
)

# Mitigation signals
_MITIGATION_RE = re.compile(
    r"\b(mitigat|contingency|response|action|control|avoid|transfer|accept|reduce)\b",
    re.IGNORECASE,
)

# Risk owner signals
_OWNER_RE = re.compile(
    r"\b(owner|responsible|assigned to|risk owner|accountable)\b", re.IGNORECASE
)

# Probability/impact signals
_PROB_IMPACT_RE = re.compile(
    r"\b(probability|likelihood|impact|severity|high|medium|low|H|M|L|RAG|red|amber|green)\b",
    re.IGNORECASE,
)

# Required risk category coverage — at least some of these should appear
_RISK_CATEGORIES: dict[str, re.Pattern] = {
    "Schedule / timeline risk": re.compile(r"\b(schedule|delay|deadline|overrun|late)\b", re.IGNORECASE),
    "Resource / people risk": re.compile(r"\b(resource|staff|key person|dependency|availability|turnover|attrition)\b", re.IGNORECASE),
    "Technical / integration risk": re.compile(r"\b(technical|integration|system|technology|infrastructure|architecture|failure)\b", re.IGNORECASE),
    "Budget / cost risk": re.compile(r"\b(budget|cost|financ|overrun|spend|fund)\b", re.IGNORECASE),
    "Scope creep risk": re.compile(r"\b(scope|creep|change|expand|requirement)\b", re.IGNORECASE),
    "Regulatory / compliance risk": re.compile(r"\b(regulat|compliance|legal|gdpr|audit|policy|standard)\b", re.IGNORECASE),
}

# Minimum number of distinct risks expected
_MIN_RISK_COUNT_RE = re.compile(r"\brisk\s*[#\d:]", re.IGNORECASE)


def check_risks(sections: ExtractedSections) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    counter = 1

    def _id() -> str:
        nonlocal counter
        fid = f"RSK-{counter:03d}"
        counter += 1
        return fid

    # RSK — No risk section
    if not sections.risks:
        findings.append(RuleFinding(
            rule_id=_id(),
            category="risk",
            severity=Severity.CRITICAL,
            title="No risk section present",
            explanation="The plan contains no risk register, risk log, or risk management section.",
            suggested_fix=(
                "Create a Risk Register with columns for: Risk ID, Description, "
                "Probability, Impact, Owner, Mitigation, and Status."
            ),
            rule_name="RISK_SECTION_PRESENT",
        ))
        return findings

    text = sections.risks

    # RSK — No formal risk register
    if not _REGISTER_RE.search(text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="risk",
            severity=Severity.HIGH,
            title="No formal risk register detected",
            explanation=(
                "The risks section does not appear to contain a structured risk register. "
                "Ad-hoc risk lists without structure are difficult to track and manage."
            ),
            suggested_fix=(
                "Formalise risks in a structured register table with ID, description, "
                "probability, impact, owner, and mitigation columns."
            ),
            rule_name="FORMAL_RISK_REGISTER",
        ))

    # RSK — No mitigation strategies
    if not _MITIGATION_RE.search(text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="risk",
            severity=Severity.CRITICAL,
            title="No risk mitigation strategies documented",
            explanation=(
                "No mitigation, contingency, or response actions were detected in the risks section. "
                "Listing risks without mitigations provides no actionable protection."
            ),
            suggested_fix=(
                "For every risk, document a mitigation strategy: Avoid, Transfer, Reduce, or Accept. "
                "Include contingency plans for high-impact risks."
            ),
            rule_name="RISK_MITIGATIONS_PRESENT",
        ))

    # RSK — No risk owners
    if not _OWNER_RE.search(text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="risk",
            severity=Severity.HIGH,
            title="No risk owners assigned",
            explanation=(
                "Risks have no assigned owner. Without ownership, risks go unmonitored "
                "and mitigations are not actioned."
            ),
            suggested_fix="Assign a named owner to every risk who is responsible for monitoring and mitigation.",
            rule_name="RISK_OWNERS_ASSIGNED",
        ))

    # RSK — No probability/impact scoring
    if not _PROB_IMPACT_RE.search(text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="risk",
            severity=Severity.MEDIUM,
            title="Risks not scored for probability or impact",
            explanation=(
                "No probability, impact, or severity ratings were detected. "
                "Without scoring, risks cannot be prioritised."
            ),
            suggested_fix=(
                "Score each risk on a probability × impact matrix (e.g. High/Medium/Low). "
                "Use RAG (Red/Amber/Green) status for visibility."
            ),
            rule_name="RISK_SCORED",
        ))

    # RSK — Missing risk categories
    missing_categories = [
        cat for cat, pattern in _RISK_CATEGORIES.items()
        if not pattern.search(text)
    ]
    if len(missing_categories) >= 3:
        findings.append(RuleFinding(
            rule_id=_id(),
            category="risk",
            severity=Severity.MEDIUM,
            title=f"Risk register missing {len(missing_categories)} key risk categories",
            explanation=(
                f"The following common risk categories appear absent: "
                f"{', '.join(missing_categories[:3])}{'...' if len(missing_categories) > 3 else ''}."
            ),
            suggested_fix=(
                "Ensure all major risk categories are considered: Schedule, Resource, Technical, "
                "Budget, Scope Creep, and Regulatory/Compliance."
            ),
            rule_name="RISK_CATEGORY_COVERAGE",
        ))

    return findings
