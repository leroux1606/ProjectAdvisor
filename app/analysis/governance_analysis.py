"""
Governance Analysis Module — evaluates decision-making structure, change control,
reporting, and escalation paths.
"""

from __future__ import annotations

import json

from app.analysis.base import SYSTEM_PROMPT_BASE, parse_llm_json, section_text
from app.analysis.models import Finding, Severity, GovernanceAnalysisResult
from app.pipeline.section_extractor import ExtractedSections
from app.utils.llm_client import call_llm

_SCHEMA = {
    "findings": [
        {
            "id": "GOV-001",
            "category": "governance",
            "severity": "critical|high|medium|low|info",
            "title": "short title",
            "description": "detailed description",
            "recommendation": "actionable recommendation",
        }
    ],
    "governance_score": "float 0-10",
}

_PROMPT = """Analyse the governance and oversight aspects of this project plan.

Evaluate:
1. Is a project sponsor or executive owner identified?
2. Is there a steering committee or project board?
3. Is a change control process defined?
4. Are escalation paths documented?
5. Is there a defined reporting cadence (status reports, dashboards)?
6. Are stage gates or phase reviews defined?
7. Is there a defined acceptance / sign-off process for deliverables?
8. Is there a lessons-learned or post-project review process?
9. Are RACI or responsibility assignments documented?

{sections}

Return JSON matching this schema exactly:
{schema}
"""


def run_governance_analysis(sections: ExtractedSections) -> GovernanceAnalysisResult:
    sections_text = "\n\n".join([
        section_text(sections.governance, "Governance"),
        section_text(sections.objectives, "Objectives"),
        section_text(sections.resources, "Resources"),
        section_text(sections.deliverables, "Deliverables"),
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

    data = parse_llm_json(raw, context="governance_analysis")

    findings = [
        Finding(
            id=f.get("id", f"GOV-{i:03d}"),
            category="governance",
            severity=Severity(f.get("severity", "medium")),
            title=f.get("title", ""),
            description=f.get("description", ""),
            recommendation=f.get("recommendation", ""),
        )
        for i, f in enumerate(data.get("findings", []), start=1)
    ]

    return GovernanceAnalysisResult(
        findings=findings,
        governance_score=float(data.get("governance_score", 5.0)),
    )
