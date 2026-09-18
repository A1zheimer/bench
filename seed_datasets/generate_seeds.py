"""
Seed Dataset Generator for DataAgentBench.

Two-tier strategy:
  1. PRIMARY: Real data from sklearn built-in datasets, sliced and shuffled
     for anti-contamination while preserving genuine statistical properties.
  2. FALLBACK: Synthetic data with realistic distributions for domains
     not covered by sklearn (ECommerce, time series, etc.).

Usage:
    python -m seed_datasets.generate_seeds
"""
from __future__ import annotations

import json
import os
import pathlib
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

OUTPUT_DIR = pathlib.Path(__file__).parent
SEED = 42  # Global reproducibility seed


# ====================================================================
# Core utility: anti-contamination slicing
# ====================================================================

def slice_dataset(
    X: np.ndarray,
    y: np.ndarray,
    feature_names: List[str],
    target_name: str = "target",
    feature_ratio: float = 0.6,
    row_ratio: float = 0.5,
    seed: int = SEED,
) -> pd.DataFrame:
    """
    Slice a sklearn dataset to prevent direct memorization.

    1. Randomly select `feature_ratio` of columns (破坏全局特征结构)
    2. Randomly sample `row_ratio` of rows (破坏样本分布)
    3. Shuffle row order

    Preserves local correlations but destroys global fingerprint.
    """
    rng = np.random.default_rng(seed)

    n_samples, n_features = X.shape
    n_keep_features = max(3, int(n_features * feature_ratio))
    n_keep_rows = max(50, int(n_samples * row_ratio))

    # Select features
    feature_idx = sorted(rng.choice(n_features, n_keep_features, replace=False))
    selected_features = [feature_names[i] for i in feature_idx]
    X_sliced = X[:, feature_idx]

    # Sample rows
    row_idx = rng.choice(n_samples, n_keep_rows, replace=False)
    X_sliced = X_sliced[row_idx]
    y_sliced = y[row_idx]

    # Shuffle
    shuffle_idx = rng.permutation(n_keep_rows)
    X_sliced = X_sliced[shuffle_idx]
    y_sliced = y_sliced[shuffle_idx]

    df = pd.DataFrame(X_sliced, columns=selected_features)
    df[target_name] = y_sliced
    return df


def _inject_missing(df: pd.DataFrame, columns: list, rate: float = 0.08, rng=None):
    """Inject MCAR NaN into specified columns at the given rate."""
    if rng is None:
        rng = np.random.default_rng(99)
    for col in columns:
        if col in df.columns:
            mask = rng.random(len(df)) < rate
            df.loc[mask, col] = np.nan
    return df


def _save(df: pd.DataFrame, rel_path: str, source: str) -> dict:
    """Save CSV and return metadata entry for manifest."""
    abs_path = OUTPUT_DIR / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(abs_path, index=False)

    # Compute basic stats
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    missing_rate = float(df.isnull().mean().mean())

    meta = {
        "rows": len(df),
        "columns": list(df.columns),
        "source": source,
        "missing_rate": round(missing_rate, 4),
        "numeric_columns": numeric_cols,
    }
    print(f"  {rel_path}: {len(df)} rows x {len(df.columns)} cols (source={source})")
    return meta


# ====================================================================
# REAL DATA: sklearn-based datasets
# ====================================================================

def gen_breast_cancer() -> Tuple[str, dict]:
    """Breast Cancer Wisconsin — Biomedical classification."""
    from sklearn.datasets import load_breast_cancer

    data = load_breast_cancer()
    df = slice_dataset(
        data.data, data.target, list(data.feature_names),
        target_name="diagnosis",
        feature_ratio=0.5, row_ratio=0.5, seed=SEED + 1,
    )
    # Map target: 0=malignant, 1=benign
    df["diagnosis"] = df["diagnosis"].map({0: "malignant", 1: "benign"})
    df = _inject_missing(df, df.select_dtypes("number").columns[:3].tolist(), 0.06,
                         np.random.default_rng(SEED + 1))

    rel_path = "biomedical/breast_cancer_slice.csv"
    meta = _save(df, rel_path, "real_sklearn")
    meta.update({
        "domain": "Biomedical",
        "difficulty_range": ["Easy", "Medium", "Hard"],
        "features": ["numeric", "binary_target", "missing_values", "high_dimensional"],
        "sklearn_source": "load_breast_cancer",
        "applicable_paradigms": [
            "Clinical Trial A/B Testing and Causal Inference (Propensity Score Matching)",
            "Missing Data Imputation in Clinical Records (MICE, KNN Imputer)",
        ],
        "easy_tasks": [
            "Count malignant vs benign diagnoses",
            "Compute mean of each numeric feature by diagnosis",
        ],
        "medium_tasks": [
            "Logistic regression to predict diagnosis, report AUC",
            "Impute missing values and compare model accuracy before/after",
        ],
        "hard_tasks": [
            "Feature selection (top-5 by mutual information) + cross-validated SVM",
            "PCA dimensionality reduction + clustering + diagnosis purity analysis",
        ],
    })
    return rel_path, meta


