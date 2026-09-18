from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data_agent_bench.evaluation.scoring_v3 import (
    RescoreV3Result,
    find_trace_path,
    load_trace_jsonl,
    rescore_report_v3,
)
from data_agent_bench.repository.provenance import is_verified_ground_truth


def _read_ground_truth(tasks_dir: Path, task_id: str) -> Dict[str, Any]:
    path = tasks_dir / task_id / "ground_truth" / "expected_output.json"
    return json.loads(path.read_text("utf-8"))


def _read_results(
    label: str,
    run_dir: Path,
    tasks_dir: Path,
    allowed_task_ids: Optional[Set[str]] = None,
    include_unverified: bool = False,
) -> List[RescoreV3Result]:
    results: List[RescoreV3Result] = []
    for report_path in sorted(run_dir.glob("*/report.json")):
        report = json.loads(report_path.read_text("utf-8"))
        task_id = str(report.get("instance_id") or report_path.parent.name)
        if allowed_task_ids is not None and task_id not in allowed_task_ids:
            continue
        ground_truth = _read_ground_truth(tasks_dir, task_id)
        if not include_unverified and not is_verified_ground_truth(ground_truth):
            continue
        trace_path = find_trace_path(report_path)
        trace_steps = load_trace_jsonl(trace_path) if trace_path else []
        results.append(rescore_report_v3(
            report,
            trace_steps,
            ground_truth,
            report_path=str(report_path),
            trace_path=str(trace_path or ""),
        ))
    return results


def _mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _aggregate(label: str, results: List[RescoreV3Result]) -> Dict[str, str]:
    non_timeout = [result for result in results if not result.timeout_or_api_failure]
    return {
        "Model": label,
        "Reports": str(len(results)),
        "FinalAcc": f"{_mean([r.final_answer.accuracy for r in results]):.3f}",
        "ObservedTraceAcc": f"{_mean([r.trace_grounded.accuracy for r in results]):.3f}",
        "GroundedFinalAcc": f"{_mean([r.grounded_final.accuracy for r in results]):.3f}",
        "FinalAcc_no_timeout": f"{_mean([r.final_answer.accuracy for r in non_timeout]):.3f}",
        "ObservedTraceAcc_no_timeout": f"{_mean([r.trace_grounded.accuracy for r in non_timeout]):.3f}",
        "GroundedFinalAcc_no_timeout": f"{_mean([r.grounded_final.accuracy for r in non_timeout]):.3f}",
        "Timeout/API Rate": f"{(len(results) - len(non_timeout)) / len(results):.1%}" if results else "0.0%",
        "Format Miss Rate": f"{_mean([1.0 if r.format_miss() else 0.0 for r in results]):.1%}",
        "Ungrounded Final Rate": f"{_mean([1.0 if r.ungrounded_final() else 0.0 for r in results]):.1%}",
        "TraceIntegrity": f"{_mean([r.trace_integrity for r in results]):.3f}",
        "Process": f"{_mean([r.process_quality for r in results]):.3f}",
        "ExecSafety": f"{_mean([r.execution_safety for r in results]):.3f}",
        "AnaSafety": f"{_mean([r.analytical_safety for r in results]):.3f}",
    }


def _per_task_row(label: str, result: RescoreV3Result) -> Dict[str, str]:
    delta = result.trace_grounded.accuracy - result.final_answer.accuracy
    source_counts = {
        key: value for key, value in result.trace_grounded.sources.items()
        if key != "none" and value > 0
    }
    return {
        "Model": label,
        "Task": result.task_id,
        "FinalAcc": f"{result.final_answer.accuracy:.3f}",
        "ObservedTraceAcc": f"{result.trace_grounded.accuracy:.3f}",
        "GroundedFinalAcc": f"{result.grounded_final.accuracy:.3f}",
        "ObservedMinusFinal": f"{delta:.3f}",
        "Failure": result.failure,
        "ExtractedSource": str(source_counts or result.trace_grounded.sources),
        "MissedKeys": ", ".join(result.format_miss_keys()),
        "UngroundedKeys": ", ".join(result.ungrounded_final_keys()),
        "TracePath": result.trace_path,
    }


