"""
AdversarialDirtier: Systematically injects real-world data quality issues
into seed datasets for robustness testing.

Injection intensity scales with difficulty level (Easy/Medium/Hard).
Every injection is logged so ground truth can be adjusted accordingly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


@dataclass
class InjectionLog:
    """Records all injections applied to a dataset."""
    mcar_columns: List[str] = field(default_factory=list)
    mcar_rate: float = 0.0
    mnar_columns: List[Dict] = field(default_factory=list)  # [{col, condition_col, threshold, rate}]
    schema_drift_columns: List[str] = field(default_factory=list)
    encoding_trap_columns: List[str] = field(default_factory=list)
    timezone_mix_columns: List[str] = field(default_factory=list)
    outlier_columns: List[str] = field(default_factory=list)
    n_outliers_injected: int = 0
    n_duplicate_rows: int = 0

    def to_dict(self) -> dict:
        return {
            "mcar": {"columns": self.mcar_columns, "rate": self.mcar_rate},
            "mnar": self.mnar_columns,
            "schema_drift": self.schema_drift_columns,
            "encoding_traps": self.encoding_trap_columns,
            "timezone_mix": self.timezone_mix_columns,
            "outliers": {"columns": self.outlier_columns, "count": self.n_outliers_injected},
            "duplicate_rows": self.n_duplicate_rows,
        }


# Difficulty-level injection configs
DIFFICULTY_CONFIG = {
    "Easy": {
        "mcar_rate": 0.03,
        "mcar_cols": 1,
        "mnar": False,
        "schema_drift": False,
        "encoding_trap": False,
        "timezone_mix": False,
        "outliers": 0,
        "duplicates": 0,
    },
    "Medium": {
        "mcar_rate": 0.08,
        "mcar_cols": 2,
        "mnar": True,
        "mnar_cols": 1,
        "schema_drift": True,
        "schema_drift_cols": 1,
        "schema_drift_ratio": 0.05,
        "encoding_trap": True,
        "encoding_trap_cols": 1,
        "timezone_mix": False,
        "outliers": 3,
        "duplicates": 0,
    },
    "Hard": {
        "mcar_rate": 0.15,
        "mcar_cols": 3,
        "mnar": True,
        "mnar_cols": 3,
        "schema_drift": True,
        "schema_drift_cols": 3,
        "schema_drift_ratio": 0.10,
        "encoding_trap": True,
        "encoding_trap_cols": 3,
        "timezone_mix": True,
        "outliers": 10,
        "duplicates": 5,
    },
}


class AdversarialDirtier:
    """
    Injects realistic data quality issues into a DataFrame.

    All operations are seeded for reproducibility.
    """

    def __init__(self, seed: int = 42):
        self.rng = np.random.default_rng(seed)

    def apply_all(
        self, df: pd.DataFrame, difficulty: str = "Medium"
    ) -> Tuple[pd.DataFrame, InjectionLog]:
        """
        Apply all difficulty-appropriate injections.

        Returns (dirty_df, injection_log).
        """
        config = DIFFICULTY_CONFIG.get(difficulty, DIFFICULTY_CONFIG["Medium"])
        log = InjectionLog()
        df = df.copy()

        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        cat_cols = df.select_dtypes(include="object").columns.tolist()
        datetime_cols = [c for c in df.columns if "date" in c.lower() or "time" in c.lower()]

        # 1. MCAR missing
        n_mcar = min(config["mcar_cols"], len(numeric_cols))
        if n_mcar > 0:
            mcar_targets = list(self.rng.choice(numeric_cols, n_mcar, replace=False))
            df = self.inject_mcar_missing(df, mcar_targets, config["mcar_rate"])
            log.mcar_columns = mcar_targets
            log.mcar_rate = config["mcar_rate"]

        # 2. MNAR missing (business-logic driven)
        if config.get("mnar") and len(numeric_cols) >= 2:
            n_mnar = min(config.get("mnar_cols", 1), len(numeric_cols) - 1)
            for i in range(n_mnar):
                target_col = numeric_cols[i]
                condition_col = numeric_cols[(i + 1) % len(numeric_cols)]
                threshold = float(df[condition_col].quantile(0.75))
                df = self.inject_mnar_missing(df, target_col, condition_col, threshold)
                log.mnar_columns.append({
                    "col": target_col,
                    "condition_col": condition_col,
                    "threshold": threshold,
                    "rate": 0.6,
                })

        # 3. Schema drift
        if config.get("schema_drift") and numeric_cols:
            n_drift = min(config.get("schema_drift_cols", 1), len(numeric_cols))
            drift_targets = list(self.rng.choice(numeric_cols, n_drift, replace=False))
            ratio = config.get("schema_drift_ratio", 0.05)
            for col in drift_targets:
                df = self.inject_schema_drift(df, col, ratio)
            log.schema_drift_columns = drift_targets

        # 4. Encoding traps
        if config.get("encoding_trap") and cat_cols:
            n_trap = min(config.get("encoding_trap_cols", 1), len(cat_cols))
            trap_targets = list(self.rng.choice(cat_cols, n_trap, replace=False))
            for col in trap_targets:
                df = self.inject_encoding_trap(df, col)
            log.encoding_trap_columns = trap_targets

        # 5. Timezone mix
        if config.get("timezone_mix") and datetime_cols:
            for col in datetime_cols[:1]:
                df = self.inject_timezone_mix(df, col)
                log.timezone_mix_columns.append(col)

        # 6. Outlier clusters (only on columns still purely numeric)
        n_outliers = config.get("outliers", 0)
        still_numeric = df.select_dtypes(include="number").columns.tolist()
        if n_outliers > 0 and still_numeric:
            outlier_col = self.rng.choice(still_numeric)
            df = self.inject_outlier_cluster(df, outlier_col, n_outliers)
            log.outlier_columns = [outlier_col]
            log.n_outliers_injected = n_outliers

        # 7. Near-duplicate rows
        n_dupes = config.get("duplicates", 0)
        if n_dupes > 0:
            df = self.inject_duplicate_rows(df, n_dupes)
            log.n_duplicate_rows = n_dupes

        return df, log

    # ------------------------------------------------------------------
    # Individual injection methods
    # ------------------------------------------------------------------

    def inject_mcar_missing(
        self, df: pd.DataFrame, columns: List[str], rate: float = 0.08
    ) -> pd.DataFrame:
        """MCAR (Missing Completely At Random) — uniform random NaN."""
        for col in columns:
            if col in df.columns:
                mask = self.rng.random(len(df)) < rate
                df.loc[mask, col] = np.nan
        return df

    def inject_mnar_missing(
        self,
        df: pd.DataFrame,
        col: str,
        condition_col: str,
        threshold: float,
        rate: float = 0.6,
    ) -> pd.DataFrame:
        """
        MNAR (Missing Not At Random): missingness depends on another column's value.

        Example: when income > threshold, tax_record is missing with `rate` probability.
        """
        if col not in df.columns or condition_col not in df.columns:
            return df
        high_mask = df[condition_col] > threshold
        random_mask = self.rng.random(len(df)) < rate
        df.loc[high_mask & random_mask, col] = np.nan
        return df

    def inject_schema_drift(
        self, df: pd.DataFrame, col: str, drift_ratio: float = 0.05
    ) -> pd.DataFrame:
        """
        Mix formatted strings into a numeric column.

        12500.00 → "$12,500" / "12,500.00 USD" / "1.25万"
        """
        if col not in df.columns:
            return df

        n_drift = max(1, int(len(df) * drift_ratio))
        drift_idx = self.rng.choice(len(df), n_drift, replace=False)

        formats = [
            lambda v: f"${v:,.0f}",
            lambda v: f"{v:,.2f} USD",
            lambda v: f"{v / 10000:.2f}万" if abs(v) >= 10000 else f"{v:.1f}",
            lambda v: f"{v:.1f}%",
        ]

        # Must convert column to object dtype to hold strings
        df[col] = df[col].astype(object)
        for idx in drift_idx:
            val = df.iloc[idx][col]
            if pd.notna(val):
                fmt = formats[self.rng.integers(0, len(formats))]
                try:
                    df.iat[idx, df.columns.get_loc(col)] = fmt(float(val))
                except (ValueError, TypeError):
                    pass
        return df

    def inject_encoding_trap(self, df: pd.DataFrame, col: str) -> pd.DataFrame:
        """
        Inconsistent casing and whitespace in categorical column.

        "Apple" → mixed ["Apple", "apple", "APPLE", "apple "]
        """
        if col not in df.columns:
            return df

        transforms = [
            lambda s: s.lower(),
            lambda s: s.upper(),
            lambda s: s + " ",  # trailing space
            lambda s: " " + s,  # leading space
            lambda s: s.title(),
        ]

        n_trap = max(1, int(len(df) * 0.15))
        trap_idx = self.rng.choice(len(df), n_trap, replace=False)

        for idx in trap_idx:
            val = df.iloc[idx][col]
            if pd.notna(val) and isinstance(val, str):
                transform = transforms[self.rng.integers(0, len(transforms))]
                df.iat[idx, df.columns.get_loc(col)] = transform(val)
        return df

    def inject_timezone_mix(self, df: pd.DataFrame, col: str) -> pd.DataFrame:
        """
        Mix timezone formats in datetime-like string column.

        "2024-01-15" → "2024-01-15T08:30:00Z" or "2024-01-15 03:30:00-05:00"
        """
        if col not in df.columns:
            return df

        tz_formats = [
            lambda d: f"{d}T{self.rng.integers(0,24):02d}:{self.rng.integers(0,60):02d}:00Z",
            lambda d: f"{d} {self.rng.integers(0,24):02d}:{self.rng.integers(0,60):02d}:00-05:00",
            lambda d: f"{d} {self.rng.integers(0,24):02d}:{self.rng.integers(0,60):02d}:00+08:00",
        ]

        n_mix = max(1, int(len(df) * 0.10))
        mix_idx = self.rng.choice(len(df), n_mix, replace=False)

        df[col] = df[col].astype(object)
        for idx in mix_idx:
            val = df.iloc[idx][col]
            if pd.notna(val):
                val_str = str(val)[:10]  # Take date part only
                fmt = tz_formats[self.rng.integers(0, len(tz_formats))]
                df.iat[idx, df.columns.get_loc(col)] = fmt(val_str)
        return df

    def inject_outlier_cluster(
        self, df: pd.DataFrame, col: str, n_outliers: int = 3
    ) -> pd.DataFrame:
        """
        Inject extreme outliers (>5σ) that form a small cluster.

        Not random scatter — a coherent anomaly group to test whether
        agents delete vs analyze them.
        """
        if col not in df.columns:
            return df

        mean = df[col].mean()
        std = df[col].std()
        if pd.isna(std) or std == 0:
            return df

        # Generate cluster of outliers around 6σ above mean
        cluster_center = mean + 6 * std
        outlier_vals = cluster_center + self.rng.normal(0, std * 0.3, n_outliers)

        outlier_idx = self.rng.choice(len(df), min(n_outliers, len(df)), replace=False)
        for i, idx in enumerate(outlier_idx):
            df.iat[idx, df.columns.get_loc(col)] = round(outlier_vals[i], 4)
        return df

    def inject_duplicate_rows(
        self, df: pd.DataFrame, n_dupes: int = 5
    ) -> pd.DataFrame:
        """
        Near-duplicate rows: copy a row but perturb one numeric column slightly.
        """
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        if not numeric_cols:
            return df

        source_idx = self.rng.choice(len(df), min(n_dupes, len(df)), replace=False)
        new_rows = []
        for idx in source_idx:
            row = df.iloc[idx].copy()
            perturb_col = self.rng.choice(numeric_cols)
            val = row[perturb_col]
            if pd.notna(val) and val != 0:
                row[perturb_col] = val * (1 + self.rng.normal(0, 0.001))
            new_rows.append(row)

        if new_rows:
            dupes = pd.DataFrame(new_rows)
            df = pd.concat([df, dupes], ignore_index=True)
            # Shuffle to hide duplicates
            df = df.sample(frac=1, random_state=int(self.rng.integers(0, 10000))).reset_index(drop=True)

        return df
