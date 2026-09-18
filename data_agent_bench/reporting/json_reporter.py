from __future__ import annotations

import json
import pathlib
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

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
from ..models.trace import AgentTrace


class JSONReporter:
    """
    Assembles EvaluationReport from all evaluation components and
    serializes to bench_runs/<instance_id>/<run_id>/report.json.
    """

    FRAMEWORK_VERSION = "1.0.0"

    def build(
        self,
        task: TaskInput,
        trace: AgentTrace,
        final_output: Dict[str, Any],
        det_score: DeterministicScore,
        proc_score: ProcessScore,
        risk_score: RiskScore,
        metrics: MetricBundle,
        failure: Optional[FailureAttribution],
        trace_grounding_score: Optional[TraceGroundingScore] = None,
        trace_integrity_score: Optional[TraceIntegrityScore] = None,
        scorer_audit_score: Optional[ScorerAuditScore] = None,
    ) -> EvaluationReport:
        report_id = str(uuid.uuid4())
        trajectory_summary: List[Dict[str, Any]] = [
            {
                "step": s.step,
                "action": s.action,
                "observation": s.observation[:300],
                "action_type": s.action_type.value,
            }
            for s in trace.steps
        ]

        return EvaluationReport(
            report_id=report_id,
            instance_id=task.instance_id,
            timestamp=datetime.utcnow(),
            deterministic=det_score,
            process=proc_score,
            risk=risk_score,
            metrics=metrics,
            failure_attribution=failure,
            trajectory_summary=trajectory_summary,
            final_code=str(final_output.get("final_code", "")),
            execution_result=str(final_output.get("execution_result", "")),
            raw_agent_output=str(final_output.get("raw_agent_output", "")),
            benchmark_extracted_answer=final_output.get("benchmark_extracted_answer", {}) or {},
            framework_version=self.FRAMEWORK_VERSION,
            trace_grounding=trace_grounding_score,
            trace_integrity=trace_integrity_score,
            scorer_audit=scorer_audit_score,
        )

    def write(self, report: EvaluationReport, output_dir: pathlib.Path) -> pathlib.Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / "report.json"
        report_dict = report.to_dict()
        report_path.write_text(
            json.dumps(report_dict, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        return report_path

    def summary_table(self, report: EvaluationReport) -> Dict[str, Any]:
        """Compact dict for CLI table display."""
        m = report.metrics
        return {
            "instance_id": report.instance_id,
            "completion": f"{m.completion_rate:.0%}",
            "accuracy": f"{m.result_accuracy:.3f}",
            "process": f"{m.process_quality:.3f}",
            "safety": f"{m.safety_score:.3f}",
            "tokens": m.total_tokens,
            "cost_usd": f"${m.total_cost_usd:.4f}",
            "wall_time": f"{m.wall_time_seconds:.1f}s",
            "risk_level": report.risk.risk_level,
            "failure": report.failure_attribution.primary_cause if report.failure_attribution else "-",
            "termination": report.metrics.completion_rate > 0 and "completed" or "incomplete",
        }
