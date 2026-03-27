"""
Rule engine unit tests — no LLM required.
Tests each rule module with controlled inputs: good plans, bad plans, edge cases.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from app.pipeline.section_extractor import ExtractedSections
from app.rule_engine.models import Severity
from app.rule_engine.structure_rules import check_structure
from app.rule_engine.timeline_rules import check_timeline
from app.rule_engine.risk_rules import check_risks
from app.rule_engine.resource_rules import check_resources
from app.rule_engine.governance_rules import check_governance
from app.rule_engine.consistency_rules import check_consistency


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rule_ids(findings) -> list[str]:
    return [f.rule_id for f in findings]

def _rule_names(findings) -> list[str]:
    return [f.rule_name for f in findings]

def _severities(findings) -> list[str]:
    return [f.severity.value for f in findings]

def _has_rule(findings, rule_name: str) -> bool:
    return any(f.rule_name == rule_name for f in findings)


# ═══════════════════════════════════════════════════════════════════════════════
# STRUCTURE RULES
# ═══════════════════════════════════════════════════════════════════════════════

class TestStructureRules:

    def test_all_missing_sections_flagged_as_critical(self):
        sections = ExtractedSections()  # all None
        findings = check_structure(sections)
        critical = [f for f in findings if f.severity == Severity.CRITICAL]
        # All 6 core sections missing → 6 critical findings
        assert len(critical) == 6
        assert _has_rule(findings, "REQUIRED_SECTION_PRESENT")

    def test_thin_section_flagged(self):
        sections = ExtractedSections(
            objectives="Deliver the thing.",  # 3 words — below minimum
            scope="We will do some work on the system and deliver outputs to stakeholders.",
            deliverables="A report and a system and documentation for users to review and approve.",
            timeline="Phase 1: 4 weeks. Phase 2: 6 weeks. Phase 3: 2 weeks. Milestone: go-live.",
            resources="Project Manager: Jane. Developer: John. Analyst: Sarah.",
            risks="Risk: delay. Mitigation: buffer. Owner: PM. Probability: medium. Impact: high.",
        )
        findings = check_structure(sections)
        assert _has_rule(findings, "SECTION_MINIMUM_CONTENT")
        thin = [f for f in findings if f.rule_name == "SECTION_MINIMUM_CONTENT"]
        assert any("objectives" in f.title.lower() for f in thin)

    def test_non_smart_objectives_flagged(self):
        sections = ExtractedSections(
            objectives="We want to improve the system and make it better for users.",
            scope="Improve the customer portal system for all users.",
            deliverables="A new portal with improved features and better performance.",
            timeline="Phase 1: 4 weeks. Phase 2: 6 weeks. Milestone: launch.",
            resources="PM, Developer, Tester assigned to the project.",
            risks="Risk: delay. Mitigation: buffer. Owner: PM.",
        )
        findings = check_structure(sections)
        assert _has_rule(findings, "SMART_OBJECTIVES_MEASURABLE")
        assert _has_rule(findings, "SMART_OBJECTIVES_TIME_BOUND")

    def test_smart_objectives_not_flagged(self):
        sections = ExtractedSections(
            objectives=(
                "Reduce customer onboarding time by 40% by Q3 2025. "
                "Achieve 99.9% system uptime measured monthly by automated monitoring. "
                "Deliver all features by 31 December 2025 with full sign-off."
            ),
            scope="Redesign the customer onboarding portal for all enterprise users globally.",
            deliverables=(
                "New portal with sign-off from product owner upon UAT completion and acceptance. "
                "Training materials approved by HR. Runbook reviewed by tech lead."
            ),
            timeline=(
                "Phase 1: 4 weeks. Phase 2: 6 weeks. Milestone: launch by Q3. "
                "Buffer: 1 week contingency. After Phase 1 completes."
            ),
            resources=(
                "PM: Jane Smith (100% FTE). Developer: John Doe (80% FTE). "
                "Sponsor: CTO. Tech Lead: Sarah Lee (60% FTE)."
            ),
            risks=(
                "Risk: schedule delay. Mitigation: add buffer and weekly tracking. "
                "Owner: PM Jane. Probability: medium. Impact: high."
            ),
        )
        findings = check_structure(sections)
        assert not _has_rule(findings, "SMART_OBJECTIVES_MEASURABLE")
        assert not _has_rule(findings, "SMART_OBJECTIVES_TIME_BOUND")

    def test_deliverables_without_acceptance_criteria_flagged(self):
        sections = ExtractedSections(
            objectives="Deliver system by Q4 2025 with 30% performance improvement.",
            scope="Build new data pipeline.",
            deliverables="A data pipeline and documentation and training materials.",
            timeline="Phase 1: 4 weeks. Phase 2: 6 weeks. Milestone: launch.",
            resources="PM, Developer, Analyst.",
            risks="Risk: delay. Mitigation: buffer. Owner: PM.",
        )
        findings = check_structure(sections)
        assert _has_rule(findings, "DELIVERABLES_ACCEPTANCE_CRITERIA")

    def test_deliverables_with_acceptance_criteria_not_flagged(self):
        sections = ExtractedSections(
            objectives="Deliver system by Q4 2025 with 30% performance improvement.",
            scope="Build new data pipeline.",
            deliverables="Data pipeline — accepted when sign-off from data owner and UAT criteria met.",
            timeline="Phase 1: 4 weeks. Phase 2: 6 weeks. Milestone: launch.",
            resources="PM, Developer, Analyst.",
            risks="Risk: delay. Mitigation: buffer. Owner: PM.",
        )
        findings = check_structure(sections)
        assert not _has_rule(findings, "DELIVERABLES_ACCEPTANCE_CRITERIA")

    def test_no_findings_for_complete_good_plan(self):
        sections = ExtractedSections(
            objectives=(
                "Reduce processing time by 30% by Q2 2026. "
                "Achieve 99.5% uptime measured by automated monitoring. "
                "Complete migration by 30 June 2026."
            ),
            scope=(
                "In scope: full migration of the legacy billing system to cloud infrastructure, "
                "including data migration, configuration, and user acceptance testing. "
                "Out of scope: CRM integration, mobile application changes, and third-party reporting tools."
            ),
            deliverables=(
                "1. Migrated billing system — accepted when sign-off from finance director after UAT. "
                "2. Data migration report — approved by data owner. "
                "3. Training materials — verified by HR."
            ),
            timeline=(
                "Phase 1 (Discovery): 3 weeks. "
                "Phase 2 (Development): 8 weeks. "
                "Phase 3 (Testing/UAT): 3 weeks with review and sign-off. "
                "Milestone: go-live 30 June 2026. Buffer: 1 week contingency."
            ),
            resources=(
                "Project Manager: Jane Smith (100% FTE). "
                "Lead Developer: John Doe (80% FTE). "
                "Business Analyst: Sarah Lee (60% FTE). "
                "QA Tester: Mike Brown (50% FTE)."
            ),
            risks=(
                "Risk Register: "
                "R001 — Data loss during migration. Probability: Medium. Impact: High. "
                "Owner: Lead Developer. Mitigation: Full backup before migration, rollback plan. "
                "R002 — Key person dependency (John Doe). Probability: Low. Impact: High. "
                "Owner: PM. Mitigation: Knowledge transfer sessions, documentation."
            ),
            budget="Total budget: £120,000. Contingency: £15,000 (12.5%).",
            assumptions="Assumes legacy system access granted by week 2.",
            governance=(
                "Project Sponsor: CTO. Steering Committee: CFO, CTO, Head of Engineering. "
                "Change control process: all changes via Change Request form, approved by sponsor. "
                "Weekly status reports. Monthly steering committee reviews. Stage gate at end of each phase."
            ),
        )
        findings = check_structure(sections)
        critical_high = [f for f in findings if f.severity in (Severity.CRITICAL, Severity.HIGH)]
        assert len(critical_high) == 0, f"Unexpected critical/high findings: {[(f.rule_name, f.title) for f in critical_high]}"


# ═══════════════════════════════════════════════════════════════════════════════
# TIMELINE RULES
# ═══════════════════════════════════════════════════════════════════════════════

class TestTimelineRules:

    def test_missing_timeline_is_critical(self):
        sections = ExtractedSections()
        findings = check_timeline(sections)
        assert len(findings) == 1
        assert findings[0].severity == Severity.CRITICAL
        assert findings[0].rule_name == "TIMELINE_SECTION_PRESENT"

    def test_missing_milestones_flagged(self):
        sections = ExtractedSections(
            timeline="Phase 1: 4 weeks. Phase 2: 6 weeks. Phase 3: 2 weeks."
        )
        findings = check_timeline(sections)
        assert _has_rule(findings, "MILESTONES_DEFINED")

    def test_milestones_present_not_flagged(self):
        sections = ExtractedSections(
            timeline="Phase 1: 4 weeks. Milestone: design complete. Phase 2: 6 weeks. Go-live: Q3."
        )
        findings = check_timeline(sections)
        assert not _has_rule(findings, "MILESTONES_DEFINED")

    def test_missing_dependencies_flagged(self):
        sections = ExtractedSections(
            timeline="Phase 1: 4 weeks. Phase 2: 6 weeks. Milestone: launch."
        )
        findings = check_timeline(sections)
        assert _has_rule(findings, "TASK_DEPENDENCIES_DOCUMENTED")

    def test_dependencies_present_not_flagged(self):
        sections = ExtractedSections(
            timeline="Phase 2 starts after Phase 1 is complete. Milestone: launch."
        )
        findings = check_timeline(sections)
        assert not _has_rule(findings, "TASK_DEPENDENCIES_DOCUMENTED")

    def test_no_buffer_flagged(self):
        sections = ExtractedSections(
            timeline="Phase 1: 4 weeks. Phase 2: 6 weeks. Milestone: launch."
        )
        findings = check_timeline(sections)
        assert _has_rule(findings, "SCHEDULE_BUFFER_PRESENT")

    def test_buffer_present_not_flagged(self):
        sections = ExtractedSections(
            timeline="Phase 1: 4 weeks. Phase 2: 6 weeks. Buffer: 1 week contingency. Milestone: launch."
        )
        findings = check_timeline(sections)
        assert not _has_rule(findings, "SCHEDULE_BUFFER_PRESENT")

    def test_unrealistic_duration_flagged(self):
        sections = ExtractedSections(
            timeline=(
                "Architecture design: 1 day. "
                "Development: 2 days. "
                "Milestone: launch. Buffer: 1 week. "
                "Review and testing: 2 weeks. After development completes."
            )
        )
        findings = check_timeline(sections)
        assert _has_rule(findings, "UNREALISTIC_TASK_DURATION")

    def test_no_review_time_flagged(self):
        sections = ExtractedSections(
            timeline="Phase 1: 4 weeks. Phase 2: 6 weeks. Milestone: launch. Buffer: 1 week."
        )
        findings = check_timeline(sections)
        assert _has_rule(findings, "REVIEW_TIME_ALLOCATED")

    def test_review_time_present_not_flagged(self):
        sections = ExtractedSections(
            timeline="Phase 1: 4 weeks. UAT: 2 weeks. Review and sign-off: 1 week. Milestone: launch. Buffer: 1 week."
        )
        findings = check_timeline(sections)
        assert not _has_rule(findings, "REVIEW_TIME_ALLOCATED")


# ═══════════════════════════════════════════════════════════════════════════════
# RISK RULES
# ═══════════════════════════════════════════════════════════════════════════════

class TestRiskRules:

    def test_missing_risk_section_is_critical(self):
        sections = ExtractedSections()
        findings = check_risks(sections)
        assert len(findings) == 1
        assert findings[0].severity == Severity.CRITICAL
        assert findings[0].rule_name == "RISK_SECTION_PRESENT"

    def test_no_mitigation_is_critical(self):
        sections = ExtractedSections(
            risks="Risk 1: delay. Risk 2: budget overrun. Risk 3: key person leaves."
        )
        findings = check_risks(sections)
        assert _has_rule(findings, "RISK_MITIGATIONS_PRESENT")
        mitigation_finding = next(f for f in findings if f.rule_name == "RISK_MITIGATIONS_PRESENT")
        assert mitigation_finding.severity == Severity.CRITICAL

    def test_no_owners_flagged(self):
        sections = ExtractedSections(
            risks="Risk: delay. Mitigation: add buffer. Probability: high. Impact: medium."
        )
        findings = check_risks(sections)
        assert _has_rule(findings, "RISK_OWNERS_ASSIGNED")

    def test_owners_present_not_flagged(self):
        sections = ExtractedSections(
            risks=(
                "Risk: delay. Mitigation: add buffer. Owner: PM. "
                "Probability: high. Impact: medium."
            )
        )
        findings = check_risks(sections)
        assert not _has_rule(findings, "RISK_OWNERS_ASSIGNED")

    def test_no_probability_impact_flagged(self):
        sections = ExtractedSections(
            risks="Risk: delay. Mitigation: buffer. Owner: PM."
        )
        findings = check_risks(sections)
        assert _has_rule(findings, "RISK_SCORED")

    def test_complete_risk_register_no_critical_high(self):
        sections = ExtractedSections(
            risks=(
                "Risk Register:\n"
                "R001 — Schedule delay. Probability: High. Impact: High. Owner: PM. "
                "Mitigation: weekly tracking, contingency buffer.\n"
                "R002 — Key person dependency. Probability: Medium. Impact: High. Owner: PM. "
                "Mitigation: cross-training, documentation.\n"
                "R003 — Technical integration failure. Probability: Medium. Impact: High. Owner: Tech Lead. "
                "Mitigation: spike testing, fallback architecture.\n"
                "R004 — Budget overrun. Probability: Low. Impact: High. Owner: Sponsor. "
                "Mitigation: monthly cost reviews, change control.\n"
                "R005 — Scope creep. Probability: High. Impact: Medium. Owner: PM. "
                "Mitigation: change control process, scope freeze after design.\n"
                "R006 — Regulatory compliance. Probability: Low. Impact: Critical. Owner: Compliance Lead. "
                "Mitigation: legal review at design stage."
            )
        )
        findings = check_risks(sections)
        critical_high = [f for f in findings if f.severity in (Severity.CRITICAL, Severity.HIGH)]
        assert len(critical_high) == 0, f"Unexpected: {[(f.rule_name, f.title) for f in critical_high]}"


# ═══════════════════════════════════════════════════════════════════════════════
# RESOURCE RULES
# ═══════════════════════════════════════════════════════════════════════════════

class TestResourceRules:

    def test_missing_resource_section_is_critical(self):
        sections = ExtractedSections()
        findings = check_resources(sections)
        assert len(findings) == 1
        assert findings[0].severity == Severity.CRITICAL
        assert findings[0].rule_name == "RESOURCE_SECTION_PRESENT"

    def test_missing_pm_flagged(self):
        sections = ExtractedSections(
            resources="Developer: John (80% FTE). Tester: Sarah (50% FTE)."
        )
        findings = check_resources(sections)
        assert _has_rule(findings, "REQUIRED_ROLE_PRESENT")
        pm_finding = [f for f in findings if "Project Manager" in f.title]
        assert len(pm_finding) >= 1

    def test_missing_sponsor_flagged(self):
        sections = ExtractedSections(
            resources="Project Manager: Jane (100% FTE). Developer: John (80% FTE)."
        )
        findings = check_resources(sections)
        sponsor_finding = [f for f in findings if "Sponsor" in f.title]
        assert len(sponsor_finding) >= 1

    def test_no_allocation_flagged(self):
        sections = ExtractedSections(
            resources="Project Manager: Jane. Developer: John. Tester: Sarah."
        )
        findings = check_resources(sections)
        assert _has_rule(findings, "RESOURCE_ALLOCATION_SPECIFIED")

    def test_allocation_present_not_flagged(self):
        sections = ExtractedSections(
            resources=(
                "Project Manager: Jane (100% FTE). "
                "Developer: John (80% FTE). "
                "Sponsor: CTO."
            )
        )
        findings = check_resources(sections)
        assert not _has_rule(findings, "RESOURCE_ALLOCATION_SPECIFIED")

    def test_vendor_in_scope_but_not_resources_flagged(self):
        sections = ExtractedSections(
            scope="We will use a third-party vendor for payment processing integration.",
            resources="Project Manager: Jane (100% FTE). Developer: John (80% FTE). Sponsor: CTO.",
        )
        findings = check_resources(sections)
        assert _has_rule(findings, "VENDOR_RESOURCES_ALIGNED")

    def test_vendor_in_both_scope_and_resources_not_flagged(self):
        sections = ExtractedSections(
            scope="We will use a third-party vendor for payment processing integration.",
            resources=(
                "Project Manager: Jane (100% FTE). Developer: John (80% FTE). Sponsor: CTO. "
                "External vendor: PaymentCo (contractor for payment module)."
            ),
        )
        findings = check_resources(sections)
        assert not _has_rule(findings, "VENDOR_RESOURCES_ALIGNED")


# ═══════════════════════════════════════════════════════════════════════════════
# GOVERNANCE RULES
# ═══════════════════════════════════════════════════════════════════════════════

class TestGovernanceRules:

    def test_no_sponsor_is_critical(self):
        sections = ExtractedSections(
            objectives="Deliver system by Q4.",
            scope="Build new portal.",
        )
        findings = check_governance(sections)
        assert _has_rule(findings, "SPONSOR_IDENTIFIED")
        sponsor_finding = next(f for f in findings if f.rule_name == "SPONSOR_IDENTIFIED")
        assert sponsor_finding.severity == Severity.CRITICAL

    def test_no_change_control_flagged(self):
        sections = ExtractedSections(
            governance="Project sponsor: CTO. Weekly status reports."
        )
        findings = check_governance(sections)
        assert _has_rule(findings, "CHANGE_CONTROL_DEFINED")

    def test_no_escalation_flagged(self):
        sections = ExtractedSections(
            governance="Project sponsor: CTO. Change control via change request form."
        )
        findings = check_governance(sections)
        assert _has_rule(findings, "ESCALATION_PATH_DEFINED")

    def test_no_reporting_flagged(self):
        sections = ExtractedSections(
            governance=(
                "Project sponsor: CTO. Change control via change request form. "
                "Escalation path: PM → CTO."
            )
        )
        findings = check_governance(sections)
        assert _has_rule(findings, "REPORTING_CADENCE_DEFINED")

    def test_complete_governance_no_critical_high(self):
        sections = ExtractedSections(
            governance=(
                "Project Sponsor: CTO (executive sponsor). "
                "Steering Committee: CFO, CTO, Head of Engineering. "
                "Change control: all changes submitted via Change Request form, reviewed by CCB, "
                "approved by sponsor. "
                "Escalation path: Team → PM → Steering Committee → Sponsor. "
                "Reporting: weekly status reports to PM, monthly highlight reports to sponsor. "
                "Stage gates at end of each phase with go/no-go decision by project board. "
                "Lessons learned session at project close."
            )
        )
        findings = check_governance(sections)
        critical_high = [f for f in findings if f.severity in (Severity.CRITICAL, Severity.HIGH)]
        assert len(critical_high) == 0, f"Unexpected: {[(f.rule_name, f.title) for f in critical_high]}"


# ═══════════════════════════════════════════════════════════════════════════════
# CONSISTENCY RULES
# ═══════════════════════════════════════════════════════════════════════════════

class TestConsistencyRules:

    def test_low_scope_deliverable_overlap_flagged(self):
        sections = ExtractedSections(
            scope="Migrate the legacy billing database to cloud infrastructure with encryption.",
            deliverables="Mobile application with push notifications and social login features.",
        )
        findings = check_consistency(sections)
        assert _has_rule(findings, "SCOPE_DELIVERABLE_ALIGNMENT")

    def test_good_scope_deliverable_overlap_not_flagged(self):
        sections = ExtractedSections(
            scope="Migrate the legacy billing database to cloud infrastructure with full encryption.",
            deliverables=(
                "Migrated billing database on cloud infrastructure. "
                "Encryption configuration documented and verified. "
                "Migration runbook and rollback plan."
            ),
        )
        findings = check_consistency(sections)
        assert not _has_rule(findings, "SCOPE_DELIVERABLE_ALIGNMENT")

    def test_objectives_deliverable_misalignment_flagged(self):
        sections = ExtractedSections(
            objectives="Improve customer satisfaction scores and reduce support tickets by 30% by Q4.",
            deliverables="New database schema, API gateway, infrastructure upgrade, monitoring dashboard.",
        )
        findings = check_consistency(sections)
        assert _has_rule(findings, "OBJECTIVES_DELIVERABLE_ALIGNMENT")


# ═══════════════════════════════════════════════════════════════════════════════
# SCORING ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class TestScoringEngine:

    def test_empty_bundle_scores_ten(self):
        from app.rule_engine.models import HybridBundle, CategoryResult
        from app.pipeline.scoring_engine import compute_scores

        bundle = HybridBundle(
            structure=CategoryResult(category="structure", label="Structure", rule_findings=[]),
            timeline=CategoryResult(category="timeline", label="Timeline", rule_findings=[]),
            risk=CategoryResult(category="risk", label="Risk", rule_findings=[]),
            resource=CategoryResult(category="resource", label="Resource", rule_findings=[]),
            governance=CategoryResult(category="governance", label="Governance", rule_findings=[]),
            consistency=CategoryResult(category="consistency", label="Consistency", rule_findings=[]),
        )
        scores = compute_scores(bundle)
        assert scores.overall == 10.0
        assert scores.grade == "A"

    def test_critical_finding_reduces_score(self):
        from app.rule_engine.models import HybridBundle, CategoryResult, RuleFinding, Severity
        from app.pipeline.scoring_engine import compute_scores

        critical = RuleFinding(
            rule_id="STR-001", category="structure", severity=Severity.CRITICAL,
            title="Test", explanation="Test", suggested_fix="Test", rule_name="TEST"
        )
        bundle = HybridBundle(
            structure=CategoryResult(category="structure", label="Structure", rule_findings=[critical]),
            timeline=CategoryResult(category="timeline", label="Timeline", rule_findings=[]),
            risk=CategoryResult(category="risk", label="Risk", rule_findings=[]),
            resource=CategoryResult(category="resource", label="Resource", rule_findings=[]),
            governance=CategoryResult(category="governance", label="Governance", rule_findings=[]),
            consistency=CategoryResult(category="consistency", label="Consistency", rule_findings=[]),
        )
        scores = compute_scores(bundle)
        assert scores.structure < 10.0
        assert scores.overall < 10.0

    def test_score_never_below_zero(self):
        from app.rule_engine.models import HybridBundle, CategoryResult, RuleFinding, Severity
        from app.pipeline.scoring_engine import compute_scores

        # Flood with critical findings
        findings = [
            RuleFinding(
                rule_id=f"STR-{i:03d}", category="structure", severity=Severity.CRITICAL,
                title=f"Issue {i}", explanation="x", suggested_fix="x", rule_name="TEST"
            )
            for i in range(20)
        ]
        bundle = HybridBundle(
            structure=CategoryResult(category="structure", label="Structure", rule_findings=findings),
            timeline=CategoryResult(category="timeline", label="Timeline", rule_findings=findings),
            risk=CategoryResult(category="risk", label="Risk", rule_findings=findings),
            resource=CategoryResult(category="resource", label="Resource", rule_findings=findings),
            governance=CategoryResult(category="governance", label="Governance", rule_findings=findings),
            consistency=CategoryResult(category="consistency", label="Consistency", rule_findings=findings),
        )
        scores = compute_scores(bundle)
        assert scores.overall >= 0.0
        assert scores.structure >= 0.0
        assert scores.grade == "F"

    def test_grade_thresholds(self):
        from app.pipeline.scoring_engine import _grade
        assert _grade(9.0) == "A"
        assert _grade(7.5) == "B"
        assert _grade(6.0) == "C"
        assert _grade(4.5) == "D"
        assert _grade(2.0) == "F"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION EXTRACTOR (regex)
# ═══════════════════════════════════════════════════════════════════════════════

class TestSectionExtractor:

    def _preprocess(self, text: str):
        from app.pipeline.preprocessor import PreprocessedText
        return PreprocessedText(
            cleaned_text=text,
            line_count=len(text.splitlines()),
            word_count=len(text.split()),
            char_count=len(text),
        )

    def test_markdown_headings_extracted(self):
        from app.pipeline.section_extractor import _extract_by_regex

        text = """
