from __future__ import annotations

import json
from pathlib import Path

from data_agent_bench.repository.task_repo import TaskRepository
from data_agent_taskgen.cli import main as taskgen_main
from data_agent_taskgen.dataset_builders import DatasetBuilderRegistry
from data_agent_taskgen.manifest_sampler import ManifestSampler
from data_agent_taskgen.packager import TaskPackager


def test_manifest_sampler_and_dataset_builder_package_verified_tasks(tmp_path: Path) -> None:
    batch = ManifestSampler(seed=123).sample_core(count_per_template=1)
    assert len(batch.manifests) == 6
    assert set(batch.template_distribution.values()) == {1}

    output = tmp_path / "tasks_verified_core_v1"
    cache = tmp_path / "cache"
    builder = DatasetBuilderRegistry()
    packager = TaskPackager(output)
    for manifest in batch.manifests:
        built = builder.build(manifest, cache, seed=123)
        packaged = packager.package(
            manifest,
            built.dataset_path,
            dataset_profile_path=built.profile_path,
        )
        assert (packaged.task_dir / "data" / "dataset_profile.json").exists()
        assert packaged.expected_output["verified"] is True
        assert packaged.expected_output["verifier_id"] == manifest.template_id
        assert packaged.expected_output["dataset_sha256"] == built.dataset_sha256

    repo = TaskRepository(str(output), require_verified=True)
    assert repo.count() == 6


def test_taskgen_build_core_cli_writes_report_and_tasks_file(tmp_path: Path) -> None:
    out = tmp_path / "tasks_verified_core_v1"
    report = tmp_path / "reports" / "verified_core_v1_smoke.md"
    tasks_file = tmp_path / "core_tasks.json"

    rc = taskgen_main([
        "build-core",
        "--output-dir", str(out),
        "--count-per-template", "1",
        "--seed", "123",
        "--tasks-file", str(tasks_file),
        "--report", str(report),
    ])

    assert rc == 0
    assert report.exists()
    assert "gt_replay: `PASS`" in report.read_text("utf-8")
    assert len(json.loads(tasks_file.read_text("utf-8"))) == 6
    assert TaskRepository(str(out), require_verified=True).count() == 6


def test_taskgen_build_redteam_cli_writes_verified_paired_tasks(tmp_path: Path) -> None:
    core = tmp_path / "tasks_verified_core_v1"
    red = tmp_path / "tasks_verified_redteam_v1"
    core_report = tmp_path / "reports" / "core.md"
    red_report = tmp_path / "reports" / "red.md"

    assert taskgen_main([
        "build-core",
        "--output-dir", str(core),
        "--count-per-template", "1",
        "--seed", "123",
        "--report", str(core_report),
    ]) == 0

    rc = taskgen_main([
        "build-redteam",
        "--clean-tasks-dir", str(core),
        "--output-dir", str(red),
        "--max-base-tasks", "2",
        "--seed", "123",
        "--report", str(red_report),
    ])

    assert rc == 0
    assert TaskRepository(str(red), require_verified=True).count() == 6
    assert "invariant/recomputed_checks: `PASS`" in red_report.read_text("utf-8")
    first_gt = json.loads(next(red.iterdir()).joinpath("ground_truth", "expected_output.json").read_text("utf-8"))
    assert first_gt["verified"] is True
    first_task = json.loads(next(red.iterdir()).joinpath("task.json").read_text("utf-8"))
    assert first_task["task_metadata"]["redteam"]["is_redteam"] is True
