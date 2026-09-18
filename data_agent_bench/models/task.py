from __future__ import annotations

import dataclasses
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class Domain(str, Enum):
    BIOMEDICAL = "Biomedical"
    FINANCE = "Finance"
    ECOMMERCE = "ECommerce"
    GEOSPATIAL = "Geospatial"
    GENERIC = "Generic"
    SQL = "SQL"
    SCIENTIFIC = "Scientific"
    NLP_TEXT = "NLP_Text"
    CLIMATE = "Climate"
    HR_ANALYTICS = "HR_Analytics"
    MANUFACTURING = "Manufacturing"


class Difficulty(str, Enum):
    EASY = "Easy"
    MEDIUM = "Medium"
    HARD = "Hard"


@dataclasses.dataclass(frozen=True)
class TaskMetadata:
    domain: Domain
    difficulty: Difficulty
    tags: Tuple[str, ...] = dataclasses.field(default_factory=tuple)
    primary_task_type: Optional[str] = None
    secondary_task_types: Tuple[str, ...] = dataclasses.field(default_factory=tuple)
    challenge_dimensions: Tuple[str, ...] = dataclasses.field(default_factory=tuple)
    contamination_risk: str = "low"       # "low" / "medium" / "high"
    canary_value: Optional[float] = None  # unique float embedded in dataset for contamination detection

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TaskMetadata":
        return cls(
            domain=Domain(d["domain"]),
            difficulty=Difficulty(d["difficulty"]),
            tags=tuple(d.get("tags", [])),
            primary_task_type=d.get("primary_task_type"),
            secondary_task_types=tuple(d.get("secondary_task_types", [])),
            challenge_dimensions=tuple(d.get("challenge_dimensions", [])),
            contamination_risk=d.get("contamination_risk", "low"),
            canary_value=d.get("canary_value"),
        )

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "domain": self.domain.value,
            "difficulty": self.difficulty.value,
            "tags": list(self.tags),
            "contamination_risk": self.contamination_risk,
        }
        if self.primary_task_type:
            result["primary_task_type"] = self.primary_task_type
        if self.secondary_task_types:
            result["secondary_task_types"] = list(self.secondary_task_types)
        if self.challenge_dimensions:
            result["challenge_dimensions"] = list(self.challenge_dimensions)
        if self.canary_value is not None:
            result["canary_value"] = self.canary_value
        return result


@dataclasses.dataclass(frozen=True)
class TaskContext:
    problem_statement: str
    dataset_preview: str
    expert_knowledge: str = ""
    extra: Dict[str, Any] = dataclasses.field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TaskContext":
        return cls(
            problem_statement=d["problem_statement"],
            dataset_preview=d["dataset_preview"],
            expert_knowledge=d.get("expert_knowledge", ""),
            extra={k: v for k, v in d.items()
                   if k not in ("problem_statement", "dataset_preview", "expert_knowledge")},
        )

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "problem_statement": self.problem_statement,
            "dataset_preview": self.dataset_preview,
            "expert_knowledge": self.expert_knowledge,
        }
        result.update(self.extra)
        return result


@dataclasses.dataclass(frozen=True)
class EnvironmentConfig:
    image: str
    max_steps: int
    budget: float
    timeout_seconds: int = 300
    allowed_tools: Tuple[str, ...] = dataclasses.field(
        default_factory=lambda: ("python_repl", "file_read", "web_search")
    )

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EnvironmentConfig":
        return cls(
            image=d["image"],
            max_steps=int(d["max_steps"]),
            budget=float(d["budget"]),
            timeout_seconds=int(d.get("timeout_seconds", 300)),
            allowed_tools=tuple(d.get("allowed_tools", ["python_repl", "file_read", "web_search"])),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "image": self.image,
            "max_steps": self.max_steps,
            "budget": self.budget,
            "timeout_seconds": self.timeout_seconds,
            "allowed_tools": list(self.allowed_tools),
        }


@dataclasses.dataclass(frozen=True)
class TaskInput:
    instance_id: str
    task_metadata: TaskMetadata
    context: TaskContext
    environment_config: EnvironmentConfig
    ground_truth_path: Optional[str] = None
    task_dir: Optional[str] = None   # absolute path to task folder, set by TaskRepository

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TaskInput":
        return cls(
            instance_id=d["instance_id"],
            task_metadata=TaskMetadata.from_dict(d["task_metadata"]),
            context=TaskContext.from_dict(d["context"]),
            environment_config=EnvironmentConfig.from_dict(d["environment_config"]),
            ground_truth_path=d.get("ground_truth_path"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "task_metadata": self.task_metadata.to_dict(),
            "context": self.context.to_dict(),
            "environment_config": self.environment_config.to_dict(),
            "ground_truth_path": self.ground_truth_path,
        }
