"""
Report Generator — assembles a structured AuditReport from all pipeline outputs.
No LLM calls. Pure data assembly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.analysis.models import AnalysisBundle, Finding, Severity
from app.pipeline.scoring_engine import ScoreBreakdown
from app.pipeline.section_extractor import ExtractedSections


@dataclass
class RecommendationItem:
    priority: int          # 1 = highest
    category: str
    title: str
    action: str
    severity: Severity


@dataclass
class FindingsGroup:
    category: str
    label: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.HIGH)


@dataclass
class AuditReport:
    generated_at: str
    source_name: Optional[str]
    word_count: int
    sections_found: list[str]
    sections_missing: list[str]
    overall_score: float
    grade: str
    score_breakdown: ScoreBreakdown
    top_issues: list[Finding]
    findings_groups: list[FindingsGroup]
    recommendations: list[RecommendationItem]


_SEVERITY_PRIORITY: dict[Severity, int] = {
    Severity.CRITICAL: 1,
    Severity.HIGH: 2,
    Severity.MEDIUM: 3,
    Severity.LOW: 4,
    Severity.INFO: 5,
}


def _build_recommendations(bundle: AnalysisBundle) -> list[RecommendationItem]:
    """Derive prioritised, actionable recommendations from all findings."""
    items: list[RecommendationItem] = []

    all_findings: list[Finding] = []
    for module in [bundle.structure, bundle.consistency, bundle.timeline,
                   bundle.risk, bundle.resource, bundle.governance]:
        if module:
            all_findings.extend(module.findings)

    # Deduplicate by title (case-insensitive)
    seen_titles: set[str] = set()
    unique_findings: list[Finding] = []
    for f in all_findings:
        key = f.title.lower().strip()
        if key not in seen_titles:
            seen_titles.add(key)
            unique_findings.append(f)

    # Sort: critical first, then by category
    unique_findings.sort(key=lambda f: (_SEVERITY_PRIORITY.get(f.severity, 99), f.category))

    for i, finding in enumerate(unique_findings, start=1):
        items.append(RecommendationItem(
            priority=i,
            category=finding.category,
            title=finding.title,
            action=finding.recommendation,
            severity=finding.severity,
        ))

    return items


def generate_report(
    source_name: Optional[str],
    word_count: int,
    sections: ExtractedSections,
    bundle: AnalysisBundle,
    scores: ScoreBreakdown,
) -> AuditReport:
    findings_groups: list[FindingsGroup] = [
        FindingsGroup(
            category="structure",
            label="Structure & Completeness",
            findings=bundle.structure.findings if bundle.structure else [],
        ),
        FindingsGroup(
            category="consistency",
            label="Internal Consistency",
            findings=bundle.consistency.findings if bundle.consistency else [],
        ),
        FindingsGroup(
            category="timeline",
            label="Timeline & Scheduling",
            findings=bundle.timeline.findings if bundle.timeline else [],
        ),
        FindingsGroup(
            category="risk",
            label="Risk Management",
            findings=bundle.risk.findings if bundle.risk else [],
        ),
        FindingsGroup(
            category="resource",
            label="Resource Planning",
            findings=bundle.resource.findings if bundle.resource else [],
        ),
        FindingsGroup(
            category="governance",
            label="Governance & Oversight",
            findings=bundle.governance.findings if bundle.governance else [],
        ),
    ]

    recommendations = _build_recommendations(bundle)

    return AuditReport(
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        source_name=source_name,
        word_count=word_count,
        sections_found=sections.present_sections(),
        sections_missing=sections.missing_sections(),
        overall_score=scores.overall,
        grade=scores.grade,
        score_breakdown=scores,
        top_issues=scores.top_issues,
        findings_groups=findings_groups,
        recommendations=recommendations,
    )
