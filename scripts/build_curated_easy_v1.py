from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.audit_gt_pilot20 import (  # noqa: E402
    DEFAULT_TASKS_DIR,
    diabetes_comorbidity_metrics,
    ecommerce_revenue_by_category,
    file_sha256,
    iris_correlation_metrics,
    iris_outlier_metrics,
)


CURATED_VERSION = "curated_easy_v1"
CURATED_TASK_IDS = ["DS_TASK_061", "DS_TASK_066", "DS_TASK_120", "DS_TASK_150", "DS_TASK_153"]
DEFAULT_OUTPUT_DIR = Path("/Users/bytedance/Desktop/bench/tasks_curated_easy_v1")
DEFAULT_TASKS_FILE = Path("/Users/bytedance/Desktop/bench/curated_easy5_tasks.json")
DEFAULT_REPAIR_REPORT = Path("/Users/bytedance/Desktop/bench/reports/gt_repair_curated_easy_v1.md")
CANARY_POLICY = "include_all_rows_unless_prompt_excludes_outliers"


def build_curated_easy_v1(
    *,
    source_tasks_dir: Path = DEFAULT_TASKS_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    tasks_file: Path = DEFAULT_TASKS_FILE,
    repair_report: Path = DEFAULT_REPAIR_REPORT,
    force: bool = True,
) -> List[Dict[str, Any]]:
    if output_dir.exists():
        if not force:
            raise FileExistsError(f"{output_dir} already exists; pass force=True to replace it")
        _safe_rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    records: List[Dict[str, Any]] = []
    for task_id in CURATED_TASK_IDS:
        src = source_tasks_dir / task_id
        dst = output_dir / task_id
        shutil.copytree(src, dst)
        record = repair_task(dst)
        records.append(record)

    tasks_file.write_text(json.dumps(CURATED_TASK_IDS, indent=2), "utf-8")
    repair_report.parent.mkdir(parents=True, exist_ok=True)
    repair_report.write_text(render_repair_report(records), "utf-8")
    return records


def repair_task(task_dir: Path) -> Dict[str, Any]:
    task_id = task_dir.name
    task_path = task_dir / "task.json"
    gt_path = task_dir / "ground_truth" / "expected_output.json"
    meta_path = task_dir / "generation_meta.json"
    task = _read_json(task_path)
    meta = _read_json(meta_path) if meta_path.exists() else {}
    df = pd.read_csv(task_dir / "data" / "dataset.csv")
    dataset_hash = file_sha256(task_dir / "data" / "dataset.csv")

    if task_id == "DS_TASK_061":
        task, gt, formula = _repair_061(task, df, dataset_hash)
    elif task_id == "DS_TASK_066":
        task, gt, formula = _repair_066(task, df, dataset_hash)
    elif task_id == "DS_TASK_120":
        task, gt, formula = _repair_120(task, df, dataset_hash)
    elif task_id == "DS_TASK_150":
        task, gt, formula = _repair_150(task, df, dataset_hash)
    elif task_id == "DS_TASK_153":
        task, gt, formula = _repair_153(task, df, dataset_hash)
    else:
        raise ValueError(f"Unsupported curated task: {task_id}")

    repaired_at = _now()
    gt.update(_provenance(task_id, dataset_hash, formula, repaired_at))
    meta = _repair_generation_meta(meta, task_id, formula, dataset_hash, repaired_at)

    _write_json(task_path, task)
    _write_json(gt_path, gt)
    _write_json(meta_path, meta)
    return {
        "task_id": task_id,
        "formula": formula,
        "dataset_sha256": dataset_hash,
        "key_values": gt["key_values"],
        "prompt": task["context"]["problem_statement"],
    }


def verify_curated_task(task_dir: Path) -> Dict[str, Any]:
    task_id = task_dir.name
    gt = _read_json(task_dir / "ground_truth" / "expected_output.json")
    df = pd.read_csv(task_dir / "data" / "dataset.csv")
    expected = gt.get("key_values") or {}
    actual = curated_recompute(task_id, df)
    mismatches = []
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        if isinstance(expected_value, (int, float)) and isinstance(actual_value, (int, float)):
            tolerance = 1e-8 if isinstance(expected_value, int) else max(1e-8, abs(float(expected_value)) * 1e-8)
            if abs(float(expected_value) - float(actual_value)) > tolerance:
                mismatches.append({"key": key, "expected": expected_value, "actual": actual_value})
        elif expected_value != actual_value:
            mismatches.append({"key": key, "expected": expected_value, "actual": actual_value})
    return {
        "task_id": task_id,
        "verified": not mismatches,
        "mismatches": mismatches,
        "actual": actual,
    }


