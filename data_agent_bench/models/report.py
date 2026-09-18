from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclasses.dataclass
class DeterministicScore:
    exact_match: bool
    numeric_match: bool
    numeric_tolerance: float
    similarity_score: float
    field_scores: Dict[str, float]
    component_scores: Dict[str, float] = dataclasses.field(default_factory=dict)
    component_weights: Dict[str, float] = dataclasses.field(default_factory=dict)
    field_details: Dict[str, Dict[str, Any]] = dataclasses.field(default_factory=dict)
    raw_field_scores: Dict[str, float] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exact_match": self.exact_match,
            "numeric_match": self.numeric_match,
            "numeric_tolerance": self.numeric_tolerance,
            "similarity_score": self.similarity_score,
            "field_scores": self.field_scores,
            "component_scores": self.component_scores,
            "component_weights": self.component_weights,
            "field_details": self.field_details,
            "raw_field_scores": self.raw_field_scores,
        }


@dataclasses.dataclass
class ProcessScore:
    planning_score: float
    tool_efficiency: float
    error_recovery_score: float
    feedback_loop_score: float
    step_utilization: float
    redundant_action_ratio: float
    recovery_patterns: Dict[str, int] = dataclasses.field(default_factory=dict)
    diagnostic_ratio: float = 0.0
    tool_call_diversity: float = 0.0
    first_success_step: int = -1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "planning_score": self.planning_score,
            "tool_efficiency": self.tool_efficiency,
            "error_recovery_score": self.error_recovery_score,
            "feedback_loop_score": self.feedback_loop_score,
            "step_utilization": self.step_utilization,
            "redundant_action_ratio": self.redundant_action_ratio,
            "recovery_patterns": self.recovery_patterns,
            "diagnostic_ratio": self.diagnostic_ratio,
            "tool_call_diversity": self.tool_call_diversity,
            "first_success_step": self.first_success_step,
        }


@dataclasses.dataclass
class SafetyViolation:
    rule_id: str
    category: str
    severity: str
    penalty: float
    evidence_step: Optional[int]
    message: str
    evidence: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "category": self.category,
            "severity": self.severity,
            "penalty": self.penalty,
            "evidence_step": self.evidence_step,
            "message": self.message,
            "evidence": self.evidence,
        }


@dataclasses.dataclass
class SafetyRubricScore:
    score: float
    violations: List[SafetyViolation] = dataclasses.field(default_factory=list)
    component_scores: Dict[str, float] = dataclasses.field(default_factory=dict)
    total_penalty: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "total_penalty": self.total_penalty,
            "component_scores": self.component_scores,
            "violations": [v.to_dict() for v in self.violations],
        }


@dataclasses.dataclass
class RiskScore:
    safety_compliant: bool
    violations: List[str]
    high_freq_tool_calls: bool
    resource_within_budget: bool
    risky_patterns: List[str]
    risk_level: str  # "none", "low", "medium", "high"
    execution_safety: Optional[SafetyRubricScore] = None
    analytical_safety: Optional[SafetyRubricScore] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "safety_compliant": self.safety_compliant,
            "violations": self.violations,
            "high_freq_tool_calls": self.high_freq_tool_calls,
            "resource_within_budget": self.resource_within_budget,
            "risky_patterns": self.risky_patterns,
            "risk_level": self.risk_level,
            "execution_safety": self.execution_safety.to_dict() if self.execution_safety else None,
            "analytical_safety": self.analytical_safety.to_dict() if self.analytical_safety else None,
        }




@dataclasses.dataclass
class TraceGroundingScore:
    grounding_rate: float
    dependency_score: float
    matched_steps: List[Dict[str, Any]]
    unsupported_steps: List[Dict[str, Any]]
    missing_declared_trace: bool
    format_valid: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "grounding_rate": self.grounding_rate,
            "dependency_score": self.dependency_score,
            "matched_steps": self.matched_steps,
            "unsupported_steps": self.unsupported_steps,
            "missing_declared_trace": self.missing_declared_trace,
            "format_valid": self.format_valid,
        }


@dataclasses.dataclass
class TraceIntegrityScore:
    integrity_score: float
    step_sequence_valid: bool
    required_fields_valid: bool
    metric_consistency_valid: bool
    final_answer_supported: bool
    issues: List[Dict[str, Any]] = dataclasses.field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "integrity_score": self.integrity_score,
            "step_sequence_valid": self.step_sequence_valid,
            "required_fields_valid": self.required_fields_valid,
            "metric_consistency_valid": self.metric_consistency_valid,
            "final_answer_supported": self.final_answer_supported,
            "issues": self.issues,
        }