def gen_diabetes() -> Tuple[str, dict]:
    """Diabetes regression — Biomedical regression."""
    from sklearn.datasets import load_diabetes

    data = load_diabetes()
    df = slice_dataset(
        data.data, data.target, list(data.feature_names),
        target_name="progression",
        feature_ratio=0.7, row_ratio=0.6, seed=SEED + 2,
    )
    df = _inject_missing(df, ["bmi", "bp"], 0.08, np.random.default_rng(SEED + 2))

    rel_path = "biomedical/diabetes_slice.csv"
    meta = _save(df, rel_path, "real_sklearn")
    meta.update({
        "domain": "Biomedical",
        "difficulty_range": ["Easy", "Medium", "Hard"],
        "features": ["numeric", "regression_target", "missing_values"],
        "sklearn_source": "load_diabetes",
        "applicable_paradigms": [
            "Dose-Response Modeling and Non-linear Curve Fitting",
            "Missing Data Imputation in Clinical Records (MICE, KNN Imputer)",
        ],
        "easy_tasks": [
            "Correlation between each feature and progression",
            "Summary statistics of all numeric columns",
        ],
        "medium_tasks": [
            "Linear regression with R-squared and RMSE",
            "Compare imputation strategies on prediction accuracy",
        ],
        "hard_tasks": [
            "Ridge/Lasso regression with cross-validation + feature importance",
            "Non-linear modeling (polynomial/GAM) vs linear, report AIC comparison",
        ],
    })
    return rel_path, meta


def gen_wine() -> Tuple[str, dict]:
    """Wine recognition — Scientific multi-class classification."""
    from sklearn.datasets import load_wine

    data = load_wine()
    df = slice_dataset(
        data.data, data.target, list(data.feature_names),
        target_name="cultivar",
        feature_ratio=0.7, row_ratio=0.8, seed=SEED + 3,
    )
    df["cultivar"] = df["cultivar"].map({0: "ClassA", 1: "ClassB", 2: "ClassC"})
    df = _inject_missing(df, df.select_dtypes("number").columns[:2].tolist(), 0.05,
                         np.random.default_rng(SEED + 3))

    rel_path = "scientific/wine_slice.csv"
    meta = _save(df, rel_path, "real_sklearn")
    meta.update({
        "domain": "Scientific",
        "difficulty_range": ["Easy", "Medium", "Hard"],
        "features": ["numeric", "multiclass_target", "missing_values"],
        "sklearn_source": "load_wine",
        "applicable_paradigms": [
            "Factorial ANOVA with Interaction Effects and Post-hoc Tests",
            "Genomic Data Dimensionality Reduction (PCA, t-SNE, UMAP)",
        ],
        "easy_tasks": [
            "Mean of each feature grouped by cultivar",
            "Which cultivar has the highest mean alcohol content?",
        ],
        "medium_tasks": [
            "One-way ANOVA for each feature across cultivars",
            "PCA to 2D and visualize cluster separation",
        ],
        "hard_tasks": [
            "Multi-class classification with cross-validated F1 (macro)",
            "MANOVA + post-hoc discriminant analysis",
        ],
    })
    return rel_path, meta


