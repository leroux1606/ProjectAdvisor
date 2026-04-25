"""
LLM Engine — secondary analysis layer.
Produces AIInsight objects to enrich rule findings with soft issues,
wording improvements, and contextual suggestions.

This module MUST:
- Never be the sole source of truth for any finding
- Degrade gracefully if the LLM is unavailable
- Return only structured JSON (no free-form narrative)
- Not duplicate what the rule engine already caught
"""

from __future__ import annotations

import json
import logging

from app.llm.openrouter import llm_available
from app.pipeline.section_extractor import ExtractedSections
from app.rule_engine.models import AIInsight, HybridBundle

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a senior project auditor (PRINCE2 Practitioner, PMP certified).
Your role is to identify SOFT issues that deterministic rules cannot detect:
- Vague, ambiguous, or uncommitted language in objectives
- Logical gaps in reasoning between sections
- Missing implied dependencies
- Wording that sounds professional but lacks substance

Rules:
- Return ONLY valid JSON matching the schema provided.
- Do NOT repeat issues that are obvious structural facts (missing sections, no dates, etc).
  Those are already handled by the rule engine.
- Focus on QUALITY, CLARITY, and COHERENCE issues.
- Be concise and professional. No filler language.
- Maximum 3 insights per category.
"""

_PROMPT_TEMPLATE = """Review the following project plan sections and identify soft quality issues.

{sections_text}

Return a JSON object with this exact structure:
{{
  "insights": [
    {{
      "category": "structure|timeline|risk|resource|governance|consistency",
      "title": "short descriptive title (max 10 words)",
      "insight": "what the problem is and why it matters (2-3 sentences)",
      "suggestion": "specific actionable improvement (1-2 sentences)"
    }}
  ]
}}

Focus only on issues not already covered by rule-based checks such as:
- Missing sections
- Missing dates
- Missing roles
- Missing mitigations

Identify instead: vagueness, internal contradictions, implied assumptions, weak commitments,
and quality gaps in the existing content.
Maximum 8 insights total.
"""


def _format_sections(sections: ExtractedSections) -> str:
    parts = []
    pairs = [
        ("Objectives", sections.objectives),
        ("Scope", sections.scope),
        ("Deliverables", sections.deliverables),
        ("Timeline", sections.timeline),
        ("Resources", sections.resources),
        ("Risks", sections.risks),
        ("Governance", sections.governance),
    ]
    for label, content in pairs:
        if content:
            parts.append(f"### {label}\n{content[:1500]}")
    return "\n\n".join(parts) if parts else "[No sections extracted]"


def generate_insights(
    sections: ExtractedSections,
    bundle: HybridBundle,
) -> HybridBundle:
    """
    Call the LLM for soft insights and attach them to the appropriate CategoryResult
    in the bundle. Returns the bundle unchanged if LLM is unavailable.
    """
    if not llm_available():
        logger.info("No LLM provider configured — skipping AI insights.")
        return bundle

    try:
        from app.utils.llm_client import call_llm  # noqa: PLC0415

        sections_text = _format_sections(sections)
        prompt = _PROMPT_TEMPLATE.format(sections_text=sections_text)

        raw = call_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=prompt,
            temperature=0.0,
            max_tokens=1500,
        )

        data = json.loads(raw)
        insights_data = data.get("insights", [])

    except Exception as exc:
        logger.warning("LLM insight generation failed (non-fatal): %s", exc)
        return bundle

    # Map category string to CategoryResult
    category_map = {
        "structure": bundle.structure,
        "timeline": bundle.timeline,
        "risk": bundle.risk,
        "resource": bundle.resource,
        "governance": bundle.governance,
        "consistency": bundle.consistency,
    }

    for item in insights_data:
        cat = item.get("category", "").lower().strip()
        target = category_map.get(cat)
        if target is None:
            continue
        insight = AIInsight(
            category=cat,
            title=item.get("title", ""),
            insight=item.get("insight", ""),
            suggestion=item.get("suggestion", ""),
        )
        target.ai_insights.append(insight)

    return bundle
