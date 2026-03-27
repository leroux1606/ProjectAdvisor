"""
Timeline Analysis Module — detects unrealistic durations, missing dependencies, overlaps.
"""

from __future__ import annotations

import json

from app.analysis.base import SYSTEM_PROMPT_BASE, parse_llm_json, section_text
from app.analysis.models import Finding, Severity, TimelineAnalysisResult
from app.pipeline.section_extractor import ExtractedSections
from app.utils.llm_client import call_llm

_SCHEMA = {
    "unrealistic_durations": ["list of tasks/phases with unrealistic time estimates"],
    "missing_dependencies": ["list of tasks that lack dependency definitions"],
    "overlaps": ["list of tasks that appear to overlap without sufficient resources"],
    "findings": [
        {
            "id": "TML-001",
            "category": "timeline",
            "severity": "critical|high|medium|low|info",
            "title": "short title",
            "description": "detailed description",
            "recommendation": "actionable recommendation",
        }
    ],
    "timeline_score": "float 0-10",
}

_PROMPT = """Analyse the timeline section of this project plan.

Evaluate:
1. Are task durations realistic given the described complexity and team size?
2. Are task dependencies explicitly defined? Which tasks lack predecessors/successors?
3. Are there tasks scheduled in parallel that would require the same resource simultaneously?
4. Is there buffer/contingency time built in?
5. Does the timeline account for review, testing, and sign-off cycles?
6. Are milestones clearly defined with dates?
7. Is the critical path identifiable?

{sections}

Return JSON matching this schema exactly:
{schema}
"""


def run_timeline_analysis(sections: ExtractedSections) -> TimelineAnalysisResult:
    sections_text = "\n\n".join([
        section_text(sections.timeline, "Timeline"),
        section_text(sections.resources, "Resources"),
        section_text(sections.deliverables, "Deliverables"),
        section_text(sections.scope, "Scope"),
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

    data = parse_llm_json(raw, context="timeline_analysis")

    findings = [
        Finding(
            id=f.get("id", f"TML-{i:03d}"),
            category="timeline",
            severity=Severity(f.get("severity", "medium")),
            title=f.get("title", ""),
            description=f.get("description", ""),
            recommendation=f.get("recommendation", ""),
        )
        for i, f in enumerate(data.get("findings", []), start=1)
    ]

    return TimelineAnalysisResult(
        unrealistic_durations=data.get("unrealistic_durations", []),
        missing_dependencies=data.get("missing_dependencies", []),
        overlaps=data.get("overlaps", []),
        findings=findings,
        timeline_score=float(data.get("timeline_score", 5.0)),
    )
