"""
Report Generator — assembles a structured AuditReport from all pipeline outputs.
No LLM calls. Pure data assembly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.pipeline.scoring_engine import ScoreBreakdown
from app.pipeline.section_extractor import ExtractedSections
from app.rule_engine.models import AIInsight, CategoryResult, HybridBundle, RuleFinding, Severity


_SEVERITY_PRIORITY: dict[Severity, int] = {
    Severity.CRITICAL: 1,
    Severity.HIGH: 2,
    Severity.MEDIUM: 3,
    Severity.LOW: 4,
    Severity.INFO: 5,
}


@dataclass
class RecommendationItem:
    priority: int
    category: str
    rule_id: str
    title: str
    action: str
    severity: Severity
    rule_name: str


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
    top_issues: list[RuleFinding]
    category_results: list[CategoryResult]
    recommendations: list[RecommendationItem]
    ai_insights: list[AIInsight]
    llm_enabled: bool


def _build_recommendations(bundle: HybridBundle) -> list[RecommendationItem]:
    all_findings = bundle.all_rule_findings()

    # Deduplicate by title (case-insensitive)
    seen: set[str] = set()
    unique: list[RuleFinding] = []
    for f in all_findings:
        key = f.title.lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(f)

    unique.sort(key=lambda f: (_SEVERITY_PRIORITY.get(f.severity, 99), f.category))

    return [
        RecommendationItem(
            priority=i,
            category=f.category,
            rule_id=f.rule_id,
            title=f.title,
            action=f.suggested_fix,
            severity=f.severity,
            rule_name=f.rule_name,
        )
        for i, f in enumerate(unique, start=1)
    ]


def generate_report(
    source_name: Optional[str],
    word_count: int,
    sections: ExtractedSections,
    bundle: HybridBundle,
    scores: ScoreBreakdown,
    llm_enabled: bool = False,
) -> AuditReport:
    category_order = [
        bundle.structure,
        bundle.consistency,
        bundle.timeline,
        bundle.risk,
        bundle.resource,
        bundle.governance,
    ]
    category_results = [c for c in category_order if c is not None]
    recommendations = _build_recommendations(bundle)
    all_insights = bundle.all_ai_insights()

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
        category_results=category_results,
        recommendations=recommendations,
        ai_insights=all_insights,
        llm_enabled=llm_enabled,
    )
