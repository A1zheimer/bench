from __future__ import annotations

import math
from typing import Dict, List, Optional


class ReproducibilityChecker:
    """
    Multi-run reproducibility metrics.

    pass@k  — probability at least one of k attempts succeeds
               (HumanEval unbiased estimator: Chen et al. 2021)
    CV      — coefficient of variation (std / mean)
    """

    N_RUNS_DEFAULT = 5

    # ------------------------------------------------------------------
    # pass@k  (unbiased estimator)
    # ------------------------------------------------------------------

    @staticmethod
    def pass_at_k(n: int, c: int, k: int) -> float:
        """
        Unbiased estimator of pass@k.

        Args:
            n: total number of runs
            c: number of correct runs
            k: number of samples to draw

        Returns:
            probability in [0, 1]
        """
        if n - c < k:
            return 1.0
        # 1 - C(n-c, k) / C(n, k)
        return 1.0 - math.comb(n - c, k) / math.comb(n, k)

    @staticmethod
    def pass_at_k_curve(scores: List[float], threshold: float = 0.8) -> Dict[str, float]:
        """
        Compute pass@1, pass@3, pass@5 from a list of run scores.

        A run is considered "correct" if score >= threshold.
        """
        n = len(scores)
        c = sum(1 for s in scores if s >= threshold)
        result: Dict[str, float] = {}
        for k in [1, 3, 5]:
            if n >= k:
                result[f"pass@{k}"] = round(ReproducibilityChecker.pass_at_k(n, c, k), 4)
        return result

    # ------------------------------------------------------------------
    # Coefficient of variation
    # ------------------------------------------------------------------

    @staticmethod
    def coefficient_of_variation(scores: List[float]) -> float:
        """
        CV = std / mean.  Returns 0.0 for single-element or zero-mean lists.

        Interpretation:
          CV < 0.10  → highly reproducible
          CV < 0.30  → moderately reproducible
          CV >= 0.30 → unstable / high variance
        """
        n = len(scores)
        if n < 2:
            return 0.0
        mean = sum(scores) / n
        if mean == 0:
            return 0.0
        variance = sum((s - mean) ** 2 for s in scores) / (n - 1)
        return round(math.sqrt(variance) / abs(mean), 4)

    # ------------------------------------------------------------------
    # Full reproducibility report for one task × one model
    # ------------------------------------------------------------------

    @staticmethod
    def reproducibility_report(
        scores: List[float],
        threshold: float = 0.8,
        label: str = "",
    ) -> Dict:
        """
        Aggregate reproducibility stats for a list of runs.
        """
        n = len(scores)
        if n == 0:
            return {"label": label, "n": 0}
        mean = sum(scores) / n
        variance = sum((s - mean) ** 2 for s in scores) / max(n - 1, 1)
        std = math.sqrt(variance)
        return {
            "label": label,
            "n": n,
            "mean": round(mean, 4),
            "std": round(std, 4),
            "min": round(min(scores), 4),
            "max": round(max(scores), 4),
            "cv": ReproducibilityChecker.coefficient_of_variation(scores),
            "stability": (
                "high" if ReproducibilityChecker.coefficient_of_variation(scores) < 0.10
                else "medium" if ReproducibilityChecker.coefficient_of_variation(scores) < 0.30
                else "low"
            ),
            **ReproducibilityChecker.pass_at_k_curve(scores, threshold),
        }

    # ------------------------------------------------------------------
    # Cross-task summary (pass@k matrix)
    # ------------------------------------------------------------------

    @staticmethod
    def task_pass_at_k_summary(
        task_scores: Dict[str, List[float]],
        k_values: Optional[List[int]] = None,
        threshold: float = 0.8,
    ) -> Dict[str, float]:
        """
        Given {task_id: [score_run1, score_run2, ...]}, compute mean pass@k
        across all tasks.

        Returns {"mean_pass@1": ..., "mean_pass@3": ..., "mean_pass@5": ...}
        """
        if k_values is None:
            k_values = [1, 3, 5]
        accum: Dict[str, List[float]] = {f"pass@{k}": [] for k in k_values}
        for _task, scores in task_scores.items():
            n = len(scores)
            c = sum(1 for s in scores if s >= threshold)
            for k in k_values:
                if n >= k:
                    accum[f"pass@{k}"].append(
                        ReproducibilityChecker.pass_at_k(n, c, k)
                    )
        return {
            f"mean_{key}": round(sum(vals) / len(vals), 4) if vals else 0.0
            for key, vals in accum.items()
        }
