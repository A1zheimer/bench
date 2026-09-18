"""
ContrastiveAnalyzer: Statistical analysis of contrastive experiment results.

Computes degradation summaries, runs paired statistical tests (Wilcoxon/t-test),
and generates degradation matrices for LaTeX output.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List

import numpy as np
import pandas as pd
from scipy import stats

from ..experiments.contrastive import PairedResult


class ContrastiveAnalyzer:
    """Analyzes paired clean-vs-perturbed results to quantify memorization effects."""

    @staticmethod
    def _safe_float(v):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        return round(v, 6)

    def analyze(self, paired_results: List[PairedResult]) -> Dict[str, Any]:
        """
        Full analysis pipeline.

        Returns a dict with:
          - total_pairs, models_tested, conditions_tested
          - degradation_summary (per model × condition)
          - statistical_tests (paired t-test, Wilcoxon, Cohen's d)
          - degradation_matrix (models × levels, values = mean ΔCAS)
        """
        if not paired_results:
            return {"error": "No paired results to analyze."}

        data = []
        for r in paired_results:
            clean_acc = r.metrics_clean.get("result_accuracy", 0)
            clean_proc = r.metrics_clean.get("process_quality", 0)
            clean_safety = r.metrics_clean.get("safety_score", 0)
            pert_acc = r.metrics_perturbed.get("result_accuracy", 0)
            pert_proc = r.metrics_perturbed.get("process_quality", 0)
            pert_safety = r.metrics_perturbed.get("safety_score", 0)

            cas_clean = CAS_WEIGHTS["accuracy"] * clean_acc + CAS_WEIGHTS["process"] * clean_proc + CAS_WEIGHTS["safety"] * clean_safety
            cas_pert = CAS_WEIGHTS["accuracy"] * pert_acc + CAS_WEIGHTS["process"] * pert_proc + CAS_WEIGHTS["safety"] * pert_safety

            data.append({
                "task_id": r.instance_id,
                "agent_model": r.agent_model,
                "condition": r.condition,
                "clean_acc": clean_acc,
                "pert_acc": pert_acc,
                "delta_acc": r.delta_accuracy,
                "clean_proc": clean_proc,
                "pert_proc": pert_proc,
                "delta_proc": r.delta_process,
                "clean_cas": cas_clean,
                "pert_cas": cas_pert,
                "delta_cas": r.delta_cas,
            })

        df = pd.DataFrame(data)

        return {
            "total_pairs": len(df),
            "models_tested": df["agent_model"].unique().tolist(),
            "conditions_tested": df["condition"].unique().tolist(),
            "degradation_summary": self._degradation_summary(df),
            "statistical_tests": self._statistical_tests(df),
            "degradation_matrix": self._degradation_matrix(df),
        }

    def _degradation_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Per-model, per-condition mean/max degradation."""
        summary: Dict[str, Any] = {}
        for model in df["agent_model"].unique():
            mdf = df[df["agent_model"] == model]
            summary[model] = {}
            for cond in sorted(mdf["condition"].unique()):
                cdf = mdf[mdf["condition"] == cond]
                summary[model][cond] = {
                    "n": len(cdf),
                    "mean_clean_cas": self._safe_float(float(cdf["clean_cas"].mean())),
                    "mean_pert_cas": self._safe_float(float(cdf["pert_cas"].mean())),
                    "mean_delta_cas": self._safe_float(float(cdf["delta_cas"].mean())),
                    "std_delta_cas": self._safe_float(float(cdf["delta_cas"].std(ddof=1))),
                    "max_degradation": self._safe_float(float(cdf["delta_cas"].max())),
                    "mean_delta_acc": self._safe_float(float(cdf["delta_acc"].mean())),
                    "mean_delta_proc": self._safe_float(float(cdf["delta_proc"].mean())),
                }
        return summary

    def _statistical_tests(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Paired statistical tests per model:
          - Paired t-test (parametric)
          - Wilcoxon signed-rank (non-parametric, preferred for small n)
          - Cohen's d effect size
        """
        results: Dict[str, Any] = {}
        for model in df["agent_model"].unique():
            mdf = df[df["agent_model"] == model]
            clean = mdf["clean_cas"].values
            pert = mdf["pert_cas"].values
            diff = clean - pert

            entry: Dict[str, Any] = {"n": len(mdf)}

            # Paired t-test
            if len(diff) >= 2 and np.std(diff, ddof=1) > 0:
                t_stat, p_t = stats.ttest_rel(clean, pert)
                entry["ttest_t"] = self._safe_float(float(t_stat))
                entry["ttest_p"] = self._safe_float(float(p_t))
                entry["ttest_significant"] = bool(p_t < 0.05)
            else:
                entry["ttest_p"] = None

            # Wilcoxon signed-rank (requires n >= 6 for meaningful result)
            if len(diff) >= 6:
                try:
                    w_stat, p_w = stats.wilcoxon(diff, alternative="greater")
                    entry["wilcoxon_w"] = self._safe_float(float(w_stat))
                    entry["wilcoxon_p"] = self._safe_float(float(p_w))
                    entry["wilcoxon_significant"] = bool(p_w < 0.05)
                except ValueError:
                    entry["wilcoxon_p"] = None
            else:
                entry["wilcoxon_p"] = None

            # Cohen's d
            if np.std(diff, ddof=1) > 0:
                cohens_d = float(np.mean(diff) / np.std(diff, ddof=1))
                entry["cohens_d"] = self._safe_float(cohens_d)
                entry["effect_size"] = (
                    "large" if abs(cohens_d) >= 0.8
                    else "medium" if abs(cohens_d) >= 0.5
                    else "small" if abs(cohens_d) >= 0.2
                    else "negligible"
                )
            else:
                entry["cohens_d"] = 0.0
                entry["effect_size"] = "negligible"

            results[model] = entry

        return results

    def _degradation_matrix(self, df: pd.DataFrame) -> Dict[str, Dict[str, float]]:
        """
        Degradation matrix: rows=models, cols=perturbation levels, values=mean ΔCAS.

        Suitable for direct LaTeX table rendering.
        """
        matrix: Dict[str, Dict[str, float]] = {}
        for model in sorted(df["agent_model"].unique()):
            mdf = df[df["agent_model"] == model]
            row: Dict[str, float] = {}
            for cond in sorted(mdf["condition"].unique()):
                cdf = mdf[mdf["condition"] == cond]
                row[cond] = self._safe_float(float(cdf["delta_cas"].mean()))
            matrix[model] = row
        return matrix