def gen_california_housing() -> Tuple[str, dict]:
    """California Housing — Finance-style regression. Uses fetch with fallback."""
    try:
        from sklearn.datasets import fetch_california_housing
        data = fetch_california_housing()
        df = slice_dataset(
            data.data, data.target, list(data.feature_names),
            target_name="median_house_value",
            feature_ratio=0.8, row_ratio=0.025,  # 20640 → ~500 rows
            seed=SEED + 4,
        )
        df = _inject_missing(df, ["AveRooms", "AveBedrms"], 0.07,
                             np.random.default_rng(SEED + 4))
        source = "real_sklearn"
    except Exception:
        # Fallback: generate realistic housing data synthetically
        print("    (fetch_california_housing unavailable, using synthetic fallback)")
        rng = np.random.default_rng(SEED + 4)
        n = 500
        income = np.clip(rng.lognormal(1.5, 0.6, n), 0.5, 15).round(4)
        house_age = rng.integers(1, 52, n).astype(float)
        rooms = np.clip(rng.lognormal(1.5, 0.4, n), 1, 20).round(2)
        population = rng.integers(100, 5000, n).astype(float)
        latitude = rng.uniform(32.5, 41.5, n).round(2)
        longitude = rng.uniform(-124.0, -114.5, n).round(2)
        value = (income * 0.3 + rng.normal(0, 0.5, n) + 1.5).round(4)
        value = np.clip(value, 0.15, 5.0)
        df = pd.DataFrame({
            "MedInc": income, "HouseAge": house_age, "AveRooms": rooms,
            "Population": population, "Latitude": latitude, "Longitude": longitude,
            "median_house_value": value,
        })
        df = _inject_missing(df, ["AveRooms"], 0.07, rng)
        source = "synthetic"

    rel_path = "finance/california_housing_slice.csv"
    meta = _save(df, rel_path, source)
    meta.update({
        "domain": "Finance",
        "difficulty_range": ["Easy", "Medium", "Hard"],
        "features": ["numeric", "regression_target", "missing_values", "spatial"],
        "applicable_paradigms": [
            "Credit Risk Modeling and Imbalanced Classification (SMOTE)",
            "Time Series Forecasting (e.g., ARIMA, Prophet, LSTM) with Heteroskedasticity",
        ],
        "easy_tasks": [
            "Average house value by income bracket (quartiles)",
            "Correlation matrix of all features",
        ],
        "medium_tasks": [
            "Linear regression for house value, report R-squared and top-3 features",
            "Detect and handle outliers in house value, re-fit model",
        ],
        "hard_tasks": [
            "Spatial regression accounting for latitude/longitude clusters",
            "Random Forest vs Ridge regression comparison with cross-validated RMSE",
        ],
    })
    return rel_path, meta


def gen_iris() -> Tuple[str, dict]:
    """Iris — Scientific basic classification (Easy only)."""
    from sklearn.datasets import load_iris

    data = load_iris()
    # No slicing — Iris is small (150 rows) and well-known; Easy tasks only
    df = pd.DataFrame(data.data, columns=data.feature_names)
    df["species"] = [data.target_names[t] for t in data.target]
    # Shuffle
    df = df.sample(frac=1, random_state=SEED + 5).reset_index(drop=True)

    rel_path = "scientific/iris_full.csv"
    meta = _save(df, rel_path, "real_sklearn")
    meta.update({
        "domain": "Scientific",
        "difficulty_range": ["Easy"],
        "features": ["numeric", "multiclass_target", "small_dataset"],
        "sklearn_source": "load_iris",
        "applicable_paradigms": [
            "Factorial ANOVA with Interaction Effects and Post-hoc Tests",
        ],
        "easy_tasks": [
            "Mean petal length per species",
            "Which species has the widest sepal?",
        ],
    })
    return rel_path, meta


# ====================================================================
# SYNTHETIC FALLBACK: domains not in sklearn
# ====================================================================

