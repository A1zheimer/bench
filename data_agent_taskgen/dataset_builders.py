from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd

from .manifest import TaskManifest
from .verifiers import sha256_file


@dataclass(frozen=True)
class DatasetBuildResult:
    dataset_path: Path
    profile_path: Path
    dataset_sha256: str
    profile: Dict[str, Any]


SYNTHETIC_COLUMN_TYPES: Dict[str, str] = {
    "product_category": "categorical",
    "region": "categorical",
    "channel": "categorical",
    "total_cost": "numeric",
    "transaction_amount": "numeric",
    "discount_rate": "numeric",
    "marketing_spend": "numeric",
    "revenue": "numeric",
    "processing_time": "numeric",
    "risk_score": "numeric",
    "fraud_flag": "binary",
    "age": "numeric",
    "length_of_stay": "numeric",
    "diabetes": "binary",
    "hypertension": "binary",
    "readmitted": "binary",
    "sepal_length": "numeric",
    "sepal_width": "numeric",
    "petal_length": "numeric",
    "petal_width": "numeric",
}


class DatasetBuilderRegistry:
    """Deterministic dataset builders used by formal TaskGen.

    The registry deliberately avoids LLM-generated data. A manifest may request
    either the synthetic tabular builder or a seed CSV copy. In both cases the
    output dataset and profile are deterministic for a given manifest and seed.
    """

    def build(
        self,
        manifest: TaskManifest,
        output_dir: str | Path,
        *,
        seed: int = 20260521,
    ) -> DatasetBuildResult:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        builder_id = manifest.dataset_builder

        if builder_id == "seed_csv_copy_v1":
            return self._copy_seed_csv(manifest, output_dir)
        if builder_id in {"synthetic_tabular_v1", "manifest_dataset"}:
            return self._synthetic_tabular(manifest, output_dir, seed=seed)
        raise ValueError(f"Unknown dataset_builder: {builder_id}")

    def _copy_seed_csv(self, manifest: TaskManifest, output_dir: Path) -> DatasetBuildResult:
        source = manifest.operation.get("seed_csv_path")
        if not source:
            raise ValueError("seed_csv_copy_v1 requires operation.seed_csv_path")
        source_path = Path(source)
        if not source_path.exists():
            raise FileNotFoundError(f"Seed CSV not found: {source_path}")
        dataset_path = output_dir / f"{manifest.task_id}_dataset.csv"
        shutil.copy2(source_path, dataset_path)
        profile = profile_csv(dataset_path)
        profile.update({
            "builder_id": "seed_csv_copy_v1",
            "source_csv": str(source_path),
            "task_id": manifest.task_id,
        })
        profile_path = _write_profile(output_dir, manifest.task_id, profile)
        return DatasetBuildResult(dataset_path, profile_path, sha256_file(dataset_path), profile)

    def _synthetic_tabular(
        self,
        manifest: TaskManifest,
        output_dir: Path,
        *,
        seed: int,
    ) -> DatasetBuildResult:
        rng = np.random.default_rng(_stable_seed(seed, manifest.task_id))
        df = make_synthetic_tabular_dataset(rng)
        dataset_path = output_dir / f"{manifest.task_id}_dataset.csv"
        df.to_csv(dataset_path, index=False)
        profile = profile_dataframe(df)
        profile.update({
            "builder_id": "synthetic_tabular_v1",
            "seed": seed,
            "task_seed": _stable_seed(seed, manifest.task_id),
            "task_id": manifest.task_id,
        })
        profile_path = _write_profile(output_dir, manifest.task_id, profile)
        return DatasetBuildResult(dataset_path, profile_path, sha256_file(dataset_path), profile)


