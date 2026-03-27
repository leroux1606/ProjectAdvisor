"""
Base utilities shared by all analysis modules.
"""

from __future__ import annotations

import json
import re
from typing import Any


SYSTEM_PROMPT_BASE = """You are a project plan auditor operating under PRINCE2 and PMBOK standards.
Your role is to identify weaknesses, risks, and inconsistencies in project plans.

Rules:
- Return ONLY valid JSON matching the schema provided.
- Do NOT include explanations, markdown, or any text outside the JSON.
- Do NOT hallucinate data. Only analyse what is present in the input.
- If a section is absent, state that explicitly in the relevant finding.
- Be direct and professional. Avoid filler language.
- Severity levels: critical | high | medium | low | info
"""


def parse_llm_json(raw: str, context: str = "") -> dict[str, Any]:
    """Parse JSON from LLM response, with fallback regex extraction."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        raise ValueError(
            f"Analysis module [{context}] returned unparseable JSON.\n"
            f"Raw response (first 300 chars): {raw[:300]}"
        )


def section_text(value: str | None, label: str) -> str:
    """Format an optional section for inclusion in a prompt."""
    if value:
        return f"### {label}\n{value}"
    return f"### {label}\n[NOT PROVIDED]"
