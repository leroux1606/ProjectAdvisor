"""
Section Extraction Layer — identifies and extracts the canonical project plan
sections from preprocessed text using an LLM with a strict JSON schema.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from app.pipeline.preprocessor import PreprocessedText
from app.utils.llm_client import call_llm

SECTION_NAMES = [
    "objectives",
    "scope",
    "deliverables",
    "timeline",
    "resources",
    "risks",
    "governance",
    "assumptions",
    "constraints",
    "budget",
]

_EXTRACTION_PROMPT = """You are a document parser. Extract the content of each project plan section from the text below.

Return ONLY a JSON object with these exact keys:
{section_keys}

Rules:
- Each value must be the verbatim extracted text for that section, or null if the section is absent.
- Do NOT summarise, interpret, or add information.
- Do NOT include any text outside the JSON object.
- If a section heading exists but has no content, return an empty string "".

Project plan text:
---
{text}
---
"""


@dataclass
class ExtractedSections:
    objectives: Optional[str] = None
    scope: Optional[str] = None
    deliverables: Optional[str] = None
    timeline: Optional[str] = None
    resources: Optional[str] = None
    risks: Optional[str] = None
    governance: Optional[str] = None
    assumptions: Optional[str] = None
    constraints: Optional[str] = None
    budget: Optional[str] = None
    raw_json: dict = field(default_factory=dict)

    def present_sections(self) -> list[str]:
        return [
            name for name in SECTION_NAMES
            if getattr(self, name) not in (None, "")
        ]

    def missing_sections(self) -> list[str]:
        core = ["objectives", "scope", "deliverables", "timeline", "resources", "risks"]
        return [name for name in core if getattr(self, name) in (None, "")]


def extract_sections(preprocessed: PreprocessedText) -> ExtractedSections:
    section_keys = json.dumps(SECTION_NAMES)
    prompt = _EXTRACTION_PROMPT.format(
        section_keys=section_keys,
        text=preprocessed.cleaned_text[:12000],  # guard against token overflow
    )

    raw_response = call_llm(
        system_prompt=(
            "You are a structured document parser. "
            "You extract sections from project plans and return only valid JSON."
        ),
        user_prompt=prompt,
        temperature=0.0,
    )

    try:
        data = json.loads(raw_response)
    except json.JSONDecodeError:
        # Attempt to recover a JSON block from the response
        match = __import__("re").search(r"\{.*\}", raw_response, __import__("re").DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            raise ValueError(f"Section extractor returned non-JSON response: {raw_response[:200]}")

    sections = ExtractedSections(raw_json=data)
    for key in SECTION_NAMES:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            setattr(sections, key, value.strip())
        else:
            setattr(sections, key, None)

    return sections
