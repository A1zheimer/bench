from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _read_reports(run_dir: Path) -> List[Dict[str, Any]]:
    reports: List[Dict[str, Any]] = []
    for path in sorted(run_dir.glob("*/report.json")):
        data = json.loads(path.read_text("utf-8"))
        data["_report_path"] = str(path)
        reports.append(data)
    return reports


def _mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _raw_accuracy(report: Dict[str, Any]) -> float:
    det = report.get("scores", {}).get("deterministic", {})
    raw_scores = det.get("raw_field_scores") or {}
    sim = float(det.get("similarity_score") or 0.0)
    if raw_scores and all(float(v) >= 1.0 for v in raw_scores.values()):
        return 1.0
    field_avg = _mean([float(v) for v in raw_scores.values()]) if raw_scores else 0.0
    return 0.7 * field_avg + 0.3 * sim


def _safety_score(scores: Dict[str, Any], key: str) -> float:
    direct = scores.get(key) or {}
    nested = (scores.get("risk") or {}).get(key) or {}
    return float((direct or nested).get("score", 0.0))


def _table(rows: List[Dict[str, str]], headers: List[str]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row.get(h, "") for h in headers) + " |")
    return "\n".join(lines)


def _summarize(label: str, run_dir: Path) -> Tuple[Dict[str, Any], List[Dict[str, str]]]:
    reports = _read_reports(run_dir)
    rows: List[Dict[str, str]] = []
    source_counter: Counter[str] = Counter()
    failures: Counter[str] = Counter()
    audit_misses = 0

    for report in reports:
        metrics = report.get("metrics", {})
        scores = report.get("scores", {})
        extracted = report.get("benchmark_extracted_answer") or {}
        audit = scores.get("scorer_audit") or {}
        failure = report.get("failure_attribution") or {}
        source = str(extracted.get("source", "none"))
        source_counter[source] += 1
        failure_cause = str(failure.get("primary_cause", "none"))
        failures[failure_cause] += 1
        if audit.get("missed_trace_value"):
            audit_misses += 1

        rows.append({
            "Model": label,
            "Task": str(report.get("instance_id", "")),
            "RawAcc": f"{_raw_accuracy(report):.3f}",
            "TraceAcc": f"{float(metrics.get('result_accuracy', 0.0)):.3f}",
            "Process": f"{float(metrics.get('process_quality', 0.0)):.3f}",
            "ExecSafe": f"{_safety_score(scores, 'execution_safety'):.3f}",
            "AnaSafe": f"{_safety_score(scores, 'analytical_safety'):.3f}",
            "TraceInt": f"{float((scores.get('trace_integrity') or {}).get('integrity_score', 0.0)):.3f}",
            "ExtractSrc": source,
            "Audit": "missed" if audit.get("missed_trace_value") else "ok",
            "Failure": failure_cause,
        })

    summary = {
        "label": label,
        "count": len(reports),
        "raw_accuracy": _mean([_raw_accuracy(r) for r in reports]),
        "trace_accuracy": _mean([float(r.get("metrics", {}).get("result_accuracy", 0.0)) for r in reports]),
        "process": _mean([float(r.get("metrics", {}).get("process_quality", 0.0)) for r in reports]),
        "exec_safety": _mean([_safety_score(r.get("scores", {}), "execution_safety") for r in reports]),
        "ana_safety": _mean([_safety_score(r.get("scores", {}), "analytical_safety") for r in reports]),
        "trace_integrity": _mean([float((r.get("scores", {}).get("trace_integrity") or {}).get("integrity_score", 0.0)) for r in reports]),
        "scorer_audit_hit_rate": audit_misses / len(reports) if reports else 0.0,
        "sources": dict(source_counter),
        "failures": dict(failures),
    }
    return summary, rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a validity-repair report from V2 benchmark runs.")
    parser.add_argument("--run", action="append", required=True, help="Model label and run dir as label=/path/to/run")
    parser.add_argument("--output", required=True, help="Markdown output path")
    args = parser.parse_args()

    summaries: List[Dict[str, Any]] = []
    all_rows: List[Dict[str, str]] = []
    for item in args.run:
        label, raw_path = item.split("=", 1)
        summary, rows = _summarize(label, Path(raw_path))
        summaries.append(summary)
        all_rows.extend(rows)

    lines = ["# DataAgentBench Validity Repair Report", ""]
    lines.append("## Aggregate")
    lines.append("")
    lines.append(_table([
        {
            "Model": s["label"],
            "Reports": str(s["count"]),
            "RawAcc": f"{s['raw_accuracy']:.3f}",
            "TraceAcc": f"{s['trace_accuracy']:.3f}",
            "Process": f"{s['process']:.3f}",
            "ExecSafe": f"{s['exec_safety']:.3f}",
            "AnaSafe": f"{s['ana_safety']:.3f}",
            "TraceInt": f"{s['trace_integrity']:.3f}",
            "AuditHit": f"{s['scorer_audit_hit_rate']:.1%}",
            "Sources": str(s["sources"]),
            "Failures": str(s["failures"]),
        }
        for s in summaries
    ], ["Model", "Reports", "RawAcc", "TraceAcc", "Process", "ExecSafe", "AnaSafe", "TraceInt", "AuditHit", "Sources", "Failures"]))

    lines.extend(["", "## Per-task", ""])
    lines.append(_table(all_rows, [
        "Model", "Task", "RawAcc", "TraceAcc", "Process", "ExecSafe",
        "AnaSafe", "TraceInt", "ExtractSrc", "Audit", "Failure",
    ]))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), "utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
