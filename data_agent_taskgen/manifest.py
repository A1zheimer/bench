from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


class ManifestValidationError(ValueError):
    pass


@dataclass
class TaskManifest:
    task_id: str
    template_id: str
    domain: str
    difficulty: str
    primary_task_type: str
    problem_statement: str
    operation: Dict[str, Any]
    dataset_builder: str = "manifest_dataset"
    secondary_task_types: List[str] = field(default_factory=list)
    challenge_dimensions: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    expert_knowledge: str = ""
    max_steps: int = 8
    budget: float = 1.0
    timeout_seconds: int = 120
    allowed_tools: List[str] = field(default_factory=lambda: ["python_repl"])
    redteam: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskManifest":
        required = {
            "task_id",
            "template_id",
            "domain",
            "difficulty",
            "primary_task_type",
            "problem_statement",
            "operation",
        }
        missing = sorted(required - set(data))
        if missing:
            raise ManifestValidationError(f"TaskManifest missing keys: {missing}")
        manifest = cls(
            task_id=str(data["task_id"]),
            template_id=str(data["template_id"]),
            domain=str(data["domain"]),
            difficulty=str(data["difficulty"]),
            primary_task_type=str(data["primary_task_type"]),
            problem_statement=str(data["problem_statement"]),
            operation=dict(data["operation"]),
            dataset_builder=str(data.get("dataset_builder", "manifest_dataset")),
            secondary_task_types=list(data.get("secondary_task_types", [])),
            challenge_dimensions=list(data.get("challenge_dimensions", [])),
            tags=list(data.get("tags", [])),
            expert_knowledge=str(data.get("expert_knowledge", "")),
            max_steps=int(data.get("max_steps", 8)),
            budget=float(data.get("budget", 1.0)),
            timeout_seconds=int(data.get("timeout_seconds", 120)),
            allowed_tools=list(data.get("allowed_tools", ["python_repl"])),
            redteam=dict(data.get("redteam", {})),
        )
        manifest.validate()
        return manifest

    @classmethod
    def from_path(cls, path: str | Path) -> "TaskManifest":
        return cls.from_dict(json.loads(Path(path).read_text("utf-8")))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "template_id": self.template_id,
            "domain": self.domain,
            "difficulty": self.difficulty,
            "primary_task_type": self.primary_task_type,
            "secondary_task_types": self.secondary_task_types,
            "challenge_dimensions": self.challenge_dimensions,
            "tags": self.tags,
            "dataset_builder": self.dataset_builder,
            "problem_statement": self.problem_statement,
            "expert_knowledge": self.expert_knowledge,
            "operation": self.operation,
            "max_steps": self.max_steps,
            "budget": self.budget,
            "timeout_seconds": self.timeout_seconds,
            "allowed_tools": self.allowed_tools,
            "redteam": self.redteam,
        }

    def validate(self) -> None:
        if not self.task_id.startswith("DS_TASK_"):
            raise ManifestValidationError("task_id must start with DS_TASK_")
        if not self.operation:
            raise ManifestValidationError("operation must not be empty")
        if self.max_steps <= 0:
            raise ManifestValidationError("max_steps must be positive")
        if self.budget <= 0:
            raise ManifestValidationError("budget must be positive")
        if self.redteam:
            required = {
                "is_redteam",
                "base_task_id",
                "attack_type",
                "attack_level",
                "gt_policy",
                "perturbation_seed",
            }
            missing = sorted(required - set(self.redteam))
            if missing:
                raise ManifestValidationError(f"redteam missing keys: {missing}")
            if self.redteam.get("gt_policy") not in {"invariant", "recomputed"}:
                raise ManifestValidationError("redteam.gt_policy must be invariant or recomputed")
