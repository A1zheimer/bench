from __future__ import annotations

import re
import statistics
from typing import Any, Dict, List, Optional

from ..models.report import DeterministicScore, ScorerAuditScore
from ..models.task import TaskInput
from ..models.trace import AgentTrace, TraceStep
from .base import BaseEvaluator


NUMBER_RE = r"-?\d+\.?\d*(?:[eE][+-]?\d+)?"


class ScorerAudit(BaseEvaluator):
    """Audits whether deterministic scoring missed values present in trace."""

    NUMERIC_TOLERANCE = 0.05

    @property
    def name(self) -> str:
        return "ScorerAudit"

    def evaluate(
        self,
        task: TaskInput,
        trace: AgentTrace,
        final_output: Dict[str, Any],
        ground_truth: Optional[Dict[str, Any]],
        deterministic_score: Optional[DeterministicScore] = None,
    ) -> ScorerAuditScore:
        if not ground_truth or deterministic_score is None:
            return ScorerAuditScore(False, False, [], [])

        field_avg = (
            statistics.mean(deterministic_score.field_scores.values())
            if deterministic_score.field_scores else 0.0
        )
        low_score = field_avg < 0.5 and not deterministic_score.numeric_match
        hits = self._trace_value_hits(trace, final_output, ground_truth)
        missed_hits = [
            hit for hit in hits
            if deterministic_score.field_scores.get(hit["key"], 0.0) < 0.5
        ]
        missed_trace_value = low_score and bool(missed_hits)
        extracted = final_output.get("benchmark_extracted_answer") or {}
        extracted_keys = set((extracted.get("key_values") or {}).keys())
        format_extraction_issue = missed_trace_value and any(hit["key"] not in extracted_keys for hit in missed_hits)

        notes: List[str] = []
        if missed_trace_value:
            notes.append("SCORER_MISSED_TRACE_VALUE")
        if format_extraction_issue:
            notes.append("FORMAT_EXTRACTION_ISSUE")

        return ScorerAuditScore(
            missed_trace_value=missed_trace_value,
            format_extraction_issue=format_extraction_issue,
            trace_value_hits=missed_hits,
            audit_notes=notes,
        )

    def _trace_value_hits(
        self,
        trace: AgentTrace,
        final_output: Dict[str, Any],
        ground_truth: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        hits: List[Dict[str, Any]] = []
        expected: Dict[str, float] = {
            key: float(value)
            for key, value in (ground_truth.get("key_values") or {}).items()
            if isinstance(value, (int, float))
        }

        sources: List[tuple[Optional[int], str, str]] = [
            (None, "execution_result", str(final_output.get("execution_result", ""))),
            (None, "raw_agent_output", str(final_output.get("raw_agent_output", ""))),
        ]
        for step in trace.steps:
            sources.append((step.step, "trace_step", self._step_text(step)))

        for key, expected_value in expected.items():
            for source_step, source, text in sources:
                for raw_num in re.findall(NUMBER_RE, text):
                    value = float(raw_num)
                    rel_err = self._relative_error(value, expected_value)
                    if rel_err <= self.NUMERIC_TOLERANCE:
                        hits.append({
                            "key": key,
                            "expected_value": expected_value,
                            "observed_value": value,
                            "relative_error": round(rel_err, 6),
                            "source": source,
                            "source_step": source_step,
                        })
                        break
                if hits and hits[-1]["key"] == key:
                    break
        return hits

    def _relative_error(self, observed: float, expected: float) -> float:
        if expected == 0:
            return 0.0 if abs(observed) < 1e-6 else float("inf")
        return abs(observed - expected) / abs(expected)

    @staticmethod
    def _step_text(step: TraceStep) -> str:
        return "\n".join([
            str(step.action or ""),
            str(step.thought or ""),
            str(step.observation or ""),
            str(step.tool_args or ""),
            str(step.tool_result or ""),
        ])
