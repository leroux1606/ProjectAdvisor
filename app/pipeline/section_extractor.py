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

# Build compiled patterns per section.
# Two forms:
#   full_text_pattern : used to search within the full document text (anchored, multiline)
#   heading_pattern   : used to match a single extracted heading string (unanchored)
_HEADING_PATTERNS: dict[str, re.Pattern] = {
    section: re.compile(
        r"(?:" + "|".join(aliases) + r")",
        re.IGNORECASE,
    )
    for section, aliases in _HEADING_ALIASES.items()
}

# Separate full-text patterns for the "no headings found" fallback
_FULLTEXT_PATTERNS: dict[str, re.Pattern] = {
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


def _is_heading_line(line: str) -> bool:
    """Return True if a line looks like a section heading (not body content)."""
    stripped = line.strip()
    if not stripped:
        return False
    # Markdown heading
    if re.match(r"^#{1,4}\s+\S", stripped):
        return True
    # Short line (≤ 60 chars) ending with colon and no sentence-ending punctuation before it
    if len(stripped) <= 60 and stripped.endswith(":") and "." not in stripped[:-1]:
        return True
    # ALL-CAPS short line
    if stripped.isupper() and 3 <= len(stripped) <= 50:
        return True
    return False


def _extract_by_regex(text: str) -> ExtractedSections:
    """
    Two-pass extraction:
    Pass 1 — identify heading lines and split text into chunks.
    Pass 2 — match each chunk heading to a canonical section name.
    """
    lines = text.splitlines()

    # Pass 1: find heading line indices
    heading_indices = [i for i, line in enumerate(lines) if _is_heading_line(line)]

    if not heading_indices:
        # No headings — fall back to keyword presence in full text
        sections = ExtractedSections(extraction_method="regex")
        for section, pattern in _FULLTEXT_PATTERNS.items():
            if pattern.search(text):
                setattr(sections, section, text[:3000])
        return sections

    # Build chunks: heading -> body text
    chunks: list[tuple[str, str]] = []
    for idx, heading_line_idx in enumerate(heading_indices):
        heading = lines[heading_line_idx].strip()
        next_idx = heading_indices[idx + 1] if idx + 1 < len(heading_indices) else len(lines)
        body_lines = lines[heading_line_idx + 1: next_idx]
        body = "\n".join(body_lines).strip()
        chunks.append((heading, body))

    # Pass 2: match each heading to a canonical section
    sections = ExtractedSections(extraction_method="regex")

    for heading, body in chunks:
        # Normalise: strip markdown prefix and trailing punctuation
        clean = re.sub(r"^#+\s*", "", heading).rstrip(":. \t").strip()

        for canonical, pattern in _HEADING_PATTERNS.items():
            if pattern.search(clean):
                existing = getattr(sections, canonical)
                if existing:
                    setattr(sections, canonical, existing + "\n" + body)
                else:
                    setattr(sections, canonical, body if body else None)
                break  # first canonical match wins

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
