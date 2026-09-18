from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class TrainRecord:
    """A normalized training sample emitted from generation pipeline."""

    task_id: str
    instruction: str
    response: str
    quality_tier: str = "silver"  # gold | silver | reject
    verified: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    @classmethod
    def from_generated_task(cls, task: Any, task_path: Optional[str] = None) -> "TrainRecord":
        ctx = task.task_json.get("context", {}) if isinstance(task.task_json, dict) else {}
        problem = ctx.get("problem_statement", "")
        expert = ctx.get("expert_knowledge", "")
        dataset_preview = ctx.get("dataset_preview", "")

        instruction_parts = [f"## Problem\n{problem}"]
        if expert:
            instruction_parts.append(f"## Domain Knowledge\n{expert}")
        if dataset_preview:
            instruction_parts.append(
                f"## Dataset\nThe dataset is available at `{dataset_preview}`. "
                "Load it with pandas before starting your analysis."
            )

        response_parts = [f"```python\n{(task.solution_code or '').strip()}\n```"]
        key_values = (task.ground_truth or {}).get("key_values", {}) if isinstance(task.ground_truth, dict) else {}
        if key_values:
            kv = "\n".join(f"- **{k}**: {v}" for k, v in key_values.items())
            response_parts.append(f"\n**Results:**\n{kv}")

        quality_tier = "gold" if bool(getattr(task, "verified", False)) else "reject"

        return cls(
            task_id=str(getattr(task, "instance_id", "")),
            instruction="\n\n".join(instruction_parts),
            response="\n".join(response_parts),
            quality_tier=quality_tier,
            verified=bool(getattr(task, "verified", False)),
            metadata={
                "task_path": task_path or "",
                "canary_value": getattr(task, "canary_value", None),
                "trace_steps": len(getattr(task, "generation_trace", []) or []),
            },
        )


@dataclass
class TrainResult:
    """Training batch execution result."""

    success: bool
    consumed: int
    latency_ms: float
    loss: Optional[float] = None
    error: str = ""
