"""
Domain-specific deterministic rule packs layered on top of the universal rules.
"""

from __future__ import annotations

import re

from app.pipeline.section_extractor import ExtractedSections
from app.project_types import GENERAL_PROJECT
from app.rule_engine.models import RuleFinding, Severity


def _combined_text(sections: ExtractedSections) -> str:
    return " ".join(
        filter(
            None,
            [
                sections.objectives,
                sections.scope,
                sections.deliverables,
                sections.timeline,
                sections.resources,
                sections.risks,
                sections.governance,
                sections.assumptions,
                sections.constraints,
                sections.budget,
            ],
        )
    )


def _software_it_rules(sections: ExtractedSections) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    counter = 1
    full_text = _combined_text(sections)
    nfr_re = re.compile(r"\b(security|performance|availability|scalability|latency|resilience|backup|recovery)\b", re.IGNORECASE)
    cutover_re = re.compile(r"\b(cutover|deployment|release plan|go-live|rollback|hypercare)\b", re.IGNORECASE)
    architecture_re = re.compile(r"\b(architecture|integration design|solution design|technical design)\b", re.IGNORECASE)

    def _id() -> str:
        nonlocal counter
        rid = f"DOM-SW-{counter:03d}"
        counter += 1
        return rid

    if not architecture_re.search(full_text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="structure",
            severity=Severity.MEDIUM,
            title="Software plan lacks architecture or design reference",
            explanation="No architecture, integration design, or technical design language was detected for this software project.",
            suggested_fix="Add a technical design or architecture section covering integrations, environments, and major components.",
            rule_name="SOFTWARE_ARCHITECTURE_DEFINED",
        ))
    if not nfr_re.search(full_text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="structure",
            severity=Severity.HIGH,
            title="No non-functional requirements detected",
            explanation="Software projects should define service quality expectations such as security, performance, availability, or resilience.",
            suggested_fix="Document non-functional requirements and acceptance thresholds for security, performance, availability, and recovery.",
            rule_name="SOFTWARE_NFR_DEFINED",
        ))
    if not cutover_re.search(full_text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="timeline",
            severity=Severity.HIGH,
            title="No cutover or support readiness plan",
            explanation="The plan does not mention deployment, rollback, go-live support, or hypercare arrangements.",
            suggested_fix="Add cutover, rollback, go-live validation, and post-deployment support activities to the plan.",
            rule_name="SOFTWARE_CUTOVER_READY",
        ))
    return findings


def _data_ai_rules(sections: ExtractedSections) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    counter = 1
    full_text = _combined_text(sections)
    data_quality_re = re.compile(r"\b(data quality|lineage|master data|profiling|cleansing|catalog|governance)\b", re.IGNORECASE)
    model_eval_re = re.compile(r"\b(accuracy|precision|recall|f1|auc|evaluation|validation|baseline|drift)\b", re.IGNORECASE)
    privacy_bias_re = re.compile(r"\b(privacy|gdpr|bias|fairness|ethics|explainability|pii|sensitive data)\b", re.IGNORECASE)

    def _id() -> str:
        nonlocal counter
        rid = f"DOM-DA-{counter:03d}"
        counter += 1
        return rid

    if not data_quality_re.search(full_text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="risk",
            severity=Severity.HIGH,
            title="No data quality or data governance plan",
            explanation="Data and AI projects need explicit controls for data quality, lineage, and stewardship.",
            suggested_fix="Define data quality checks, ownership, lineage expectations, and remediation steps before delivery.",
            rule_name="DATA_GOVERNANCE_DEFINED",
        ))
    if not model_eval_re.search(full_text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="structure",
            severity=Severity.HIGH,
            title="No model evaluation criteria detected",
            explanation="The plan does not define how analytical or AI outputs will be validated, benchmarked, or monitored.",
            suggested_fix="Add evaluation metrics, baselines, validation datasets, and monitoring criteria for the model or analytics outputs.",
            rule_name="MODEL_EVALUATION_DEFINED",
        ))
    if not privacy_bias_re.search(full_text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="governance",
            severity=Severity.MEDIUM,
            title="No privacy, bias, or explainability safeguards",
            explanation="AI and data projects should explicitly address privacy, sensitive data handling, and fairness or explainability considerations.",
            suggested_fix="Document privacy controls, sensitive-data handling, and any fairness or explainability checks required for approval.",
            rule_name="DATA_PRIVACY_BIAS_CONTROLS",
        ))
    return findings