# Objectives
Reduce processing time by 30% by Q4 2025.

# Scope
In scope: billing system migration. Out of scope: CRM.

# Deliverables
Migrated system, documentation, training materials.

# Timeline
Phase 1: 4 weeks. Milestone: design complete.

# Resources
PM: Jane (100% FTE). Developer: John (80% FTE).

# Risks
Risk: delay. Mitigation: buffer. Owner: PM. Probability: medium.
"""
        sections = _extract_by_regex(text)
        assert sections.objectives is not None
        assert sections.scope is not None
        assert sections.deliverables is not None
        assert sections.timeline is not None
        assert sections.resources is not None
        assert sections.risks is not None
        assert len(sections.present_sections()) >= 5

    def test_plain_headings_extracted(self):
        from app.pipeline.section_extractor import _extract_by_regex

        text = """
Objectives:
Reduce processing time by 30% by Q4 2025.

Scope:
In scope: billing system migration.

Risks:
Risk: delay. Mitigation: buffer. Owner: PM.
"""
        sections = _extract_by_regex(text)
        assert len(sections.present_sections()) >= 2

    def test_missing_sections_detected(self):
        from app.pipeline.section_extractor import _extract_by_regex

        text = """
# Objectives
Reduce processing time by 30% by Q4 2025.

