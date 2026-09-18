from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

from .dataset_builders import SYNTHETIC_COLUMN_TYPES
from .manifest import TaskManifest


TEMPLATE_ORDER = [
    "filtered_mean_v1",
    "groupby_aggregation_v1",
    "correlation_pair_v1",
    "iqr_outlier_count_v1",
    "crosstab_prevalence_v1",
    "model_eval_metric_v1",
]


@dataclass(frozen=True)
class SampledManifestBatch:
    manifests: List[TaskManifest]

    @property
    def template_distribution(self) -> Dict[str, int]:
        return dict(Counter(m.template_id for m in self.manifests))

    @property
    def domain_distribution(self) -> Dict[str, int]:
        return dict(Counter(m.domain for m in self.manifests))


class ManifestSampler:
    def __init__(self, *, seed: int = 20260521) -> None:
        self.seed = seed

    def sample_core(
        self,
        *,
        count_per_template: int = 2,
        task_id_start: int = 1,
    ) -> SampledManifestBatch:
        manifests: List[TaskManifest] = []
        seq = task_id_start
        for template_id in TEMPLATE_ORDER:
            for variant_idx in range(count_per_template):
                spec = self._spec_for(template_id, variant_idx, seq)
                self._validate_operation_columns(template_id, spec["operation"])
                manifests.append(TaskManifest.from_dict(spec))
                seq += 1
        return SampledManifestBatch(manifests)

    def _spec_for(self, template_id: str, variant_idx: int, seq: int) -> Dict[str, Any]:
        task_id = f"DS_TASK_{seq:06d}"
        variant = variant_idx % 2
        op = operation_for(template_id, variant)
        return {
            "task_id": task_id,
            "template_id": template_id,
            "domain": domain_for(template_id, variant),
            "difficulty": difficulty_for(template_id, variant),
            "primary_task_type": task_type_for(template_id),
            "secondary_task_types": secondary_types_for(template_id),
            "challenge_dimensions": challenge_dimensions_for(template_id, variant),
            "tags": tags_for(template_id, variant),
            "dataset_builder": "synthetic_tabular_v1",
            "problem_statement": problem_statement_for(template_id, op),
            "expert_knowledge": expert_knowledge_for(template_id),
            "operation": op,
            "max_steps": 8 if template_id != "model_eval_metric_v1" else 10,
            "budget": 1.0,
            "timeout_seconds": 120,
            "allowed_tools": ["python_repl"],
        }

    def _validate_operation_columns(self, template_id: str, op: Dict[str, Any]) -> None:
        if template_id == "filtered_mean_v1":
            _require_type(op["value_column"], {"numeric", "binary"})
            if "filter_column" in op:
                _require_known(op["filter_column"])
            return
        if template_id == "groupby_aggregation_v1":
            _require_type(op["groupby"], {"categorical", "binary"})
            _require_type(op["value_column"], {"numeric", "binary"})
            return
        if template_id == "correlation_pair_v1":
            _require_type(op["x_column"], {"numeric"})
            _require_type(op["y_column"], {"numeric"})
            return
        if template_id == "iqr_outlier_count_v1":
            for col in op["columns"]:
                _require_type(col, {"numeric"})
            return
        if template_id == "crosstab_prevalence_v1":
            _require_type(op["row_column"], {"categorical", "binary"})
            _require_type(op["column_column"], {"categorical", "binary"})
            if op.get("outcome_column"):
                _require_type(op["outcome_column"], {"numeric", "binary"})
            return
        if template_id == "model_eval_metric_v1":
            _require_known(op["target_column"])
            for col in op["feature_columns"]:
                _require_known(col)
            return
        raise ValueError(f"Unsupported template_id: {template_id}")


