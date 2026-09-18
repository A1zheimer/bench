"""Infer task taxonomy fields from existing tags.

By default this is a dry run. Pass --write to update task.json files in-place.
The inferred labels are intentionally conservative and can be manually refined.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Iterable


TASK_TYPE_KEYWORDS = {
    "descriptive_aggregation": {
        "aggregation", "group-by", "means", "descriptive-statistics",
        "filtering", "cross-tabulation", "distribution", "basic",
        "frequency", "readmission-rate",
    },
    "statistical_inference": {
        "anova", "correlation", "statistical-test", "mcnemar",
        "factorial-design", "hypothesis", "p-value",
    },
    "time_series_forecasting": {
        "time-series", "forecasting", "seasonal-decomposition", "arima",
        "changepoint-detection", "cusum", "daily-trends",
    },
    "predictive_modeling": {
        "logistic-regression", "regression", "prediction", "cross-validation",
        "calibration", "ensemble-stacking", "meta-learner",
        "classification", "auc",
    },
    "risk_anomaly_decision": {
        "anomaly-detection", "fraud detection", "cost-sensitive learning",
        "anomaly scoring", "monte carlo simulations", "credit-risk",
        "var", "threshold-optimization", "fpr", "fairness-audit",
        "disparate-impact", "equalized-odds",
    },
    "data_quality_robustness": {
        "missing-values", "imputation", "heteroskedasticity",
        "contamination", "schema-drift", "outlier", "noisy",
    },
    "specialized_domain_analysis": {
        "survival-analysis", "kaplan-meier", "cox-ph",
        "cox proportional hazards", "spatial interpolation", "idw",
        "kriging", "pca", "shap", "treatment-effect",
        "uplift-modeling", "dimensionality-reduction",
        "dose-response modeling", "non-linear curve fitting",
    },
}


CHALLENGE_KEYWORDS = {
    "missing_values": {"missing-values", "imputation"},
    "outlier_handling": {"outlier", "anomaly", "contamination"},
    "heteroskedasticity": {"heteroskedasticity"},
    "semantic_perturbation": {"semantic", "obfuscated", "canary"},
    "censoring": {"right-censoring", "censoring"},
    "class_imbalance_or_cost": {
        "cost-sensitive", "threshold-optimization", "fpr", "fraud",
    },
}


def _normalise(values: Iterable[str]) -> set[str]:
    return {str(v).strip().lower() for v in values}


def infer_taxonomy(tags: Iterable[str], problem_statement: str = "") -> dict:
    haystack = _normalise(tags)
    haystack_text = " ".join(sorted(haystack)) + " " + problem_statement.lower()

    scores = Counter()
    for task_type, keywords in TASK_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in haystack or kw in haystack_text:
                scores[task_type] += 1

    if scores:
        primary, _ = scores.most_common(1)[0]
        secondary = [t for t, _ in scores.most_common() if t != primary]
    else:
        primary = "descriptive_aggregation"
        secondary = []

    challenges = []
    for challenge, keywords in CHALLENGE_KEYWORDS.items():
        if any(kw in haystack or kw in haystack_text for kw in keywords):
            challenges.append(challenge)

    return {
        "primary_task_type": primary,
        "secondary_task_types": secondary,
        "challenge_dimensions": challenges,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks-dir", default="tasks")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    tasks_dir = Path(args.tasks_dir)
    counts = Counter()
    for task_file in sorted(tasks_dir.glob("DS_TASK_*/task.json")):
        task = json.loads(task_file.read_text())
        meta = task.setdefault("task_metadata", {})
        context = task.get("context", {})
        inferred = infer_taxonomy(
            meta.get("tags", []),
            context.get("problem_statement", ""),
        )
        counts[inferred["primary_task_type"]] += 1

        print(
            f"{task['instance_id']}: {inferred['primary_task_type']} "
            f"secondary={inferred['secondary_task_types']} "
            f"challenges={inferred['challenge_dimensions']}"
        )

        if args.write:
            meta.update(inferred)
            task_file.write_text(json.dumps(task, indent=2, ensure_ascii=False) + "\n")

    print("\nPrimary task-type distribution:")
    for task_type, count in counts.most_common():
        print(f"  {task_type}: {count}")


if __name__ == "__main__":
    main()