# Scope
In scope: billing system migration.
"""
        sections = _extract_by_regex(text)
        missing = sections.missing_sections()
        assert "risks" in missing
        assert "timeline" in missing
        assert "resources" in missing


# ═══════════════════════════════════════════════════════════════════════════════
# INPUT LAYER
# ═══════════════════════════════════════════════════════════════════════════════

class TestInputLayer:

    def test_ingest_plain_text(self):
        from app.pipeline.input_layer import ingest_text
        raw = ingest_text("This is a project plan with some content about objectives and scope.")
        assert raw.source == "text"
        assert raw.filename is None
        assert len(raw.raw_text) > 0

    def test_ingest_empty_text_raises(self):
        from app.pipeline.input_layer import ingest_text
        with pytest.raises(ValueError):
            ingest_text("")

    def test_ingest_whitespace_only_raises(self):
        from app.pipeline.input_layer import ingest_text
        with pytest.raises(ValueError):
            ingest_text("   \n\n  ")

    def test_ingest_txt_file(self):
        from app.pipeline.input_layer import ingest_file
        content = "Project plan content for testing purposes with objectives and scope."
        raw = ingest_file("test.txt", content.encode("utf-8"))
        assert raw.source == "upload"
        assert raw.filename == "test.txt"
        assert "objectives" in raw.raw_text

    def test_unsupported_file_type_raises(self):
        from app.pipeline.input_layer import ingest_file
        with pytest.raises(ValueError, match="Unsupported file type"):
            ingest_file("plan.xlsx", b"some bytes")

    def test_empty_file_raises(self):
        from app.pipeline.input_layer import ingest_file
        with pytest.raises(ValueError):
            ingest_file("plan.txt", b"   ")


# ═══════════════════════════════════════════════════════════════════════════════
# PREPROCESSOR
# ═══════════════════════════════════════════════════════════════════════════════

class TestPreprocessor:

    def test_windows_line_endings_normalised(self):
        from app.pipeline.preprocessor import preprocess
        from app.pipeline.input_layer import RawInput
        raw = RawInput(source="text", filename=None, raw_text="Line 1\r\nLine 2\r\nLine 3")
        result = preprocess(raw)
        assert "\r" not in result.cleaned_text

    def test_word_count_correct(self):
        from app.pipeline.preprocessor import preprocess
        from app.pipeline.input_layer import RawInput
        raw = RawInput(source="text", filename=None, raw_text="one two three four five")
        result = preprocess(raw)
        assert result.word_count == 5

    def test_excessive_blank_lines_collapsed(self):
        from app.pipeline.preprocessor import preprocess
        from app.pipeline.input_layer import RawInput
        raw = RawInput(source="text", filename=None, raw_text="A\n\n\n\n\nB")
        result = preprocess(raw)
        assert "\n\n\n" not in result.cleaned_text


# ═══════════════════════════════════════════════════════════════════════════════
# FULL PIPELINE (no LLM)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFullPipeline:

    GOOD_PLAN = """
