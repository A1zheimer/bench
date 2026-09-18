"""
SeedAnalyzer: Automatically analyzes seed CSVs and updates manifest.json
with computed statistical properties and taxonomy tag matching.

Usage:
    from seed_datasets.seed_analyzer import SeedAnalyzer
    analyzer = SeedAnalyzer()
    analyzer.analyze_and_update_manifest("seed_datasets/manifest.json")
"""
from __future__ import annotations

import json
import pathlib
from typing import Any, Dict, List

import numpy as np
import pandas as pd


# Tag-matching rules: if condition is met, apply these taxonomy tags
TAG_RULES = [
    {
        "condition": lambda stats: stats["missing_rate"] > 0.10,
        "tags": ["Missing Data Imputation"],
    },
    {
        "condition": lambda stats: stats.get("class_imbalance_ratio", 1.0) > 5.0,
        "tags": ["Imbalanced Classification (SMOTE)"],
    },
    {
        "condition": lambda stats: stats.get("has_datetime", False),
        "tags": ["Time Series"],
    },
    {
        "condition": lambda stats: stats["n_numeric_cols"] > 20,
        "tags": ["Dimensionality Reduction (PCA, t-SNE)"],
    },
    {
        "condition": lambda stats: stats["n_categorical_cols"] > 5,
        "tags": ["High-Cardinality Categorical Variables"],
    },
    {
        "condition": lambda stats: stats.get("max_skewness", 0) > 2.0,
        "tags": ["Outlier Detection"],
    },
]


class SeedAnalyzer:
    """Analyzes seed CSV files and computes statistical metadata."""

    def analyze_csv(self, csv_path: str) -> Dict[str, Any]:
        """
        Read a CSV and compute comprehensive statistical properties.

        Returns a dict suitable for merging into manifest.json entries.
        """
        df = pd.read_csv(csv_path)

        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        cat_cols = df.select_dtypes(include="object").columns.tolist()
        datetime_cols = [c for c in df.columns if "date" in c.lower() or "time" in c.lower()]

        # Basic stats
        stats: Dict[str, Any] = {
            "rows": len(df),
            "n_columns": len(df.columns),
            "n_numeric_cols": len(numeric_cols),
            "n_categorical_cols": len(cat_cols),
            "has_datetime": len(datetime_cols) > 0,
            "missing_rate": round(float(df.isnull().mean().mean()), 4),
            "missing_per_column": {
                col: round(float(df[col].isnull().mean()), 4)
                for col in df.columns
                if df[col].isnull().any()
            },
        }

        # Numeric column distributions
        if numeric_cols:
            desc = df[numeric_cols].describe()
            stats["numeric_summary"] = {
                col: {
                    "mean": round(float(desc.loc["mean", col]), 4),
                    "std": round(float(desc.loc["std", col]), 4),
                    "min": round(float(desc.loc["min", col]), 4),
                    "max": round(float(desc.loc["max", col]), 4),
                }
                for col in numeric_cols[:10]  # Cap at 10 to keep manifest compact
            }

            # Skewness
            skewness = df[numeric_cols].skew()
            stats["max_skewness"] = round(float(skewness.abs().max()), 4)

            # Top-5 correlations
            if len(numeric_cols) >= 2:
                corr = df[numeric_cols].corr()
                # Get upper triangle pairs
                pairs = []
                for i in range(len(corr.columns)):
                    for j in range(i + 1, len(corr.columns)):
                        val = corr.iloc[i, j]
                        if pd.notna(val):
                            pairs.append((corr.columns[i], corr.columns[j], round(float(val), 3)))
                pairs.sort(key=lambda x: abs(x[2]), reverse=True)
                stats["top_correlations"] = [
                    f"{a}~{b}: {v}" for a, b, v in pairs[:5]
                ]

        # Categorical column cardinality
        if cat_cols:
            stats["categorical_cardinality"] = {
                col: int(df[col].nunique())
                for col in cat_cols[:10]
            }

            # Class imbalance detection (look for binary-ish target columns)
            for col in cat_cols:
                nunique = df[col].nunique()
                if 2 <= nunique <= 5:
                    value_counts = df[col].value_counts()
                    ratio = value_counts.max() / max(value_counts.min(), 1)
                    stats["class_imbalance_ratio"] = round(float(ratio), 2)
                    stats["imbalance_column"] = col
                    break

        # Also check numeric binary columns for imbalance
        for col in numeric_cols:
            unique_vals = df[col].dropna().unique()
            if len(unique_vals) == 2 and set(unique_vals).issubset({0, 1, 0.0, 1.0}):
                pos_rate = float(df[col].mean())
                if pos_rate < 0.2 or pos_rate > 0.8:
                    imbalance = max(pos_rate, 1 - pos_rate) / max(min(pos_rate, 1 - pos_rate), 0.01)
                    stats["class_imbalance_ratio"] = round(imbalance, 2)
                    stats["imbalance_column"] = col
                    break

        # Auto-match taxonomy tags
        matched_tags = []
        for rule in TAG_RULES:
            try:
                if rule["condition"](stats):
                    matched_tags.extend(rule["tags"])
            except (KeyError, TypeError):
                pass
        stats["auto_tags"] = matched_tags

        return stats

    def analyze_and_update_manifest(self, manifest_path: str) -> Dict[str, Any]:
        """
        Read manifest.json, re-analyze each CSV, and update
        the `statistical_properties` field.

        Returns the updated manifest dict.
        """
        manifest_path = pathlib.Path(manifest_path)
        seed_dir = manifest_path.parent

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        for rel_path, entry in manifest.items():
            csv_path = seed_dir / rel_path
            if not csv_path.exists():
                continue

            stats = self.analyze_csv(str(csv_path))
            entry["statistical_properties"] = stats

            # Merge auto_tags into applicable_paradigms if not already present
            existing = set(entry.get("applicable_paradigms", []))
            for tag in stats.get("auto_tags", []):
                if tag not in existing:
                    entry.setdefault("applicable_paradigms", []).append(tag)

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        print(f"Updated {len(manifest)} entries in {manifest_path}")
        return manifest