def gen_transactions_synthetic() -> Tuple[str, dict]:
    """Synthetic credit card transactions — Finance fraud detection."""
    rng = np.random.default_rng(SEED + 10)
    n = 600
    customer_id = rng.integers(1000, 1100, n)
    amount = np.where(
        rng.random(n) < 0.05,
        rng.lognormal(7, 1.2, n),
        rng.lognormal(4, 0.8, n),
    ).round(2)
    is_fraud = (rng.random(n) < 0.05).astype(int)
    category = rng.choice(
        ["Food", "Electronics", "Travel", "Entertainment", "Utilities", "Healthcare"],
        n, p=[0.30, 0.15, 0.10, 0.15, 0.20, 0.10],
    )
    hour = np.clip(rng.normal(14, 5, n), 0, 23).astype(int)
    hour[is_fraud == 1] = rng.choice([1, 2, 3, 23, 0], is_fraud.sum())
    day_of_week = rng.integers(0, 7, n)
    base_date = pd.Timestamp("2024-01-01")
    dates = [base_date + pd.Timedelta(days=int(d)) for d in rng.integers(0, 180, n)]

    df = pd.DataFrame({
        "transaction_id": range(1, n + 1),
        "customer_id": customer_id,
        "date": [d.strftime("%Y-%m-%d") for d in dates],
        "hour": hour, "day_of_week": day_of_week,
        "amount": amount, "category": category,
        "is_fraud": is_fraud,
    })

    rel_path = "finance/transactions.csv"
    meta = _save(df, rel_path, "synthetic")
    meta.update({
        "domain": "Finance",
        "difficulty_range": ["Easy", "Medium", "Hard"],
        "features": ["categorical", "numeric", "binary_target", "temporal", "class_imbalance"],
        "applicable_paradigms": [
            "Fraud Detection with Cost-Sensitive Learning and Anomaly Scoring",
            "Credit Risk Modeling and Imbalanced Classification (SMOTE)",
        ],
        "easy_tasks": ["Total spending per category", "Count transactions per day_of_week"],
        "medium_tasks": ["Anomaly detection with z-score on amount", "Fraud classifier with precision/recall"],
        "hard_tasks": ["Isolation forest with ROC-AUC", "Time-aware train/test + cost-sensitive learning"],
    })
    return rel_path, meta


def gen_orders_synthetic() -> Tuple[str, dict]:
    """Synthetic e-commerce orders with seasonality."""
    rng = np.random.default_rng(SEED + 11)
    n = 800
    customer_id = rng.integers(100, 300, n)
    month_probs = [0.06, 0.06, 0.07, 0.07, 0.08, 0.08, 0.08, 0.08, 0.08, 0.09, 0.12, 0.13]
    months = rng.choice(range(1, 13), n, p=month_probs)
    days = rng.integers(1, 29, n)
    order_dates = [f"2023-{m:02d}-{d:02d}" for m, d in zip(months, days)]
    category = rng.choice(
        ["Electronics", "Clothing", "Home", "Books", "Sports", "Food"],
        n, p=[0.20, 0.25, 0.15, 0.15, 0.10, 0.15],
    )
    unit_price = np.where(
        category == "Electronics", rng.lognormal(5, 0.8, n),
        np.where(category == "Clothing", rng.lognormal(3.5, 0.5, n),
                 rng.lognormal(3, 0.6, n))
    ).round(2)
    quantity = rng.choice([1, 1, 1, 2, 2, 3], n)
    total = (unit_price * quantity).round(2)
    returned = (rng.random(n) < 0.08).astype(int)
    rating = np.where(returned == 1, rng.choice([1, 2, 3], n), rng.choice([3, 4, 4, 5, 5], n))
    channel = rng.choice(["Web", "Mobile", "App"], n, p=[0.40, 0.35, 0.25])

    df = pd.DataFrame({
        "order_id": range(10001, 10001 + n),
        "customer_id": customer_id,
        "order_date": order_dates,
        "category": category, "unit_price": unit_price,
        "quantity": quantity, "total_amount": total,
        "channel": channel, "returned": returned, "rating": rating,
    })

    rel_path = "ecommerce/orders.csv"
    meta = _save(df, rel_path, "synthetic")
    meta.update({
        "domain": "ECommerce",
        "difficulty_range": ["Easy", "Medium", "Hard"],
        "features": ["categorical", "numeric", "temporal", "seasonal"],
        "applicable_paradigms": [
            "Customer Lifetime Value (CLV) Prediction (BTYD models, RFM analysis)",
            "Seasonal Decomposition of Revenue Time Series",
        ],
        "easy_tasks": ["Total revenue by category", "Monthly order count trend"],
        "medium_tasks": ["RFM segmentation of customers", "Seasonal decomposition of monthly revenue"],
        "hard_tasks": ["CLV prediction with BTYD model", "Market basket analysis with association rules"],
    })
    return rel_path, meta


