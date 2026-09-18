from __future__ import annotations

import json
from pathlib import Path

from data_agent_bench.generation.pipeline import GenerationPipeline, GenerationSpec
from data_agent_bench.generation.quality_gate import GenerationQualityGate
from data_agent_bench.generation.task_generator_agent import GeneratedTask


def _task(verified: bool = True, trace: list[dict] | None = None) -> GeneratedTask:
    return GeneratedTask(
        instance_id="DS_TASK_999",
        task_json={
            "instance_id": "DS_TASK_999",
            "task_metadata": {
                "domain": "Finance",
                "difficulty": "Easy",
                "canary_value": 42.0,
            },
            "context": {
                "problem_statement": "Compute the average value.",
                "dataset_preview": "data/dataset.csv",
            },
            "environment_config": {
                "image": "ds-agent-v1:latest",
                "max_steps": 5,
                "budget": 0.5,
            },
        },
        ground_truth={
            "execution_result": "average_value = 1.0",
            "key_values": {"average_value": 1.0},
        },
        data_files=[],
        data_generation_code="import pandas as pd\npd.DataFrame({'value':[1]}).to_csv('dataset.csv', index=False)",
        solution_code="print('average_value = 1.0')",
        canary_value=42.0,
        verified=verified,
        generation_trace=trace or [{"step": 1, "action": "submit_task", "forced": False}],
    )


def test_generation_quality_gate_accepts_verified_clean_task() -> None:
    result = GenerationQualityGate.formal().evaluate(_task())

    assert result.accepted
    assert result.quality_tier == "verified"
    assert result.issues == []


def test_generation_quality_gate_rejects_unverified_trace_error_forced_submit() -> None:
    trace = [
        {"step": 1, "action": "python_repl", "result_preview": "ERROR: file not found"},
        {"step": 2, "action": "submit_task", "forced": True},
    ]
    result = GenerationQualityGate.formal().evaluate(_task(verified=False, trace=trace))

    assert not result.accepted
    assert "GT_NOT_VERIFIED: deterministic solution verification failed" in result.issues
    assert "GENERATION_TRACE_ERRORS: 1" in result.issues
    assert "FORCED_SUBMIT_AFTER_ERRORS" in result.issues


class _FakeGenerator:
    def __init__(self, output_root: Path, task: GeneratedTask) -> None:
        self.output_root = output_root
        self._task = task
        self.packaged: list[str] = []

    def generate(self, domain: str, difficulty: str, task_number: int, tags: list[str] | None = None) -> GeneratedTask:
        self._task.instance_id = f"DS_TASK_{task_number:03d}"
        self._task.task_json["instance_id"] = self._task.instance_id
        return self._task

    def package_to_disk(self, task: GeneratedTask) -> str:
        task_dir = self.output_root / task.instance_id
        (task_dir / "ground_truth").mkdir(parents=True)
        (task_dir / "task.json").write_text(json.dumps(task.task_json), "utf-8")
        (task_dir / "ground_truth" / "expected_output.json").write_text(
            json.dumps(task.ground_truth),
            "utf-8",
        )
        self.packaged.append(task.instance_id)
        return str(task_dir)


def test_generation_pipeline_rejects_before_packaging(tmp_path: Path) -> None:
    generator = _FakeGenerator(tmp_path, _task(verified=False))
    pipeline = GenerationPipeline(generator=generator, enforce_quality_gate=True)

    report = pipeline.run([GenerationSpec(domain="Finance", difficulty="Easy", count=1)])

    assert report.total_generated == 0
    assert report.total_rejected == 1
    assert not generator.packaged
    assert report.failed_tasks[0]["error"].startswith("quality_gate_rejected")