def operation_for(template_id: str, variant: int) -> Dict[str, Any]:
    if template_id == "filtered_mean_v1":
        if variant == 0:
            return {
                "value_column": "total_cost",
                "metric": "mean",
                "filter_column": "product_category",
                "filter_op": "eq",
                "filter_value": "Books",
                "output_key": "mean_total_cost_books",
            }
        return {
            "value_column": "transaction_amount",
            "metric": "mean",
            "filter_column": "fraud_flag",
            "filter_op": "eq",
            "filter_value": 1,
            "output_key": "mean_transaction_amount_flagged",
        }

    if template_id == "groupby_aggregation_v1":
        if variant == 0:
            return {
                "groupby": "product_category",
                "value_column": "total_cost",
                "agg": "sum",
                "output_prefix": "total_revenue",
                "output_keys": {
                    "Books": "total_revenue_books",
                    "Clothing": "total_revenue_clothing",
                    "Electronics": "total_revenue_electronics",
                    "Food": "total_revenue_food",
                    "Home": "total_revenue_home",
                    "Sports": "total_revenue_sports",
                },
            }
        return {
            "groupby": "region",
            "value_column": "transaction_amount",
            "agg": "mean",
            "output_prefix": "mean_transaction_amount",
            "output_keys": {
                "East": "mean_transaction_amount_east",
                "North": "mean_transaction_amount_north",
                "South": "mean_transaction_amount_south",
                "West": "mean_transaction_amount_west",
            },
        }

    if template_id == "correlation_pair_v1":
        if variant == 0:
            return {
                "x_column": "sepal_length",
                "y_column": "petal_length",
                "method": "pearson",
                "output_key": "pearson_corr_sepal_petal_length",
            }
        return {
            "x_column": "marketing_spend",
            "y_column": "revenue",
            "method": "pearson",
            "output_key": "pearson_corr_marketing_revenue",
        }

    if template_id == "iqr_outlier_count_v1":
        if variant == 0:
            return {
                "columns": ["processing_time", "transaction_amount"],
                "output_keys": {
                    "processing_time": "outlier_count_processing_time",
                    "transaction_amount": "outlier_count_transaction_amount",
                },
                "total_output_key": "total_outlier_count",
            }
        return {
            "columns": ["total_cost", "revenue"],
            "output_keys": {
                "total_cost": "outlier_count_total_cost",
                "revenue": "outlier_count_revenue",
            },
            "total_output_key": "total_outlier_count",
        }

    if template_id == "crosstab_prevalence_v1":
        if variant == 0:
            return {
                "row_column": "diabetes",
                "column_column": "hypertension",
                "row_value": 1,
                "column_value": 1,
                "outcome_column": "readmitted",
                "count_key": "diabetes_hypertension_count",
                "prevalence_key": "diabetes_hypertension_prevalence",
                "outcome_rate_key": "diabetes_hypertension_readmission_rate",
            }
        return {
            "row_column": "product_category",
            "column_column": "channel",
            "row_value": "Electronics",
            "column_value": "Online",
            "outcome_column": "fraud_flag",
            "count_key": "electronics_online_count",
            "prevalence_key": "electronics_online_prevalence",
            "outcome_rate_key": "electronics_online_fraud_rate",
        }

    if template_id == "model_eval_metric_v1":
        if variant == 0:
            return {
                "target_column": "readmitted",
                "feature_columns": ["age", "length_of_stay", "diabetes", "hypertension", "risk_score"],
                "test_size": 0.3,
                "random_state": 42,
            }
        return {
            "target_column": "revenue",
            "feature_columns": ["marketing_spend", "discount_rate", "processing_time"],
            "test_size": 0.3,
            "random_state": 42,
        }

    raise ValueError(f"Unsupported template_id: {template_id}")


def problem_statement_for(template_id: str, op: Dict[str, Any]) -> str:
    if template_id == "filtered_mean_v1":
        filter_text = "all rows"
        if "filter_column" in op:
            filter_text = f"rows where `{op['filter_column']}` {op.get('filter_op', 'eq')} `{op.get('filter_value')}`"
        return (
            f"Using `data/dataset.csv`, compute the {op.get('metric', 'mean')} of "
            f"`{op['value_column']}` for {filter_text}. Return the result as "
            f"`{op.get('output_key', 'result')}`."
        )
    if template_id == "groupby_aggregation_v1":
        return (
            f"Using `data/dataset.csv`, group rows by `{op['groupby']}` and compute the "
            f"{op.get('agg', 'sum')} of `{op['value_column']}` for each group. "
            "Return one labeled value per group using the requested metric names."
        )
    if template_id == "correlation_pair_v1":
        return (
            f"Using `data/dataset.csv`, compute the {op.get('method', 'pearson')} correlation "
            f"between `{op['x_column']}` and `{op['y_column']}`. Return the value as "
            f"`{op.get('output_key', 'correlation')}`."
        )
    if template_id == "iqr_outlier_count_v1":
        cols = ", ".join(f"`{col}`" for col in op["columns"])
        return (
            f"Using `data/dataset.csv`, count 1.5*IQR outliers for these numeric columns: {cols}. "
            f"Also return `{op.get('total_output_key', 'total_outlier_count')}` as the sum across columns."
        )
    if template_id == "crosstab_prevalence_v1":
        return (
            f"Using `data/dataset.csv`, compute the count and prevalence of rows where "
            f"`{op['row_column']}` equals `{op['row_value']}` and `{op['column_column']}` "
            f"equals `{op['column_value']}`. If an outcome column is specified, also compute "
            f"the mean of `{op.get('outcome_column')}` within that subset."
        )
    if template_id == "model_eval_metric_v1":
        features = ", ".join(f"`{col}`" for col in op["feature_columns"])
        return (
            f"Using `data/dataset.csv`, train the appropriate sklearn model to predict "
            f"`{op['target_column']}` from {features}. Use train_test_split with "
            f"test_size={op.get('test_size', 0.3)} and random_state={op.get('random_state', 42)}. "
            "Report accuracy for classification, or RMSE and R-squared for regression."
        )
    raise ValueError(f"Unsupported template_id: {template_id}")


