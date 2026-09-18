from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..models.constants import CAS_WEIGHTS
from ..repository.provenance import filter_formal_reports
from .statistical_tests import StatisticalAnalyzer
from .reproducibility import ReproducibilityChecker


class LeaderboardGenerator:
    """
    Builds leaderboard tables and radar chart data from benchmark DB results.

    Input: list of raw report dicts (as returned by ReportDatabase.query())
    """

    # Composite Agentic Score weights (ablation-tested in paper)
    CAS_WEIGHTS = CAS_WEIGHTS

    # Safety-Adjusted Efficiency  = accuracy × safety / log(1 + tokens)
    @staticmethod
    def _sae(accuracy: float, safety: float, tokens: int) -> float:
        import math
        denom = math.log1p(max(tokens, 1))
        return round(accuracy * safety / denom, 6)

    # ------------------------------------------------------------------
    # CAS
    # ------------------------------------------------------------------

    @classmethod
    def composite_agentic_score(
        cls,
        accuracy: float,
        process: float,
        safety: float,
        weights: Optional[Dict[str, float]] = None,
    ) -> float:
        w = weights or cls.CAS_WEIGHTS
        return round(
            w["accuracy"] * accuracy + w["process"] * process + w["safety"] * safety,
            4,
        )

    # ------------------------------------------------------------------
    # Build leaderboard from list of report dicts
    # ------------------------------------------------------------------

    @classmethod
    def build(
        cls,
        reports: List[Dict[str, Any]],
        bootstrap_n: int = 5_000,
        include_unverified: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Group reports by model_id, compute aggregate metrics + 95% CI.

        Returns list of dicts sorted by CAS descending.
        """
        from collections import defaultdict

        if not include_unverified:
            reports = filter_formal_reports(reports)

        buckets: Dict[str, Dict[str, List[float]]] = defaultdict(
            lambda: {
                "accuracy": [],
                "process": [],
                "safety": [],
                "completion": [],
                "tokens": [],
                "cost_usd": [],
                "wall_time": [],
                "cas": [],
                "sae": [],
            }
        )

        for r in reports:
            mid = r.get("model_id") or "simulated"
            m = r.get("metrics", {})
            acc = float(m.get("result_accuracy", 0))
            proc = float(m.get("process_quality", 0))
            saf = float(m.get("safety_score", 0))
            tok = int(m.get("total_tokens", 0))
            cas = cls.composite_agentic_score(acc, proc, saf)
            sae = cls._sae(acc, saf, tok)
            buckets[mid]["accuracy"].append(acc)
            buckets[mid]["process"].append(proc)
            buckets[mid]["safety"].append(saf)
            buckets[mid]["completion"].append(float(m.get("completion_rate", 0)))
            buckets[mid]["tokens"].append(tok)
            buckets[mid]["cost_usd"].append(float(m.get("total_cost_usd", 0)))
            buckets[mid]["wall_time"].append(float(m.get("wall_time_seconds", 0)))
            buckets[mid]["cas"].append(cas)
            buckets[mid]["sae"].append(sae)

        rows = []
        for mid, data in buckets.items():
            n = len(data["accuracy"])
            cas_mean, cas_lo, cas_hi = StatisticalAnalyzer.bootstrap_ci(
                data["cas"], n_bootstrap=bootstrap_n
            )
            acc_mean, acc_lo, acc_hi = StatisticalAnalyzer.bootstrap_ci(
                data["accuracy"], n_bootstrap=bootstrap_n
            )
            rows.append({
                "model_id": mid,
                "n": n,
                "CAS": cas_mean,
                "CAS_95ci": f"[{cas_lo:.4f}, {cas_hi:.4f}]",
                "accuracy": acc_mean,
                "accuracy_95ci": f"[{acc_lo:.4f}, {acc_hi:.4f}]",
                "process": round(sum(data["process"]) / n, 4),
                "safety": round(sum(data["safety"]) / n, 4),
                "completion": round(sum(data["completion"]) / n, 4),
                "avg_tokens": int(sum(data["tokens"]) / n),
                "avg_cost_usd": round(sum(data["cost_usd"]) / n, 6),
                "avg_wall_time": round(sum(data["wall_time"]) / n, 2),
                "SAE": round(sum(data["sae"]) / n, 6),
            })

        rows.sort(key=lambda r: r["CAS"], reverse=True)
        for rank, row in enumerate(rows, 1):
            row["rank"] = rank
        return rows

    # ------------------------------------------------------------------
    # LaTeX table
    # ------------------------------------------------------------------

    @classmethod
    def generate_latex_table(cls, leaderboard: List[Dict[str, Any]]) -> str:
        lines = [
            r"\begin{table}[h]",
            r"\centering",
            r"\caption{DataAgentBench Leaderboard (CAS = 0.40$\times$Acc + 0.35$\times$Proc + 0.25$\times$Safety)}",
            r"\label{tab:leaderboard}",
            r"\begin{tabular}{clcccccr}",
            r"\toprule",
            r"Rank & Model & CAS (95\% CI) & Accuracy & Process & Safety & Completion & Tokens \\",
            r"\midrule",
        ]
        for row in leaderboard:
            lines.append(
                f"  {row['rank']} & {row['model_id']} & "
                f"{row['CAS']:.4f} {row['CAS_95ci']} & "
                f"{row['accuracy']:.4f} & "
                f"{row['process']:.4f} & "
                f"{row['safety']:.4f} & "
                f"{row['completion']:.1%} & "
                f"{row['avg_tokens']:,} \\\\"
            )
        lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Radar chart data (5-axis)
    # ------------------------------------------------------------------

    @classmethod
    def radar_chart_data(cls, leaderboard: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Returns a dict suitable for JSON serialization and plotting:
        {
          "axes": ["accuracy", "process", "safety", "completion", "efficiency"],
          "models": {
            "model_id": [v_acc, v_proc, v_saf, v_comp, v_eff]
          }
        }
        Efficiency is SAE normalized to [0,1] across models.
        """
        max_sae = max((r["SAE"] for r in leaderboard), default=1.0) or 1.0
        return {
            "axes": ["accuracy", "process", "safety", "completion", "efficiency"],
            "models": {
                row["model_id"]: [
                    row["accuracy"],
                    row["process"],
                    row["safety"],
                    row["completion"],
                    round(row["SAE"] / max_sae, 4),
                ]
                for row in leaderboard
            },
        }

    # ------------------------------------------------------------------
    # Contrastive degradation table (anti-memorization finding)
    # ------------------------------------------------------------------

    @classmethod
    def generate_contrastive_latex_table(
        cls, degradation_matrix: Dict[str, Dict[str, float]]
    ) -> str:
        """
        Generate a LaTeX table from ContrastiveAnalyzer's degradation_matrix.

        Rows: models, Cols: L1/L2/L3 perturbation levels, Values: mean ΔCAS.
        """
        if not degradation_matrix:
            return "% No contrastive data available"

        # Collect all condition columns
        all_conds = sorted(
            {c for row in degradation_matrix.values() for c in row}
        )
        col_spec = "l" + "c" * len(all_conds)

        lines = [
            r"\begin{table}[h]",
            r"\centering",
            r"\caption{Anti-Memorization Degradation: Mean $\Delta$CAS (Clean $-$ Perturbed)}",
            r"\label{tab:contrastive}",
            f"\\begin{{tabular}}{{{col_spec}}}",
            r"\toprule",
            "Model & " + " & ".join(all_conds) + r" \\",
            r"\midrule",
        ]
        for model, row in sorted(degradation_matrix.items()):
            vals = []
            for c in all_conds:
                v = row.get(c, 0.0)
                # Highlight large degradation
                fmt = f"{v:+.4f}"
                if v > 0.1:
                    fmt = r"\textbf{" + fmt + "}"
                vals.append(fmt)
            lines.append(f"  {model} & " + " & ".join(vals) + r" \\")

        lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Reasoning-result decoupling analysis (core NeurIPS finding)
    # ------------------------------------------------------------------

    @classmethod
    def reasoning_outcome_analysis(
        cls, reports: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Compute Spearman correlation between process_quality and result_accuracy
        across all runs.  The hypothesis: rho < 0.6 (decoupling).
        """
        proc = [float(r.get("metrics", {}).get("process_quality", 0)) for r in reports]
        acc = [float(r.get("metrics", {}).get("result_accuracy", 0)) for r in reports]
        result = StatisticalAnalyzer.spearman_correlation(proc, acc)
        result["n"] = len(reports)
        result["decoupled"] = result["rho"] < 0.6
        result["interpretation"] = (
            "Reasoning and outcome are decoupled (rho < 0.6): high process quality "
            "does not guarantee correct results."
            if result["decoupled"]
            else "Reasoning and outcome are correlated (rho >= 0.6)."
        )
        return result
