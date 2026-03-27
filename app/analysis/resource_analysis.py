"""
Resource Analysis Module — detects over-allocation, missing roles, skill gaps.
"""

from __future__ import annotations

import json

from app.analysis.base import SYSTEM_PROMPT_BASE, parse_llm_json, section_text
from app.analysis.models import Finding, Severity, ResourceAnalysisResult
from app.pipeline.section_extractor import ExtractedSections
from app.utils.llm_client import call_llm

_SCHEMA = {
    "over_allocated": ["list of resources or roles that appear over-committed"],
    "missing_roles": ["list of roles required by the plan but not listed in resources"],
    "skill_mismatches": ["list of tasks that require skills not present in the listed team"],
    "findings": [
        {
            "id": "RES-001",
            "category": "resource",
            "severity": "critical|high|medium|low|info",
            "title": "short title",
            "description": "detailed description",
            "recommendation": "actionable recommendation",
        }
    ],
    "resource_score": "float 0-10",
}

_PROMPT = """Analyse the resource planning section of this project plan.

Evaluate:
1. Are all required roles explicitly listed?
2. Are resources assigned to specific tasks or phases?
3. Are any individuals or teams assigned to multiple parallel tasks without sufficient capacity?
4. Are specialist skills required (e.g. security, architecture, testing) but not listed?
5. Is there a project manager / delivery lead identified?
6. Is there a named sponsor or steering committee?
7. Are external vendors or contractors identified where needed?
8. Is onboarding or ramp-up time accounted for?

{sections}

Return JSON matching this schema exactly:
{schema}
"""


def run_resource_analysis(sections: ExtractedSections) -> ResourceAnalysisResult:
    sections_text = "\n\n".join([
        section_text(sections.resources, "Resources"),
        section_text(sections.timeline, "Timeline"),
        section_text(sections.deliverables, "Deliverables"),
        section_text(sections.scope, "Scope"),
        section_text(sections.governance, "Governance"),
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

    data = parse_llm_json(raw, context="resource_analysis")

    findings = [
        Finding(
            id=f.get("id", f"RES-{i:03d}"),
            category="resource",
            severity=Severity(f.get("severity", "medium")),
            title=f.get("title", ""),
            description=f.get("description", ""),
            recommendation=f.get("recommendation", ""),
        )
        for i, f in enumerate(data.get("findings", []), start=1)
    ]

    return ResourceAnalysisResult(
        over_allocated=data.get("over_allocated", []),
        missing_roles=data.get("missing_roles", []),
        skill_mismatches=data.get("skill_mismatches", []),
        findings=findings,
        resource_score=float(data.get("resource_score", 5.0)),
    )
