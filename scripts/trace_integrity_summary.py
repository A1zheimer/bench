from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data_agent_bench.evaluation.trace_integrity import TraceIntegrityValidator
from data_agent_bench.models.trace import ActionType, AgentTrace, TerminationInfo, TraceStep


def _parse_datetime(value: Optional[str]) -> datetime:
    if not value:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.utcnow()


def _load_trace_step(raw: Dict[str, Any]) -> TraceStep:
    action_type = raw.get("action_type") or ActionType.THINK.value
    try:
        parsed_type = ActionType(action_type)
    except ValueError:
        parsed_type = ActionType.ERROR

    return TraceStep(
        step=int(raw.get("step", 0)),
        timestamp=_parse_datetime(raw.get("timestamp")),
        action_type=parsed_type,
        action=str(raw.get("action", "")),
        observation=str(raw.get("observation", "")),
        thought=str(raw.get("thought", "")),
        tool_name=raw.get("tool_name"),
        tool_args=raw.get("tool_args"),
        tool_result=raw.get("tool_result"),
        tokens_in=int(raw.get("tokens_in", 0) or 0),
        tokens_out=int(raw.get("tokens_out", 0) or 0),
        latency_ms=float(raw.get("latency_ms", 0.0) or 0.0),
        cost_usd=float(raw.get("cost_usd", 0.0) or 0.0),
        metadata=raw.get("metadata") or {},
    )


def _load_trace_jsonl(path: Path) -> List[TraceStep]:
    steps: List[TraceStep] = []
    for line in path.read_text("utf-8").splitlines():
        if line.strip():
            steps.append(_load_trace_step(json.loads(line)))
    return steps


def _find_trace_path(task_dir: Path) -> Optional[Path]:
    traces = sorted(task_dir.glob("*/trace.jsonl"))
    return traces[-1] if traces else None


def _infer_termination(report: Dict[str, Any]) -> TerminationInfo:
    failure = report.get("failure_attribution") or {}
    reason = failure.get("primary_cause") or "completed"
    return TerminationInfo(reason=str(reason), forced=False, details="inferred from report.json")


def _build_trace(instance_id: str, steps: List[TraceStep], report: Dict[str, Any]) -> AgentTrace:
    metrics = report.get("metrics") or {}
    start = steps[0].timestamp if steps else datetime.utcnow()
    wall_time = float(metrics.get("wall_time_seconds", 0.0) or 0.0)
    end = start + timedelta(seconds=max(wall_time, 0.0))
    return AgentTrace(
        instance_id=instance_id,
        start_time=start,
        end_time=end,
        steps=steps,
        termination=_infer_termination(report),
        wall_time_seconds=wall_time,
        total_tokens=int(metrics.get("total_tokens", 0) or 0),
        total_cost_usd=float(metrics.get("total_cost_usd", 0.0) or 0.0),
    )


def iter_reports(run_dir: Path) -> Iterable[Path]:
    yield from sorted(run_dir.glob("*/report.json"))


def summarize_run(run_dir: Path) -> List[Dict[str, Any]]:
    validator = TraceIntegrityValidator()
    rows: List[Dict[str, Any]] = []

    for report_path in iter_reports(run_dir):
        report = json.loads(report_path.read_text("utf-8"))
        instance_id = str(report.get("instance_id") or report_path.parent.name)
        trace_path = _find_trace_path(report_path.parent)
        if trace_path is None:
            rows.append({
                "instance_id": instance_id,
                "integrity_score": 0.0,
                "step_sequence_valid": False,
                "required_fields_valid": False,
                "metric_consistency_valid": False,
                "final_answer_supported": False,
                "issue_count": 1,
                "issues": [{"check": "trace_file", "severity": "high", "message": "Missing trace.jsonl"}],
            })
            continue

        steps = _load_trace_jsonl(trace_path)
        trace = _build_trace(instance_id, steps, report)
        final_output = {
            "final_code": report.get("final_code", ""),
            "execution_result": report.get("execution_result", ""),
        }
        score = validator.evaluate(None, trace, final_output, None)  # type: ignore[arg-type]
        row = score.to_dict()
        row["instance_id"] = instance_id
        row["trace_path"] = str(trace_path)
        row["issue_count"] = len(score.issues)
        rows.append(row)
    return rows


def _markdown_table(rows: List[Dict[str, Any]]) -> str:
    headers = [
        "Task",
        "Score",
        "Seq",
        "Fields",
        "Metrics",
        "Final",
        "Issues",
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for r in rows:
        lines.append(
            "| "
            + " | ".join([
                str(r["instance_id"]),
                f"{float(r['integrity_score']):.3f}",
                str(r["step_sequence_valid"]),
                str(r["required_fields_valid"]),
                str(r["metric_consistency_valid"]),
                str(r["final_answer_supported"]),
                str(r["issue_count"]),
            ])
            + " |"
        )
    return "\n".join(lines)


def write_summary(run_rows: Dict[str, List[Dict[str, Any]]], output: Path) -> None:
    lines = ["# Trace Integrity Summary", ""]
    for label, rows in run_rows.items():
        scores = [float(r["integrity_score"]) for r in rows]
        issue_checks = Counter(
            issue.get("check", "unknown")
            for row in rows
            for issue in row.get("issues", [])
        )
        lines.append(f"## {label}")
        lines.append("")
        lines.append(f"- Reports: {len(rows)}")
        lines.append(f"- Mean integrity: {sum(scores) / len(scores):.3f}" if scores else "- Mean integrity: n/a")
        lines.append(f"- Issue checks: {dict(issue_checks)}")
        lines.append("")
        lines.append(_markdown_table(rows))
        lines.append("")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), "utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize trace integrity for benchmark run directories.")
    parser.add_argument("run_dirs", nargs="+", help="Run directories containing <task>/report.json and trace.jsonl")
    parser.add_argument("--output", default="", help="Optional markdown output path")
    args = parser.parse_args()

    run_rows = {Path(d).name: summarize_run(Path(d)) for d in args.run_dirs}
    if args.output:
        write_summary(run_rows, Path(args.output))
    else:
        print(json.dumps(run_rows, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
