"""
Shared Pydantic models for analysis module outputs.
All analysis modules return typed objects defined here.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Finding(BaseModel):
    id: str
    category: str
    severity: Severity
    title: str
    description: str
    recommendation: str


class StructureAnalysisResult(BaseModel):
    missing_sections: list[str] = Field(default_factory=list)
    weak_sections: list[str] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    completeness_score: float = Field(ge=0.0, le=10.0)


class ConsistencyAnalysisResult(BaseModel):
    scope_deliverable_issues: list[str] = Field(default_factory=list)
    timeline_effort_issues: list[str] = Field(default_factory=list)
    resource_workload_issues: list[str] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    consistency_score: float = Field(ge=0.0, le=10.0)


class TimelineAnalysisResult(BaseModel):
    unrealistic_durations: list[str] = Field(default_factory=list)
    missing_dependencies: list[str] = Field(default_factory=list)
    overlaps: list[str] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    timeline_score: float = Field(ge=0.0, le=10.0)


class RiskAnalysisResult(BaseModel):
    missing_risks: list[str] = Field(default_factory=list)
    unmitigated_risks: list[str] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    risk_score: float = Field(ge=0.0, le=10.0)


class ResourceAnalysisResult(BaseModel):
    over_allocated: list[str] = Field(default_factory=list)
    missing_roles: list[str] = Field(default_factory=list)
    skill_mismatches: list[str] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    resource_score: float = Field(ge=0.0, le=10.0)


class GovernanceAnalysisResult(BaseModel):
    findings: list[Finding] = Field(default_factory=list)
    governance_score: float = Field(ge=0.0, le=10.0)


class AnalysisBundle(BaseModel):
    structure: Optional[StructureAnalysisResult] = None
    consistency: Optional[ConsistencyAnalysisResult] = None
    timeline: Optional[TimelineAnalysisResult] = None
    risk: Optional[RiskAnalysisResult] = None
    resource: Optional[ResourceAnalysisResult] = None
    governance: Optional[GovernanceAnalysisResult] = None
