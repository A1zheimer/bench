from __future__ import annotations

import ast
import json
from pathlib import Path

import pandas as pd
import pytest

from data_agent_bench.analysis.leaderboard import LeaderboardGenerator
from data_agent_bench.repository.provenance import is_verified_ground_truth
from data_agent_bench.repository.task_repo import TaskRepository
from data_agent_taskgen import TaskManifest, TaskPackager, VerifierRegistry
from data_agent_taskgen.redteam import RedteamMetadataError, RedteamSpec, assert_invariant_gt


def _dataset(path: Path) -> Path:
    df = pd.DataFrame({
        "product_category": ["Books", "Books", "Food"],
        "total_cost": [10.0, 15.0, 7.5],
    })
    csv_path = path / "dataset.csv"
    df.to_csv(csv_path, index=False)
    return csv_path


def _manifest() -> TaskManifest:
    return TaskManifest.from_dict({
        "task_id": "DS_TASK_001",
        "template_id": "groupby_aggregation_v1",
        "domain": "ECommerce",
        "difficulty": "Easy",
        "primary_task_type": "descriptive_aggregation",
        "tags": ["revenue analysis"],
        "problem_statement": "Compute total revenue for each product category.",
        "operation": {
            "groupby": "product_category",
            "value_column": "total_cost",
            "agg": "sum",
            "output_prefix": "total_revenue",
        },
    })


def test_taskgen_packager_writes_verified_static_task_consumed_by_bench_repo(tmp_path: Path) -> None:
    dataset_path = _dataset(tmp_path)
    packager = TaskPackager(tmp_path / "tasks_verified_core_v1")

    packaged = packager.package(_manifest(), dataset_path)

    assert (packaged.task_dir / "task_manifest.json").exists()
    assert (packaged.task_dir / "data" / "dataset.csv").exists()
    expected = json.loads((packaged.task_dir / "ground_truth" / "expected_output.json").read_text("utf-8"))
    assert is_verified_ground_truth(expected)
    assert expected["key_values"] == {
        "total_revenue_books": 25.0,
        "total_revenue_food": 7.5,
    }

    repo = TaskRepository(str(tmp_path / "tasks_verified_core_v1"), require_verified=True)
    assert repo.count() == 1
    assert repo.get("DS_TASK_001").ground_truth_path


def test_task_repository_skips_unverified_tasks_by_default_when_requested(tmp_path: Path) -> None:
    task_dir = tmp_path / "tasks_legacy_unverified" / "DS_TASK_001"
    (task_dir / "ground_truth").mkdir(parents=True)
    (task_dir / "task.json").write_text(json.dumps(_manifest().to_dict() | {
        "instance_id": "DS_TASK_001",
        "task_metadata": {"domain": "ECommerce", "difficulty": "Easy"},
        "context": {"problem_statement": "x", "dataset_preview": "data/dataset.csv"},
        "environment_config": {"image": "x", "max_steps": 1, "budget": 1.0},
    }), "utf-8")
    (task_dir / "ground_truth" / "expected_output.json").write_text(json.dumps({
        "execution_result": "x",
        "key_values": {"x": 1.0},
        "verified": False,
    }), "utf-8")

    repo = TaskRepository(str(tmp_path / "tasks_legacy_unverified"), require_verified=True)
    assert repo.count() == 0
    assert repo.skipped_unverified == ["DS_TASK_001"]


def test_redteam_metadata_validation_and_invariant_gt_check() -> None:
    spec = RedteamSpec.from_dict({
        "base_task_id": "DS_TASK_001",
        "attack_type": "schema_obfuscation",
        "attack_level": "L1",
        "gt_policy": "invariant",
        "perturbation_seed": 20260521,
    })
    assert spec.to_manifest_redteam()["is_redteam"] is True
    assert_invariant_gt({"key_values": {"x": 1.0}}, {"key_values": {"x": 1.0}})

    with pytest.raises(RedteamMetadataError):
        RedteamSpec.from_dict({
            "base_task_id": "DS_TASK_001",
            "attack_type": "schema_obfuscation",
            "attack_level": "L1",
            "gt_policy": "unknown",
            "perturbation_seed": 1,
        })


def test_leaderboard_excludes_unverified_reports_by_default() -> None:
    verified = {
        "model_id": "model-a",
        "metrics": {"result_accuracy": 1, "process_quality": 1, "safety_score": 1, "completion_rate": 1},
        "metadata": {"task_provenance": {"verified": True, "source_set": "verified"}},
    }
    legacy = {
        "model_id": "model-b",
        "metrics": {"result_accuracy": 1, "process_quality": 1, "safety_score": 1, "completion_rate": 1},
        "metadata": {"task_provenance": {"verified": False, "source_set": "legacy_unverified"}},
    }

    rows = LeaderboardGenerator.build([verified, legacy], bootstrap_n=10)

    assert [row["model_id"] for row in rows] == ["model-a"]


def test_bench_package_does_not_import_taskgen_package() -> None:
    root = Path("data_agent_bench")
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text("utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(alias.name.startswith("data_agent_taskgen") for alias in node.names):
                    offenders.append(str(path))
            elif isinstance(node, ast.ImportFrom):
                if (node.module or "").startswith("data_agent_taskgen"):
                    offenders.append(str(path))
    assert offenders == []
