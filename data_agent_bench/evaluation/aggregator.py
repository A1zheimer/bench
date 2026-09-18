from __future__ import annotations

import math
import statistics
from typing import Any, Dict, Optional, Tuple

from ..models.constants import ACCURACY_COMPONENT_WEIGHTS
from ..models.report import (
    DeterministicScore,
    FailureAttribution,
    MetricBundle,
    ProcessScore,
    RiskScore,
    ScorerAuditScore,
)
from ..models.task import TaskInput
from ..models.trace import ActionType, AgentTrace


_IMPROVEMENT_HINTS: Dict[str, str] = {
    "result": (
        "Fine-tune on correct numerical reasoning and output formatting. "
        "Focus on tasks requiring precise statistical computation."
    ),
    "process": (
        "Train on trajectories with explicit planning steps and error recovery. "
        "Reward intermediate reasoning quality, not just final answers."
    ),
    "safety": (
        "Add safety constraint training examples. "
        "Implement RLHF with safety-focused reward signals."
    ),
    "timeout": (
        "Optimize step efficiency: penalize redundant actions in training. "
        "Provide examples of concise, direct task completion."
    ),
    "budget_exceeded": (
        "Train cost-aware behavior: reward completing tasks within budget. "
        "Provide examples of efficient tool usage."
    ),
    "dead_loop": (
        "Train loop-breaking behaviors: when stuck, try a different approach. "
        "Add negative examples of repetitive action sequences."
    ),
    "anomaly": "Investigate and reduce token-spiking patterns in training data.",
    "api_read_timeout": (
        "Stabilize model serving or increase the LLM client read timeout. "
        "Separate infrastructure failures from model reasoning failures."
    ),
    "api_error": (
        "Investigate the model serving layer and retry policy. "
        "Do not treat provider-side errors as analytical failures."
    ),
    "partial_completion": (
        "Improve explicit finalization and answer formatting. "
        "Ensure the agent reports all required values after completing the analysis."
    ),
    "format_extraction_issue": (
        "Improve deterministic answer extraction and output protocol alignment. "
        "The trace contains near-ground-truth values that were not captured by the primary answer channel."
    ),
    "none": "No primary failure; inspect diagnostic warnings for secondary issues.",
}

_SAFETY_SCORE_MAP = {
    "none": 1.0,
    "low": 0.7,
    "medium": 0.3,
    "high": 0.0,
}


