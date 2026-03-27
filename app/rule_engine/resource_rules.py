"""
Resource Rules — deterministic checks for resource planning completeness.
"""

from __future__ import annotations

import re

from app.pipeline.section_extractor import ExtractedSections
from app.rule_engine.models import RuleFinding, Severity


# Required roles that should appear in a well-formed resource plan
_REQUIRED_ROLES: dict[str, re.Pattern] = {
    "Project Manager": re.compile(r"\b(project manager|pm\b|programme manager|delivery manager|scrum master)\b", re.IGNORECASE),
    "Project Sponsor": re.compile(r"\b(sponsor|executive sponsor|business owner|project owner)\b", re.IGNORECASE),
    "Technical Lead": re.compile(r"\b(tech lead|technical lead|architect|lead developer|engineering lead)\b", re.IGNORECASE),
}

# FTE / allocation signals
_ALLOCATION_RE = re.compile(
    r"\b(\d{1,3}%|full.?time|part.?time|fte|0\.\d\s*fte|\d+\s*days?\s*per\s*week)\b",
    re.IGNORECASE,
)

# RACI signals
_RACI_RE = re.compile(
    r"\b(raci|responsible|accountable|consulted|informed|rasci)\b", re.IGNORECASE
)

# External / vendor signals
_VENDOR_RE = re.compile(
    r"\b(vendor|contractor|third.?party|external|outsourc|supplier)\b", re.IGNORECASE
)

# Skills / competency signals
_SKILLS_RE = re.compile(
    r"\b(skill|competenc|qualif|certif|experience|expertise|specialist)\b", re.IGNORECASE
)


def check_resources(sections: ExtractedSections) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    counter = 1

    def _id() -> str:
        nonlocal counter
        fid = f"RES-{counter:03d}"
        counter += 1
        return fid

    # RES — No resources section
    if not sections.resources:
        findings.append(RuleFinding(
            rule_id=_id(),
            category="resource",
            severity=Severity.CRITICAL,
            title="No resources section present",
            explanation="The plan contains no resource planning section.",
            suggested_fix=(
                "Add a Resources section listing team members, roles, "
                "allocation percentages, and availability."
            ),
            rule_name="RESOURCE_SECTION_PRESENT",
        ))
        return findings

    text = sections.resources

    # RES — Missing required roles
    for role, pattern in _REQUIRED_ROLES.items():
        if not pattern.search(text):
            findings.append(RuleFinding(
                rule_id=_id(),
                category="resource",
                severity=Severity.HIGH,
                title=f"Missing required role: {role}",
                explanation=(
                    f"No '{role}' role was identified in the resource plan. "
                    f"This role is essential for project delivery."
                ),
                suggested_fix=f"Assign a named individual or team to the '{role}' role with defined responsibilities.",
                rule_name="REQUIRED_ROLE_PRESENT",
            ))

    # RES — No allocation percentages or FTE
    if not _ALLOCATION_RE.search(text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="resource",
            severity=Severity.HIGH,
            title="No resource allocation percentages specified",
            explanation=(
                "The resource section does not specify allocation levels (% time, FTE, or days/week). "
                "Without this, over-allocation cannot be detected or managed."
            ),
            suggested_fix=(
                "Specify allocation for each resource as % time or FTE "
                "(e.g. 'J. Smith — 80% FTE', 'Dev Team — 3 days/week')."
            ),
            rule_name="RESOURCE_ALLOCATION_SPECIFIED",
        ))

    # RES — No RACI or responsibility assignment
    if not _RACI_RE.search(text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="resource",
            severity=Severity.MEDIUM,
            title="No RACI or responsibility matrix",
            explanation=(
                "The plan does not include a RACI chart or clear responsibility assignments. "
                "Without this, accountability is unclear and tasks fall between the cracks."
            ),
            suggested_fix=(
                "Create a RACI matrix mapping deliverables to team members "
                "as Responsible, Accountable, Consulted, or Informed."
            ),
            rule_name="RACI_DEFINED",
        ))

    # RES — No skills or competency requirements
    if not _SKILLS_RE.search(text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="resource",
            severity=Severity.LOW,
            title="No skills or competency requirements listed",
            explanation=(
                "The resource section lists roles but does not specify required skills, "
                "experience levels, or certifications."
            ),
            suggested_fix=(
                "For key roles, document required skills and minimum experience levels. "
                "Highlight specialist requirements that may need external sourcing."
            ),
            rule_name="SKILLS_REQUIREMENTS_LISTED",
        ))

    # RES — Check if vendor/external dependency is mentioned in scope but not in resources
    if sections.scope and _VENDOR_RE.search(sections.scope):
        if not _VENDOR_RE.search(text):
            findings.append(RuleFinding(
                rule_id=_id(),
                category="resource",
                severity=Severity.HIGH,
                title="External vendors referenced in scope but not in resource plan",
                explanation=(
                    "The Scope section references external vendors or third-parties, "
                    "but the Resources section does not include them."
                ),
                suggested_fix=(
                    "Add all external vendors, contractors, and third-party dependencies "
                    "to the Resources section with roles, contacts, and lead times."
                ),
                rule_name="VENDOR_RESOURCES_ALIGNED",
            ))

    return findings
