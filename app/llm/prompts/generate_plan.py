"""
Prompt builders for the Plan Generator.

The model receives a user prompt + project type and must produce a markdown
project plan that covers the canonical sections the rule engine looks for.
Section headings must use H2 (##) so the regex extractor picks them up.
"""

from __future__ import annotations

from app.project_types import PROJECT_TYPE_MAP, get_project_type_label


_REQUIRED_SECTIONS = [
    "Objectives",
    "Scope",
    "Deliverables",
    "Timeline",
    "Resources",
    "Risks",
    "Governance",
    "Assumptions",
    "Constraints",
    "Budget",
]


SYSTEM_PROMPT = """You are a senior project manager (PRINCE2 Practitioner, PMP certified).
Produce realistic, well-structured project plans that a project board would accept.

Output rules:
- Markdown only, no preamble or closing remarks.
- Use H2 (##) for each required section heading, exactly as named.
- Each section must contain real content — no placeholders, no "TBD".
- Use concrete dates, named roles, measurable success criteria, and explicit costs.
- Be specific to the user's request and the project type. Do not produce generic boilerplate.
- Risks must include cause, impact, likelihood, and mitigation.
- Timeline must include phases, milestones, and dates.
- Governance must include named roles (sponsor, project manager, board) and reporting cadence.
- Keep total length between 800 and 2000 words.
"""


def build_user_prompt(user_prompt: str, project_type: str) -> str:
    profile = PROJECT_TYPE_MAP.get(project_type) or PROJECT_TYPE_MAP["general"]
    sections_block = "\n".join(f"- ## {name}" for name in _REQUIRED_SECTIONS)
    return f"""Project type: {get_project_type_label(profile.id)}
Project-type focus: {profile.description}

User request:
\"\"\"
{user_prompt.strip()}
\"\"\"

Required sections (use these exact H2 headings, in this order):
{sections_block}

Produce the project plan now.
"""
