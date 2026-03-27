"""
Structure Analysis Module — evaluates completeness of project plan sections.
"""

from __future__ import annotations

import json

from app.analysis.base import SYSTEM_PROMPT_BASE, parse_llm_json, section_text
from app.analysis.models import Finding, Severity, StructureAnalysisResult
from app.pipeline.section_extractor import ExtractedSections
from app.utils.llm_client import call_llm

_SCHEMA = {
    "missing_sections": ["list of section names that are absent"],
    "weak_sections": ["list of section names that are present but lack substance"],
    "findings": [
        {
            "id": "STR-001",
            "category": "structure",
            "severity": "critical|high|medium|low|info",
            "title": "short title",
            "description": "detailed description",
            "recommendation": "actionable recommendation",
        }
    ],
    "completeness_score": "float 0-10",
}

_PROMPT = """Analyse the structural completeness of this project plan.

Expected sections: Objectives, Scope, Deliverables, Timeline, Resources, Risks.
Optional but valuable: Governance, Assumptions, Constraints, Budget.

Evaluate:
1. Which core sections are missing entirely?
2. Which sections are present but vague, incomplete, or lack measurable content?
3. Are objectives SMART (Specific, Measurable, Achievable, Relevant, Time-bound)?
4. Are deliverables clearly defined with acceptance criteria?
5. Is governance / decision-making structure defined?

{sections}

Return JSON matching this schema exactly:
{schema}
"""


def run_structure_analysis(sections: ExtractedSections) -> StructureAnalysisResult:
    sections_text = "\n\n".join([
        section_text(sections.objectives, "Objectives"),
        section_text(sections.scope, "Scope"),
        section_text(sections.deliverables, "Deliverables"),
        section_text(sections.timeline, "Timeline"),
        section_text(sections.resources, "Resources"),
        section_text(sections.risks, "Risks"),
        section_text(sections.governance, "Governance"),
        section_text(sections.assumptions, "Assumptions"),
        section_text(sections.constraints, "Constraints"),
        section_text(sections.budget, "Budget"),
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

    data = parse_llm_json(raw, context="structure_analysis")

    findings = [
        Finding(
            id=f.get("id", f"STR-{i:03d}"),
            category="structure",
            severity=Severity(f.get("severity", "medium")),
            title=f.get("title", ""),
            description=f.get("description", ""),
            recommendation=f.get("recommendation", ""),
        )
        for i, f in enumerate(data.get("findings", []), start=1)
    ]

    return StructureAnalysisResult(
        missing_sections=data.get("missing_sections", []),
        weak_sections=data.get("weak_sections", []),
        findings=findings,
        completeness_score=float(data.get("completeness_score", 5.0)),
    )
