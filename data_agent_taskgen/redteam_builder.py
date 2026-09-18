from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from .dataset_builders import profile_dataframe, sha256_file
from .manifest import TaskManifest
from .manifest_sampler import problem_statement_for
from .packager import PackagedTask, TaskPackager
from .redteam import RedteamSpec, assert_invariant_gt


ATTACK_TYPES = ["schema_obfuscation", "distractor_columns", "dirty_data"]


@dataclass(frozen=True)
class RedteamBuildResult:
    packaged_tasks: List[PackagedTask]
    report_rows: List[Dict[str, Any]]


class RedteamBuilder:
    def __init__(
        self,
        clean_tasks_dir: str | Path,
        output_dir: str | Path,
        *,
        seed: int = 20260521,
    ) -> None:
        self.clean_tasks_dir = Path(clean_tasks_dir)
        self.output_dir = Path(output_dir)
        self.seed = seed
        self.packager = TaskPackager(self.output_dir)

    def build(self, *, max_base_tasks: int = 5) -> RedteamBuildResult:
        base_dirs = self._select_base_tasks(max_base_tasks)
        packaged: List[PackagedTask] = []
        rows: List[Dict[str, Any]] = []
        tmp_root = self.output_dir.parent / f".{self.output_dir.name}_build_cache"
        tmp_root.mkdir(parents=True, exist_ok=True)

        for base_idx, base_dir in enumerate(base_dirs, start=1):
            manifest = TaskManifest.from_path(base_dir / "task_manifest.json")
            clean_gt = json.loads((base_dir / "ground_truth" / "expected_output.json").read_text("utf-8"))
            clean_df = pd.read_csv(base_dir / "data" / "dataset.csv")
            for attack_idx, attack_type in enumerate(ATTACK_TYPES, start=1):
                task_id = f"DS_TASK_{900000 + base_idx * 10 + attack_idx:06d}"
                red_manifest, red_df, gt_policy = self._perturb(
                    manifest,
                    clean_df,
                    task_id=task_id,
                    attack_type=attack_type,
                    attack_idx=attack_idx,
                )
                dataset_path = tmp_root / f"{task_id}_dataset.csv"
                profile_path = tmp_root / f"{task_id}_dataset_profile.json"
                red_df.to_csv(dataset_path, index=False)
                profile = profile_dataframe(red_df)
                profile.update({
                    "builder_id": f"redteam_{attack_type}_v1",
                    "base_task_id": manifest.task_id,
                    "attack_type": attack_type,
                    "perturbation_seed": self.seed,
                    "dataset_sha256": sha256_file(dataset_path),
                })
                profile_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False), "utf-8")

                task = self.packager.package(
                    red_manifest,
                    dataset_path,
                    dataset_profile_path=profile_path,
                )
                if gt_policy == "invariant":
                    assert_invariant_gt(clean_gt, task.expected_output)
                packaged.append(task)
                rows.append({
                    "task_id": task.task_id,
                    "base_task_id": manifest.task_id,
                    "template_id": manifest.template_id,
                    "attack_type": attack_type,
                    "gt_policy": gt_policy,
                    "replay": "PASS",
                    "key_count": len(task.expected_output.get("key_values", {})),
                })
        return RedteamBuildResult(packaged, rows)

    def _select_base_tasks(self, max_base_tasks: int) -> List[Path]:
        task_dirs = [
            p for p in sorted(self.clean_tasks_dir.iterdir())
            if p.is_dir() and (p / "task_manifest.json").exists()
        ]
        by_template: Dict[str, Path] = {}
        for path in task_dirs:
            manifest = TaskManifest.from_path(path / "task_manifest.json")
            by_template.setdefault(manifest.template_id, path)
        selected = list(by_template.values())[:max_base_tasks]
        if len(selected) < max_base_tasks:
            for path in task_dirs:
                if path not in selected:
                    selected.append(path)
                if len(selected) >= max_base_tasks:
                    break
        return selected

    def _perturb(
        self,
        manifest: TaskManifest,
        df: pd.DataFrame,
        *,
        task_id: str,
        attack_type: str,
        attack_idx: int,
    ) -> tuple[TaskManifest, pd.DataFrame, str]:
        rng = np.random.default_rng(self.seed + attack_idx + int(task_id.rsplit("_", 1)[-1]))
        data = manifest.to_dict()
        data["task_id"] = task_id
        data["redteam"] = RedteamSpec.from_dict({
            "base_task_id": manifest.task_id,
            "attack_type": attack_type,
            "attack_level": "L1",
            "gt_policy": "recomputed" if attack_type == "dirty_data" else "invariant",
            "perturbation_seed": self.seed,
        }).to_manifest_redteam()
        data["tags"] = list(dict.fromkeys([*data.get("tags", []), "redteam", attack_type]))
        data["challenge_dimensions"] = list(dict.fromkeys([
            *data.get("challenge_dimensions", []),
            attack_type,
        ]))

        if attack_type == "schema_obfuscation":
            mapping = {col: f"col_{idx:03d}" for idx, col in enumerate(df.columns, start=1)}
            perturbed = df.rename(columns=mapping)
            data["operation"] = _rename_operation_columns(manifest.template_id, data["operation"], mapping)
            data["problem_statement"] = problem_statement_for(manifest.template_id, data["operation"])
            data["expert_knowledge"] = (
                f"Columns have been systematically obfuscated from base task {manifest.task_id}. "
                "Use the column names shown in the prompt and dataset, not domain assumptions."
            )
            return TaskManifest.from_dict(data), perturbed, "invariant"

        if attack_type == "distractor_columns":
            perturbed = df.copy()
            perturbed["distractor_noise"] = rng.normal(0, 1, size=len(perturbed)).round(5)
            perturbed["distractor_group"] = rng.choice(["alpha", "beta", "gamma"], size=len(perturbed))
            perturbed["pseudo_target"] = rng.integers(0, 2, size=len(perturbed))
            data["problem_statement"] = (
                manifest.problem_statement
                + " The dataset may include unrelated distractor columns; ignore columns not required by the task."
            )
            return TaskManifest.from_dict(data), perturbed, "invariant"

        if attack_type == "dirty_data":
            perturbed = _dirty_data(df.copy(), rng)
            data["problem_statement"] = (
                manifest.problem_statement
                + " The dataset may contain missing values, outliers, or flipped binary entries; follow the task definition exactly."
            )
            return TaskManifest.from_dict(data), perturbed, "recomputed"

        raise ValueError(f"Unsupported attack_type: {attack_type}")


