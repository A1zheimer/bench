from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from json import JSONDecoder
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from ..models.report import TraceGroundingScore
from ..models.task import TaskInput
from ..models.trace import ActionType, AgentTrace, TraceStep
from .base import BaseEvaluator


@dataclass(frozen=True)
class OperationRule:
    predicate: str
    operations: Tuple[str, ...]
    any_signals: Tuple[str, ...]
    all_signals: Tuple[str, ...] = ()


_OPERATION_RULES: Tuple[OperationRule, ...] = (
    OperationRule(
        predicate="LOADS",
        operations=("read_csv", "read_excel", "read_json", "file_read", "load_data"),
        any_signals=("read_csv", "read_excel", "read_json", "pd.read_", "load_dataset", "file_read"),
    ),
    OperationRule(
        predicate="INSPECTS",
        operations=("inspect_schema", "head", "info", "describe", "dtypes", "columns"),
        any_signals=(".head", "head(", ".info", "info(", ".describe", "describe(", ".columns", "dtypes", ".shape", "shape"),
    ),
    OperationRule(
        predicate="CLEANS",
        operations=("clean_missing", "fillna", "dropna", "type_cast", "handle_outlier", "normalize"),
        any_signals=("fillna", "dropna", "isna", "isnull", "notna", "notnull", "clip(", "astype", "replace(", "to_datetime", "quantile", "zscore"),
    ),
    OperationRule(
        predicate="AGGREGATES",
        operations=("aggregate", "groupby_sum", "groupby_mean", "groupby_count", "pivot", "value_counts"),
        any_signals=("groupby", ".agg", "agg(", ".sum", "sum(", ".mean", "mean(", ".count", "count(", "pivot_table", "value_counts"),
    ),
    OperationRule(
        predicate="JOINS",
        operations=("join", "merge", "concat"),
        any_signals=(".merge", "merge(", ".join", "join(", "concat("),
    ),
    OperationRule(
        predicate="TRAINS",
        operations=("fit", "train", "model_train", "regression", "classifier"),
        any_signals=(".fit(", "fit(", "train_test_split", "sklearn", "statsmodels", "xgboost", "lightgbm"),
    ),
    OperationRule(
        predicate="VALIDATES",
        operations=("validate", "verify", "recompute", "assert", "isclose", "check"),
        any_signals=("assert", "isclose", "allclose", "equals", "round(", "recompute", "validate", "check", "expected", "compare"),
    ),
    OperationRule(
        predicate="REPORTS",
        operations=("report", "final_answer", "return_answer"),
        any_signals=("final answer", "final_answer", "key_values", "submit final answer"),
    ),
)


