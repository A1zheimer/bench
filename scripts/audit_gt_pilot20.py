from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


DEFAULT_TASKS_DIR = Path("/Users/bytedance/Desktop/bench-llmbox/tasks")
DEFAULT_PILOT_FILE = Path("/Users/bytedance/Desktop/bench-llmbox/pilot_20_tasks.json")
DEFAULT_REPORT_MD = Path("/Users/bytedance/Desktop/bench/reports/gt_audit_pilot20.md")
DEFAULT_REPORT_JSON = Path("/Users/bytedance/Desktop/bench/reports/gt_audit_pilot20.json")

TEMPLATE_GT_KEYS = {
    "mean_value",
    "max_correlation",
    "total_missing",
    "outlier_count",
    "correlation",
}

ADVANCED_TAGS = {
    "ROC-analysis",
    "threshold-tuning",
    "binary-classification",
    "ensemble-stacking",
    "cross-validation",
    "meta-learner",
    "SARIMA",
    "seasonal-forecasting",
    "temperature",
    "GARCH",
    "volatility-modeling",
    "time-series",
    "ARIMA",
    "factor-model",
    "PCA",
    "asset-pricing",
    "chi-squared",
    "independence-test",
    "categorical",
    "two-way-ANOVA",
    "drug-efficacy",
    "interaction",
}


@dataclass
class AuditRow:
    task_id: str
    domain: str
    difficulty: str
    tags: List[str]
    gt_key_values: Dict[str, Any]
    recomputed_key_values: Dict[str, Any]
    generator: str
    generated_at: str
    verified: bool
    generation_trace_error_count: int
    forced_submit: bool
    audit_status: str
    issues: List[str] = field(default_factory=list)
    recommendation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "domain": self.domain,
            "difficulty": self.difficulty,
            "tags": self.tags,
            "gt_key_values": self.gt_key_values,
            "recomputed_key_values": self.recomputed_key_values,
            "generator": self.generator,
            "generated_at": self.generated_at,
            "verified": self.verified,
            "generation_trace_error_count": self.generation_trace_error_count,
            "forced_submit": self.forced_submit,
            "audit_status": self.audit_status,
            "issues": self.issues,
            "recommendation": self.recommendation,
        }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text("utf-8"))


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_task_ids(pilot_file: Path) -> List[str]:
    value = load_json(pilot_file)
    if not isinstance(value, list):
        raise ValueError(f"{pilot_file} must contain a JSON list of task ids")
    return [str(item) for item in value]


