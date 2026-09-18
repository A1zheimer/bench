from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable


REQUIRED_GT_PROVENANCE = {
    "verified",
    "verifier_id",
    "dataset_sha256",
    "formula",
    "computed_at",
}

EXCLUDED_SOURCE_SETS = {"legacy_unverified", "taskgen_candidates"}


def load_ground_truth(gt_path: str | Path) -> Dict[str, Any]:
    return json.loads(Path(gt_path).read_text("utf-8"))


def is_verified_ground_truth(gt: Dict[str, Any]) -> bool:
    if gt.get("verified") is not True:
        return False
    for key in REQUIRED_GT_PROVENANCE - {"verified"}:
        if not str(gt.get(key, "")).strip():
            return False
    return True


def task_dir_is_verified(task_dir: str | Path) -> bool:
    gt_path = Path(task_dir) / "ground_truth" / "expected_output.json"
    if not gt_path.exists():
        return False
    try:
        return is_verified_ground_truth(load_ground_truth(gt_path))
    except Exception:
        return False


def task_provenance(gt: Dict[str, Any], *, source_set: str = "") -> Dict[str, Any]:
    return {
        "verified": is_verified_ground_truth(gt),
        "verifier_id": gt.get("verifier_id"),
        "dataset_sha256": gt.get("dataset_sha256"),
        "formula": gt.get("formula"),
        "computed_at": gt.get("computed_at"),
        "source_set": source_set or gt.get("source_set") or "",
    }


def report_is_formal(report: Dict[str, Any]) -> bool:
    metadata = report.get("metadata") or {}
    provenance = metadata.get("task_provenance") or {}
    if provenance.get("source_set") in EXCLUDED_SOURCE_SETS:
        return False
    return provenance.get("verified") is True


def filter_formal_reports(reports: Iterable[Dict[str, Any]]) -> list[Dict[str, Any]]:
    return [report for report in reports if report_is_formal(report)]