class TraceGroundingVerifier(BaseEvaluator):
    """
    Verifies that a declared typed action trace is grounded in observed tool logs.

    The verifier intentionally does not require a single canonical expert path.
    It checks whether the agent's declared typed action units are supported by
    concrete evidence in AgentTrace: executed code, tool results, observations,
    action types, and final-answer steps.
    """

    @property
    def name(self) -> str:
        return "TraceGroundingVerifier"

    def evaluate(
        self,
        task: TaskInput,
        trace: AgentTrace,
        final_output: Dict[str, Any],
        ground_truth: Optional[Dict[str, Any]],
    ) -> TraceGroundingScore:
        declared_trace = self.extract_declared_trace(trace, final_output)
        if declared_trace is None:
            return TraceGroundingScore(
                grounding_rate=0.0,
                dependency_score=1.0,
                matched_steps=[],
                unsupported_steps=[],
                missing_declared_trace=True,
                format_valid=False,
            )

        format_valid, format_issues = self._validate_declared_trace(declared_trace)
        matched_steps: List[Dict[str, Any]] = []
        unsupported_steps: List[Dict[str, Any]] = []

        if not format_valid:
            for issue in format_issues:
                unsupported_steps.append({"reason": issue})
            return TraceGroundingScore(
                grounding_rate=0.0,
                dependency_score=0.0,
                matched_steps=[],
                unsupported_steps=unsupported_steps,
                missing_declared_trace=False,
                format_valid=False,
            )

        step_grounded: Dict[str, bool] = {}
        for declared in declared_trace:
            result = self._ground_step(declared, trace.steps)
            step_id = str(declared.get("step_id", ""))
            step_grounded[step_id] = result["grounded"]
            if result["grounded"]:
                matched_steps.append(result)
            else:
                unsupported_steps.append(result)

        total = len(declared_trace)
        grounding_rate = len(matched_steps) / total if total else 0.0
        dependency_score = self._dependency_score(declared_trace, step_grounded)

        return TraceGroundingScore(
            grounding_rate=round(grounding_rate, 4),
            dependency_score=round(dependency_score, 4),
            matched_steps=matched_steps,
            unsupported_steps=unsupported_steps,
            missing_declared_trace=False,
            format_valid=True,
        )

    # ------------------------------------------------------------------
    # Declared trace parsing
    # ------------------------------------------------------------------

    def extract_declared_trace(
        self,
        trace: AgentTrace,
        final_output: Dict[str, Any],
    ) -> Optional[List[Dict[str, Any]]]:
        candidates: List[str] = []

        direct = final_output.get("declared_trace")
        if isinstance(direct, list):
            return direct

        for key in ("final_answer", "execution_result", "final_code"):
            value = final_output.get(key)
            if isinstance(value, str) and "declared_trace" in value:
                candidates.append(value)

        for step in reversed(trace.steps):
            for value in (step.thought, step.action, step.observation):
                if isinstance(value, str) and "declared_trace" in value:
                    candidates.append(value)

        for text in candidates:
            parsed = self._parse_declared_trace_from_text(text)
            if parsed is not None:
                return parsed
        return None

    def _parse_declared_trace_from_text(self, text: str) -> Optional[List[Dict[str, Any]]]:
        for block in self._json_like_blocks(text):
            obj = self._loads_jsonish(block)
            if isinstance(obj, dict) and isinstance(obj.get("declared_trace"), list):
                return obj["declared_trace"]
            if isinstance(obj, list):
                return obj

        decoder = JSONDecoder()
        for idx, char in enumerate(text):
            if char not in "[{":
                continue
            snippet = text[idx:]
            try:
                obj, _ = decoder.raw_decode(snippet)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and isinstance(obj.get("declared_trace"), list):
                return obj["declared_trace"]
            if isinstance(obj, list) and all(isinstance(x, dict) for x in obj):
                return obj

        # A tolerant fallback for single-quoted Python-ish dicts in final answers.
        marker = "declared_trace"
        if marker in text:
            start = text.rfind("{", 0, text.find(marker))
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                obj = self._loads_jsonish(text[start:end + 1])
                if isinstance(obj, dict) and isinstance(obj.get("declared_trace"), list):
                    return obj["declared_trace"]
        return None

    @staticmethod
    def _json_like_blocks(text: str) -> Iterable[str]:
        fenced = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
        for block in fenced:
            yield block.strip()
        yield text.strip()

    @staticmethod
    def _loads_jsonish(text: str) -> Any:
        try:
            return json.loads(text)
        except Exception:
            pass
        try:
            return ast.literal_eval(text)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Grounding checks
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_declared_trace(declared_trace: Any) -> Tuple[bool, List[str]]:
        issues: List[str] = []
        if not isinstance(declared_trace, list):
            return False, ["declared_trace must be a list"]
        for idx, step in enumerate(declared_trace):
            if not isinstance(step, dict):
                issues.append(f"declared_trace[{idx}] must be an object")
                continue
            if not step.get("step_id"):
                issues.append(f"declared_trace[{idx}] missing step_id")
            if not step.get("predicate") and not step.get("operation") and not step.get("intent"):
                issues.append(f"declared_trace[{idx}] missing predicate/operation/intent")
        return not issues, issues

    def _ground_step(self, declared: Dict[str, Any], observed_steps: Sequence[TraceStep]) -> Dict[str, Any]:
        evidence_step = declared.get("evidence_step")
        candidates = list(observed_steps)
        if evidence_step is not None:
            try:
                evidence_num = int(evidence_step)
            except (TypeError, ValueError):
                return self._unsupported(declared, f"invalid evidence_step={evidence_step!r}")
            candidates = [s for s in observed_steps if s.step == evidence_num]
            if not candidates:
                return self._unsupported(declared, f"evidence_step {evidence_num} not found")

        best: Optional[Dict[str, Any]] = None
        for observed in candidates:
            grounded, signals, reason = self._matches_observed_step(declared, observed)
            if grounded:
                result = self._matched(declared, observed, signals)
                if best is None or len(signals) > len(best.get("matched_signals", [])):
                    best = result
            elif best is None:
                best = self._unsupported(declared, reason, observed.step)

        if best and best.get("grounded"):
            return best
        return best or self._unsupported(declared, "no observed evidence matched")

    def _matches_observed_step(self, declared: Dict[str, Any], observed: TraceStep) -> Tuple[bool, List[str], str]:
        text = self._observed_text(observed)
        predicate = str(declared.get("predicate") or "").upper()
        operation = str(declared.get("operation") or declared.get("intent") or "").lower()
        inputs = [str(x).lower() for x in declared.get("inputs", []) if isinstance(x, (str, int, float))]
        status = str(declared.get("status") or "").lower()

        if status == "success" and observed.tool_result and str(observed.tool_result).startswith("ERROR:"):
            return False, [], "declared success but observed step errored"

        if predicate == "REPORTS" or operation in ("report", "final_answer", "return_answer"):
            if observed.action_type == ActionType.FINAL_ANSWER or "final answer" in text or "key_values" in text:
                return True, ["final_answer"], ""
            return False, [], "no final answer evidence"

        rule = self._select_rule(predicate, operation)
        if rule is None:
            return False, [], f"no grounding rule for predicate={predicate!r} operation={operation!r}"

        matched_signals: List[str] = []
        if observed.action_type == ActionType.FILE_READ and rule.predicate == "LOADS":
            matched_signals.append("file_read")

        for signal in rule.any_signals:
            if signal.lower() in text:
                matched_signals.append(signal)

        for signal in rule.all_signals:
            if signal.lower() not in text:
                return False, matched_signals, f"missing required signal {signal!r}"

        op_ok = self._operation_specific_match(operation, text)
        if not matched_signals and not op_ok:
            return False, [], f"no signals for {rule.predicate}/{operation or 'generic'}"
        if op_ok and operation:
            matched_signals.append(operation)

        input_hits = self._input_hits(inputs, text)
        matched_signals.extend(input_hits)

        # If the declared step names specific non-dataset inputs, require at least one
        # of them to appear. This catches unsupported claims while staying tolerant of
        # DATA_PATH / dataset.csv aliases.
        semantic_inputs = [x for x in inputs if not self._is_dataset_alias(x)]
        if semantic_inputs and not input_hits:
            return False, matched_signals, f"none of declared inputs found: {semantic_inputs}"

        return True, sorted(set(matched_signals)), ""

    @staticmethod
    def _observed_text(step: TraceStep) -> str:
        parts = [
            step.action,
            step.thought,
            step.observation,
            str(step.tool_name or ""),
            str(step.tool_args or ""),
            str(step.tool_result or ""),
            step.action_type.value,
        ]
        if step.tool_args and isinstance(step.tool_args, dict):
            parts.append(str(step.tool_args.get("code", "")))
        return "\n".join(parts).lower()

    @staticmethod
    def _select_rule(predicate: str, operation: str) -> Optional[OperationRule]:
        for rule in _OPERATION_RULES:
            if predicate == rule.predicate:
                return rule
            if operation in rule.operations:
                return rule
        if operation:
            for rule in _OPERATION_RULES:
                if any(op in operation for op in rule.operations):
                    return rule
        return None

    @staticmethod
    def _operation_specific_match(operation: str, text: str) -> bool:
        if operation == "groupby_sum":
            return "groupby" in text and (".sum" in text or "sum(" in text)
        if operation == "groupby_mean":
            return "groupby" in text and (".mean" in text or "mean(" in text)
        if operation == "groupby_count":
            return "groupby" in text and (".count" in text or "count(" in text or "size(" in text)
        if operation == "read_csv":
            return "read_csv" in text or "file_read" in text
        if operation in ("inspect_schema", "head", "describe", "dtypes"):
            return any(s in text for s in (".head", "head(", ".describe", "describe(", ".columns", "dtypes", ".info", "info("))
        return bool(operation and operation in text)

    @classmethod
    def _input_hits(cls, inputs: Sequence[str], text: str) -> List[str]:
        hits: List[str] = []
        for item in inputs:
            norm = item.strip().lower()
            if not norm:
                continue
            if cls._is_dataset_alias(norm):
                if any(alias in text for alias in ("dataset.csv", "data_path", "pd.read_", "file_read")):
                    hits.append(item)
            elif norm in text:
                hits.append(item)
        return hits

    @staticmethod
    def _is_dataset_alias(value: str) -> bool:
        return value in {"dataset", "dataset.csv", "data/dataset.csv", "data_path", "data", "csv"} or value.endswith(".csv")

    @staticmethod
    def _matched(declared: Dict[str, Any], observed: TraceStep, signals: Sequence[str]) -> Dict[str, Any]:
        return {
            "step_id": declared.get("step_id"),
            "predicate": declared.get("predicate"),
            "operation": declared.get("operation"),
            "grounded": True,
            "evidence_step": declared.get("evidence_step"),
            "matched_observed_step": observed.step,
            "matched_signals": list(signals),
        }

    @staticmethod
    def _unsupported(declared: Dict[str, Any], reason: str, observed_step: Optional[int] = None) -> Dict[str, Any]:
        result = {
            "step_id": declared.get("step_id"),
            "predicate": declared.get("predicate"),
            "operation": declared.get("operation"),
            "grounded": False,
            "evidence_step": declared.get("evidence_step"),
            "reason": reason,
        }
        if observed_step is not None:
            result["matched_observed_step"] = observed_step
        return result

    @staticmethod
    def _dependency_score(declared_trace: List[Dict[str, Any]], step_grounded: Dict[str, bool]) -> float:
        positions = {str(step.get("step_id")): idx for idx, step in enumerate(declared_trace)}
        total = 0
        ok = 0
        for idx, step in enumerate(declared_trace):
            current_id = str(step.get("step_id"))
            for dep in step.get("depends_on", []) or []:
                dep_id = str(dep)
                total += 1
                if dep_id in positions and positions[dep_id] < idx and step_grounded.get(dep_id) and step_grounded.get(current_id):
                    ok += 1
        return ok / total if total else 1.0
