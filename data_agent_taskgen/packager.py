from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from data_agent_bench.repository.provenance import is_verified_ground_truth
from data_agent_bench.repository.schema_validator import SchemaValidator

from .manifest import TaskManifest
from .verifiers import VerifierRegistry


@dataclass
class PackagedTask:
    task_id: str
    task_dir: Path
    task_json: Dict[str, Any]
    expected_output: Dict[str, Any]


class TaskPackager:
    def __init__(self, output_root: str | Path, registry: VerifierRegistry | None = None) -> None:
        self.output_root = Path(output_root)
        self.registry = registry or VerifierRegistry()

    def package(
        self,
        manifest: TaskManifest | Dict[str, Any],
        dataset_path: str | Path,
        *,
        dataset_profile_path: str | Path | None = None,
    ) -> PackagedTask:
        if isinstance(manifest, dict):
            manifest = TaskManifest.from_dict(manifest)

        source_dataset = Path(dataset_path)
        if not source_dataset.exists():
            raise FileNotFoundError(f"Dataset not found: {source_dataset}")

        task_dir = self.output_root / manifest.task_id
        data_dir = task_dir / "data"
        gt_dir = task_dir / "ground_truth"
        data_dir.mkdir(parents=True, exist_ok=True)
        gt_dir.mkdir(exist_ok=True)

        packaged_dataset = data_dir / "dataset.csv"
        shutil.copy2(source_dataset, packaged_dataset)
        if dataset_profile_path is not None:
            profile_source = Path(dataset_profile_path)
            if profile_source.exists():
                shutil.copy2(profile_source, data_dir / "dataset_profile.json")

        gt = self.registry.verify(packaged_dataset, manifest).to_expected_output()
        task_json = self._task_json(manifest)

        SchemaValidator.validate_task_input(task_json)
        SchemaValidator.validate_ground_truth(gt)
        if not is_verified_ground_truth(gt):
            raise ValueError("Packager produced expected_output without verified provenance")

        (task_dir / "task_manifest.json").write_text(
            json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False),
            "utf-8",
        )
        (task_dir / "task.json").write_text(
            json.dumps(task_json, indent=2, ensure_ascii=False),
            "utf-8",
        )
        (gt_dir / "expected_output.json").write_text(
            json.dumps(gt, indent=2, ensure_ascii=False),
            "utf-8",
        )
        (task_dir / "generation_meta.json").write_text(
            json.dumps(
                {
                    "generator": "data_agent_taskgen:manifest_packager",
                    "verified": True,
                    "verifier_id": gt["verifier_id"],
                    "dataset_sha256": gt["dataset_sha256"],
                    "source_set": "verified",
                },
                indent=2,
                ensure_ascii=False,
            ),
            "utf-8",
        )

        self.replay_verify(task_dir)
        return PackagedTask(
            task_id=manifest.task_id,
            task_dir=task_dir,
            task_json=task_json,
            expected_output=gt,
        )

    def replay_verify(self, task_dir: str | Path) -> Dict[str, Any]:
        task_dir = Path(task_dir)
        manifest = TaskManifest.from_path(task_dir / "task_manifest.json")
        dataset_path = task_dir / "data" / "dataset.csv"
        expected_path = task_dir / "ground_truth" / "expected_output.json"
        expected = json.loads(expected_path.read_text("utf-8"))
        replayed = self.registry.verify(dataset_path, manifest).to_expected_output()

        if expected.get("dataset_sha256") != replayed.get("dataset_sha256"):
            raise ValueError("dataset_sha256 mismatch during verifier replay")
        if expected.get("verifier_id") != replayed.get("verifier_id"):
            raise ValueError("verifier_id mismatch during verifier replay")
        if expected.get("key_values") != replayed.get("key_values"):
            raise ValueError(
                "key_values mismatch during verifier replay: "
                f"expected={expected.get('key_values')} replayed={replayed.get('key_values')}"
            )
        return replayed

    @staticmethod
    def _task_json(manifest: TaskManifest) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {
            "domain": manifest.domain,
            "difficulty": manifest.difficulty,
            "tags": manifest.tags,
            "primary_task_type": manifest.primary_task_type,
            "secondary_task_types": manifest.secondary_task_types,
            "challenge_dimensions": manifest.challenge_dimensions,
            "generation_quality": "verified",
        }
        if manifest.redteam:
            metadata["redteam"] = manifest.redteam
        return {
            "instance_id": manifest.task_id,
            "task_metadata": metadata,
            "context": {
                "problem_statement": manifest.problem_statement,
                "dataset_preview": "data/dataset.csv",
                "expert_knowledge": manifest.expert_knowledge,
            },
            "environment_config": {
                "image": "ds-agent-v1:latest",
                "max_steps": manifest.max_steps,
                "budget": manifest.budget,
                "timeout_seconds": manifest.timeout_seconds,
                "allowed_tools": manifest.allowed_tools,
            },
            "max_steps": manifest.max_steps,
        }
