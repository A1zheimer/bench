from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional, Tuple


class StatisticalAnalyzer:
    """
    Non-parametric statistical tests and confidence intervals for benchmark results.

    All methods are self-contained (no scipy/numpy required) so they run in any
    environment.  When numpy/scipy ARE installed the results are identical but
    faster implementations can be added as drop-in replacements.
    """

    # ------------------------------------------------------------------
    # Bootstrap confidence interval
    # ------------------------------------------------------------------

    @staticmethod
    def bootstrap_ci(
        scores: List[float],
        n_bootstrap: int = 10_000,
        alpha: float = 0.05,
        seed: int = 42,
    ) -> Tuple[float, float, float]:
        """
        Percentile bootstrap confidence interval for the mean.

        Returns (mean, lower, upper) at (1-alpha) confidence level.
        """
        if not scores:
            return (0.0, 0.0, 0.0)
        rng = random.Random(seed)
        n = len(scores)
        means = []
        for _ in range(n_bootstrap):
            sample = [rng.choice(scores) for _ in range(n)]
            means.append(sum(sample) / n)
        means.sort()
        lo_idx = int(math.floor((alpha / 2) * n_bootstrap))
        hi_idx = int(math.ceil((1 - alpha / 2) * n_bootstrap)) - 1
        mean = sum(scores) / n
        return (round(mean, 4), round(means[lo_idx], 4), round(means[hi_idx], 4))

    # ------------------------------------------------------------------
    # Wilcoxon signed-rank test (paired, two-sided)
    # ------------------------------------------------------------------

    @staticmethod
    def wilcoxon_pairwise(
        scores_a: List[float],
        scores_b: List[float],
    ) -> Dict[str, Any]:
        """
        Wilcoxon signed-rank test comparing two paired score lists.

        Returns dict with keys: W_statistic, p_value (approximated via
        normal approximation for n >= 10), effect_size_r, significant (α=0.05).
        """
        if len(scores_a) != len(scores_b):
            raise ValueError("Score lists must be the same length.")
        diffs = [a - b for a, b in zip(scores_a, scores_b)]
        nonzero = [(abs(d), d) for d in diffs if d != 0]
        n = len(nonzero)
        if n == 0:
            return {"W_statistic": 0.0, "p_value": 1.0, "effect_size_r": 0.0, "significant": False}

        # Rank absolute differences (average ties)
        nonzero.sort(key=lambda x: x[0])
        ranks: List[float] = []
        i = 0
        while i < n:
            j = i
            while j < n and nonzero[j][0] == nonzero[i][0]:
                j += 1
            avg_rank = (i + 1 + j) / 2
            ranks.extend([avg_rank] * (j - i))
            i = j

        W_plus = sum(r for r, (_, d) in zip(ranks, nonzero) if d > 0)
        W_minus = sum(r for r, (_, d) in zip(ranks, nonzero) if d < 0)
        W = min(W_plus, W_minus)

        # Normal approximation (n >= 10 for reasonable accuracy)
        mean_w = n * (n + 1) / 4
        var_w = n * (n + 1) * (2 * n + 1) / 24
        if var_w == 0:
            p_value = 1.0
        else:
            z = (W - mean_w) / math.sqrt(var_w)
            # Two-tailed p via standard normal CDF approximation
            p_value = 2 * StatisticalAnalyzer._norm_sf(abs(z))

        # Effect size r = z / sqrt(N)  (N = total observations)
        z_for_effect = (W - mean_w) / math.sqrt(var_w) if var_w > 0 else 0
        effect_r = abs(z_for_effect) / math.sqrt(n)

        return {
            "W_statistic": round(W, 4),
            "p_value": round(p_value, 4),
            "effect_size_r": round(effect_r, 4),
            "significant": p_value < 0.05,
        }

    # ------------------------------------------------------------------
    # Friedman test  (k related samples, non-parametric ANOVA)
    # ------------------------------------------------------------------

    @staticmethod
    def friedman_test(
        model_score_matrix: List[List[float]],
    ) -> Dict[str, Any]:
        """
        Friedman test on a (n_tasks × n_models) matrix.

        Returns chi2_statistic, p_value (chi2 approximation, df=k-1),
        and significant flag.
        """
        n = len(model_score_matrix)       # tasks
        if n == 0:
            return {"chi2": 0.0, "p_value": 1.0, "df": 0, "significant": False}
        k = len(model_score_matrix[0])    # models
        if k <= 1:
            return {"chi2": 0.0, "p_value": 1.0, "df": 0, "significant": False}

        # Rank within each row
        rank_sums = [0.0] * k
        for row in model_score_matrix:
            indexed = sorted(enumerate(row), key=lambda x: x[1])
            ranks = [0.0] * k
            i = 0
            while i < k:
                j = i
                while j < k and indexed[j][1] == indexed[i][1]:
                    j += 1
                avg = (i + 1 + j) / 2
                for m in range(i, j):
                    ranks[indexed[m][0]] = avg
                i = j
            for j in range(k):
                rank_sums[j] += ranks[j]

        # Friedman statistic
        chi2 = (12 / (n * k * (k + 1))) * sum(r ** 2 for r in rank_sums) - 3 * n * (k + 1)
        df = k - 1
        p_value = StatisticalAnalyzer._chi2_sf(chi2, df)

        return {
            "chi2": round(chi2, 4),
            "p_value": round(p_value, 4),
            "df": df,
            "significant": p_value < 0.05,
            "rank_sums": {f"model_{i}": round(r, 2) for i, r in enumerate(rank_sums)},
        }

    # ------------------------------------------------------------------
    # Holm-Bonferroni correction
    # ------------------------------------------------------------------

    @staticmethod
    def holm_bonferroni_correction(
        p_values: List[float], alpha: float = 0.05
    ) -> List[bool]:
        """
        Holm-Bonferroni step-down correction for multiple comparisons.

        Returns a list of booleans: True = reject null hypothesis.
        """
        m = len(p_values)
        indexed = sorted(enumerate(p_values), key=lambda x: x[1])
        reject = [False] * m
        for rank, (orig_idx, p) in enumerate(indexed):
            threshold = alpha / (m - rank)
            if p <= threshold:
                reject[orig_idx] = True
            else:
                break  # step-down: once we fail, all remaining also fail
        return reject

    # ------------------------------------------------------------------
    # Spearman rank correlation
    # ------------------------------------------------------------------

    @staticmethod
    def spearman_correlation(x: List[float], y: List[float]) -> Dict[str, float]:
        """
        Spearman rank correlation coefficient and approximate p-value.
        """
        n = len(x)
        if n < 3:
            return {"rho": 0.0, "p_value": 1.0}

        def rank_list(lst: List[float]) -> List[float]:
            indexed = sorted(enumerate(lst), key=lambda v: v[1])
            ranks = [0.0] * n
            i = 0
            while i < n:
                j = i
                while j < n and indexed[j][1] == indexed[i][1]:
                    j += 1
                avg = (i + 1 + j) / 2
                for m in range(i, j):
                    ranks[indexed[m][0]] = avg
                i = j
            return ranks

        rx, ry = rank_list(x), rank_list(y)
        d2 = sum((a - b) ** 2 for a, b in zip(rx, ry))
        rho = 1 - (6 * d2) / (n * (n ** 2 - 1))

        # t approximation for p-value
        if abs(rho) >= 1.0:
            p_value = 0.0
        else:
            t_stat = rho * math.sqrt((n - 2) / (1 - rho ** 2))
            # two-tailed, approximate with normal for large n
            p_value = 2 * StatisticalAnalyzer._norm_sf(abs(t_stat))

        return {"rho": round(rho, 4), "p_value": round(p_value, 4)}

    # ------------------------------------------------------------------
    # Private helpers: distribution approximations
    # ------------------------------------------------------------------

    @staticmethod
    def _norm_sf(z: float) -> float:
        """Survival function of N(0,1): P(Z > z). Abramowitz & Stegun 26.2.17."""
        t = 1 / (1 + 0.2316419 * abs(z))
        poly = t * (0.319381530
                    + t * (-0.356563782
                           + t * (1.781477937
                                  + t * (-1.821255978
                                         + t * 1.330274429))))
        p = 1 - (1 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * z ** 2) * poly
        return 1 - p if z > 0 else p

    @staticmethod
    def _chi2_sf(x: float, df: int) -> float:
        """
        Survival function for chi-squared distribution (df degrees of freedom).
        Uses regularized incomplete gamma function via series expansion.
        """
        if x <= 0:
            return 1.0
        return StatisticalAnalyzer._reg_upper_gamma(df / 2, x / 2)

    @staticmethod
    def _reg_upper_gamma(a: float, x: float, max_iter: int = 200) -> float:
        """Regularized upper incomplete gamma function Q(a, x) via continued fraction."""
        if x < a + 1:
            # Series expansion for lower gamma, then Q = 1 - P
            return 1 - StatisticalAnalyzer._reg_lower_gamma_series(a, x, max_iter)
        # Lentz continued fraction
        fpmin = 1e-300
        b = x + 1 - a
        c = 1 / fpmin
        d = 1 / b
        h = d
        for i in range(1, max_iter + 1):
            an = -i * (i - a)
            b += 2
            d = an * d + b
            if abs(d) < fpmin:
                d = fpmin
            c = b + an / c
            if abs(c) < fpmin:
                c = fpmin
            d = 1 / d
            delta = d * c
            h *= delta
            if abs(delta - 1) < 1e-10:
                break
        return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h

    @staticmethod
    def _reg_lower_gamma_series(a: float, x: float, max_iter: int = 200) -> float:
        """Regularized lower incomplete gamma P(a, x) via series expansion."""
        if x == 0:
            return 0.0
        ap = a
        s = 1 / a
        delta = s
        for _ in range(max_iter):
            ap += 1
            delta *= x / ap
            s += delta
            if abs(delta) < abs(s) * 1e-10:
                break
        return s * math.exp(-x + a * math.log(x) - math.lgamma(a))
