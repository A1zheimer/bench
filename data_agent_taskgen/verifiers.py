from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import accuracy_score, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

from .manifest import TaskManifest


@dataclass
class VerifiedGroundTruth:
    execution_result: str
    key_values: Dict[str, float]
    key_aliases: Dict[str, List[str]]
    required_keywords: List[str]
    formula: str
    verifier_id: str
    verifier_version: str = "1.0"
    dataset_sha256: str = ""
    computed_at: str = ""
    verified: bool = True
    include_canary_policy: str = "include_all_rows_unless_prompt_excludes_outliers"
    components: Dict[str, Any] = field(default_factory=dict)

    def to_expected_output(self) -> Dict[str, Any]:
        return {
            "execution_result": self.execution_result,
            "key_values": self.key_values,
            "key_aliases": self.key_aliases,
            "required_keywords": self.required_keywords,
            "formula": self.formula,
            "verifier_id": self.verifier_id,
            "verifier_version": self.verifier_version,
            "dataset_sha256": self.dataset_sha256,
            "computed_at": self.computed_at,
            "verified": self.verified,
            "include_canary_policy": self.include_canary_policy,
            **({"components": self.components} if self.components else {}),
        }


VerifierFn = Callable[[Path, TaskManifest], VerifiedGroundTruth]


class VerifierRegistry:
    def __init__(self) -> None:
        self._verifiers: Dict[str, VerifierFn] = {
            "filtered_mean_v1": verify_filtered_mean,
            "groupby_aggregation_v1": verify_groupby_aggregation,
            "correlation_pair_v1": verify_correlation_pair,
            "iqr_outlier_count_v1": verify_iqr_outlier_count,
            "crosstab_prevalence_v1": verify_crosstab_prevalence,
            "model_eval_metric_v1": verify_model_eval_metric,
        }

    def get(self, verifier_id: str) -> VerifierFn:
        if verifier_id not in self._verifiers:
            raise KeyError(f"Unknown verifier_id/template_id: {verifier_id}")
        return self._verifiers[verifier_id]

    def verify(self, dataset_path: str | Path, manifest: TaskManifest) -> VerifiedGroundTruth:
        verifier = self.get(manifest.template_id)
        result = verifier(Path(dataset_path), manifest)
        result.dataset_sha256 = sha256_file(dataset_path)
        result.computed_at = datetime.now(timezone.utc).isoformat()
        return result


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_filtered_mean(dataset_path: Path, manifest: TaskManifest) -> VerifiedGroundTruth:
    op = manifest.operation
    df = pd.read_csv(dataset_path)
    value_col = _require_column(df, op["value_column"])
    metric = op.get("metric", "mean")
    filtered = _apply_filter(df, op)
    if metric == "mean":
        value = float(filtered[value_col].mean())
        formula = f"mean({value_col} where {_filter_formula(op)})"
    elif metric == "sum":
        value = float(filtered[value_col].sum())
        formula = f"sum({value_col} where {_filter_formula(op)})"
    elif metric == "count":
        value = float(len(filtered))
        formula = f"count(rows where {_filter_formula(op)})"
    else:
        raise ValueError(f"Unsupported filtered metric: {metric}")
    key = op.get("output_key") or f"{metric}_{value_col}"
    return _gt(
        manifest,
        {key: value},
        formula,
        aliases={key: [key.replace("_", " ")]},
        keywords=[metric, value_col],
    )


def verify_groupby_aggregation(dataset_path: Path, manifest: TaskManifest) -> VerifiedGroundTruth:
    op = manifest.operation
    df = pd.read_csv(dataset_path)
    group_col = _require_column(df, op["groupby"])
    value_col = _require_column(df, op["value_column"])
    agg = op.get("agg", "sum")
    grouped = getattr(df.groupby(group_col)[value_col], agg)().sort_index()
    output_keys = op.get("output_keys") or {}
    prefix = op.get("output_prefix", f"{agg}_{value_col}")
    key_values: Dict[str, float] = {}
    key_aliases: Dict[str, List[str]] = {}
    for group_value, metric_value in grouped.items():
        key = output_keys.get(str(group_value)) or _safe_key(prefix, str(group_value))
        key_values[key] = float(metric_value)
        key_aliases[key] = [key.replace("_", " "), str(group_value), f"{agg} {group_value}"]
    return _gt(
        manifest,
        key_values,
        f"groupby({group_col}).{agg}({value_col})",
        aliases=key_aliases,
        keywords=[group_col, value_col, agg],
    )


def verify_correlation_pair(dataset_path: Path, manifest: TaskManifest) -> VerifiedGroundTruth:
    op = manifest.operation
    df = pd.read_csv(dataset_path)
    x = _require_column(df, op["x_column"])
    y = _require_column(df, op["y_column"])
    method = op.get("method", "pearson")
    value = float(df[x].corr(df[y], method=method))
    key = op.get("output_key") or f"corr_{x}_{y}"
    return _gt(
        manifest,
        {key: value},
        f"{method}_corr({x}, {y})",
        aliases={key: [key.replace("_", " "), f"correlation {x} {y}"]},
        keywords=[method, "correlation"],
    )


