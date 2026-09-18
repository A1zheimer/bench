from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data_agent_bench.evaluation.scoring_v3 import find_trace_path, load_trace_jsonl, rescore_report_v3


def _read_ground_truth(tasks_dir: Path, task_id: str) -> Dict[str, Any]:
    path = tasks_dir / task_id / "ground_truth" / "expected_output.json"
    return json.loads(path.read_text("utf-8"))


def _preview(text: str, limit: int = 500) -> str:
    compact = "\n".join(line.rstrip() for line in str(text).splitlines() if line.strip())
    if len(compact) <= limit:
        return compact
    return compact[:limit] + "\n..."


def _failure(report: Dict[str, Any]) -> str:
    failure = report.get("failure_attribution") or {}
    return str(failure.get("primary_failure") or failure.get("primary_cause") or "none")


def _score_block(title: str, score: Any) -> List[str]:
    lines = [f"## {title}", "", f"accuracy: {score.accuracy:.4f}", ""]
    lines.append("| key | score | expected | extracted | rel_error | source | step |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for key, detail in score.field_scores.items():
        lines.append(
            "| "
            + " | ".join([
                key,
                f"{detail.score:.4f}",
                _fmt(detail.expected_value),
                _fmt(detail.extracted_value),
                _fmt(detail.relative_error),
                str(detail.source),
                "" if detail.source_step is None else str(detail.source_step),
            ])
            + " |"
        )
    lines.append("")
    return lines


def _fmt(value: Optional[float]) -> str:
    if value is None:
        return ""
    return f"{value:.8g}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect one report/trace under scoring V3.")
    parser.add_argument("--tasks-dir", required=True, help="Path to task directories.")
    parser.add_argument("--report", required=True, help="Path to report.json.")
    parser.add_argument("--trace", help="Optional path to trace.jsonl. Auto-detected from report dir when omitted.")
    args = parser.parse_args()

    report_path = Path(args.report)
    report = json.loads(report_path.read_text("utf-8"))
    task_id = str(report.get("instance_id") or report_path.parent.name)
    ground_truth = _read_ground_truth(Path(args.tasks_dir), task_id)
    trace_path = Path(args.trace) if args.trace else find_trace_path(report_path)
    trace_steps = load_trace_jsonl(trace_path) if trace_path else []
    result = rescore_report_v3(
        report,
        trace_steps,
        ground_truth,
        report_path=str(report_path),
        trace_path=str(trace_path or ""),
    )

    scores = report.get("scores") or {}
    lines: List[str] = [
        f"# Trace Score Viewer: {task_id}",
        "",
        f"report: {report_path}",
        f"trace: {trace_path or 'not found'}",
        f"ground_truth_keys: {', '.join((ground_truth.get('key_values') or {}).keys())}",
        f"failure: {_failure(report)}",
        f"timeout_or_api_failure: {result.timeout_or_api_failure}",
        f"process_quality: {result.process_quality:.4f}",
        f"trace_integrity: {result.trace_integrity:.4f}",
        f"execution_safety: {result.execution_safety:.4f}",
        f"analytical_safety: {result.analytical_safety:.4f}",
        "",
    ]
    lines.extend(_score_block("Final Answer Accuracy", result.final_answer))
    lines.extend(_score_block("Observed Trace Accuracy", result.trace_grounded))
    lines.extend(_score_block("Grounded Final Accuracy", result.grounded_final))
    lines.extend([
        "## Diagnostic",
        "",
        f"format_miss_keys: {', '.join(result.format_miss_keys()) or 'none'}",
        f"ungrounded_final_keys: {', '.join(result.ungrounded_final_keys()) or 'none'}",
        f"legacy_report_scorer_audit: {json.dumps(scores.get('scorer_audit') or {}, ensure_ascii=False)}",
        "",
        "## Final Code",
        "",
        "```python",
        _preview(report.get("final_code", ""), 1200),
        "```",
        "",
        "## Execution Result",
        "",
        "```text",
        _preview(report.get("execution_result", ""), 1200),
        "```",
        "",
        "## Trace Steps",
        "",
    ])

    for step in trace_steps:
        lines.extend([
            f"### Step {step.get('step', '?')}",
            "",
            f"action_type: {step.get('action_type', '')}",
            f"action: {_preview(str(step.get('action') or ''), 200)}",
            "",
            "```text",
            _preview("\n".join([
                str(step.get("observation") or ""),
                str(step.get("tool_result") or ""),
            ]), 1000),
            "```",
            "",
        ])

    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