def recompute_known_key_values(task_dir: Path, gt_key_values: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data_path = task_dir / "data" / "dataset.csv"
    if not data_path.exists():
        return {}
    df = pd.read_csv(data_path)
    gt_key_values = gt_key_values or {}
    result: Dict[str, Any] = {}

    if "mean_value" in gt_key_values:
        result["mean_value"] = round(float(df.mean(numeric_only=True).iloc[0]), 4)

    if "total_missing" in gt_key_values:
        result["total_missing"] = int(df.isnull().sum().sum())

    if "max_correlation" in gt_key_values:
        value = _max_abs_correlation(df)
        if value is not None:
            result["max_correlation"] = round(float(value), 4)

    if "outlier_count" in gt_key_values:
        result["outlier_count"] = total_iqr_outlier_count(df)

    if "correlation" in gt_key_values:
        value = _max_abs_correlation(df)
        if value is not None:
            result["correlation"] = round(float(value), 4)

    if "average_stay_duration_readmitted" in gt_key_values and {"readmission", "hospital_stay_days"} <= set(df.columns):
        result["average_stay_duration_readmitted"] = float(
            df.loc[df["readmission"] == 1, "hospital_stay_days"].mean()
        )

    if {"product_category", "total_cost"} <= set(df.columns):
        totals = ecommerce_revenue_by_category(df)
        for category, value in totals.items():
            key = f"total_revenue_{_slug(category)}"
            if key in gt_key_values:
                result[key] = value

    if {"has_diabetes", "has_hypertension", "readmitted_30d"} <= set(df.columns):
        result.update(diabetes_comorbidity_metrics(df))

    if {"sepal_length_cm", "sepal_width_cm", "petal_length_cm", "petal_width_cm"} <= set(df.columns):
        result.update(iris_correlation_metrics(df))
        result.update(iris_outlier_metrics(df))

    return {k: v for k, v in result.items() if k in gt_key_values}


def ecommerce_revenue_by_category(df: pd.DataFrame) -> Dict[str, float]:
    return {
        str(category): round(float(value), 2)
        for category, value in df.groupby("product_category")["total_cost"].sum().sort_index().items()
    }


def diabetes_comorbidity_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    both = (df["has_diabetes"] == 1) & (df["has_hypertension"] == 1)
    ct = pd.crosstab(df["has_diabetes"], df["has_hypertension"])
    return {
        "diabetes_hypertension_count": int(both.sum()),
        "diabetes_hypertension_prevalence": float(both.mean()),
        "readmission_rate_diabetes_hypertension": float(df.loc[both, "readmitted_30d"].mean()),
        "crosstab_diabetes0_hypertension0": int(ct.loc[0, 0]),
        "crosstab_diabetes0_hypertension1": int(ct.loc[0, 1]),
        "crosstab_diabetes1_hypertension0": int(ct.loc[1, 0]),
        "crosstab_diabetes1_hypertension1": int(ct.loc[1, 1]),
    }


def iris_correlation_metrics(df: pd.DataFrame) -> Dict[str, float]:
    corr = df.corr(numeric_only=True)
    masked = corr.abs().mask(np.eye(len(corr), dtype=bool))
    values = masked.unstack().dropna().sort_values(ascending=False)
    return {
        "corr_sepal_length_petal_length": float(df["sepal_length_cm"].corr(df["petal_length_cm"])),
        "corr_sepal_width_petal_width": float(df["sepal_width_cm"].corr(df["petal_width_cm"])),
        "max_abs_correlation": float(values.iloc[0]),
    }


def iris_outlier_metrics(df: pd.DataFrame) -> Dict[str, int]:
    counts = iqr_outlier_counts(df)
    result = {f"outlier_count_{column}": int(count) for column, count in counts.items()}
    result["total_outlier_count"] = int(sum(counts.values()))
    return result


def iqr_outlier_counts(df: pd.DataFrame) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for column in df.select_dtypes(include=["float64", "int64"]).columns:
        q1 = df[column].quantile(0.25)
        q3 = df[column].quantile(0.75)
        iqr = q3 - q1
        counts[column] = int(((df[column] < q1 - 1.5 * iqr) | (df[column] > q3 + 1.5 * iqr)).sum())
    return counts


def total_iqr_outlier_count(df: pd.DataFrame) -> int:
    return int(sum(iqr_outlier_counts(df).values()))


def audit_task(task_dir: Path) -> AuditRow:
    task = load_json(task_dir / "task.json")
    gt = load_json(task_dir / "ground_truth" / "expected_output.json")
    meta_path = task_dir / "generation_meta.json"
    meta = load_json(meta_path) if meta_path.exists() else {}

    task_id = str(task.get("instance_id") or task_dir.name)
    metadata = task.get("task_metadata") or {}
    tags = [str(item) for item in metadata.get("tags", [])]
    gt_key_values = gt.get("key_values") or {}
    recomputed = recompute_known_key_values(task_dir, gt_key_values)

    trace = meta.get("trace") or []
    generation_trace_error_count = sum(1 for step in trace if "ERROR" in str(step.get("result_preview", "")))
    forced_submit = any(step.get("action") == "submit_task" and bool(step.get("forced")) for step in trace)
    verified = bool(meta.get("verified", False))

    issues: List[str] = []
    mismatches = _value_mismatches(gt_key_values, recomputed)
    issues.extend(mismatches)
    if _prompt_gt_mismatch(tags, gt_key_values):
        issues.append("PROMPT_GT_MISMATCH: template GT keys do not match advanced task tags")
    if not verified:
        issues.append("UNVERIFIED: generation_meta.verified=false")
    if generation_trace_error_count:
        issues.append(f"GENERATION_TRACE_ERRORS: {generation_trace_error_count}")
    if forced_submit:
        issues.append("FORCED_SUBMIT: generation trace ended with forced submit")

    audit_status = _classify_status(
        gt_key_values=gt_key_values,
        recomputed=recomputed,
        mismatches=mismatches,
        prompt_gt_mismatch=_prompt_gt_mismatch(tags, gt_key_values),
        generation_trace_error_count=generation_trace_error_count,
    )
    return AuditRow(
        task_id=task_id,
        domain=str(metadata.get("domain", "")),
        difficulty=str(metadata.get("difficulty", "")),
        tags=tags,
        gt_key_values=gt_key_values,
        recomputed_key_values=recomputed,
        generator=str(meta.get("generator", "")),
        generated_at=str(meta.get("generated_at", "")),
        verified=verified,
        generation_trace_error_count=generation_trace_error_count,
        forced_submit=forced_submit,
        audit_status=audit_status,
        issues=issues,
        recommendation=_recommendation(audit_status),
    )


def audit_pilot(tasks_dir: Path, pilot_file: Path) -> List[AuditRow]:
    rows: List[AuditRow] = []
    for task_id in load_task_ids(pilot_file):
        task_dir = tasks_dir / task_id
        if not task_dir.exists():
            rows.append(AuditRow(
                task_id=task_id,
                domain="",
                difficulty="",
                tags=[],
                gt_key_values={},
                recomputed_key_values={},
                generator="",
                generated_at="",
                verified=False,
                generation_trace_error_count=0,
                forced_submit=False,
                audit_status="NEEDS_MANUAL_REDESIGN",
                issues=[f"MISSING_TASK_DIR: {task_dir}"],
                recommendation="Locate or regenerate the task before using it.",
            ))
            continue
        rows.append(audit_task(task_dir))
    return rows


def write_reports(rows: List[AuditRow], markdown_path: Path, json_path: Path) -> None:
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps([row.to_dict() for row in rows], indent=2, ensure_ascii=False), "utf-8")
    markdown_path.write_text(render_markdown(rows), "utf-8")