def _rename_operation_columns(template_id: str, op: Dict[str, Any], mapping: Dict[str, str]) -> Dict[str, Any]:
    renamed = json.loads(json.dumps(op))
    for key in (
        "value_column",
        "filter_column",
        "groupby",
        "x_column",
        "y_column",
        "row_column",
        "column_column",
        "outcome_column",
        "target_column",
    ):
        if renamed.get(key) in mapping:
            renamed[key] = mapping[renamed[key]]
    for key in ("columns", "feature_columns"):
        if key in renamed:
            renamed[key] = [mapping.get(col, col) for col in renamed[key]]
    if template_id == "iqr_outlier_count_v1" and "output_keys" in renamed:
        renamed["output_keys"] = {
            mapping.get(col, col): output_key
            for col, output_key in renamed["output_keys"].items()
        }
    return renamed


def _dirty_data(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    binary_cols = [
        col for col in df.columns
        if set(df[col].dropna().unique().tolist()).issubset({0, 1})
    ]
    for col in binary_cols[:3]:
        idx = rng.choice(len(df), size=max(2, len(df) // 35), replace=False)
        df.loc[idx, col] = 1 - df.loc[idx, col].astype(int)

    numeric_cols = [
        col for col in df.select_dtypes(include="number").columns
        if col not in binary_cols
    ]
    for col in numeric_cols[:5]:
        idx = rng.choice(len(df), size=max(2, len(df) // 45), replace=False)
        std = float(df[col].std() or 1.0)
        df.loc[idx, col] = df.loc[idx, col] + rng.normal(5 * std, 1.5 * std, size=len(idx))
        miss_idx = rng.choice(len(df), size=max(1, len(df) // 80), replace=False)
        df.loc[miss_idx, col] = np.nan
    return df
