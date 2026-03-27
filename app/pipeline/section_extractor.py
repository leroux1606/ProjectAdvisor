"""
Section Extraction Layer — extracts canonical sections from preprocessed text.

Strategy:
1. PRIMARY: Deterministic regex-based heading detection (no LLM, always runs)
2. FALLBACK: LLM-based extraction when regex yields fewer than 2 sections

This ensures the pipeline works even without LLM access.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from app.pipeline.preprocessor import PreprocessedText

logger = logging.getLogger(__name__)

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

# Maps each canonical section name to a list of heading aliases to detect
_HEADING_ALIASES: dict[str, list[str]] = {
    "objectives": [
        "objective", "goals?", "purpose", "aims?", "vision", "mission",
        "project goals?", "business objectives?",
    ],
    "scope": [
        "scope", "in.scope", "out.of.scope", "scope of work", "project scope",
        "inclusions?", "exclusions?",
    ],
    "deliverables": [
        "deliverable", "output", "product", "artefact", "artifact",
        "project deliverable",
    ],
    "timeline": [
        "timeline", "schedule", "gantt", "milestones?", "phases?",
        "project plan", "work breakdown", "wbs", "roadmap",
    ],
    "resources": [
        "resource", "team", "staffing", "personnel", "people", "roles? and responsibilities",
        "human resources?", "workforce",
    ],
    "risks": [
        "risk", "issue", "risk register", "risk management", "threats?",
        "risk and issue",
    ],
    "governance": [
        "governance", "oversight", "steering", "project board", "escalation",
        "change control", "reporting", "management structure",
    ],
    "assumptions": [
        "assumption",
    ],
    "constraints": [
        "constraint", "limitation", "dependency", "dependencies",
    ],
    "budget": [
        "budget", "cost", "financial", "finance", "funding", "expenditure",
    ],
}

# Build compiled patterns per section
_HEADING_PATTERNS: dict[str, re.Pattern] = {
    section: re.compile(
        r"^#+\s*(?:" + "|".join(aliases) + r")\b"
        r"|^(?:" + "|".join(aliases) + r")[:\s]*$",
        re.IGNORECASE | re.MULTILINE,
    )
    for section, aliases in _HEADING_ALIASES.items()
}


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
    extraction_method: str = "regex"  # "regex" | "llm"

    def present_sections(self) -> list[str]:
        return [
            name for name in SECTION_NAMES
            if getattr(self, name) not in (None, "")
        ]

    def missing_sections(self) -> list[str]:
        core = ["objectives", "scope", "deliverables", "timeline", "resources", "risks"]
        return [name for name in core if getattr(self, name) in (None, "")]


def _extract_by_regex(text: str) -> ExtractedSections:
    """
    Split document into sections by detecting headings.
    Returns sections found; undetected sections remain None.
    """
    # Split on any line that looks like a heading (markdown or plain)
    heading_re = re.compile(
        r"^(#{1,4}\s+.+|[A-Z][A-Za-z\s&/]{2,60}[:\.]?)\s*$",
        re.MULTILINE,
    )

    # Find all heading positions
    splits = [(m.start(), m.group(0).strip()) for m in heading_re.finditer(text)]

    if not splits:
        # No headings found — try to assign full text to whichever sections match
        sections = ExtractedSections(extraction_method="regex")
        for section, pattern in _HEADING_PATTERNS.items():
            if pattern.search(text):
                # Section keyword appears inline — use the full text as a rough proxy
                setattr(sections, section, text[:3000])
        return sections

    # Build a dict: heading_text -> content
    chunks: dict[str, str] = {}
    for i, (pos, heading) in enumerate(splits):
        next_pos = splits[i + 1][0] if i + 1 < len(splits) else len(text)
        content = text[pos:next_pos].strip()
        # Remove the heading line itself from content
        lines = content.splitlines()
        body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
        chunks[heading] = body

    sections = ExtractedSections(extraction_method="regex")

    for canonical, pattern in _HEADING_PATTERNS.items():
        for heading, body in chunks.items():
            if pattern.match(heading) or pattern.search(heading):
                existing = getattr(sections, canonical)
                if existing:
                    # Append if multiple headings match same section
                    setattr(sections, canonical, existing + "\n" + body)
                else:
                    setattr(sections, canonical, body if body else None)
                break  # first match wins per section

    return sections


def _extract_by_llm(preprocessed: PreprocessedText) -> ExtractedSections:
    """LLM-based section extraction — used only as fallback."""
    from app.utils.llm_client import call_llm  # noqa: PLC0415

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
    section_keys = json.dumps(SECTION_NAMES)
    prompt = _EXTRACTION_PROMPT.format(
        section_keys=section_keys,
        text=preprocessed.cleaned_text[:12000],
    )

    raw_response = call_llm(
        system_prompt=(
            "You are a structured document parser. "
            "Extract sections from project plans and return only valid JSON."
        ),
        user_prompt=prompt,
        temperature=0.0,
    )

    try:
        data = json.loads(raw_response)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_response, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            raise ValueError(f"LLM section extractor returned non-JSON: {raw_response[:200]}")

    sections = ExtractedSections(raw_json=data, extraction_method="llm")
    for key in SECTION_NAMES:
        value = data.get(key)
        setattr(sections, key, value.strip() if isinstance(value, str) and value.strip() else None)

    return sections


def extract_sections(preprocessed: PreprocessedText) -> ExtractedSections:
    """
    Primary: attempt regex-based extraction.
    Fallback: use LLM if fewer than 2 sections found and API key is available.
    """
    import os  # noqa: PLC0415

    sections = _extract_by_regex(preprocessed.cleaned_text)
    found = len(sections.present_sections())

    if found >= 2:
        logger.info("Section extraction via regex: %d sections found.", found)
        return sections

    # Regex yielded little — try LLM if available
    if os.getenv("OPENAI_API_KEY"):
        logger.info("Regex found only %d sections — attempting LLM extraction.", found)
        try:
            llm_sections = _extract_by_llm(preprocessed)
            llm_found = len(llm_sections.present_sections())
            if llm_found > found:
                logger.info("LLM extraction found %d sections.", llm_found)
                return llm_sections
        except Exception as exc:
            logger.warning("LLM section extraction failed (non-fatal): %s", exc)

    # Return whatever regex found, even if sparse
    logger.info("Using regex extraction result with %d sections.", found)
    return sections