def gen_user_sessions_synthetic() -> Tuple[str, dict]:
    """Synthetic web sessions with conversion data."""
    rng = np.random.default_rng(SEED + 12)
    n = 600
    user_id = rng.integers(1000, 1200, n)
    duration_sec = np.clip(rng.exponential(300, n), 5, 3600).astype(int)
    pages_viewed = np.clip(rng.poisson(5, n), 1, 30)
    bounce = (pages_viewed == 1).astype(int)
    device = rng.choice(["Desktop", "Mobile", "Tablet"], n, p=[0.45, 0.40, 0.15])
    source = rng.choice(["Organic", "Paid", "Social", "Direct", "Email"],
                        n, p=[0.35, 0.20, 0.15, 0.20, 0.10])
    conv_prob = 1 / (1 + np.exp(-(-4 + 0.003 * duration_sec + 0.2 * pages_viewed)))
    converted = (rng.random(n) < conv_prob).astype(int)
    cart_value = np.where(converted, rng.lognormal(4, 0.8, n), 0).round(2)

    base = pd.Timestamp("2024-01-01")
    timestamps = [base + pd.Timedelta(hours=int(h)) for h in rng.integers(0, 24 * 90, n)]

    df = pd.DataFrame({
        "session_id": [f"S{i:06d}" for i in range(1, n + 1)],
        "user_id": user_id,
        "timestamp": [t.strftime("%Y-%m-%d %H:%M") for t in timestamps],
        "device": device, "traffic_source": source,
        "duration_seconds": duration_sec, "pages_viewed": pages_viewed,
        "bounce": bounce, "converted": converted, "cart_value": cart_value,
    })

    rel_path = "ecommerce/user_sessions.csv"
    meta = _save(df, rel_path, "synthetic")
    meta.update({
        "domain": "ECommerce",
        "difficulty_range": ["Easy", "Medium", "Hard"],
        "features": ["categorical", "numeric", "binary_target", "temporal"],
        "applicable_paradigms": [
            "Conversion Funnel Drop-off Analysis and Cohort Retention",
            "A/B Test Analysis with Statistical Power and Effect Size",
        ],
        "easy_tasks": ["Conversion rate by device type", "Bounce rate calculation"],
        "medium_tasks": ["Conversion prediction model with AUC", "Cohort retention analysis"],
        "hard_tasks": ["Funnel analysis with multi-touch attribution", "User journey clustering"],
    })
    return rel_path, meta


def gen_lab_experiment_synthetic() -> Tuple[str, dict]:
    """Synthetic factorial experiment data."""
    rng = np.random.default_rng(SEED + 13)
    factors = {
        "temperature_C": [20, 30, 40, 50],
        "concentration_mM": [0.1, 0.5, 1.0, 5.0],
        "catalyst": ["None", "TypeA", "TypeB", "TypeC"],
    }
    rows = []
    for temp in factors["temperature_C"]:
        for conc in factors["concentration_mM"]:
            for cat in factors["catalyst"]:
                n_rep = rng.integers(8, 12)
                for rep in range(n_rep):
                    base_yield = 40 + 0.5 * temp + 10 * np.log(conc + 0.01)
                    cat_effect = {"None": 0, "TypeA": 8, "TypeB": 12, "TypeC": 5}[cat]
                    interaction = 0.1 * temp * conc if cat != "None" else 0
                    noise = rng.normal(0, 3)
                    measured_yield = max(0, base_yield + cat_effect + interaction + noise)
                    rows.append({
                        "experiment_id": len(rows) + 1,
                        "temperature_C": temp, "concentration_mM": conc,
                        "catalyst": cat, "replicate": rep + 1,
                        "yield_percent": round(measured_yield, 2),
                        "reaction_time_min": round(max(1, rng.normal(45, 10)), 1),
                        "purity_percent": round(np.clip(rng.normal(92, 5), 50, 99.9), 1),
                    })
    df = pd.DataFrame(rows)
    df = _inject_missing(df, ["purity_percent"], 0.04, rng)

    rel_path = "scientific/lab_experiment.csv"
    meta = _save(df, rel_path, "synthetic")
    meta.update({
        "domain": "Scientific",
        "difficulty_range": ["Easy", "Medium", "Hard"],
        "features": ["factorial_design", "numeric", "categorical", "missing_values"],
        "applicable_paradigms": [
            "Factorial ANOVA with Interaction Effects and Post-hoc Tests",
            "Response Surface Methodology and Experiment Optimization",
        ],
        "easy_tasks": ["Mean yield by catalyst type", "Effect of temperature on yield"],
        "medium_tasks": ["Two-way ANOVA (temperature x catalyst)", "Regression model for yield"],
        "hard_tasks": ["Full factorial ANOVA with interactions", "Response surface optimization"],
    })
    return rel_path, meta