def curated_recompute(task_id: str, df: pd.DataFrame) -> Dict[str, Any]:
    if task_id == "DS_TASK_061":
        return {
            "average_stay_duration_readmitted": float(
                df.loc[df["readmission"] == 1, "hospital_stay_days"].mean()
            )
        }
    if task_id == "DS_TASK_066":
        return {
            f"total_revenue_{category.lower()}": value
            for category, value in ecommerce_revenue_by_category(df).items()
        }
    if task_id == "DS_TASK_120":
        return diabetes_comorbidity_metrics(df)
    if task_id == "DS_TASK_150":
        return iris_correlation_metrics(df)
    if task_id == "DS_TASK_153":
        return iris_outlier_metrics(df)
    raise ValueError(f"Unsupported curated task: {task_id}")


def render_repair_report(records: List[Dict[str, Any]]) -> str:
    lines = [
        "# DataAgentBench Curated Easy v1 GT Repair Report",
        "",
        f"Curated version: `{CURATED_VERSION}`",
        "",
        "| Task | Formula | Key Values | Dataset SHA256 |",
        "| --- | --- | --- | --- |",
    ]
    for record in records:
        lines.append(
            "| "
            + " | ".join([
                record["task_id"],
                record["formula"],
                json.dumps(record["key_values"], ensure_ascii=False, sort_keys=True).replace("|", "\\|"),
                record["dataset_sha256"],
            ])
            + " |"
        )
    return "\n".join(lines) + "\n"


def _repair_061(task: Dict[str, Any], df: pd.DataFrame, dataset_hash: str) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
    value = float(df.loc[df["readmission"] == 1, "hospital_stay_days"].mean())
    formula = "mean(hospital_stay_days where readmission == 1)"
    gt = {
        "execution_result": f"The average hospital stay duration for readmitted patients is {value:.12f} days.",
        "key_values": {"average_stay_duration_readmitted": value},
        "key_aliases": {
            "average_stay_duration_readmitted": [
                "average hospital stay duration readmitted",
                "average hospital stay days for readmitted patients",
                "average_hospital_stay_duration_readmitted",
                "average_hospital_stay_days_for_readmitted",
                "readmitted average stay",
            ]
        },
        "required_keywords": ["average", "readmission", "hospital stay"],
    }
    return task, gt, formula


def _repair_066(task: Dict[str, Any], df: pd.DataFrame, dataset_hash: str) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
    totals = {
        f"total_revenue_{category.lower()}": value
        for category, value in ecommerce_revenue_by_category(df).items()
    }
    formula = "groupby(product_category).sum(total_cost)"
    gt = {
        "execution_result": "Total revenue was computed for every product category using total_cost.",
        "key_values": totals,
        "key_aliases": {
            key: [key.replace("_", " "), key.replace("total_revenue_", "revenue ")]
            for key in totals
        },
        "required_keywords": ["total revenue", "product category", "eCommerce"],
    }
    return task, gt, formula


def _repair_120(task: Dict[str, Any], df: pd.DataFrame, dataset_hash: str) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
    task = copy.deepcopy(task)
    task["context"]["problem_statement"] = (
        "Analyze diabetes and hypertension comorbidity in the biomedical dataset. "
        "Compute the 2x2 crosstab of has_diabetes by has_hypertension, the number and prevalence "
        "of patients with both diabetes and hypertension, and the 30-day readmission rate among those comorbid patients."
    )
    task["context"]["expert_knowledge"] = (
        "Use has_diabetes, has_hypertension, and readmitted_30d directly. Include all rows unless the task explicitly asks "
        "to remove outliers or canary values."
    )
    values = diabetes_comorbidity_metrics(df)
    formula = "crosstab(has_diabetes, has_hypertension); mean(readmitted_30d where both == 1)"
    gt = {
        "execution_result": "Computed diabetes-hypertension crosstab, comorbidity prevalence, and readmission rate.",
        "key_values": values,
        "key_aliases": {
            "diabetes_hypertension_count": ["comorbidity count", "both diabetes and hypertension count"],
            "diabetes_hypertension_prevalence": ["comorbidity prevalence", "both diabetes and hypertension prevalence"],
            "readmission_rate_diabetes_hypertension": ["readmission rate comorbid", "readmission rate both diabetes hypertension"],
        },
        "required_keywords": ["diabetes", "hypertension", "comorbidity", "readmission"],
    }
    return task, gt, formula


