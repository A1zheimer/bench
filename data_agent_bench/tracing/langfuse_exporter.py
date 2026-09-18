from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from ..models.report import (
    DeterministicScore,
    EvaluationReport,
    FailureAttribution,
    MetricBundle,
    ProcessScore,
    RiskScore,
    ScorerAuditScore,
    TraceGroundingScore,
    TraceIntegrityScore,
)
from ..models.task import TaskInput
from ..models.trace import ActionType, AgentTrace, TraceStep

logger = logging.getLogger(__name__)


def _short(value: Any, limit: int = 6000) -> Any:
    if value is None:
        return None
    text = str(value)
    if len(text) <= limit:
        return value
    return text[:limit] + f"\n...[truncated {len(text) - limit} chars]"


def _score_items(
    det: DeterministicScore,
    proc: ProcessScore,
    risk: RiskScore,
    trace_grounding: Optional[TraceGroundingScore],
    trace_integrity: Optional[TraceIntegrityScore],
    metrics: MetricBundle,
) -> Iterable[tuple[str, float, str]]:
    yield "completion_rate", metrics.completion_rate, "Benchmark soft completion rate."
    yield "result_accuracy", metrics.result_accuracy, "Deterministic answer accuracy."
    yield "process_quality", metrics.process_quality, "Process auditor score."
    yield "safety_score", metrics.safety_score, "Execution/resource safety score."
    yield "token_efficiency", metrics.token_efficiency, "Accuracy normalized by token usage."
    yield "deterministic_similarity", det.similarity_score, "Raw deterministic similarity score."
    yield "process_tool_efficiency", proc.tool_efficiency, "Tool efficiency component."
    yield "process_error_recovery", proc.error_recovery_score, "Error recovery component."
    yield "risk_compliant", 1.0 if risk.safety_compliant else 0.0, "Risk assessor compliance flag."
    if trace_grounding is not None:
        yield "trace_grounding_rate", trace_grounding.grounding_rate, "Declared trace grounding rate."
        yield "trace_dependency_score", trace_grounding.dependency_score, "Declared trace dependency score."
    if trace_integrity is not None:
        yield "trace_integrity", trace_integrity.integrity_score, "Observed trace structural integrity."


