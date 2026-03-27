"""
Rule Engine Runner — executes all deterministic rule modules and assembles a HybridBundle.
No LLM calls. This is the primary analysis layer.
"""

from __future__ import annotations

from app.pipeline.section_extractor import ExtractedSections
from app.rule_engine.consistency_rules import check_consistency
from app.rule_engine.domain_rules import check_domain_rules
from app.rule_engine.governance_rules import check_governance
from app.rule_engine.models import CategoryResult, HybridBundle
from app.rule_engine.resource_rules import check_resources
from app.rule_engine.risk_rules import check_risks
from app.rule_engine.structure_rules import check_structure
from app.rule_engine.timeline_rules import check_timeline


def run_rules(sections: ExtractedSections, project_type: str = "general") -> HybridBundle:
    """
    Run all deterministic rule checks and return a HybridBundle
    with empty ai_insights lists (to be filled by the LLM engine if enabled).
    """
    bundle = HybridBundle(
        structure=CategoryResult(
            category="structure",
            label="Structure & Completeness",
            rule_findings=check_structure(sections),
        ),
        timeline=CategoryResult(
            category="timeline",
            label="Timeline & Scheduling",
            rule_findings=check_timeline(sections),
        ),
        risk=CategoryResult(
            category="risk",
            label="Risk Management",
            rule_findings=check_risks(sections),
        ),
        resource=CategoryResult(
            category="resource",
            label="Resource Planning",
            rule_findings=check_resources(sections),
        ),
        governance=CategoryResult(
            category="governance",
            label="Governance & Oversight",
            rule_findings=check_governance(sections),
        ),
        consistency=CategoryResult(
            category="consistency",
            label="Internal Consistency",
            rule_findings=check_consistency(sections),
        ),
    )
    for finding in check_domain_rules(sections, project_type):
        category = getattr(bundle, finding.category, None)
        if category is not None:
            category.rule_findings.append(finding)
    return bundle