# Objectives
Reduce customer onboarding time by 40% by Q3 2026.
Achieve 99.9% system uptime measured monthly by automated monitoring.
Complete full migration by 30 June 2026.

# Scope
In scope: migration of legacy billing system to cloud infrastructure.
Out of scope: CRM integration, mobile app changes, third-party reporting.

# Deliverables
1. Migrated billing system — accepted when sign-off from Finance Director after UAT completion.
2. Data migration report — approved by Data Owner.
3. Training materials — verified by HR Director.
4. Runbook and rollback plan — reviewed by Tech Lead.

# Timeline
Phase 1 (Discovery): 3 weeks. After kick-off.
Phase 2 (Development): 8 weeks. Depends on Phase 1 completion.
Phase 3 (Testing/UAT): 3 weeks with review and sign-off. After development.
Phase 4 (Go-live): 1 week. Milestone: go-live 30 June 2026.
Buffer: 1 week contingency reserve.

# Resources
Project Manager: Jane Smith (100% FTE).
Lead Developer: John Doe (80% FTE).
Business Analyst: Sarah Lee (60% FTE).
QA Tester: Mike Brown (50% FTE).
Project Sponsor: CTO.

# Risks
Risk Register:
R001 — Schedule delay. Probability: High. Impact: High. Owner: PM Jane Smith.
Mitigation: weekly tracking, 1-week contingency buffer built into schedule.
R002 — Key person dependency (John Doe). Probability: Low. Impact: High. Owner: PM.
Mitigation: cross-training sessions, full documentation of all work.
R003 — Technical integration failure. Probability: Medium. Impact: High. Owner: Tech Lead.
Mitigation: spike testing in Phase 1, fallback architecture documented.
R004 — Budget overrun. Probability: Low. Impact: High. Owner: Sponsor.
Mitigation: monthly cost reviews, change control process enforced.
R005 — Scope creep. Probability: High. Impact: Medium. Owner: PM.
Mitigation: change control process, scope freeze after Phase 1.
R006 — Regulatory compliance risk. Probability: Low. Impact: Critical. Owner: Compliance Lead.
Mitigation: legal review at design stage, GDPR assessment completed.

