"""
Report Generator — assembles a structured AuditReport from all pipeline outputs.
No LLM calls. Pure data assembly.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from app.pipeline.scoring_engine import ScoreBreakdown
from app.project_types import get_project_type_label
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
    project_type: str
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


def _to_json_safe(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, list):
        return [_to_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_json_safe(item) for key, item in value.items()}
    return value


def report_to_dict(report: AuditReport) -> dict:
    return _to_json_safe(asdict(report))


def report_to_json(report: AuditReport) -> str:
    return json.dumps(report_to_dict(report))


def report_from_dict(data: dict) -> AuditReport:
    def _finding(item: dict) -> RuleFinding:
        return RuleFinding(
            rule_id=item["rule_id"],
            category=item["category"],
            severity=Severity(item["severity"]),
            title=item["title"],
            explanation=item["explanation"],
            suggested_fix=item["suggested_fix"],
            rule_name=item["rule_name"],
        )

    def _insight(item: dict) -> AIInsight:
        return AIInsight(
            category=item["category"],
            title=item["title"],
            insight=item["insight"],
            suggestion=item["suggestion"],
        )

    def _category(item: dict) -> CategoryResult:
        return CategoryResult(
            category=item["category"],
            label=item["label"],
            rule_findings=[_finding(f) for f in item.get("rule_findings", [])],
            ai_insights=[_insight(i) for i in item.get("ai_insights", [])],
        )

    score_data = data["score_breakdown"]
    scores = ScoreBreakdown(
        structure=score_data["structure"],
        consistency=score_data["consistency"],
        timeline=score_data["timeline"],
        risk=score_data["risk"],
        resource=score_data["resource"],
        governance=score_data["governance"],
        overall=score_data["overall"],
        grade=score_data["grade"],
        top_issues=[_finding(f) for f in score_data.get("top_issues", [])],
    )

    return AuditReport(
        generated_at=data["generated_at"],
        source_name=data.get("source_name"),
        project_type=data.get("project_type", "general"),
        word_count=data["word_count"],
        sections_found=data.get("sections_found", []),
        sections_missing=data.get("sections_missing", []),
        overall_score=data["overall_score"],
        grade=data["grade"],
        score_breakdown=scores,
        top_issues=[_finding(f) for f in data.get("top_issues", [])],
        category_results=[_category(c) for c in data.get("category_results", [])],
        recommendations=[
            RecommendationItem(
                priority=item["priority"],
                category=item["category"],
                rule_id=item["rule_id"],
                title=item["title"],
                action=item["action"],
                severity=Severity(item["severity"]),
                rule_name=item["rule_name"],
            )
            for item in data.get("recommendations", [])
        ],
        ai_insights=[_insight(i) for i in data.get("ai_insights", [])],
        llm_enabled=data.get("llm_enabled", False),
    )


def report_from_json(raw: str) -> AuditReport:
    return report_from_dict(json.loads(raw))


def report_to_markdown(report: AuditReport) -> str:
    lines = [
        "# Project Plan Scrutinizer Report",
        "",
        f"- Generated: {report.generated_at}",
        f"- Source: {report.source_name or 'Pasted project plan'}",
        f"- Project type: {get_project_type_label(report.project_type)}",
        f"- Words: {report.word_count}",
        f"- Overall score: {report.overall_score} / 10",
        f"- Grade: {report.grade}",
        f"- Mode: {'Rule-based + AI Insights' if report.llm_enabled else 'Rule-based only'}",
        "",
        "## Sections",
        "",
        f"- Found: {', '.join(report.sections_found) if report.sections_found else 'None'}",
        f"- Missing: {', '.join(report.sections_missing) if report.sections_missing else 'None'}",
        "",
        "## Top Issues",
        "",
    ]

    if report.top_issues:
        for issue in report.top_issues:
            lines.extend(
                [
                    f"- [{issue.severity.value.upper()}] {issue.title}",
                    f"  - Rule: {issue.rule_id} · {issue.rule_name}",
                    f"  - Why: {issue.explanation}",
                    f"  - Fix: {issue.suggested_fix}",
                ]
            )
    else:
        lines.append("- No top issues recorded.")

    lines.extend(["", "## Recommendations", ""])
    if report.recommendations:
        for item in report.recommendations:
            lines.append(
                f"{item.priority}. {item.title} ({item.severity.value.upper()}) - {item.action}"
            )
    else:
        lines.append("No recommendations generated.")

    return "\n".join(lines)


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
    project_type: str,
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
        project_type=project_type,
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
