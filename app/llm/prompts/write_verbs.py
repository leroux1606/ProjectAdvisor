"""
Prompt builders for write-action verbs: rewrite_section, add_section,
regenerate_timeline.

All write verbs ask the model to return the FULL revised plan in markdown.
This is the most robust strategy across plan formats: the model preserves
the original document structure and only changes the targeted section.
The caller then diffs original vs revised and lets the user accept/reject
before any state changes.
"""

from __future__ import annotations


SYSTEM_PROMPT = """You are a senior project manager editing an existing project plan.

Hard rules:
- Output the FULL revised plan in markdown — preserve every section that you
  are not asked to change, exactly as it was.
- Use H2 (##) headings for section names. Do not invent a different heading
  style than the original document already uses.
- Do not add a preamble, closing remark, or explanation — return only the
  revised plan.
- Do not include placeholders like "TBD" or "[insert here]".
- Keep the rest of the document's tone and formatting.
- Do not introduce code, scripts, or HTML.
"""


def build_rewrite_prompt(plan_text: str, section: str, instructions: str) -> str:
    instr = instructions.strip() or "improve clarity, specificity, and rigour"
    return f"""Rewrite the **{section}** section of the plan below.
Apply this guidance: {instr}

Leave every other section unchanged.

Return the FULL revised plan in markdown.

--- ORIGINAL PLAN ---
{plan_text}
--- END PLAN ---
"""


def build_regenerate_timeline_prompt(plan_text: str, constraints: str) -> str:
    instr = constraints.strip() or "tighten phasing and add concrete milestone dates"
    return f"""Regenerate the **Timeline** section of the plan below.
Apply this guidance: {instr}

Leave every other section unchanged.

Return the FULL revised plan in markdown.

--- ORIGINAL PLAN ---
{plan_text}
--- END PLAN ---
"""


def build_add_section_prompt(plan_text: str, section: str, instructions: str) -> str:
    instr = instructions.strip() or "draft realistic, specific content"
    return f"""Add a new **{section}** section to the plan below.
Apply this guidance: {instr}

If the section already exists, expand it instead of duplicating it.
Leave every other section unchanged.

Return the FULL revised plan in markdown.

--- ORIGINAL PLAN ---
{plan_text}
--- END PLAN ---
"""
