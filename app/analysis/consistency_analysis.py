"""
Consistency Analysis Module — detects contradictions between plan sections.
"""

from __future__ import annotations

import json

from app.analysis.base import SYSTEM_PROMPT_BASE, parse_llm_json, section_text
from app.analysis.models import Finding, Severity, ConsistencyAnalysisResult
from app.pipeline.section_extractor import ExtractedSections
from app.utils.llm_client import call_llm

_SCHEMA = {
    "scope_deliverable_issues": ["list of mismatches between scope and deliverables"],
    "timeline_effort_issues": ["list of mismatches between timeline and effort/resources"],
    "resource_workload_issues": ["list of mismatches between resources and workload"],
    "findings": [
        {
            "id": "CON-001",
            "category": "consistency",
            "severity": "critical|high|medium|low|info",
            "title": "short title",
            "description": "detailed description",
            "recommendation": "actionable recommendation",
        }
    ],
    "consistency_score": "float 0-10",
}

_PROMPT = """Analyse the internal consistency of this project plan.

Check for contradictions and mismatches between:
1. Scope vs Deliverables — Are all deliverables within scope? Are scope items not reflected in deliverables?
2. Timeline vs Effort — Is the time allocated realistic given the tasks and team size?
3. Resources vs Workload — Are the listed resources sufficient for the described workload?
4. Objectives vs Deliverables — Do deliverables actually achieve the stated objectives?
5. Assumptions vs Constraints — Do they contradict each other?

{sections}

Return JSON matching this schema exactly:
{schema}
"""


def run_consistency_analysis(sections: ExtractedSections) -> ConsistencyAnalysisResult:
    sections_text = "\n\n".join([
        section_text(sections.objectives, "Objectives"),
        section_text(sections.scope, "Scope"),
        section_text(sections.deliverables, "Deliverables"),
        section_text(sections.timeline, "Timeline"),
        section_text(sections.resources, "Resources"),
        section_text(sections.assumptions, "Assumptions"),
        section_text(sections.constraints, "Constraints"),
    ])

    prompt = _PROMPT.format(
        sections=sections_text,
        schema=json.dumps(_SCHEMA, indent=2),
    )

    raw = call_llm(
        system_prompt=SYSTEM_PROMPT_BASE,
        user_prompt=prompt,
        temperature=0.0,
    )

    data = parse_llm_json(raw, context="consistency_analysis")

    findings = [
        Finding(
            id=f.get("id", f"CON-{i:03d}"),
            category="consistency",
            severity=Severity(f.get("severity", "medium")),
            title=f.get("title", ""),
            description=f.get("description", ""),
            recommendation=f.get("recommendation", ""),
        )
        for i, f in enumerate(data.get("findings", []), start=1)
    ]

    return ConsistencyAnalysisResult(
        scope_deliverable_issues=data.get("scope_deliverable_issues", []),
        timeline_effort_issues=data.get("timeline_effort_issues", []),
        resource_workload_issues=data.get("resource_workload_issues", []),
        findings=findings,
        consistency_score=float(data.get("consistency_score", 5.0)),
    )