def _construction_rules(sections: ExtractedSections) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    counter = 1
    full_text = _combined_text(sections)
    permits_re = re.compile(r"\b(permit|approval|inspection|planning consent|building control|regulator)\b", re.IGNORECASE)
    safety_re = re.compile(r"\b(safety|hse|hazard|method statement|site induction|ppe)\b", re.IGNORECASE)
    procurement_re = re.compile(r"\b(procurement|material lead time|long lead|subcontractor|supplier|commissioning)\b", re.IGNORECASE)

    def _id() -> str:
        nonlocal counter
        rid = f"DOM-CN-{counter:03d}"
        counter += 1
        return rid

    if not permits_re.search(full_text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="governance",
            severity=Severity.HIGH,
            title="No permits or approvals pathway defined",
            explanation="Construction and infrastructure projects typically depend on permits, inspections, or formal approvals before work or handover.",
            suggested_fix="Add a permits and approvals plan with authorities, dependencies, and target approval dates.",
            rule_name="CONSTRUCTION_APPROVALS_DEFINED",
        ))
    if not safety_re.search(full_text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="risk",
            severity=Severity.CRITICAL,
            title="No health and safety planning detected",
            explanation="No health, safety, or hazard management language was found, which is a major gap for physical delivery projects.",
            suggested_fix="Include a safety management approach, hazard controls, site rules, and named HSE responsibilities.",
            rule_name="CONSTRUCTION_SAFETY_DEFINED",
        ))
    if not procurement_re.search(full_text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="timeline",
            severity=Severity.HIGH,
            title="No procurement or commissioning readiness plan",
            explanation="The plan does not mention material lead times, subcontractor coordination, or commissioning activities.",
            suggested_fix="Add procurement milestones, long-lead items, subcontractor interfaces, and commissioning/handover tasks.",
            rule_name="CONSTRUCTION_PROCUREMENT_DEFINED",
        ))
    return findings


def _compliance_rules(sections: ExtractedSections) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    counter = 1
    full_text = _combined_text(sections)
    control_re = re.compile(r"\b(control|control mapping|requirement mapping|evidence|test of control|audit evidence)\b", re.IGNORECASE)
    training_re = re.compile(r"\b(training|awareness|policy update|procedure update|change adoption)\b", re.IGNORECASE)
    signoff_re = re.compile(r"\b(attestation|sign-off|approval|submission|regulatory filing|certification)\b", re.IGNORECASE)

    def _id() -> str:
        nonlocal counter
        rid = f"DOM-CO-{counter:03d}"
        counter += 1
        return rid

    if not control_re.search(full_text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="structure",
            severity=Severity.HIGH,
            title="No control or evidence mapping detected",
            explanation="Compliance projects need traceability from requirements to controls, evidence, and ownership.",
            suggested_fix="Add a control mapping register that links requirements, controls, evidence, owners, and due dates.",
            rule_name="COMPLIANCE_CONTROL_MAPPING",
        ))
    if not training_re.search(full_text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="resource",
            severity=Severity.MEDIUM,
            title="No policy, procedure, or training rollout plan",
            explanation="The plan does not show how new controls or obligations will be embedded through procedures or training.",
            suggested_fix="Add policy/procedure updates, communications, and training tasks with named owners and audience groups.",
            rule_name="COMPLIANCE_ADOPTION_PLAN",
        ))
    if not signoff_re.search(full_text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="governance",
            severity=Severity.HIGH,
            title="No formal compliance sign-off or submission path",
            explanation="The plan does not identify who approves compliance completion or how required submissions/certifications will be handled.",
            suggested_fix="Define formal sign-off criteria, approving authorities, and any submission or certification deadlines.",
            rule_name="COMPLIANCE_SIGNOFF_DEFINED",
        ))
    return findings