def _repair_150(task: Dict[str, Any], df: pd.DataFrame, dataset_hash: str) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
    task = copy.deepcopy(task)
    task["context"]["problem_statement"] = (
        "Analyze Pearson correlations between iris measurement columns. Report the correlation between "
        "sepal_length_cm and petal_length_cm, the correlation between sepal_width_cm and petal_width_cm, "
        "and the maximum absolute off-diagonal correlation among numeric measurement columns."
    )
    task["context"]["expert_knowledge"] = "Use pandas Pearson correlation on numeric columns. Do not remove the canary row unless instructed."
    values = iris_correlation_metrics(df)
    formula = "pearson corr(sepal_length_cm, petal_length_cm), corr(sepal_width_cm, petal_width_cm), max abs off-diagonal corr"
    gt = {
        "execution_result": "Computed specified Pearson correlations and maximum absolute correlation.",
        "key_values": values,
        "key_aliases": {
            "corr_sepal_length_petal_length": ["correlation sepal length petal length", "sepal-petal length correlation"],
            "corr_sepal_width_petal_width": ["correlation sepal width petal width", "sepal-petal width correlation"],
            "max_abs_correlation": ["maximum absolute correlation", "max absolute off diagonal correlation"],
        },
        "required_keywords": ["correlation", "Pearson", "sepal", "petal"],
    }
    return task, gt, formula


def _repair_153(task: Dict[str, Any], df: pd.DataFrame, dataset_hash: str) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
    task = copy.deepcopy(task)
    task["context"]["problem_statement"] = (
        "Detect univariate outliers in each numeric iris measurement column using the 1.5*IQR rule. "
        "Report the outlier count for sepal_length_cm, sepal_width_cm, petal_length_cm, petal_width_cm, and the total count."
    )
    task["context"]["expert_knowledge"] = "Use Q1 - 1.5*IQR and Q3 + 1.5*IQR per numeric column. Include all rows."
    values = iris_outlier_metrics(df)
    formula = "per-column 1.5*IQR outlier count on numeric iris measurements"
    gt = {
        "execution_result": "Computed per-column and total IQR outlier counts.",
        "key_values": values,
        "key_aliases": {
            "total_outlier_count": ["total outlier count", "total IQR outliers"],
        },
        "required_keywords": ["outlier", "IQR", "1.5"],
    }
    return task, gt, formula


def _provenance(task_id: str, dataset_hash: str, formula: str, repaired_at: str) -> Dict[str, Any]:
    return {
        "original_task_id": task_id,
        "repair_reason": "GT repaired by deterministic recomputation from data/dataset.csv",
        "dataset_sha256": dataset_hash,
        "verifier": f"{Path(__file__).name}:{CURATED_VERSION}",
        "computed_at": repaired_at,
        "verified": True,
        "include_canary_policy": CANARY_POLICY,
        "formula": formula,
    }


def _repair_generation_meta(meta: Dict[str, Any], task_id: str, formula: str, dataset_hash: str, repaired_at: str) -> Dict[str, Any]:
    meta = copy.deepcopy(meta)
    meta["original_verified"] = meta.get("verified")
    meta["verified"] = True
    meta["curated_repair"] = {
        "curated_version": CURATED_VERSION,
        "original_task_id": task_id,
        "repaired_at": repaired_at,
        "verifier": f"{Path(__file__).name}:{CURATED_VERSION}",
        "formula": formula,
        "dataset_sha256": dataset_hash,
        "include_canary_policy": CANARY_POLICY,
    }
    return meta


def _safe_rmtree(path: Path) -> None:
    resolved = path.resolve()
    allowed_root = Path("/Users/bytedance/Desktop/bench").resolve()
    if allowed_root not in [resolved, *resolved.parents]:
        raise ValueError(f"Refusing to delete outside bench workspace: {path}")
    if path.name != "tasks_curated_easy_v1":
        raise ValueError(f"Refusing to delete unexpected directory: {path}")
    shutil.rmtree(path)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text("utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), "utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the curated easy-v1 task subset with repaired GT.")
    parser.add_argument("--source-tasks-dir", default=str(DEFAULT_TASKS_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--tasks-file", default=str(DEFAULT_TASKS_FILE))
    parser.add_argument("--repair-report", default=str(DEFAULT_REPAIR_REPORT))
    parser.add_argument("--no-force", action="store_true", help="Fail if output-dir already exists.")
    args = parser.parse_args()

    records = build_curated_easy_v1(
        source_tasks_dir=Path(args.source_tasks_dir),
        output_dir=Path(args.output_dir),
        tasks_file=Path(args.tasks_file),
        repair_report=Path(args.repair_report),
        force=not args.no_force,
    )
    for record in records:
        print(f"Repaired {record['task_id']}: {record['key_values']}")
    print(f"Wrote {args.output_dir}")
    print(f"Wrote {args.tasks_file}")
    print(f"Wrote {args.repair_report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