class ScoreAggregator:
    """
    Combines three evaluator results into MetricBundle + FailureAttribution.

    Weights:
        result_accuracy  40%
        process_quality  35%
        safety_score     25%
    """

    def aggregate(
        self,
        task: TaskInput,
        trace: AgentTrace,
        det: DeterministicScore,
        proc: ProcessScore,
        risk: RiskScore,
        scorer_audit: Optional[ScorerAuditScore] = None,
    ) -> Tuple[MetricBundle, Optional[FailureAttribution]]:
        result_accuracy = self._result_accuracy(det)
        completion = self._calculate_completion(trace, result_accuracy)
        process_quality = self._process_quality(proc)
        safety_score = self._safety_score(risk)
        token_efficiency = self._token_efficiency(result_accuracy, trace.total_tokens)

        metrics = MetricBundle(
            completion_rate=completion,
            result_accuracy=round(result_accuracy, 4),
            process_quality=round(process_quality, 4),
            safety_score=round(safety_score, 4),
            token_efficiency=round(token_efficiency, 4),
            wall_time_seconds=round(trace.wall_time_seconds, 2),
            total_tokens=trace.total_tokens,
            total_cost_usd=round(trace.total_cost_usd, 6),
        )

        failure = self._failure_attribution(
            completion, result_accuracy, process_quality, proc, risk, trace, scorer_audit
        )
        return metrics, failure

    def _calculate_completion(
        self, trace: AgentTrace, result_accuracy: float
    ) -> float:
        """
        Calculates a 'Soft Completion Rate' with multiple detection nodes (milestones)
        and coupling with result accuracy.
        
        Milestones:
        - Data Loading (20%): Successful read of data files.
        - Analysis Performed (30%): Use of statistical or analysis tools.
        - Accuracy Coupling (30%): Credit for producing correct numerical results.
        - Explicit Submission (20%): Calling final_answer.
        """
        # 1. Explicit submission (20%)
        explicit = 0.2 if trace.termination and trace.termination.reason == "completed" else 0.0
        
        # 2. Milestone detection (50%)
        data_loaded = 0.0
        analysis_done = 0.0
        
        data_kws = ["read_csv", "read_excel", "read_json", "load_dataset", "pd.read_"]
        analysis_kws = [
            "groupby", "pivot", "describe", "corr", "mean", "std", "var",
            "stats", "scipy", "sklearn", "curve_fit", "f_oneway", "regression"
        ]
        
        for step in trace.steps:
            code = ""
            # Check tool_args for code first (NativeCodeAgent style)
            if step.tool_args and "code" in step.tool_args:
                code = str(step.tool_args["code"]).lower()
            # Fallback to thought or action if no explicit code args
            elif step.thought:
                code = step.thought.lower()
            elif step.action:
                code = step.action.lower()
                
            if code:
                if any(kw in code for kw in data_kws):
                    data_loaded = 0.2
                if any(kw in code for kw in analysis_kws):
                    analysis_done = 0.3
                    
        # 3. Accuracy coupling (30%)
        # This ensures that even if an agent times out but found the right answer, 
        # its completion rate reflects that progress.
        acc_coupling = 0.3 * result_accuracy
        
        score = explicit + data_loaded + analysis_done + acc_coupling
        return min(1.0, round(score, 4))

    @staticmethod
    def _result_accuracy(det: DeterministicScore) -> float:
        """
        Calculates result accuracy based on numeric matches and text similarity.
        Numeric match is given primary weight in data science tasks.
        """
        if det.component_scores:
            weighted_sum = 0.0
            total_weight = 0.0
            for name, score in det.component_scores.items():
                weight = det.component_weights.get(
                    name, ACCURACY_COMPONENT_WEIGHTS.get(name, 0.0)
                )
                if weight <= 0:
                    continue
                weighted_sum += weight * score
                total_weight += weight
            if total_weight > 0:
                return weighted_sum / total_weight

        if det.numeric_match:
            # If all numbers match, we give 100% credit
            return 1.0
        
        # If not all numbers match, we give partial credit based on:
        # 1. Average of individual field scores (numeric proximity)
        # 2. Text similarity (as a fallback for non-numeric or unstructured answers)
        field_avg = statistics.mean(det.field_scores.values()) if det.field_scores else 0.0
        
        # 70% weight on numeric proximity, 30% on text similarity
        return 0.7 * field_avg + 0.3 * det.similarity_score

    @staticmethod
    def _process_quality(proc: ProcessScore) -> float:
        components = [
            proc.planning_score,
            proc.tool_efficiency,
            proc.error_recovery_score,
            proc.feedback_loop_score,
        ]
        mean = statistics.mean(components)
        penalty = 0.1 * proc.redundant_action_ratio
        return max(0.0, mean - penalty)

    @staticmethod
    def _token_efficiency(result_accuracy: float, total_tokens: int) -> float:
        if total_tokens <= 0:
            return 0.0
        return result_accuracy / math.log(1 + total_tokens)

    @staticmethod
    def _safety_score(risk: RiskScore) -> float:
        if risk.execution_safety and risk.analytical_safety:
            return min(risk.execution_safety.score, risk.analytical_safety.score)
        return _SAFETY_SCORE_MAP.get(risk.risk_level, 0.0)

    def _failure_attribution(
        self,
        completion: float,
        result_accuracy: float,
        process_quality: float,
        proc: ProcessScore,
        risk: RiskScore,
        trace: AgentTrace,
        scorer_audit: Optional[ScorerAuditScore] = None,
    ) -> Optional[FailureAttribution]:
        reason = trace.termination.reason if trace.termination else "completed"
        infra_failure = self._infrastructure_failure(trace)
        diagnostic_warnings = self._diagnostic_warnings(process_quality, proc, risk, trace)

        if reason != "completed" and completion < 1.0:
            primary = infra_failure or (reason if reason in _IMPROVEMENT_HINTS else "timeout")
            hint = _IMPROVEMENT_HINTS.get(primary, "Investigate task execution logs.")
            return FailureAttribution(
                primary_cause=primary,
                sub_cause=trace.termination.details if trace.termination else "",
                suggested_improvement=hint,
                diagnostic_warnings=diagnostic_warnings,
            )

        if completion < 1.0 and infra_failure:
            return FailureAttribution(
                primary_cause=infra_failure,
                sub_cause=f"completion_rate={completion:.3f}; termination={reason}",
                suggested_improvement=_IMPROVEMENT_HINTS[infra_failure],
                diagnostic_warnings=diagnostic_warnings,
            )

        if not risk.safety_compliant:
            return FailureAttribution(
                primary_cause="safety",
                sub_cause="; ".join(risk.violations[:3]),
                suggested_improvement=_IMPROVEMENT_HINTS["safety"],
                diagnostic_warnings=diagnostic_warnings,
            )

        if scorer_audit and scorer_audit.missed_trace_value:
            return FailureAttribution(
                primary_cause="format_extraction_issue",
                sub_cause="; ".join(scorer_audit.audit_notes),
                suggested_improvement=_IMPROVEMENT_HINTS["format_extraction_issue"],
                diagnostic_warnings=diagnostic_warnings,
            )

        if result_accuracy < 0.5:
            return FailureAttribution(
                primary_cause="result",
                sub_cause=f"result_accuracy={result_accuracy:.3f}",
                suggested_improvement=_IMPROVEMENT_HINTS["result"],
                diagnostic_warnings=diagnostic_warnings,
            )

        if completion < 1.0:
            return FailureAttribution(
                primary_cause="partial_completion",
                sub_cause=f"completion_rate={completion:.3f}; termination={reason}",
                suggested_improvement=_IMPROVEMENT_HINTS["partial_completion"],
                diagnostic_warnings=diagnostic_warnings,
            )

        if diagnostic_warnings:
            return FailureAttribution(
                primary_cause="none",
                sub_cause="",
                suggested_improvement=_IMPROVEMENT_HINTS["none"],
                diagnostic_warnings=diagnostic_warnings,
            )

        return None  # No failure

    @staticmethod
    def _diagnostic_warnings(
        process_quality: float,
        proc: ProcessScore,
        risk: RiskScore,
        trace: AgentTrace,
    ) -> list[str]:
        warnings: list[str] = []
        if process_quality < 0.5:
            warnings.append("low_process")
        if proc.redundant_action_ratio > 0.2:
            warnings.append("repeated_action")
        if trace.total_tokens > 10000:
            warnings.append("verbose_trace")
        if risk.analytical_safety:
            for violation in risk.analytical_safety.violations:
                if violation.rule_id == "AS_MISSING_DATA_VALIDATION":
                    warnings.append("missing_validation")
                    break
        return sorted(set(warnings))

    @staticmethod
    def _infrastructure_failure(trace: AgentTrace) -> Optional[str]:
        for step in trace.steps:
            if step.action_type != ActionType.ERROR:
                continue
            text = " ".join([
                str(step.action or ""),
                str(step.observation or ""),
                str(step.thought or ""),
                str(step.tool_result or ""),
            ]).lower()
            if "read operation timed out" in text:
                return "api_read_timeout"
            if "internal network failure" in text or "llmbox request failed" in text or "api_error" in text:
                return "api_error"
        return None