class LangfuseExporter:
    """
    Optional Langfuse exporter for benchmark observability.

    It exports two planes under one run trace:
      1. agent trajectory: model actions, tool/code steps, outputs and errors
      2. benchmark judging: deterministic, process, risk, grounding and integrity scores

    The core benchmark remains independent of Langfuse; failures here are logged
    but never fail a benchmark run.
    """

    def __init__(self, enabled: bool = False, experiment_name: str = "data-agent-bench") -> None:
        self.enabled = enabled or os.getenv("DAB_LANGFUSE_ENABLED", "").lower() in {"1", "true", "yes"}
        self.experiment_name = experiment_name
        self._client = None
        self._available = False

        if not self.enabled:
            return

        if not os.getenv("LANGFUSE_PUBLIC_KEY") or not os.getenv("LANGFUSE_SECRET_KEY"):
            logger.warning(
                "Langfuse export requested but LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY "
                "are not set. Skipping dashboard export while keeping local trace files."
            )
            return

        try:
            from langfuse import get_client  # type: ignore

            self._client = get_client()
            self._available = True
        except Exception as exc:
            logger.warning(
                "Langfuse export requested but unavailable: %s. "
                "Install `langfuse` and set LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY.",
                exc,
            )

    @property
    def available(self) -> bool:
        return self.enabled and self._available and self._client is not None

    def export_run(
        self,
        *,
        task: TaskInput,
        trace: AgentTrace,
        final_output: Dict[str, Any],
        deterministic: DeterministicScore,
        process: ProcessScore,
        risk: RiskScore,
        trace_grounding: Optional[TraceGroundingScore],
        trace_integrity: Optional[TraceIntegrityScore],
        scorer_audit: Optional[ScorerAuditScore],
        metrics: MetricBundle,
        failure: Optional[FailureAttribution],
        report: EvaluationReport,
        report_path: Path,
        model_id: str,
        run_index: int,
        temperature: float,
    ) -> None:
        if not self.available:
            return

        try:
            self._export_run_inner(
                task=task,
                trace=trace,
                final_output=final_output,
                deterministic=deterministic,
                process=process,
                risk=risk,
                trace_grounding=trace_grounding,
                trace_integrity=trace_integrity,
                scorer_audit=scorer_audit,
                metrics=metrics,
                failure=failure,
                report=report,
                report_path=report_path,
                model_id=model_id,
                run_index=run_index,
                temperature=temperature,
            )
        except Exception as exc:
            logger.warning("Langfuse export failed for %s: %s", task.instance_id, exc)

    def flush(self) -> None:
        if not self.available:
            return
        try:
            self._client.flush()
        except Exception as exc:
            logger.warning("Langfuse flush failed: %s", exc)

    def _export_run_inner(
        self,
        *,
        task: TaskInput,
        trace: AgentTrace,
        final_output: Dict[str, Any],
        deterministic: DeterministicScore,
        process: ProcessScore,
        risk: RiskScore,
        trace_grounding: Optional[TraceGroundingScore],
        trace_integrity: Optional[TraceIntegrityScore],
        scorer_audit: Optional[ScorerAuditScore],
        metrics: MetricBundle,
        failure: Optional[FailureAttribution],
        report: EvaluationReport,
        report_path: Path,
        model_id: str,
        run_index: int,
        temperature: float,
    ) -> None:
        root_name = f"benchmark.run/{task.instance_id}/{model_id}"
        metadata = {
            "experiment": self.experiment_name,
            "instance_id": task.instance_id,
            "domain": task.task_metadata.domain.value,
            "difficulty": task.task_metadata.difficulty.value,
            "model_id": model_id,
            "run_index": run_index,
            "temperature": temperature,
            "run_id": trace.metadata.get("run_id"),
            "report_id": report.report_id,
            "report_path": str(report_path),
            "termination": trace.termination.to_dict() if trace.termination else None,
        }

        with self._client.start_as_current_observation(
            as_type="span",
            name=root_name,
            input={
                "problem_statement": task.context.problem_statement,
                "expert_knowledge": task.context.expert_knowledge,
                "dataset_preview": task.context.dataset_preview,
            },
            metadata=metadata,
        ) as root:
            self._export_agent_trajectory(trace, model_id=model_id)
            self._export_benchmark_judging(
                deterministic=deterministic,
                process=process,
                risk=risk,
                trace_grounding=trace_grounding,
                trace_integrity=trace_integrity,
                scorer_audit=scorer_audit,
                metrics=metrics,
                failure=failure,
            )
            self._export_scores(
                deterministic=deterministic,
                process=process,
                risk=risk,
                trace_grounding=trace_grounding,
                trace_integrity=trace_integrity,
                metrics=metrics,
            )
            root.update(
                output={
                    "final_output": _short(final_output),
                    "benchmark_extracted_answer": _short(final_output.get("benchmark_extracted_answer")),
                    "metrics": metrics.to_dict(),
                    "failure_attribution": failure.to_dict() if failure else None,
                    "trace_integrity": trace_integrity.to_dict() if trace_integrity else None,
                    "scorer_audit": scorer_audit.to_dict() if scorer_audit else None,
                }
            )

    def _export_agent_trajectory(self, trace: AgentTrace, model_id: str) -> None:
        with self._client.start_as_current_observation(
            as_type="span",
            name="agent.trajectory",
            input={"step_count": len(trace.steps)},
            metadata={
                "total_tokens": trace.total_tokens,
                "total_cost_usd": trace.total_cost_usd,
                "wall_time_seconds": trace.wall_time_seconds,
            },
        ) as trajectory:
            for step in trace.steps:
                self._export_step(step, model_id=model_id)
            trajectory.update(output={"termination": trace.termination.to_dict() if trace.termination else None})

    def _export_step(self, step: TraceStep, model_id: str) -> None:
        observation_type = "generation" if (step.tokens_in or step.tokens_out) else "span"
        name = f"agent.step.{step.step}.{step.action_type.value}"
        kwargs: Dict[str, Any] = {
            "as_type": observation_type,
            "name": name,
            "input": {
                "action": step.action,
                "thought": _short(step.thought),
                "tool_name": step.tool_name,
                "tool_args": _short(step.tool_args),
            },
            "metadata": {
                "step": step.step,
                "action_type": step.action_type.value,
                "tokens_in": step.tokens_in,
                "tokens_out": step.tokens_out,
                "latency_ms": step.latency_ms,
                "cost_usd": step.cost_usd,
            },
        }
        if observation_type == "generation":
            kwargs["model"] = model_id

        with self._client.start_as_current_observation(**kwargs) as obs:
            obs.update(output={
                "observation": _short(step.observation),
                "tool_result": _short(step.tool_result),
            })

        if step.action_type in {ActionType.CODE_EXEC, ActionType.TOOL_CALL} and step.tool_name:
            with self._client.start_as_current_observation(
                as_type="span",
                name=f"tool.{step.tool_name}.step_{step.step}",
                input=_short(step.tool_args),
                metadata={
                    "step": step.step,
                    "tool_name": step.tool_name,
                    "action_type": step.action_type.value,
                    "latency_ms": step.latency_ms,
                },
            ) as tool_span:
                tool_span.update(output=_short(step.tool_result or step.observation))

    def _export_benchmark_judging(
        self,
        *,
        deterministic: DeterministicScore,
        process: ProcessScore,
        risk: RiskScore,
        trace_grounding: Optional[TraceGroundingScore],
        trace_integrity: Optional[TraceIntegrityScore],
        scorer_audit: Optional[ScorerAuditScore],
        metrics: MetricBundle,
        failure: Optional[FailureAttribution],
    ) -> None:
        with self._client.start_as_current_observation(
            as_type="span",
            name="benchmark.judging",
            input={"metric_inputs": metrics.to_dict()},
        ) as judging:
            self._span("judge.deterministic", deterministic.to_dict())
            self._span("judge.process", process.to_dict())
            self._span("judge.risk", risk.to_dict())
            if trace_grounding is not None:
                self._span("judge.trace_grounding", trace_grounding.to_dict())
            if trace_integrity is not None:
                self._span("judge.trace_integrity", trace_integrity.to_dict())
            if scorer_audit is not None:
                self._span("judge.scorer_audit", scorer_audit.to_dict())
            judging.update(output={
                "metrics": metrics.to_dict(),
                "failure_attribution": failure.to_dict() if failure else None,
            })

    def _span(self, name: str, output: Dict[str, Any]) -> None:
        with self._client.start_as_current_observation(as_type="span", name=name) as span:
            span.update(output=output)

    def _export_scores(
        self,
        *,
        deterministic: DeterministicScore,
        process: ProcessScore,
        risk: RiskScore,
        trace_grounding: Optional[TraceGroundingScore],
        trace_integrity: Optional[TraceIntegrityScore],
        metrics: MetricBundle,
    ) -> None:
        for name, value, comment in _score_items(
            deterministic, process, risk, trace_grounding, trace_integrity, metrics
        ):
            try:
                self._client.score_current_span(name=name, value=float(value), comment=comment)
            except Exception:
                logger.debug("Could not export Langfuse score %s", name, exc_info=True)
