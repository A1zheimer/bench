"""Wilcoxon test + Cohen's d for degradation matrix."""
import pandas as pd
import numpy as np
from scipy.stats import wilcoxon

df = pd.read_csv("results/all_results.csv")

print("=" * 80)
print("Table 3: ΔCAS Degradation Matrix")
print("=" * 80)

results = []
for agent in df["agent"].unique():
    clean = df[(df["agent"] == agent) & (df["condition"] == "clean")].set_index("task_id")["CAS"]
    for level in ["L1", "L2", "L3"]:
        perturbed = df[(df["agent"] == agent) & (df["condition"] == level)].set_index("task_id")["CAS"]
        common = clean.index.intersection(perturbed.index)
        if len(common) < 5:
            continue
        delta = clean[common] - perturbed[common]
        mean_d = delta.mean()
        std_d = delta.std()
        cohens_d = mean_d / std_d if std_d > 0 else 0
        try:
            stat, p = wilcoxon(delta, alternative="greater")
        except Exception:
            p = 1.0
        sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "†" if p < 0.10 else ""
        results.append({
            "Agent": agent, "Level": level,
            "ΔCAS": f"{mean_d:.3f}", "Cohen's d": f"{cohens_d:.2f}",
            "p-value": f"{p:.4f}", "Sig": sig,
        })
        print(f"{agent:30s} {level}: ΔCAS={mean_d:.4f}, d={cohens_d:.3f}, p={p:.4f} {sig}")

result_df = pd.DataFrame(results)
result_df.to_csv("results/degradation_matrix.csv", index=False)
print(f"\nSaved to results/degradation_matrix.csv")
