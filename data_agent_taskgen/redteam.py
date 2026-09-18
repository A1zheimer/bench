from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


class RedteamMetadataError(ValueError):
    pass


@dataclass(frozen=True)
class RedteamSpec:
    base_task_id: str
    attack_type: str
    attack_level: str
    gt_policy: str
    perturbation_seed: int
    expected_invariant: str = "same_key_values"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RedteamSpec":
        required = {
            "base_task_id",
            "attack_type",
            "attack_level",
            "gt_policy",
            "perturbation_seed",
        }
        missing = sorted(required - set(data))
        if missing:
            raise RedteamMetadataError(f"redteam metadata missing keys: {missing}")
        spec = cls(
            base_task_id=str(data["base_task_id"]),
            attack_type=str(data["attack_type"]),
            attack_level=str(data["attack_level"]),
            gt_policy=str(data["gt_policy"]),
            perturbation_seed=int(data["perturbation_seed"]),
            expected_invariant=str(data.get("expected_invariant", "same_key_values")),
        )
        spec.validate()
        return spec

    def validate(self) -> None:
        if self.gt_policy not in {"invariant", "recomputed"}:
            raise RedteamMetadataError("gt_policy must be invariant or recomputed")
        if not self.base_task_id.startswith("DS_TASK_"):
            raise RedteamMetadataError("base_task_id must start with DS_TASK_")

    def to_manifest_redteam(self) -> Dict[str, Any]:
        return {
            "is_redteam": True,
            "base_task_id": self.base_task_id,
            "attack_type": self.attack_type,
            "attack_level": self.attack_level,
            "gt_policy": self.gt_policy,
            "perturbation_seed": self.perturbation_seed,
            "expected_invariant": self.expected_invariant,
        }


def assert_invariant_gt(clean_gt: Dict[str, Any], perturbed_gt: Dict[str, Any]) -> None:
    if clean_gt.get("key_values") != perturbed_gt.get("key_values"):
        raise RedteamMetadataError(
            "Invariant redteam GT mismatch: "
            f"clean={clean_gt.get('key_values')} perturbed={perturbed_gt.get('key_values')}"
        )
