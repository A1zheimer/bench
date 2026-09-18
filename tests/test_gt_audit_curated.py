from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.audit_gt_pilot20 import DEFAULT_TASKS_DIR, audit_task
from scripts.build_curated_easy_v1 import (
    CURATED_TASK_IDS,
    build_curated_easy_v1,
    verify_curated_task,
)


@pytest.fixture(scope="module")
def source_tasks_dir() -> Path:
    path = DEFAULT_TASKS_DIR
    if not path.exists():
        pytest.skip(f"Source tasks not available: {path}")
    return path


def test_audit_flags_known_pilot20_gt_failures(source_tasks_dir: Path) -> None:
    row_061 = audit_task(source_tasks_dir / "DS_TASK_061")
    row_108 = audit_task(source_tasks_dir / "DS_TASK_108")
    row_126 = audit_task(source_tasks_dir / "DS_TASK_126")
    row_059 = audit_task(source_tasks_dir / "DS_TASK_059")

    assert row_061.audit_status == "GT_VALUE_MISMATCH"
    assert any("average_stay_duration_readmitted" in issue for issue in row_061.issues)

    assert row_108.audit_status == "PROMPT_GT_MISMATCH"
    assert any("PROMPT_GT_MISMATCH" in issue for issue in row_108.issues)

    assert row_126.audit_status == "PROMPT_GT_MISMATCH"
    assert any("PROMPT_GT_MISMATCH" in issue for issue in row_126.issues)

    assert row_059.audit_status == "UNVERIFIABLE_GENERATION_TRACE"
    assert row_059.generation_trace_error_count > 0


def test_build_curated_easy_v1_recomputes_all_repaired_gt(source_tasks_dir: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "tasks_curated_easy_v1"
    tasks_file = tmp_path / "curated_easy5_tasks.json"
    repair_report = tmp_path / "gt_repair_curated_easy_v1.md"

    records = build_curated_easy_v1(
        source_tasks_dir=source_tasks_dir,
        output_dir=output_dir,
        tasks_file=tasks_file,
        repair_report=repair_report,
        force=True,
    )

    assert [record["task_id"] for record in records] == CURATED_TASK_IDS
    assert json.loads(tasks_file.read_text("utf-8")) == CURATED_TASK_IDS
    assert repair_report.exists()

    for task_id in CURATED_TASK_IDS:
        task_dir = output_dir / task_id
        gt = json.loads((task_dir / "ground_truth" / "expected_output.json").read_text("utf-8"))
        assert gt["verified"] is True
        assert gt["original_task_id"] == task_id
        assert gt["dataset_sha256"]
        assert gt["verifier"].endswith("curated_easy_v1")
        assert gt["include_canary_policy"] == "include_all_rows_unless_prompt_excludes_outliers"

        verification = verify_curated_task(task_dir)
        assert verification["verified"], verification


def test_curated_ds_task_061_uses_recomputed_average(source_tasks_dir: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "tasks_curated_easy_v1"
    build_curated_easy_v1(
        source_tasks_dir=source_tasks_dir,
        output_dir=output_dir,
        tasks_file=tmp_path / "curated_easy5_tasks.json",
        repair_report=tmp_path / "gt_repair_curated_easy_v1.md",
        force=True,
    )
    gt = json.loads((output_dir / "DS_TASK_061" / "ground_truth" / "expected_output.json").read_text("utf-8"))
    assert gt["key_values"]["average_stay_duration_readmitted"] == pytest.approx(7.397163120567376)
    assert "average_hospital_stay_duration_readmitted" in gt["key_aliases"]["average_stay_duration_readmitted"]
