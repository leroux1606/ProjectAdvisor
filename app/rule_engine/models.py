"""
Rule Engine Models — shared types for rule-based findings and AI insights.

RuleFinding  : produced by deterministic rules (primary, always present)
AIInsight    : produced by LLM (secondary, optional / gracefully absent)
HybridBundle : aggregates both layers per category
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass(frozen=True)
class RuleFinding:
    """A deterministic finding produced by an explicit rule check."""
    rule_id: str          # e.g. STR-001
    category: str         # structure | timeline | risk | resource | governance | consistency
    severity: Severity
    title: str
    explanation: str      # why the rule fired
    suggested_fix: str    # concrete action
    rule_name: str        # human-readable rule that triggered this


@dataclass(frozen=True)
class AIInsight:
    """A soft suggestion produced by the LLM to enrich a rule finding or add nuance."""
    category: str
    title: str
    insight: str          # wording improvement or soft issue
    suggestion: str       # enhanced recommendation


@dataclass
class CategoryResult:
    """Findings + insights for one analysis category."""
    category: str
    label: str
    rule_findings: list[RuleFinding] = field(default_factory=list)
    ai_insights: list[AIInsight] = field(default_factory=list)

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.rule_findings if f.severity == Severity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for f in self.rule_findings if f.severity == Severity.HIGH)

    @property
    def total_findings(self) -> int:
        return len(self.rule_findings)


@dataclass
class HybridBundle:
    """Full output of the hybrid analysis engine."""
    structure: Optional[CategoryResult] = None
    timeline: Optional[CategoryResult] = None
    risk: Optional[CategoryResult] = None
    resource: Optional[CategoryResult] = None
    governance: Optional[CategoryResult] = None
    consistency: Optional[CategoryResult] = None

    def all_rule_findings(self) -> list[RuleFinding]:
        findings: list[RuleFinding] = []
        for cat in [self.structure, self.timeline, self.risk,
                    self.resource, self.governance, self.consistency]:
            if cat:
                findings.extend(cat.rule_findings)
        return findings

    def all_ai_insights(self) -> list[AIInsight]:
        insights: list[AIInsight] = []
        for cat in [self.structure, self.timeline, self.risk,
                    self.resource, self.governance, self.consistency]:
            if cat:
                insights.extend(cat.ai_insights)
        return insights