# Governance
Project Sponsor: CTO (executive sponsor and decision authority).
Steering Committee: CFO, CTO, Head of Engineering — meets monthly.
Change control: all changes submitted via Change Request form, reviewed by CCB, approved by sponsor.
Escalation path: Team Member → PM → Steering Committee → Sponsor.
Reporting: weekly status reports to PM, monthly highlight reports to steering committee.
Stage gates at end of each phase with go/no-go decision by project board.
Lessons learned session planned at project close.

# Assumptions
Legacy system access will be granted by end of week 2.
All stakeholders available for UAT in Phase 3.

# Budget
Total budget: £150,000. Contingency: £20,000 (13%).
"""

    POOR_PLAN = """
Project Plan

We want to make things better and improve the system for users across the organisation.
The team will work on this project and deliver some outputs that stakeholders need.
It should be done soon, probably within a few months depending on how things go.
We have some people working on it from various departments who will contribute.
There might be some risks but we will deal with them as they come up during delivery.
The budget is not yet confirmed but we expect it to be reasonable for the scope involved.
"""

    def test_good_plan_scores_high(self):
        from app.pipeline.orchestrator import run_pipeline
        report = run_pipeline(text=self.GOOD_PLAN, enable_llm=False)
        assert report.overall_score >= 6.0, f"Expected >=6.0, got {report.overall_score}"
        assert report.grade in ("A", "B", "C")

    def test_poor_plan_scores_low(self):
        from app.pipeline.orchestrator import run_pipeline
        report = run_pipeline(text=self.POOR_PLAN, enable_llm=False)
        assert report.overall_score <= 5.0, f"Expected <=5.0, got {report.overall_score}"

    def test_good_plan_has_fewer_critical_findings(self):
        from app.pipeline.orchestrator import run_pipeline
        report = run_pipeline(text=self.GOOD_PLAN, enable_llm=False)
        all_findings = [f for cat in report.category_results for f in cat.rule_findings]
        critical = [f for f in all_findings if f.severity == Severity.CRITICAL]
        assert len(critical) <= 2, f"Too many critical findings on good plan: {[(f.rule_id, f.title) for f in critical]}"

    def test_poor_plan_has_many_critical_findings(self):
        from app.pipeline.orchestrator import run_pipeline
        report = run_pipeline(text=self.POOR_PLAN, enable_llm=False)
        all_findings = [f for cat in report.category_results for f in cat.rule_findings]
        critical = [f for f in all_findings if f.severity == Severity.CRITICAL]
        assert len(critical) >= 3, f"Expected >=3 critical findings on poor plan, got {len(critical)}"

    def test_report_structure_complete(self):
        from app.pipeline.orchestrator import run_pipeline
        report = run_pipeline(text=self.GOOD_PLAN, enable_llm=False)
        assert report.generated_at
        assert report.overall_score >= 0
        assert report.overall_score <= 10
        assert report.grade in ("A", "B", "C", "D", "F")
        assert len(report.category_results) == 6
        assert len(report.recommendations) > 0
        assert report.llm_enabled is False

    def test_too_short_input_raises(self):
        from app.pipeline.orchestrator import run_pipeline, PipelineError
        with pytest.raises(PipelineError, match="too short"):
            run_pipeline(text="Short text.", enable_llm=False)

    def test_no_input_raises(self):
        from app.pipeline.orchestrator import run_pipeline, PipelineError
        with pytest.raises(PipelineError):
            run_pipeline(enable_llm=False)