def make_synthetic_tabular_dataset(rng: np.random.Generator, n: int = 180) -> pd.DataFrame:
    categories = np.array(["Books", "Clothing", "Electronics", "Food", "Home", "Sports"])
    regions = np.array(["North", "South", "East", "West"])
    channels = np.array(["Online", "Retail", "Partner"])

    product_category = rng.choice(categories, size=n, p=[0.18, 0.16, 0.22, 0.18, 0.14, 0.12])
    region = rng.choice(regions, size=n)
    channel = rng.choice(channels, size=n, p=[0.52, 0.34, 0.14])
    category_base = {
        "Books": 26.0,
        "Clothing": 44.0,
        "Electronics": 310.0,
        "Food": 18.0,
        "Home": 82.0,
        "Sports": 63.0,
    }
    base_cost = np.array([category_base[c] for c in product_category])
    total_cost = np.maximum(1.0, base_cost + rng.normal(0, base_cost * 0.18))
    discount_rate = np.round(rng.beta(2, 12, size=n), 4)
    marketing_spend = np.maximum(10, rng.normal(160, 45, size=n))
    revenue = 85 + 2.7 * marketing_spend - 120 * discount_rate + rng.normal(0, 32, size=n)
    transaction_amount = np.maximum(2, total_cost * rng.normal(1.15, 0.2, size=n))
    processing_time = rng.lognormal(mean=2.0, sigma=0.35, size=n)

    outlier_idx = rng.choice(n, size=6, replace=False)
    processing_time[outlier_idx[:3]] *= 6
    transaction_amount[outlier_idx[3:]] *= 5

    risk_score = np.clip(rng.beta(2.5, 6.0, size=n) + (transaction_amount > 300) * 0.18, 0, 1)
    fraud_flag = (risk_score + rng.normal(0, 0.08, size=n) > 0.56).astype(int)

    age = rng.integers(24, 84, size=n)
    diabetes = rng.binomial(1, np.clip((age - 20) / 120, 0.08, 0.52))
    hypertension = rng.binomial(1, np.clip((age - 10) / 110 + diabetes * 0.12, 0.10, 0.70))
    readmit_prob = np.clip(0.08 + 0.08 * diabetes + 0.12 * hypertension + 0.01 * (age > 70), 0, 0.7)
    readmitted = rng.binomial(1, readmit_prob)
    length_of_stay = np.maximum(
        1,
        rng.poisson(3.2 + diabetes * 0.9 + hypertension * 0.7 + readmitted * 1.4, size=n),
    ).astype(float)

    sepal_length = rng.normal(5.9, 0.75, size=n)
    sepal_width = rng.normal(3.05, 0.32, size=n)
    petal_length = 1.35 * sepal_length - 3.1 + rng.normal(0, 0.34, size=n)
    petal_width = 0.38 * petal_length + rng.normal(0, 0.16, size=n)

    return pd.DataFrame({
        "product_category": product_category,
        "region": region,
        "channel": channel,
        "total_cost": np.round(total_cost, 2),
        "transaction_amount": np.round(transaction_amount, 2),
        "discount_rate": discount_rate,
        "marketing_spend": np.round(marketing_spend, 2),
        "revenue": np.round(revenue, 2),
        "processing_time": np.round(processing_time, 3),
        "risk_score": np.round(risk_score, 4),
        "fraud_flag": fraud_flag,
        "age": age,
        "length_of_stay": length_of_stay,
        "diabetes": diabetes,
        "hypertension": hypertension,
        "readmitted": readmitted,
        "sepal_length": np.round(sepal_length, 3),
        "sepal_width": np.round(sepal_width, 3),
        "petal_length": np.round(petal_length, 3),
        "petal_width": np.round(petal_width, 3),
    })


def profile_csv(path: str | Path) -> Dict[str, Any]:
    return profile_dataframe(pd.read_csv(path))


def profile_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
    columns = {}
    for col in df.columns:
        columns[col] = {
            "dtype": str(df[col].dtype),
            "semantic_type": _semantic_type(df[col]),
            "missing_count": int(df[col].isna().sum()),
            "unique_count": int(df[col].nunique(dropna=True)),
            "examples": [str(v) for v in df[col].dropna().head(3).tolist()],
        }
    return {
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "columns": columns,
        "numeric_columns": [col for col, spec in columns.items() if spec["semantic_type"] == "numeric"],
        "categorical_columns": [col for col, spec in columns.items() if spec["semantic_type"] == "categorical"],
        "binary_columns": [col for col, spec in columns.items() if spec["semantic_type"] == "binary"],
    }


def _semantic_type(series: pd.Series) -> str:
    values = set(series.dropna().unique().tolist())
    if values and values.issubset({0, 1, True, False}):
        return "binary"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    return "categorical"


def _write_profile(output_dir: Path, task_id: str, profile: Dict[str, Any]) -> Path:
    path = output_dir / f"{task_id}_dataset_profile.json"
    path.write_text(json.dumps(profile, indent=2, ensure_ascii=False), "utf-8")
    return path


def _stable_seed(base_seed: int, key: str) -> int:
    digest = hashlib.sha256(f"{base_seed}:{key}".encode("utf-8")).hexdigest()
    return (base_seed + int(digest[:8], 16)) % (2**32)
