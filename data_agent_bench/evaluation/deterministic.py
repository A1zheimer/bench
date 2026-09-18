from __future__ import annotations

import difflib
import re
from typing import Any, Dict, List, Optional, Tuple

from ..models.constants import ACCURACY_COMPONENT_WEIGHTS
from ..models.report import DeterministicScore
from ..models.task import TaskInput
from ..models.trace import AgentTrace
from .base import BaseEvaluator
from .scoring_v3 import DEFAULT_SOFT_CAP, score_numeric_value


class DeterministicEvaluator(BaseEvaluator):
    """
    Compares final_output against ground_truth.

    Ground truth expected_output.json:
    {
        "key_values": {"p_value": 0.034, "effect_size": 0.42},
        "alternative_key_values": [
            {"method": "monte_carlo", "VaR_95": -0.069},
            {"method": "parametric",  "VaR_95": -0.071}
        ],
        "required_keywords": []
    }

    Scoring philosophy:
    - All valid methods are treated equally (平权).
    - For each key, the agent's answer is scored against the primary GT and all
      alternatives; the MAX score across methods is taken.
    - Method differences are naturally reflected in cost/efficiency metrics.
    - required_keywords serves only as an anti-hacking guard (e.g. ensure the
      agent actually ran code rather than printing a memorised number).
    """

    NUMERIC_TOLERANCE = 0.05  # 5% relative tolerance
    NUMERIC_SOFT_CAP = DEFAULT_SOFT_CAP

    @property
    def name(self) -> str:
        return "DeterministicEvaluator"

    def evaluate(
        self,
        task: TaskInput,
        trace: AgentTrace,
        final_output: Dict[str, Any],
        ground_truth: Optional[Dict[str, Any]],
    ) -> DeterministicScore:
        if ground_truth is None:
            return DeterministicScore(
                exact_match=False,
                numeric_match=False,
                numeric_tolerance=self.NUMERIC_TOLERANCE,
                similarity_score=0.0,
                field_scores={},
                component_scores={},
                component_weights={},
            )

        result_text = str(final_output.get("execution_result", ""))
        extracted_answer = final_output.get("benchmark_extracted_answer") or {}
        gt_text = str(ground_truth.get("execution_result", ""))

        # Exact match (normalised)
        exact = self._normalize(result_text) == self._normalize(gt_text)

        # Text similarity (used as partial credit when numeric match fails)
        sim = difflib.SequenceMatcher(None, result_text, gt_text).ratio()

        # Build the list of all valid key-value sets (primary + alternatives).
        # Each alternative is a dict that may have a "method" label (ignored for
        # scoring) plus the numeric keys to compare.
        primary_kv: Dict[str, Any] = ground_truth.get("key_values", {})
        alternatives: List[Dict[str, Any]] = ground_truth.get("alternative_key_values", [])

        all_kv_sets: List[Dict[str, float]] = [
            {k: v for k, v in primary_kv.items() if isinstance(v, (int, float))}
        ]
        for alt in alternatives:
            alt_kv = {k: v for k, v in alt.items()
                      if k != "method" and isinstance(v, (int, float))}
            if alt_kv:
                all_kv_sets.append(alt_kv)

        # Collect the union of all keys across all GT sets.
        all_keys = set()
        for kv in all_kv_sets:
            all_keys.update(kv.keys())

        # Score each key: take max across all GT sets that define that key.
        field_scores: Dict[str, float] = {}
        field_details: Dict[str, Dict[str, Any]] = {}
        raw_field_scores: Dict[str, float] = {}
        all_ok = True

        for key in all_keys:
            best_field_score = 0.0
            best_detail: Dict[str, Any] = {}
            best_raw_field_score = 0.0
            for kv_set in all_kv_sets:
                if key not in kv_set:
                    continue
                raw_score, _ = self._score_field_with_detail(
                    result_text,
                    key,
                    kv_set[key],
                    extracted_answer={},
                )
                score, detail = self._score_field_with_detail(
                    result_text,
                    key,
                    kv_set[key],
                    extracted_answer=extracted_answer,
                )
                best_raw_field_score = max(best_raw_field_score, raw_score)
                best_field_score = max(best_field_score, score)
                if score >= best_field_score:
                    best_detail = detail

            field_scores[key] = round(best_field_score, 4)
            raw_field_scores[key] = round(best_raw_field_score, 4)
            field_details[key] = best_detail
            if best_field_score < 1.0:
                all_ok = False

        # Anti-hacking guard: required_keywords must appear in the output.
        # This ensures the agent actually ran computation rather than printing
        # a memorised answer. Keep this check lightweight — do not use it to
        # enforce method choice.
        required_keywords: List[str] = ground_truth.get("required_keywords", [])
        keywords_ok = all(kw.lower() in result_text.lower() for kw in required_keywords)

        component_scores, component_weights = self._score_components(
            components=ground_truth.get("components", {}),
            result_text=result_text,
            final_output=final_output,
            trace=trace,
            primary_key_values=primary_kv,
            field_scores=field_scores,
            required_keywords=required_keywords,
        )

        return DeterministicScore(
            exact_match=exact,
            numeric_match=all_ok and keywords_ok,
            numeric_tolerance=self.NUMERIC_TOLERANCE,
            similarity_score=sim,
            field_scores=field_scores,
            component_scores=component_scores,
            component_weights=component_weights,
            field_details=field_details,
            raw_field_scores=raw_field_scores,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(s: str) -> str:
        return " ".join(s.lower().split())

    def _score_field(
        self,
        result_text: str,
        key: str,
        expected_val: float,
        tolerance: Optional[float] = None,
    ) -> float:
        """Score a single field against one GT value."""
        score, _ = self._score_field_with_detail(
            result_text,
            key,
            expected_val,
            tolerance=tolerance,
            extracted_answer={},
        )
        return score

    def _score_field_with_detail(
        self,
        result_text: str,
        key: str,
        expected_val: float,
        tolerance: Optional[float] = None,
        extracted_answer: Optional[Dict[str, Any]] = None,
    ) -> Tuple[float, Dict[str, Any]]:
        tolerance = tolerance if tolerance is not None else self.NUMERIC_TOLERANCE
        if tolerance <= 0:
            tolerance = self.NUMERIC_TOLERANCE
        candidates: List[Dict[str, Any]] = []

        extracted_key_values = {}
        extracted_selected = {}
        if isinstance(extracted_answer, dict):
            extracted_key_values = extracted_answer.get("key_values") or {}
            extracted_selected = extracted_answer.get("selected") or {}
        if key in extracted_key_values and isinstance(extracted_key_values[key], (int, float)):
            selected = extracted_selected.get(key, {}) if isinstance(extracted_selected, dict) else {}
            candidates.append({
                "value": float(extracted_key_values[key]),
                "source": selected.get("source", "benchmark_extracted_answer"),
                "source_step": selected.get("source_step"),
                "matched_label": selected.get("matched_label", key),
            })

        # Prefer labeled matches: "key = 0.034", "key: 0.034"
        key_escaped = re.escape(key).replace(r"\_", r"[\s_\-]?")
        labeled_pattern = (
            rf"(?:{key_escaped})\s*[=:]\s*(-?\d+\.?\d*(?:[eE][+-]?\d+)?)"
        )
        labeled_matches = re.findall(labeled_pattern, result_text, re.IGNORECASE)

        if labeled_matches:
            candidates.extend({"value": float(m), "source": "labeled_result_text", "source_step": None} for m in labeled_matches)
        else:
            # Fallback: any number in result
            candidates.extend(
                {"value": float(m), "source": "unlabeled_result_number", "source_step": None}
                for m in re.findall(r"-?\d+\.?\d*(?:[eE][+-]?\d+)?", result_text)
            )

        if not candidates:
            return 0.0, {
                "source": "none",
                "source_step": None,
                "extracted_value": None,
                "relative_error": None,
            }

        best = 0.0
        best_detail: Dict[str, Any] = {}
        for candidate in candidates:
            num = float(candidate["value"])
            s, rel_err = score_numeric_value(
                num,
                expected_val,
                tolerance=tolerance,
                soft_cap=self.NUMERIC_SOFT_CAP,
            )
            if s > best:
                best = s
                best_detail = {
                    "source": candidate.get("source", "unknown"),
                    "source_step": candidate.get("source_step"),
                    "matched_label": candidate.get("matched_label"),
                    "extracted_value": num,
                    "expected_value": expected_val,
                    "relative_error": None if rel_err == float("inf") else round(rel_err, 8),
                }
        return best, best_detail

    def _score_components(
        self,
        components: Any,
        result_text: str,
        final_output: Dict[str, Any],
        trace: AgentTrace,
        primary_key_values: Dict[str, Any],
        field_scores: Dict[str, float],
        required_keywords: List[str],
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        """Score optional component-level accuracy diagnostics.

        The component schema is intentionally lightweight and backward
        compatible. If a task has no "components" field, old numeric scoring is
        unchanged and this returns empty dicts.
        """
        if not isinstance(components, dict) or not components:
            return {}, {}

        scores: Dict[str, float] = {}
        weights: Dict[str, float] = {}
        combined_text = self._combined_trace_text(result_text, trace)

        for name, spec in components.items():
            if not isinstance(spec, dict):
                scores[name] = 0.0
                continue
            score = self._score_component(
                name=name,
                spec=spec,
                result_text=result_text,
                combined_text=combined_text,
                final_output=final_output,
                primary_key_values=primary_key_values,
                field_scores=field_scores,
                required_keywords=required_keywords,
            )
            scores[name] = round(score, 4)
            weights[name] = float(
                spec.get(
                    "score_weight",
                    spec.get("weight", ACCURACY_COMPONENT_WEIGHTS.get(name, 0.0)),
                )
            )

        return scores, weights

    def _score_component(
        self,
        name: str,
        spec: Dict[str, Any],
        result_text: str,
        combined_text: str,
        final_output: Dict[str, Any],
        primary_key_values: Dict[str, Any],
        field_scores: Dict[str, float],
        required_keywords: List[str],
    ) -> float:
        checks: List[float] = []

        key_values = spec.get("key_values")
        if name == "numerical_result" and key_values is None:
            key_values = {
                k: v for k, v in primary_key_values.items()
                if isinstance(v, (int, float))
            }
        if isinstance(key_values, dict) and key_values:
            tolerance = spec.get("tolerance", self.NUMERIC_TOLERANCE)
            kv_scores = [
                self._score_field(result_text, key, float(value), tolerance=tolerance)
                for key, value in key_values.items()
                if isinstance(value, (int, float))
            ]
            if kv_scores:
                checks.append(sum(kv_scores) / len(kv_scores))

        if name == "numerical_result" and not checks and field_scores:
            checks.append(sum(field_scores.values()) / len(field_scores))

        target_columns = spec.get("target_columns", [])
        if isinstance(target_columns, list) and target_columns:
            checks.append(self._keyword_coverage(combined_text, target_columns))

        method_keywords = spec.get("method_keywords", [])
        if isinstance(method_keywords, list) and method_keywords:
            checks.append(self._keyword_coverage(combined_text, method_keywords))

        component_keywords = spec.get("required_keywords", [])
        if isinstance(component_keywords, list) and component_keywords:
            checks.append(self._keyword_coverage(combined_text, component_keywords))

        if name == "interpretation" and required_keywords and not component_keywords:
            checks.append(self._keyword_coverage(result_text, required_keywords))

        if name == "output_format":
            checks.append(self._score_output_format(spec, result_text, final_output))

        if name == "preprocessing" and not checks:
            preprocessing_keywords = [
                "missing", "impute", "dropna", "fillna", "outlier", "anomaly",
                "clip", "filter", "clean", "convert", "astype", "handle",
                "schema", "drift",
            ]
            checks.append(self._keyword_coverage(combined_text, preprocessing_keywords))

        if not checks:
            return 0.0
        return max(0.0, min(1.0, sum(checks) / len(checks)))

    @staticmethod
    def _keyword_coverage(text: str, keywords: List[str]) -> float:
        if not keywords:
            return 0.0
        text_lower = text.lower()
        matched = sum(1 for kw in keywords if str(kw).lower() in text_lower)
        return matched / len(keywords)

    @staticmethod
    def _combined_trace_text(result_text: str, trace: AgentTrace) -> str:
        parts = [result_text]
        for step in trace.steps:
            parts.extend([step.action or "", step.observation or "", step.thought or ""])
            if step.tool_args:
                parts.append(str(step.tool_args))
            if step.tool_result:
                parts.append(str(step.tool_result))
        return "\n".join(parts)

    @staticmethod
    def _score_output_format(
        spec: Dict[str, Any],
        result_text: str,
        final_output: Dict[str, Any],
    ) -> float:
        expected_format = str(spec.get("format", "")).lower()
        if expected_format == "json":
            if any(k in final_output for k in ("final_answer", "structured_output")):
                return 1.0
            stripped = result_text.strip()
            return 1.0 if stripped.startswith("{") and stripped.endswith("}") else 0.0
        return 1.0 if result_text.strip() else 0.0

    def _compare_numerics(
        self, result_text: str, expected_kv: Dict[str, float]
    ) -> Tuple[bool, Dict[str, float]]:
        """Legacy helper kept for backward compatibility."""
        if not expected_kv:
            return True, {}
        field_scores = {}
        all_ok = True
        for key, val in expected_kv.items():
            if not isinstance(val, (int, float)):
                continue
            score = self._score_field(result_text, key, val)
            field_scores[key] = round(score, 4)
            if score < 1.0:
                all_ok = False
        return all_ok, field_scores