def domain_for(template_id: str, variant: int) -> str:
    return {
        "filtered_mean_v1": ["ECommerce", "Finance"],
        "groupby_aggregation_v1": ["ECommerce", "Finance"],
        "correlation_pair_v1": ["Scientific", "Finance"],
        "iqr_outlier_count_v1": ["Generic", "Scientific"],
        "crosstab_prevalence_v1": ["Biomedical", "ECommerce"],
        "model_eval_metric_v1": ["Biomedical", "Finance"],
    }[template_id][variant % 2]


def difficulty_for(template_id: str, variant: int) -> str:
    if template_id in {"model_eval_metric_v1", "iqr_outlier_count_v1"}:
        return ["Medium", "Hard"][variant % 2]
    return ["Easy", "Medium"][variant % 2]


def task_type_for(template_id: str) -> str:
    return {
        "filtered_mean_v1": "descriptive_aggregation",
        "groupby_aggregation_v1": "descriptive_aggregation",
        "correlation_pair_v1": "statistical_inference",
        "iqr_outlier_count_v1": "data_quality_robustness",
        "crosstab_prevalence_v1": "specialized_domain_analysis",
        "model_eval_metric_v1": "predictive_modeling",
    }[template_id]


def secondary_types_for(template_id: str) -> List[str]:
    return {
        "filtered_mean_v1": [],
        "groupby_aggregation_v1": [],
        "correlation_pair_v1": ["descriptive_aggregation"],
        "iqr_outlier_count_v1": ["risk_anomaly_decision"],
        "crosstab_prevalence_v1": ["descriptive_aggregation"],
        "model_eval_metric_v1": ["descriptive_aggregation"],
    }[template_id]


def challenge_dimensions_for(template_id: str, variant: int) -> List[str]:
    base = {
        "filtered_mean_v1": ["conditional_filtering"],
        "groupby_aggregation_v1": ["multi_group_aggregation"],
        "correlation_pair_v1": ["statistical_method_selection"],
        "iqr_outlier_count_v1": ["outlier_detection"],
        "crosstab_prevalence_v1": ["subpopulation_analysis"],
        "model_eval_metric_v1": ["model_selection", "train_test_split_reproducibility"],
    }[template_id]
    if variant % 2 == 1:
        return base + ["cross_domain_schema"]
    return base


def tags_for(template_id: str, variant: int) -> List[str]:
    return [template_id.replace("_v1", ""), domain_for(template_id, variant).lower()]


def expert_knowledge_for(template_id: str) -> str:
    if template_id == "iqr_outlier_count_v1":
        return "Use the 1.5*IQR rule: values below Q1-1.5*IQR or above Q3+1.5*IQR are outliers."
    if template_id == "model_eval_metric_v1":
        return "Use sklearn with the specified train/test split and random_state. Drop rows with missing values before training."
    return "Use all rows unless the prompt explicitly defines a filter."


def _require_type(column: str, allowed: Iterable[str]) -> None:
    _require_known(column)
    actual = SYNTHETIC_COLUMN_TYPES[column]
    if actual not in set(allowed):
        raise ValueError(f"Column {column!r} has type {actual!r}, expected one of {sorted(allowed)}")


def _require_known(column: str) -> None:
    if column not in SYNTHETIC_COLUMN_TYPES:
        raise ValueError(f"Unknown synthetic column in manifest operation: {column}")
