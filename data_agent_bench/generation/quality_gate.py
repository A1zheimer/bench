from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List

from ..repository.schema_validator import SchemaValidationError, SchemaValidator
from .task_generator_agent import GeneratedTask


@dataclass
class GenerationGateResult:
    accepted: bool
    quality_tier: str
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "accepted": self.accepted,
            "quality_tier": self.quality_tier,
            "issues": self.issues,
            "warnings": self.warnings,
        }


@dataclass
class GenerationQualityGate:
    """
    Hard gate for generated tasks before they are allowed into formal task sets.

    The generator may use LLMs to propose tasks, datasets, and solution code.
    This gate enforces the non-negotiable contract: only tasks with verified,
    numeric, schema-valid ground truth and clean generation traces can be
    packaged by the production pipeline.
    """

    require_verified: bool = True
    reject_trace_errors: bool = True
    require_generation_code: bool = True
    require_solution_code: bool = True
    min_numeric_key_values: int = 1
    allow_forced_submit_without_errors: bool = True

    @classmethod
    def formal(cls) -> "GenerationQualityGate":
        return cls()

    @classmethod
    def permissive(cls) -> "GenerationQualityGate":
        return cls(
            require_verified=False,
            reject_trace_errors=False,
            require_generation_code=False,
            require_solution_code=False,
        )

    def evaluate(self, task: GeneratedTask) -> GenerationGateResult:
        issues: List[str] = []
        warnings: List[str] = []

        try:
            SchemaValidator.validate_generated_task(task.task_json, task.ground_truth)
        except SchemaValidationError as exc:
            issues.append(f"SCHEMA_INVALID: {exc}")

        key_values = task.ground_truth.get("key_values", {})
        numeric_count = _count_numeric_key_values(key_values)
        if numeric_count < self.min_numeric_key_values:
            issues.append(
                f"GT_NUMERIC_KEY_VALUES_TOO_FEW: expected >= {self.min_numeric_key_values}, got {numeric_count}"
            )

        if self.require_verified and not task.verified:
            issues.append("GT_NOT_VERIFIED: deterministic solution verification failed")

        if self.require_generation_code and not task.data_generation_code.strip():
            issues.append("MISSING_DATA_GENERATION_CODE")

        if self.require_solution_code and not task.solution_code.strip():
            issues.append("MISSING_SOLUTION_CODE")

        trace_errors = _trace_error_count(task.generation_trace)
        if self.reject_trace_errors and trace_errors:
            issues.append(f"GENERATION_TRACE_ERRORS: {trace_errors}")

        forced_submit = _has_forced_submit(task.generation_trace)
        if forced_submit and trace_errors:
            issues.append("FORCED_SUBMIT_AFTER_ERRORS")
        elif forced_submit and not self.allow_forced_submit_without_errors:
            issues.append("FORCED_SUBMIT_DISALLOWED")
        elif forced_submit:
            warnings.append("FORCED_SUBMIT_USED")

        suspicious_corr_keys = [
            key for key, value in key_values.items()
            if _is_suspicious_correlation_key(key, value)
        ]
        if suspicious_corr_keys:
            warnings.append(
                "SUSPICIOUS_CORRELATION_ONE: "
                + ", ".join(sorted(suspicious_corr_keys))
            )

        accepted = not issues
        return GenerationGateResult(
            accepted=accepted,
            quality_tier="verified" if accepted else "rejected",
            issues=issues,
            warnings=warnings,
        )


def _count_numeric_key_values(values: Dict[str, Any]) -> int:
    count = 0
    for value in values.values():
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            count += 1
    return count


def _trace_error_count(trace: List[Dict[str, Any]]) -> int:
    count = 0
    for entry in trace:
        result = str(entry.get("result_preview", ""))
        if result.startswith("ERROR") or "Traceback" in result:
            count += 1
    return count


def _has_forced_submit(trace: List[Dict[str, Any]]) -> bool:
    return any(
        entry.get("action") == "submit_task" and entry.get("forced") is True
        for entry in trace
    )


def _is_suspicious_correlation_key(key: str, value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    key_lower = str(key).lower()
    if "correlation" not in key_lower and "corr" not in key_lower:
        return False
    return abs(abs(float(value)) - 1.0) < 1e-12
