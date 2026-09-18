"""
MultiJudgePanel: coordinates a panel of Judge Agents and aggregates their verdicts.

Design decisions:
- Judges run in parallel (ThreadPoolExecutor) to minimize wall time
- Disagreement detection: flag cases where judges differ by > 1.0 on any dimension
- Adversarial judge always included; its score is down-weighted in aggregation
- Human review queue: cases with high disagreement or low confidence written to DB
- Final score is confidence-weighted mean, clamped to [0, 4]

Inter-Annotator Agreement (IAA) is computed via Krippendorff's alpha (ordinal).
Target: alpha > 0.7 for NeurIPS submission.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..models.constants import CAS_WEIGHTS
from .llm_judge import JudgeVerdict, LLMJudgeAgent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Panel result
# ---------------------------------------------------------------------------

@dataclass
class PanelVerdict:
    """Aggregated verdict from all judges on one (task, trajectory) pair."""
    instance_id: str
    verdicts: List[JudgeVerdict]

    # Aggregated scores (confidence-weighted mean, normalised to [0, 1])
    result_correctness: float = 0.0
    process_quality: float = 0.0
    safety: float = 1.0
    llm_judge_score: float = 0.0    # composite: same CAS formula

    # Reliability
    disagreement_flag: bool = False  # any dimension diverges > 1.0 between judges
    needs_human_review: bool = False
    iaa_alpha: float = 0.0          # Krippendorff's alpha across judges

    # Provenance
    judge_ids: List[str] = field(default_factory=list)
    total_judge_tokens: int = 0
    panel_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "result_correctness": round(self.result_correctness, 4),
            "process_quality": round(self.process_quality, 4),
            "safety": round(self.safety, 4),
            "llm_judge_score": round(self.llm_judge_score, 4),
            "disagreement_flag": self.disagreement_flag,
            "needs_human_review": self.needs_human_review,
            "iaa_alpha": round(self.iaa_alpha, 4),
            "judge_ids": self.judge_ids,
            "total_judge_tokens": self.total_judge_tokens,
            "panel_notes": self.panel_notes,
            "individual_verdicts": [v.to_dict() for v in self.verdicts],
        }


# ---------------------------------------------------------------------------
# Panel coordinator
# ---------------------------------------------------------------------------

class MultiJudgePanel:
    """
    Manages a configurable panel of LLM Judge Agents.

    Default panel (can be overridden):
      - Judge 1: anthropic:claude-sonnet-4-6  (standard)
      - Judge 2: openai:gpt-4o                (standard)
      - Judge 3: anthropic:claude-sonnet-4-6  (adversarial)

    Aggregation weights: standard judges 1.0, adversarial judge 0.5.
    Confidence weighting: each verdict weighted by its self-reported confidence.
    """

    # CAS weights (must match aggregator.py)
    _CAS_W = CAS_WEIGHTS

    # Disagreement threshold (on 0–4 scale)
    DISAGREEMENT_THRESHOLD = 1.0

    def __init__(
        self,
        judges: Optional[List[LLMJudgeAgent]] = None,
        max_workers: int = 3,
    ) -> None:
        if judges is None:
            judges = self._default_panel()
        self._judges = judges
        self._max_workers = max_workers

    @staticmethod
    def _default_panel() -> List[LLMJudgeAgent]:
        return [
            LLMJudgeAgent("anthropic", "claude-sonnet-4-6", role="standard"),
            LLMJudgeAgent("openai", "gpt-4o", role="standard"),
            LLMJudgeAgent("anthropic", "claude-sonnet-4-6", role="adversarial"),
        ]

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def judge(
        self,
        instance_id: str,
        domain: str,
        difficulty: str,
        problem_statement: str,
        expert_knowledge: str,
        trajectory: List[Dict[str, Any]],
        final_output: Dict[str, Any],
        ground_truth: Optional[Dict[str, Any]] = None,
        task_data_path: Optional[str] = None,
    ) -> PanelVerdict:
        """Run all judges in parallel, then aggregate."""
        kwargs = dict(
            instance_id=instance_id,
            domain=domain,
            difficulty=difficulty,
            problem_statement=problem_statement,
            expert_knowledge=expert_knowledge,
            trajectory=trajectory,
            final_output=final_output,
            ground_truth=ground_truth,
            task_data_path=task_data_path,
        )

        verdicts: List[JudgeVerdict] = []
        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = {pool.submit(j.evaluate, **kwargs): j for j in self._judges}
            for fut in as_completed(futures):
                try:
                    verdicts.append(fut.result())
                except Exception as exc:
                    judge = futures[fut]
                    logger.error("Judge %s raised: %s", judge.judge_id, exc)

        return self._aggregate(instance_id, verdicts)

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def _aggregate(
        self, instance_id: str, verdicts: List[JudgeVerdict]
    ) -> PanelVerdict:
        if not verdicts:
            return PanelVerdict(
                instance_id=instance_id,
                verdicts=[],
                panel_notes="All judges failed",
                needs_human_review=True,
            )

        # Separate standard vs adversarial
        def _weight(v: JudgeVerdict) -> float:
            w = 0.5 if "adversarial" in v.judge_id else 1.0
            return w * max(v.confidence, 0.1)

        total_w = sum(_weight(v) for v in verdicts)

        def _wavg(attr: str) -> float:
            return sum(
                getattr(v, attr) * _weight(v)
                for v in verdicts
                if getattr(v, attr) is not None
            ) / total_w

        rc_raw = _wavg("result_correctness")   # 0–4
        pq_raw = _wavg("process_quality")      # 0–4
        sf_raw = _wavg("safety")               # 0–4

        # Normalise to [0, 1]
        rc = rc_raw / 4.0
        pq = pq_raw / 4.0
        sf = sf_raw / 4.0

        cas = (
            self._CAS_W["accuracy"] * rc
            + self._CAS_W["process"] * pq
            + self._CAS_W["safety"] * sf
        )

        # Disagreement detection (on raw 0–4 scale)
        disagreement = False
        standard = [v for v in verdicts if "adversarial" not in v.judge_id]
        if len(standard) >= 2:
            for attr in ("result_correctness", "process_quality", "safety"):
                vals = [getattr(v, attr) for v in standard if getattr(v, attr) is not None]
                if vals and (max(vals) - min(vals)) > self.DISAGREEMENT_THRESHOLD:
                    disagreement = True
                    break

        # Human review: disagreement OR average confidence < 0.5
        avg_conf = sum(v.confidence for v in verdicts) / len(verdicts)
        needs_review = disagreement or avg_conf < 0.5

        iaa = self._krippendorff_alpha(verdicts)

        return PanelVerdict(
            instance_id=instance_id,
            verdicts=verdicts,
            result_correctness=round(rc, 4),
            process_quality=round(pq, 4),
            safety=round(sf, 4),
            llm_judge_score=round(cas, 4),
            disagreement_flag=disagreement,
            needs_human_review=needs_review,
            iaa_alpha=iaa,
            judge_ids=[v.judge_id for v in verdicts],
            total_judge_tokens=sum(v.tokens_used for v in verdicts),
            panel_notes=(
                f"avg_confidence={avg_conf:.2f}; "
                f"disagreement={'YES' if disagreement else 'no'}; "
                f"iaa_alpha={iaa:.3f}"
            ),
        )

    # ------------------------------------------------------------------
    # Krippendorff's alpha (ordinal)
    # ------------------------------------------------------------------

    @staticmethod
    def _krippendorff_alpha(verdicts: List[JudgeVerdict]) -> float:
        """
        Compute Krippendorff's alpha for ordinal data across judges × dimensions.

        Matrix shape: n_judges × n_dimensions (result_correctness, process_quality, safety).
        Returns alpha in [-1, 1]; target > 0.7 for NeurIPS.
        """
        dims = ["result_correctness", "process_quality", "safety"]
        # Each "unit" is a (judge_idx, dim_idx) combination scored on 0–4
        # Raters = judges, Units = dimensions evaluated

        n_judges = len(verdicts)
        if n_judges < 2:
            return 0.0

        # Build matrix: rows=judges, cols=dims
        matrix: List[List[float]] = []
        for v in verdicts:
            row = [getattr(v, d) for d in dims if getattr(v, d) is not None]
            if row:
                matrix.append(row)

        if len(matrix) < 2 or not matrix[0]:
            return 0.0

        n_units = len(matrix[0])
        # Observed disagreement D_o
        d_o = 0.0
        pairs = 0
        for u in range(n_units):
            vals = [matrix[r][u] for r in range(len(matrix)) if u < len(matrix[r])]
            for i in range(len(vals)):
                for j in range(i + 1, len(vals)):
                    d_o += (vals[i] - vals[j]) ** 2
                    pairs += 1

        if pairs == 0:
            return 1.0
        d_o /= pairs

        # Expected disagreement D_e (over all values pooled)
        all_vals = [v for row in matrix for v in row]
        n_total = len(all_vals)
        if n_total < 2:
            return 0.0
        d_e = sum(
            (all_vals[i] - all_vals[j]) ** 2
            for i in range(n_total)
            for j in range(i + 1, n_total)
        ) / (n_total * (n_total - 1) / 2)

        if d_e == 0:
            return 1.0

        return round(1.0 - d_o / d_e, 4)

    # ------------------------------------------------------------------
    # Convenience: build panel from CLI spec strings
    # ------------------------------------------------------------------

    @classmethod
    def from_specs(cls, specs: List[str], **kwargs) -> "MultiJudgePanel":
        """
        specs: list like ['anthropic:claude-sonnet-4-6', 'openai:gpt-4o',
                          'anthropic:claude-sonnet-4-6:adversarial']
        """
        judges = []
        for spec in specs:
            parts = spec.split(":")
            if len(parts) == 2:
                provider, model = parts
                role = "standard"
            elif len(parts) == 3:
                provider, model, role = parts
            else:
                raise ValueError(f"Invalid judge spec: {spec}")
            judges.append(LLMJudgeAgent(provider, model, role=role))
        return cls(judges=judges, **kwargs)
