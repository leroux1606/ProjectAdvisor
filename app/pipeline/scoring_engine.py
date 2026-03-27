"""
Scoring Engine — deterministic aggregation of per-module scores into an overall score.
No LLM calls. Pure computation from AnalysisBundle.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.analysis.models import AnalysisBundle, Finding, Severity


# Category weights must sum to 1.0
_WEIGHTS: dict[str, float] = {
    "structure": 0.25,
    "consistency": 0.20,
    "timeline": 0.20,
    "risk": 0.20,
    "resource": 0.10,
    "governance": 0.05,
}

_SEVERITY_PENALTY: dict[Severity, float] = {
    Severity.CRITICAL: 2.0,
    Severity.HIGH: 1.0,
    Severity.MEDIUM: 0.5,
    Severity.LOW: 0.2,
    Severity.INFO: 0.0,
}


@dataclass
class ScoreBreakdown:
    structure: float
    consistency: float
    timeline: float
    risk: float
    resource: float
    governance: float
    overall: float
    grade: str
    top_issues: list[Finding] = field(default_factory=list)


def _grade(score: float) -> str:
    if score >= 8.5:
        return "A"
    if score >= 7.0:
        return "B"
    if score >= 5.5:
        return "C"
    if score >= 4.0:
        return "D"
    return "F"


def _clamp(value: float, lo: float = 0.0, hi: float = 10.0) -> float:
    return max(lo, min(hi, value))


def _module_score(base_score: float, findings: list[Finding]) -> float:
    """Apply penalty from findings on top of the LLM-reported base score."""
    penalty = sum(_SEVERITY_PENALTY.get(f.severity, 0.0) for f in findings)
    adjusted = base_score - (penalty * 0.3)
    return _clamp(adjusted)


def compute_scores(bundle: AnalysisBundle) -> ScoreBreakdown:
    structure_score = _module_score(
        bundle.structure.completeness_score if bundle.structure else 0.0,
        bundle.structure.findings if bundle.structure else [],
    )
    consistency_score = _module_score(
        bundle.consistency.consistency_score if bundle.consistency else 0.0,
        bundle.consistency.findings if bundle.consistency else [],
    )
    timeline_score = _module_score(
        bundle.timeline.timeline_score if bundle.timeline else 0.0,
        bundle.timeline.findings if bundle.timeline else [],
    )
    risk_score = _module_score(
        bundle.risk.risk_score if bundle.risk else 0.0,
        bundle.risk.findings if bundle.risk else [],
    )
    resource_score = _module_score(
        bundle.resource.resource_score if bundle.resource else 0.0,
        bundle.resource.findings if bundle.resource else [],
    )
    governance_score = _module_score(
        bundle.governance.governance_score if bundle.governance else 0.0,
        bundle.governance.findings if bundle.governance else [],
    )

    overall = (
        structure_score * _WEIGHTS["structure"]
        + consistency_score * _WEIGHTS["consistency"]
        + timeline_score * _WEIGHTS["timeline"]
        + risk_score * _WEIGHTS["risk"]
        + resource_score * _WEIGHTS["resource"]
        + governance_score * _WEIGHTS["governance"]
    )
    overall = _clamp(overall)

    # Collect all findings and sort by severity for top issues
    all_findings: list[Finding] = []
    for module in [bundle.structure, bundle.consistency, bundle.timeline,
                   bundle.risk, bundle.resource, bundle.governance]:
        if module:
            all_findings.extend(module.findings)

    severity_order = {
        Severity.CRITICAL: 0,
        Severity.HIGH: 1,
        Severity.MEDIUM: 2,
        Severity.LOW: 3,
        Severity.INFO: 4,
    }
    all_findings.sort(key=lambda f: severity_order.get(f.severity, 99))
    top_issues = all_findings[:5]

    return ScoreBreakdown(
        structure=round(structure_score, 1),
        consistency=round(consistency_score, 1),
        timeline=round(timeline_score, 1),
        risk=round(risk_score, 1),
        resource=round(resource_score, 1),
        governance=round(governance_score, 1),
        overall=round(overall, 1),
        grade=_grade(overall),
        top_issues=top_issues,
    )