def _product_agile_rules(sections: ExtractedSections) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    counter = 1
    full_text = _combined_text(sections)
    backlog_re = re.compile(r"\b(backlog|user story|epic|prioriti|story point|refinement)\b", re.IGNORECASE)
    cadence_re = re.compile(r"\b(sprint|iteration|release cadence|demo|retrospective|stand-up)\b", re.IGNORECASE)
    ownership_re = re.compile(r"\b(product owner|customer feedback|stakeholder feedback|discovery|roadmap)\b", re.IGNORECASE)

    def _id() -> str:
        nonlocal counter
        rid = f"DOM-AG-{counter:03d}"
        counter += 1
        return rid

    if not backlog_re.search(full_text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="structure",
            severity=Severity.MEDIUM,
            title="No backlog or story structure detected",
            explanation="Agile product plans should reference epics, stories, prioritisation, or backlog management.",
            suggested_fix="Add backlog structure, prioritisation logic, and how scope will be refined across iterations.",
            rule_name="AGILE_BACKLOG_DEFINED",
        ))
    if not cadence_re.search(full_text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="timeline",
            severity=Severity.MEDIUM,
            title="No agile delivery cadence defined",
            explanation="The plan does not mention sprint cadence, demos, retrospectives, or release rhythm.",
            suggested_fix="Define sprint/release cadence and include demo, review, and retrospective checkpoints.",
            rule_name="AGILE_CADENCE_DEFINED",
        ))
    if not ownership_re.search(full_text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="resource",
            severity=Severity.HIGH,
            title="No product ownership or feedback loop",
            explanation="Product and agile delivery needs a clear product owner or mechanism for customer feedback and prioritisation.",
            suggested_fix="Identify the product owner and define how customer or stakeholder feedback changes backlog priorities.",
            rule_name="AGILE_PRODUCT_OWNERSHIP",
        ))
    return findings


def _research_rules(sections: ExtractedSections) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    counter = 1
    full_text = _combined_text(sections)
    hypothesis_re = re.compile(r"\b(hypothesis|research question|assumption to test|experiment)\b", re.IGNORECASE)
    evaluation_re = re.compile(r"\b(success criteria|evaluation|assessment|peer review|replication|validation)\b", re.IGNORECASE)
    knowledge_re = re.compile(r"\b(publication|paper|knowledge transfer|findings log|documentation|repository)\b", re.IGNORECASE)

    def _id() -> str:
        nonlocal counter
        rid = f"DOM-RS-{counter:03d}"
        counter += 1
        return rid

    if not hypothesis_re.search(full_text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="structure",
            severity=Severity.HIGH,
            title="No hypothesis or research question defined",
            explanation="Research and innovation projects should state the core question, hypothesis, or experiment objective being tested.",
            suggested_fix="Add explicit research questions, hypotheses, or experiment statements linked to the project objectives.",
            rule_name="RESEARCH_HYPOTHESIS_DEFINED",
        ))
    if not evaluation_re.search(full_text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="governance",
            severity=Severity.MEDIUM,
            title="No evaluation or validation approach detected",
            explanation="The plan does not define how outcomes will be evaluated, validated, or peer reviewed.",
            suggested_fix="Define evaluation criteria, validation methods, and who reviews the results before conclusion.",
            rule_name="RESEARCH_EVALUATION_DEFINED",
        ))
    if not knowledge_re.search(full_text):
        findings.append(RuleFinding(
            rule_id=_id(),
            category="structure",
            severity=Severity.LOW,
            title="No knowledge capture or dissemination plan",
            explanation="The plan does not show how findings, documentation, or learning outputs will be captured and shared.",
            suggested_fix="Add knowledge capture deliverables such as reports, repositories, lessons learned, or publication outputs.",
            rule_name="RESEARCH_KNOWLEDGE_CAPTURE",
        ))
    return findings


_DOMAIN_RULES = {
    GENERAL_PROJECT: lambda sections: [],
    "software_it": _software_it_rules,
    "data_ai": _data_ai_rules,
    "construction": _construction_rules,
    "compliance_regulatory": _compliance_rules,
    "product_agile": _product_agile_rules,
    "research_innovation": _research_rules,
}


def check_domain_rules(sections: ExtractedSections, project_type: str) -> list[RuleFinding]:
    rule_fn = _DOMAIN_RULES.get(project_type, _DOMAIN_RULES[GENERAL_PROJECT])
    return rule_fn(sections)

