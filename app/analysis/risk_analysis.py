"""
Risk Analysis Module — identifies missing risks and unmitigated high-impact items.
"""

from __future__ import annotations

import json

from app.analysis.base import SYSTEM_PROMPT_BASE, parse_llm_json, section_text
from app.analysis.models import Finding, Severity, RiskAnalysisResult
from app.pipeline.section_extractor import ExtractedSections
from app.utils.llm_client import call_llm

_SCHEMA = {
    "missing_risks": ["list of risk categories that are not addressed in the plan"],
    "unmitigated_risks": ["list of identified risks that have no mitigation strategy"],
    "findings": [
        {
            "id": "RSK-001",
            "category": "risk",
            "severity": "critical|high|medium|low|info",
            "title": "short title",
            "description": "detailed description",
            "recommendation": "actionable recommendation",
        }
    ],
    "risk_score": "float 0-10",
}

_PROMPT = """Analyse the risk management section of this project plan against PRINCE2 and PMBOK standards.

Evaluate:
1. Is a formal risk register present?
2. Are risks categorised (technical, schedule, resource, external, financial)?
3. Does each risk have: probability, impact, owner, and mitigation strategy?
4. Are the following common risk categories addressed?
   - Key person dependency / bus factor
   - Technology or integration risks
   - Regulatory / compliance risks
   - Budget overrun risks
   - Scope creep
   - Vendor / third-party dependency
5. Are there contingency plans for critical risks?
6. Is there a risk review cadence defined?

{sections}

Return JSON matching this schema exactly:
{schema}
"""


def run_risk_analysis(sections: ExtractedSections) -> RiskAnalysisResult:
    sections_text = "\n\n".join([
        section_text(sections.risks, "Risks"),
        section_text(sections.objectives, "Objectives"),
        section_text(sections.timeline, "Timeline"),
        section_text(sections.resources, "Resources"),
        section_text(sections.constraints, "Constraints"),
        section_text(sections.assumptions, "Assumptions"),
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

    data = parse_llm_json(raw, context="risk_analysis")

    findings = [
        Finding(
            id=f.get("id", f"RSK-{i:03d}"),
            category="risk",
            severity=Severity(f.get("severity", "medium")),
            title=f.get("title", ""),
            description=f.get("description", ""),
            recommendation=f.get("recommendation", ""),
        )
        for i, f in enumerate(data.get("findings", []), start=1)
    ]

    return RiskAnalysisResult(
        missing_risks=data.get("missing_risks", []),
        unmitigated_risks=data.get("unmitigated_risks", []),
        findings=findings,
        risk_score=float(data.get("risk_score", 5.0)),
    )
