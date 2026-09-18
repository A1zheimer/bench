"""Pilot experiment statistical analysis: Wilcoxon + Cohen's d."""
import json
import numpy as np
from pathlib import Path
from scipy.stats import wilcoxon

pilot_tasks = json.load(open("pilot_20_tasks.json"))

cas_clean, cas_L1, cas_L2, cas_L3 = [], [], [], []

for task_id in pilot_tasks:
    for cond, cas_list in [("clean", cas_clean)]:
        rpath = Path(f"runs/native_4omini/clean/{task_id}/report.json")
        if not rpath.exists():
            rpath = Path(f"bench_runs/{task_id}/report.json")
        if rpath.exists():
            r = json.load(open(rpath))
            m = r["metrics"]
            cas = 0.4 * m["result_accuracy"] + 0.35 * m["process_quality"] + 0.25 * m["safety_score"]
            cas_list.append(cas)
        else:
            cas_list.append(np.nan)

    for level, cas_list in [("L1", cas_L1), ("L2", cas_L2), ("L3", cas_L3)]:
        rpath = Path(f"pilot/{level}/{task_id}/report.json")
        if rpath.exists():
            r = json.load(open(rpath))
            m = r["metrics"]
            cas = 0.4 * m["result_accuracy"] + 0.35 * m["process_quality"] + 0.25 * m["safety_score"]
            cas_list.append(cas)
        else:
            cas_list.append(np.nan)

for level, cas_perturbed in [("L1", cas_L1), ("L2", cas_L2), ("L3", cas_L3)]:
    clean_arr = np.array(cas_clean)
    pert_arr = np.array(cas_perturbed)
    mask = ~np.isnan(clean_arr) & ~np.isnan(pert_arr)
    if mask.sum() < 5:
        print(f"{level}: insufficient data ({mask.sum()} pairs)")
        continue
    delta = clean_arr[mask] - pert_arr[mask]
    mean_delta = np.mean(delta)
    std_delta = np.std(delta)
    cohens_d = mean_delta / std_delta if std_delta > 0 else 0
    try:
        stat, p = wilcoxon(delta, alternative="greater")
    except Exception:
        p = 1.0
    print(f"{level}: ΔCAS = {mean_delta:.4f} ± {std_delta:.4f}, Cohen's d = {cohens_d:.3f}, Wilcoxon p = {p:.4f}")

print(f"\nClean CAS mean: {np.nanmean(cas_clean):.4f}")