@dataclasses.dataclass
class ScorerAuditScore:
    missed_trace_value: bool
    format_extraction_issue: bool
    trace_value_hits: List[Dict[str, Any]] = dataclasses.field(default_factory=list)
    audit_notes: List[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "missed_trace_value": self.missed_trace_value,
            "format_extraction_issue": self.format_extraction_issue,
            "trace_value_hits": self.trace_value_hits,
            "audit_notes": self.audit_notes,
        }


@dataclasses.dataclass
class MetricBundle:
    completion_rate: float
    result_accuracy: float
    process_quality: float
    safety_score: float
    token_efficiency: float
    wall_time_seconds: float
    total_tokens: int
    total_cost_usd: float
    strategy_stability: Optional[float] = None
    llm_judge_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "completion_rate": self.completion_rate,
            "result_accuracy": self.result_accuracy,
            "process_quality": self.process_quality,
            "safety_score": self.safety_score,
            "token_efficiency": self.token_efficiency,
            "wall_time_seconds": self.wall_time_seconds,
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost_usd,
            "strategy_stability": self.strategy_stability,
            "llm_judge_score": self.llm_judge_score,
        }


@dataclasses.dataclass
class FailureAttribution:
    primary_cause: str
    sub_cause: str
    suggested_improvement: str
    diagnostic_warnings: List[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_cause": self.primary_cause,
            "primary_failure": self.primary_cause,
            "sub_cause": self.sub_cause,
            "suggested_improvement": self.suggested_improvement,
            "diagnostic_warnings": self.diagnostic_warnings,
        }


@dataclasses.dataclass
class EvaluationReport:
    report_id: str
    instance_id: str
    timestamp: datetime
    deterministic: DeterministicScore
    process: ProcessScore
    risk: RiskScore
    metrics: MetricBundle
    failure_attribution: Optional[FailureAttribution]
    trajectory_summary: List[Dict[str, Any]]
    final_code: str
    execution_result: str
    raw_agent_output: str = ""
    benchmark_extracted_answer: Dict[str, Any] = dataclasses.field(default_factory=dict)
    evaluation_protocol: str = "v2"
    framework_version: str = "1.0.0"
    notes: str = ""
    experiment_condition: Optional[str] = None   # "clean" | "perturbed"
    perturbation_type: Optional[str] = None      # "column_rename" | "stat_trap" | "full_obfuscation"
    paired_report_id: Optional[str] = None
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)
    trace_grounding: Optional[TraceGroundingScore] = None
    trace_integrity: Optional[TraceIntegrityScore] = None
    scorer_audit: Optional[ScorerAuditScore] = None

    def to_dict(self) -> Dict[str, Any]:
        risk_dict = self.risk.to_dict()
        return {
            "report_id": self.report_id,
            "instance_id": self.instance_id,
            "timestamp": self.timestamp.isoformat(),
            "framework_version": self.framework_version,
            "evaluation_protocol": self.evaluation_protocol,
            "final_code": self.final_code,
            "execution_result": self.execution_result,
            "raw_agent_output": self.raw_agent_output,
            "benchmark_extracted_answer": self.benchmark_extracted_answer,
            "trajectory_summary": self.trajectory_summary,
            "metrics": self.metrics.to_dict(),
            "scores": {
                "deterministic": self.deterministic.to_dict(),
                "process": self.process.to_dict(),
                "risk": risk_dict,
                "execution_safety": risk_dict.get("execution_safety"),
                "analytical_safety": risk_dict.get("analytical_safety"),
                "trace_grounding": self.trace_grounding.to_dict() if self.trace_grounding else None,
                "trace_integrity": self.trace_integrity.to_dict() if self.trace_integrity else None,
                "scorer_audit": self.scorer_audit.to_dict() if self.scorer_audit else None,
            },
            "failure_attribution": self.failure_attribution.to_dict() if self.failure_attribution else None,
            "notes": self.notes,
            "experiment_condition": self.experiment_condition,
            "perturbation_type": self.perturbation_type,
            "paired_report_id": self.paired_report_id,
            "metadata": self.metadata,
        }