def gen_weather_synthetic() -> Tuple[str, dict]:
    """Synthetic multi-station weather data."""
    rng = np.random.default_rng(SEED + 14)
    stations = {
        "STN_NORTH": {"lat": 45.0, "base_temp": 8, "precip_scale": 3.0},
        "STN_SOUTH": {"lat": 30.0, "base_temp": 18, "precip_scale": 2.0},
        "STN_COAST": {"lat": 37.0, "base_temp": 15, "precip_scale": 4.0},
        "STN_MOUNT": {"lat": 40.0, "base_temp": 3, "precip_scale": 5.0},
        "STN_URBAN": {"lat": 38.0, "base_temp": 14, "precip_scale": 2.5},
    }
    dates = pd.date_range("2023-01-01", periods=365)
    rows = []
    for stn_name, props in stations.items():
        for date in dates:
            day_of_year = date.dayofyear
            seasonal = 12 * np.sin(2 * np.pi * (day_of_year - 80) / 365)
            temp = props["base_temp"] + seasonal + rng.normal(0, 3)
            precip_prob = 0.3 + 0.1 * np.sin(2 * np.pi * (day_of_year - 350) / 365)
            precip = rng.exponential(props["precip_scale"]) if rng.random() < precip_prob else 0
            humidity = np.clip(60 + 20 * (precip > 0) + rng.normal(0, 10), 10, 100)
            wind_speed = np.clip(rng.exponential(12), 0, 80)
            rows.append({
                "date": date.strftime("%Y-%m-%d"), "station": stn_name,
                "latitude": props["lat"],
                "temp_celsius": round(temp, 1), "precipitation_mm": round(precip, 1),
                "humidity_percent": round(humidity, 1), "wind_speed_kmh": round(wind_speed, 1),
            })
    df = pd.DataFrame(rows)
    df = _inject_missing(df, ["temp_celsius", "humidity_percent"], 0.02, rng)

    rel_path = "scientific/weather_stations.csv"
    meta = _save(df, rel_path, "synthetic")
    meta.update({
        "domain": "Scientific",
        "difficulty_range": ["Easy", "Medium", "Hard"],
        "features": ["time_series", "multi_station", "seasonal", "missing_values", "spatial"],
        "applicable_paradigms": [
            "Time Series Changepoint Detection and Trend Analysis",
            "Multi-station Climate Anomaly Detection",
        ],
        "easy_tasks": ["Average temperature per station", "Rainiest month across stations"],
        "medium_tasks": ["Seasonal decomposition of temperature", "Anomaly detection in temperature"],
        "hard_tasks": ["Spatial interpolation using latitude", "Granger causality between variables"],
    })
    return rel_path, meta


# ====================================================================
# MAIN
# ====================================================================

def main():
    """Generate all seed datasets and write manifest.json."""
    manifest: Dict[str, dict] = {}

    print("=" * 60)
    print("Generating seed datasets for DataAgentBench")
    print("=" * 60)

    # --- Real data (sklearn) ---
    print("\n[sklearn real data — sliced for anti-contamination]")
    for gen_fn in [gen_breast_cancer, gen_diabetes, gen_wine, gen_california_housing, gen_iris]:
        rel_path, meta = gen_fn()
        manifest[rel_path] = meta

    # --- Synthetic fallback ---
    print("\n[Synthetic fallback — domains not in sklearn]")
    for gen_fn in [
        gen_transactions_synthetic,
        gen_orders_synthetic,
        gen_user_sessions_synthetic,
        gen_lab_experiment_synthetic,
        gen_weather_synthetic,
    ]:
        rel_path, meta = gen_fn()
        manifest[rel_path] = meta

    # Write manifest
    manifest_path = OUTPUT_DIR / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"\nManifest written: {manifest_path} ({len(manifest)} entries)")
    print("Done.")


if __name__ == "__main__":
    main()
