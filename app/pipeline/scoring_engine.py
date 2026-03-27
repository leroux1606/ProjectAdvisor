"""
Scoring Engine — fully deterministic scoring from rule-based findings.
No LLM calls. Score is computed purely from issue count and severity weights.

Formula per category:
  base_score = 10.0
  penalty    = sum(SEVERITY_PENALTY[sev] for each finding)
  raw_score  = base_score - penalty
  score      = clamp(raw_score, 0, 10)

Overall score = weighted average of category scores.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.rule_engine.models import HybridBundle, RuleFinding, Severity


# Penalty deducted per finding at each severity level
_SEVERITY_PENALTY: dict[Severity, float] = {
    Severity.CRITICAL: 3.0,
    Severity.HIGH:     1.5,
    Severity.MEDIUM:   0.7,
    Severity.LOW:      0.3,
    Severity.INFO:     0.0,
}

# Category weights — must sum to 1.0
_WEIGHTS: dict[str, float] = {
    "structure":   0.25,
    "consistency": 0.15,
    "timeline":    0.20,
    "risk":        0.20,
    "resource":    0.12,
    "governance":  0.08,
}

_SEVERITY_ORDER: dict[Severity, int] = {
    Severity.CRITICAL: 0,
    Severity.HIGH:     1,
    Severity.MEDIUM:   2,
    Severity.LOW:      3,
    Severity.INFO:     4,
}


@dataclass
class ScoreBreakdown:
    structure:   float
    consistency: float
    timeline:    float
    risk:        float
    resource:    float
    governance:  float
    overall:     float
    grade:       str
    top_issues:  list[RuleFinding] = field(default_factory=list)


def _clamp(value: float, lo: float = 0.0, hi: float = 10.0) -> float:
    return max(lo, min(hi, value))


def _category_score(findings: list[RuleFinding]) -> float:
    penalty = sum(_SEVERITY_PENALTY.get(f.severity, 0.0) for f in findings)
    return _clamp(10.0 - penalty)


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


def compute_scores(bundle: HybridBundle) -> ScoreBreakdown:
    structure_score   = _category_score(bundle.structure.rule_findings   if bundle.structure   else [])
    consistency_score = _category_score(bundle.consistency.rule_findings if bundle.consistency else [])
    timeline_score    = _category_score(bundle.timeline.rule_findings    if bundle.timeline    else [])
    risk_score        = _category_score(bundle.risk.rule_findings        if bundle.risk        else [])
    resource_score    = _category_score(bundle.resource.rule_findings    if bundle.resource    else [])
    governance_score  = _category_score(bundle.governance.rule_findings  if bundle.governance  else [])

    overall = (
        structure_score   * _WEIGHTS["structure"]
        + consistency_score * _WEIGHTS["consistency"]
        + timeline_score    * _WEIGHTS["timeline"]
        + risk_score        * _WEIGHTS["risk"]
        + resource_score    * _WEIGHTS["resource"]
        + governance_score  * _WEIGHTS["governance"]
    )
    overall = _clamp(overall)

    # Top issues: sorted by severity, then category
    all_findings = bundle.all_rule_findings()
    all_findings.sort(key=lambda f: (_SEVERITY_ORDER.get(f.severity, 99), f.category))
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