def _table(rows: List[Dict[str, str]], headers: List[str]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_sanitize(row.get(header, "")) for header in headers) + " |")
    return "\n".join(lines)


def _sanitize(value: str) -> str:
    return str(value).replace("\n", " ").replace("|", "\\|")


def main() -> int:
    parser = argparse.ArgumentParser(description="Rescore existing reports with DataAgentBench scoring V3.")
    parser.add_argument("--tasks-dir", required=True, help="Path to task directories.")
    parser.add_argument("--run", action="append", required=True, help="Model label and run dir as label=/path/to/run.")
    parser.add_argument("--output", required=True, help="Markdown output path.")
    parser.add_argument("--task-id", action="append", default=[], help="Optional task id filter. Can be repeated.")
    parser.add_argument("--tasks-file", help="Optional JSON file containing task ids to include.")
    parser.add_argument(
        "--include-unverified",
        action="store_true",
        help="Debug only: rescore tasks without verified GT provenance.",
    )
    args = parser.parse_args()

    tasks_dir = Path(args.tasks_dir)
    allowed_task_ids = _load_allowed_task_ids(args.task_id, args.tasks_file)
    aggregate_rows: List[Dict[str, str]] = []
    per_task_rows: List[Dict[str, str]] = []

    for item in args.run:
        label, raw_path = item.split("=", 1)
        results = _read_results(
            label,
            Path(raw_path),
            tasks_dir,
            allowed_task_ids,
            include_unverified=args.include_unverified,
        )
        aggregate_rows.append(_aggregate(label, results))
        per_task_rows.extend(_per_task_row(label, result) for result in results)

    lines = [
        "# DataAgentBench Scoring V3 Rescore Report",
        "",
        "This report rescored existing report.json + trace.jsonl artifacts without rerunning models.",
        "",
        "Interpretation note: this is a scoring/trace diagnostic report, not a leaderboard. "
        "Small task filters, repaired ground truth, old traces, and timeout-heavy runs should not be used for model ranking.",
        "",
        f"Task filter: `{', '.join(sorted(allowed_task_ids)) if allowed_task_ids else 'all reports in each run directory'}`.",
        "",
        "## Aggregate",
        "",
        _table(aggregate_rows, [
            "Model",
            "Reports",
            "FinalAcc",
            "ObservedTraceAcc",
            "GroundedFinalAcc",
            "FinalAcc_no_timeout",
            "ObservedTraceAcc_no_timeout",
            "GroundedFinalAcc_no_timeout",
            "Timeout/API Rate",
            "Format Miss Rate",
            "Ungrounded Final Rate",
            "TraceIntegrity",
            "Process",
            "ExecSafety",
            "AnaSafety",
        ]),
        "",
        "## Per-task",
        "",
        _table(per_task_rows, [
            "Model",
            "Task",
            "FinalAcc",
            "ObservedTraceAcc",
            "GroundedFinalAcc",
            "ObservedMinusFinal",
            "Failure",
            "ExtractedSource",
            "MissedKeys",
            "UngroundedKeys",
            "TracePath",
        ]),
        "",
    ]

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), "utf-8")
    print(f"Wrote {output}")
    return 0


def _load_allowed_task_ids(task_ids: List[str], tasks_file: Optional[str]) -> Optional[Set[str]]:
    allowed = set(task_ids)
    if tasks_file:
        raw = json.loads(Path(tasks_file).read_text("utf-8"))
        if isinstance(raw, list):
            allowed.update(str(item) for item in raw)
        else:
            raise ValueError(f"Unsupported tasks file format: {tasks_file}")
    return allowed or None


if __name__ == "__main__":
    raise SystemExit(main())
