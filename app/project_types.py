"""
Project type profiles for tailoring deterministic rule packs.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectTypeProfile:
    id: str
    label: str
    description: str


GENERAL_PROJECT = "general"

PROJECT_TYPE_PROFILES: list[ProjectTypeProfile] = [
    ProjectTypeProfile(
        id=GENERAL_PROJECT,
        label="General Project",
        description="Balanced audit using universal planning rules only.",
    ),
    ProjectTypeProfile(
        id="software_it",
        label="Software / IT",
        description="Adds checks for testing, non-functional requirements, cutover, and support readiness.",
    ),
    ProjectTypeProfile(
        id="data_ai",
        label="Data / AI",
        description="Adds checks for data quality, model evaluation, governance, monitoring, and privacy controls.",
    ),
    ProjectTypeProfile(
        id="construction",
        label="Construction / Infrastructure",
        description="Adds checks for permits, safety planning, procurement, and commissioning readiness.",
    ),
    ProjectTypeProfile(
        id="compliance_regulatory",
        label="Compliance / Regulatory",
        description="Adds checks for control mapping, audit evidence, policy/training, and formal approvals.",
    ),
    ProjectTypeProfile(
        id="product_agile",
        label="Product / Agile",
        description="Adds checks for backlog discipline, release cadence, feedback loops, and product ownership.",
    ),
    ProjectTypeProfile(
        id="research_innovation",
        label="Research / Innovation",
        description="Adds checks for hypotheses, experiments, evaluation criteria, and knowledge capture.",
    ),
]


PROJECT_TYPE_MAP = {profile.id: profile for profile in PROJECT_TYPE_PROFILES}


def get_project_type_label(project_type: str) -> str:
    return PROJECT_TYPE_MAP.get(project_type, PROJECT_TYPE_MAP[GENERAL_PROJECT]).label