def render_markdown(rows: List[AuditRow]) -> str:
    lines = [
        "# DataAgentBench Pilot-20 Ground Truth Audit",
        "",
        "This audit is read-only: it does not modify source tasks or reports.",
        "",
        "## Summary",
        "",
    ]
    counts: Dict[str, int] = {}
    for row in rows:
        counts[row.audit_status] = counts.get(row.audit_status, 0) + 1
    lines.append("| Status | Count |")
    lines.append("| --- | ---: |")
    for status, count in sorted(counts.items()):
        lines.append(f"| {status} | {count} |")
    lines.extend([
        "",
        "## Per-task Audit",
        "",
        "| Task | Domain | Diff | Generator | Verified | Errors | Forced | Status | GT | Recomputed | Issues |",
        "| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- |",
    ])
    for row in rows:
        lines.append(
            "| "
            + " | ".join([
                row.task_id,
                row.domain,
                row.difficulty,
                row.generator,
                str(row.verified),
                str(row.generation_trace_error_count),
                str(row.forced_submit),
                row.audit_status,
                _inline_json(row.gt_key_values),
                _inline_json(row.recomputed_key_values),
                "; ".join(row.issues),
            ])
            + " |"
        )
    return "\n".join(lines) + "\n"


def _classify_status(
    *,
    gt_key_values: Dict[str, Any],
    recomputed: Dict[str, Any],
    mismatches: List[str],
    prompt_gt_mismatch: bool,
    generation_trace_error_count: int,
) -> str:
    if prompt_gt_mismatch:
        return "PROMPT_GT_MISMATCH"
    if mismatches:
        return "GT_VALUE_MISMATCH"
    if generation_trace_error_count:
        return "UNVERIFIABLE_GENERATION_TRACE"
    if gt_key_values and recomputed and set(gt_key_values).issubset(recomputed):
        return "PASS_RECOMPUTED"
    return "NEEDS_MANUAL_REDESIGN"


def _recommendation(status: str) -> str:
    return {
        "PASS_RECOMPUTED": "Can be used after adding provenance and aliases.",
        "GT_VALUE_MISMATCH": "Repair GT from deterministic recomputation before retest.",
        "PROMPT_GT_MISMATCH": "Rewrite prompt/GT pair or exclude from simple retest.",
        "UNVERIFIABLE_GENERATION_TRACE": "Manually redesign or regenerate with verified solution code.",
        "NEEDS_MANUAL_REDESIGN": "Do not use until a deterministic verifier is available.",
    }.get(status, "Review manually.")


def _value_mismatches(gt_key_values: Dict[str, Any], recomputed: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    for key, recomputed_value in recomputed.items():
        if key not in gt_key_values:
            continue
        gt_value = gt_key_values[key]
        if not isinstance(gt_value, (int, float)) or not isinstance(recomputed_value, (int, float)):
            continue
        if not _close(float(gt_value), float(recomputed_value)):
            issues.append(f"GT_VALUE_MISMATCH: {key} gt={gt_value} recomputed={recomputed_value}")
    return issues


def _close(a: float, b: float, *, rel_tol: float = 0.01, abs_tol: float = 1e-8) -> bool:
    return math.isclose(a, b, rel_tol=rel_tol, abs_tol=abs_tol)


def _prompt_gt_mismatch(tags: Iterable[str], gt_key_values: Dict[str, Any]) -> bool:
    return bool((set(tags) & ADVANCED_TAGS) and (set(gt_key_values) & TEMPLATE_GT_KEYS))


def _max_abs_correlation(df: pd.DataFrame) -> Optional[float]:
    corr = df.corr(numeric_only=True).abs()
    if corr.empty or len(corr) < 2:
        return None
    values = corr.mask(np.eye(len(corr), dtype=bool)).unstack().dropna().sort_values(ascending=False)
    return float(values.iloc[0]) if not values.empty else None


def _slug(value: str) -> str:
    return str(value).strip().lower().replace(" ", "_").replace("-", "_")


def _inline_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True).replace("|", "\\|")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit DataAgentBench pilot-20 ground truth provenance and values.")
    parser.add_argument("--tasks-dir", default=str(DEFAULT_TASKS_DIR))
    parser.add_argument("--pilot-file", default=str(DEFAULT_PILOT_FILE))
    parser.add_argument("--output-md", default=str(DEFAULT_REPORT_MD))
    parser.add_argument("--output-json", default=str(DEFAULT_REPORT_JSON))
    args = parser.parse_args()

    rows = audit_pilot(Path(args.tasks_dir), Path(args.pilot_file))
    write_reports(rows, Path(args.output_md), Path(args.output_json))
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