def verify_iqr_outlier_count(dataset_path: Path, manifest: TaskManifest) -> VerifiedGroundTruth:
    op = manifest.operation
    df = pd.read_csv(dataset_path)
    columns = op.get("columns") or list(df.select_dtypes(include="number").columns)
    output_keys = op.get("output_keys") or {}
    key_values: Dict[str, float] = {}
    key_aliases: Dict[str, List[str]] = {}
    total = 0
    for col in columns:
        col = _require_column(df, col)
        count = _iqr_outlier_count(df[col])
        total += count
        key = output_keys.get(col) or _safe_key("outlier_count", col)
        key_values[key] = float(count)
        key_aliases[key] = [key.replace("_", " "), f"{col} outliers"]
    total_key = op.get("total_output_key", "total_outlier_count")
    key_values[total_key] = float(total)
    key_aliases[total_key] = ["total outlier count", "total outliers"]
    return _gt(
        manifest,
        key_values,
        "1.5*IQR outlier count",
        aliases=key_aliases,
        keywords=["IQR", "outlier"],
    )


def verify_crosstab_prevalence(dataset_path: Path, manifest: TaskManifest) -> VerifiedGroundTruth:
    op = manifest.operation
    df = pd.read_csv(dataset_path)
    row_col = _require_column(df, op["row_column"])
    col_col = _require_column(df, op["column_column"])
    row_value = op["row_value"]
    col_value = op["column_value"]
    mask = (df[row_col] == row_value) & (df[col_col] == col_value)
    count = int(mask.sum())
    key_values = {
        op.get("count_key", f"{row_col}_{col_col}_count"): float(count),
        op.get("prevalence_key", f"{row_col}_{col_col}_prevalence"): float(count / len(df)),
    }
    if op.get("outcome_column"):
        outcome_col = _require_column(df, op["outcome_column"])
        key_values[op.get("outcome_rate_key", f"{outcome_col}_rate")] = float(df.loc[mask, outcome_col].mean())
    aliases = {key: [key.replace("_", " ")] for key in key_values}
    return _gt(
        manifest,
        key_values,
        f"crosstab({row_col}, {col_col}) with {row_col}={row_value}, {col_col}={col_value}",
        aliases=aliases,
        keywords=["crosstab", "prevalence"],
    )


def verify_model_eval_metric(dataset_path: Path, manifest: TaskManifest) -> VerifiedGroundTruth:
    op = manifest.operation
    df = pd.read_csv(dataset_path)
    target = _require_column(df, op["target_column"])
    features = [_require_column(df, col) for col in op["feature_columns"]]
    data = df[features + [target]].dropna()
    x = pd.get_dummies(data[features], drop_first=True)
    y = data[target]
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=float(op.get("test_size", 0.3)),
        random_state=int(op.get("random_state", 42)),
    )
    if _is_classification_target(y):
        model = LogisticRegression(max_iter=1000)
        model.fit(x_train, y_train)
        pred = model.predict(x_test)
        key_values = {"accuracy": float(accuracy_score(y_test, pred))}
        formula = f"logistic_regression_accuracy(target={target})"
    else:
        model = LinearRegression()
        model.fit(x_train, y_train)
        pred = model.predict(x_test)
        key_values = {
            "rmse": float(mean_squared_error(y_test, pred) ** 0.5),
            "r_squared": float(r2_score(y_test, pred)),
        }
        formula = f"linear_regression_rmse_r2(target={target})"
    aliases = {key: [key.replace("_", " ")] for key in key_values}
    return _gt(manifest, key_values, formula, aliases=aliases, keywords=["model", "evaluation"])


def _gt(
    manifest: TaskManifest,
    key_values: Dict[str, float],
    formula: str,
    *,
    aliases: Dict[str, List[str]],
    keywords: List[str],
) -> VerifiedGroundTruth:
    return VerifiedGroundTruth(
        execution_result=f"Verified by {manifest.template_id}: {formula}",
        key_values={key: _json_float(value) for key, value in key_values.items()},
        key_aliases=aliases,
        required_keywords=keywords,
        formula=formula,
        verifier_id=manifest.template_id,
    )


def _apply_filter(df: pd.DataFrame, op: Dict[str, Any]) -> pd.DataFrame:
    if "filter_column" not in op:
        return df
    col = _require_column(df, op["filter_column"])
    value = op.get("filter_value")
    comparator = op.get("filter_op", "eq")
    if comparator == "eq":
        return df[df[col] == value]
    if comparator == "ne":
        return df[df[col] != value]
    if comparator == "gt":
        return df[df[col] > value]
    if comparator == "ge":
        return df[df[col] >= value]
    if comparator == "lt":
        return df[df[col] < value]
    if comparator == "le":
        return df[df[col] <= value]
    raise ValueError(f"Unsupported filter_op: {comparator}")


def _filter_formula(op: Dict[str, Any]) -> str:
    if "filter_column" not in op:
        return "all rows"
    return f"{op['filter_column']} {op.get('filter_op', 'eq')} {op.get('filter_value')}"


def _require_column(df: pd.DataFrame, column: str) -> str:
    if column not in df.columns:
        raise ValueError(f"Column not found in dataset: {column}")
    return column


def _iqr_outlier_count(series: pd.Series) -> int:
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    lo = q1 - 1.5 * iqr
    hi = q3 + 1.5 * iqr
    return int(((series < lo) | (series > hi)).sum())


def _safe_key(*parts: str) -> str:
    raw = "_".join(str(part).strip().lower() for part in parts)
    return "".join(ch if ch.isalnum() else "_" for ch in raw).strip("_")


def _json_float(value: Any) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("GT contains non-finite numeric value")
    return value


def _is_classification_target(y: pd.Series) -> bool:
    if y.dtype == object or str(y.dtype).startswith("category"):
        return True
    unique = y.dropna().unique()
    return len(unique) <= 10 and set(unique).issubset({0, 1})
