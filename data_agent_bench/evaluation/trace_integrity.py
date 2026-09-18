from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..models.report import TraceIntegrityScore
from ..models.task import TaskInput
from ..models.trace import ActionType, AgentTrace, TraceStep
from .base import BaseEvaluator


class TraceIntegrityValidator(BaseEvaluator):
    """
    Validates the observed execution trace itself.

    This is intentionally separate from TraceGroundingVerifier: grounding checks
    whether a model-declared trace is supported by observed steps, while
    integrity checks whether the observed trace is internally trustworthy.
    """

    @property
    def name(self) -> str:
        return "TraceIntegrityValidator"

    def evaluate(
        self,
        task: TaskInput,
        trace: AgentTrace,
        final_output: Dict[str, Any],
        ground_truth: Optional[Dict[str, Any]],
    ) -> TraceIntegrityScore:
        issues: List[Dict[str, Any]] = []

        step_sequence_valid = self._check_step_sequence(trace.steps, issues)
        required_fields_valid = self._check_required_fields(trace.steps, issues)
        metric_consistency_valid = self._check_metric_consistency(trace, issues)
        final_answer_supported = self._check_final_answer_support(trace, final_output, issues)

        checks = [
            step_sequence_valid,
            required_fields_valid,
            metric_consistency_valid,
            final_answer_supported,
        ]
        integrity_score = round(sum(1.0 for ok in checks if ok) / len(checks), 4)

        return TraceIntegrityScore(
            integrity_score=integrity_score,
            step_sequence_valid=step_sequence_valid,
            required_fields_valid=required_fields_valid,
            metric_consistency_valid=metric_consistency_valid,
            final_answer_supported=final_answer_supported,
            issues=issues,
        )

    def _check_step_sequence(self, steps: List[TraceStep], issues: List[Dict[str, Any]]) -> bool:
        if not steps:
            issues.append({
                "check": "step_sequence",
                "severity": "high",
                "message": "Trace has no observed steps.",
            })
            return False

        observed = [s.step for s in steps]
        expected = list(range(1, len(steps) + 1))
        valid = observed == expected
        if not valid:
            missing = [s for s in expected if s not in observed]
            duplicates = sorted({s for s in observed if observed.count(s) > 1})
            issues.append({
                "check": "step_sequence",
                "severity": "high",
                "message": "Trace step ids are not contiguous and ordered from 1..N.",
                "observed": observed,
                "expected": expected,
                "missing": missing,
                "duplicates": duplicates,
            })
        return valid

    def _check_required_fields(self, steps: List[TraceStep], issues: List[Dict[str, Any]]) -> bool:
        valid = True
        for step in steps:
            missing = []
            if step.timestamp is None:
                missing.append("timestamp")
            if not step.action_type:
                missing.append("action_type")
            if not str(step.action or "").strip():
                missing.append("action")

            if step.action_type in {ActionType.CODE_EXEC, ActionType.TOOL_CALL}:
                if not step.tool_name:
                    missing.append("tool_name")
                if step.tool_args is None:
                    missing.append("tool_args")
                if step.tool_result is None and not str(step.observation or "").strip():
                    missing.append("tool_result_or_observation")

            if step.action_type == ActionType.ERROR:
                text = " ".join([str(step.action or ""), str(step.observation or ""), str(step.tool_result or "")])
                if "error" not in text.lower() and "exception" not in text.lower():
                    missing.append("error_evidence")

            if missing:
                valid = False
                issues.append({
                    "check": "required_fields",
                    "severity": "medium",
                    "step": step.step,
                    "message": "Trace step is missing required observable fields.",
                    "missing": missing,
                })
        return valid

    def _check_metric_consistency(self, trace: AgentTrace, issues: List[Dict[str, Any]]) -> bool:
        valid = True
        summed_tokens = sum(s.tokens_in + s.tokens_out for s in trace.steps)
        summed_cost = sum(s.cost_usd for s in trace.steps)

        if trace.total_tokens != summed_tokens:
            valid = False
            issues.append({
                "check": "metric_consistency",
                "severity": "medium",
                "message": "Trace total_tokens does not match the sum of step token counts.",
                "reported": trace.total_tokens,
                "computed": summed_tokens,
            })

        if abs(trace.total_cost_usd - summed_cost) > 1e-9:
            valid = False
            issues.append({
                "check": "metric_consistency",
                "severity": "medium",
                "message": "Trace total_cost_usd does not match the sum of step costs.",
                "reported": trace.total_cost_usd,
                "computed": summed_cost,
            })

        if trace.wall_time_seconds < 0:
            valid = False
            issues.append({
                "check": "metric_consistency",
                "severity": "high",
                "message": "Trace wall_time_seconds is negative.",
                "reported": trace.wall_time_seconds,
            })

        if trace.termination is not None and trace.end_time is None:
            valid = False
            issues.append({
                "check": "metric_consistency",
                "severity": "medium",
                "message": "Trace has termination metadata but no end_time.",
            })

        return valid

    def _check_final_answer_support(
        self,
        trace: AgentTrace,
        final_output: Dict[str, Any],
        issues: List[Dict[str, Any]],
    ) -> bool:
        has_final_step = any(s.action_type == ActionType.FINAL_ANSWER for s in trace.steps)
        has_reported_output = any(
            str(final_output.get(key, "")).strip()
            for key in ("final_answer", "execution_result", "final_code")
        )

        if trace.termination and trace.termination.reason == "completed":
            if not has_final_step and not has_reported_output:
                issues.append({
                    "check": "final_answer_support",
                    "severity": "high",
                    "message": "Trace completed but has no final answer step or non-empty final output.",
                })
                return False
            return True

        if has_reported_output and not trace.steps:
            issues.append({
                "check": "final_answer_support",
                "severity": "medium",
                "message": "Final output exists but there are no observed trace steps.",
            })
            return False

        return True
