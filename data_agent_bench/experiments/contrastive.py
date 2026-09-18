"""
ContrastiveExperiment: Orchestrates matched-pair experiments
(clean vs semantically-obfuscated) for anti-memorization evaluation.

Usage:
    experiment = ContrastiveExperiment(
        agent_specs=["openai:gpt-4o-mini", "openai:gpt-4o"],
        judge_specs=["openai:gpt-4o"],
        tasks_dir="./tasks",
        output_dir="./experiments",
        db_path="experiments.db",
    )
    results = experiment.run_batch(levels=[1, 2, 3])
"""
from __future__ import annotations

import copy
import json
import logging
import pathlib
import shutil
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

from ..models.constants import CAS_WEIGHTS
from ..database.report_db import ReportDatabase
from ..engine.executor import BenchmarkExecutor
from ..engine.agents import build_agent
from ..evaluation.aggregator import ScoreAggregator
from ..evaluation.deterministic import DeterministicEvaluator
from ..evaluation.process_auditor import ProcessAuditor
from ..evaluation.risk_assessor import RiskAssessor
from ..evaluation.trace_grounding import TraceGroundingVerifier
from ..generation.red_team_agent import RedTeamAgent
from ..models.report import EvaluationReport, MetricBundle
from ..models.task import TaskInput
from ..reporting.json_reporter import JSONReporter
from ..repository.task_repo import TaskRepository

logger = logging.getLogger(__name__)


@dataclass
class PairedResult:
    """Captures the delta between a clean and perturbed run."""

    instance_id: str
    agent_model: str
    condition: str  # "L1" | "L2" | "L3"
    metrics_clean: Dict[str, Any]
    metrics_perturbed: Dict[str, Any]
    delta_accuracy: float
    delta_process: float
    delta_cas: float
    report_clean_id: str
    report_perturbed_id: str


def _calc_cas(metrics: MetricBundle) -> float:
    return (
        CAS_WEIGHTS["accuracy"] * metrics.result_accuracy
        + CAS_WEIGHTS["process"] * metrics.process_quality
        + CAS_WEIGHTS["safety"] * metrics.safety_score
    )


class ContrastiveExperiment:
    """
    Runs matched-pair experiments: same task, clean vs obfuscated.

    For each (task, agent, level) triple:
      1. Run agent on clean task → clean report
      2. Apply RedTeamAgent perturbation at level L
      3. Run agent on perturbed task → perturbed report
      4. Compute delta metrics
    """

    def __init__(
        self,
        agent_specs: List[str],
        judge_specs: Optional[List[str]] = None,
        tasks_dir: str = "./tasks",
        output_dir: str = "./experiments",
        db_path: str = "experiments.db",
        task_ids: Optional[List[str]] = None,
        temperature: float = 0.0,
    ):
        self.agent_specs = agent_specs
        self.judge_specs = judge_specs or []
        self.tasks_dir = pathlib.Path(tasks_dir)
        self.output_dir = pathlib.Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.db = ReportDatabase(db_path)
        self.repo = TaskRepository(str(self.tasks_dir))
        self.task_ids = set(task_ids) if task_ids else None
        self.temperature = temperature

    def run_batch(self, levels: Optional[List[int]] = None) -> List[PairedResult]:
        """
        Run contrastive experiments for all tasks × agents × levels.

        Args:
            levels: Perturbation levels to test (default [1, 2, 3]).

        Returns:
            List of PairedResult with delta metrics.
        """
        levels = levels or [1, 2, 3]
        # Remove 0 from levels list (0 = clean baseline, always run)
        levels = [lv for lv in levels if lv > 0]

        results: List[PairedResult] = []

        all_tasks = list(self.repo.iter_all())
        if self.task_ids:
            all_tasks = [t for t in all_tasks if t.instance_id in self.task_ids]

        for task in all_tasks:
            # Skip already-perturbed tasks
            if hasattr(task, "context") and getattr(task.context, "obfuscation_level", None):
                continue

            for agent_spec in self.agent_specs:
                logger.info(
                    "=== Contrastive: %s | agent=%s ===",
                    task.instance_id, agent_spec,
                )

                # 1. Run clean baseline
                report_clean = self._run_condition(
                    task, agent_spec, condition="clean", level=0
                )
                if report_clean is None:
                    logger.warning("Clean run failed for %s, skipping", task.instance_id)
                    continue

                # 2. Run each perturbation level
                for level in levels:
                    report_pert = self._run_condition(
                        task, agent_spec, condition=f"L{level}", level=level
                    )
                    if report_pert is None:
                        logger.warning(
                            "L%d run failed for %s, skipping", level, task.instance_id
                        )
                        continue

                    # Link paired reports
                    if report_clean.paired_report_id:
                        report_clean.paired_report_id += f",{report_pert.report_id}"
                    else:
                        report_clean.paired_report_id = report_pert.report_id
                    report_pert.paired_report_id = report_clean.report_id

                    # Compute deltas
                    cas_clean = _calc_cas(report_clean.metrics)
                    cas_pert = _calc_cas(report_pert.metrics)

                    paired = PairedResult(
                        instance_id=task.instance_id,
                        agent_model=agent_spec,
                        condition=f"L{level}",
                        metrics_clean=report_clean.metrics.to_dict(),
                        metrics_perturbed=report_pert.metrics.to_dict(),
                        delta_accuracy=(
                            report_clean.metrics.result_accuracy
                            - report_pert.metrics.result_accuracy
                        ),
                        delta_process=(
                            report_clean.metrics.process_quality
                            - report_pert.metrics.process_quality
                        ),
                        delta_cas=cas_clean - cas_pert,
                        report_clean_id=report_clean.report_id,
                        report_perturbed_id=report_pert.report_id,
                    )
                    results.append(paired)
                    logger.info(
                        "Delta CAS (%s, L%d): %.4f",
                        task.instance_id, level, paired.delta_cas,
                    )

        logger.info("Contrastive batch complete: %d paired results", len(results))
        return results

    def _run_condition(
        self,
        base_task: TaskInput,
        agent_spec: str,
        condition: str,
        level: int,
    ) -> Optional[EvaluationReport]:
        """Run a single (task, agent, condition) and return EvaluationReport."""
        task = copy.deepcopy(base_task)
        task_id_suffix = f"{task.instance_id}_{condition}_{agent_spec.replace(':', '_')}"

        # Resolve data path
        task_dir = self.tasks_dir / base_task.instance_id
        data_path = task_dir / "data" / "dataset.csv"

        if level > 0:
            # Apply perturbation
            if not data_path.exists():
                logger.warning("No dataset.csv for %s", base_task.instance_id)
                return None

            df = pd.read_csv(data_path)
            difficulty = base_task.task_metadata.difficulty.value
            red_team = RedTeamAgent(
                provider="openai", model_id="gpt-4o",
                temperature=0.3, obfuscation_seed=42,
            )

            # Build task_json from task for perturbation
            task_json = self._task_to_json(task)
            try:
                perturbed_task, perturbed_df = red_team.perturb_level(
                    task_json, df, level=level, difficulty=difficulty,
                )
            except Exception as exc:
                logger.error("RedTeam perturbation failed for %s at L%d: %s", task.instance_id, level, exc)
                return None
            task_json, df_perturbed = perturbed_task, perturbed_df

            # Write perturbed task to temp dir
            work_dir = self.output_dir / "temp_tasks" / task_id_suffix
            work_data_dir = work_dir / "data"
            work_data_dir.mkdir(parents=True, exist_ok=True)
            df_perturbed.to_csv(work_data_dir / "dataset.csv", index=False)

            with open(work_dir / "task.json", "w", encoding="utf-8") as f:
                json.dump(task_json, f, indent=2, ensure_ascii=False)

            # Copy ground truth
            gt_src = task_dir / "ground_truth"
            if gt_src.exists():
                shutil.copytree(gt_src, work_dir / "ground_truth", dirs_exist_ok=True)

            task_root = str(work_dir)
        else:
            task_root = str(task_dir)

        # Build agent & run
        try:
            agent = build_agent(agent_spec, temperature=self.temperature)
        except Exception as exc:
            logger.error("Failed to build agent %s: %s", agent_spec, exc)
            return None

        executor = BenchmarkExecutor(
            agent=agent,
            output_dir=str(self.output_dir / "runs"),
            task_root=task_root,
            model_id=agent_spec,
            temperature=self.temperature,
        )

        try:
            trace, final_output = executor.run(task)
        except Exception as exc:
            logger.error("Execution failed (%s, %s): %s", task.instance_id, condition, exc)
            return None

        # Evaluate
        ground_truth = None
        if task.ground_truth_path:
            try:
                ground_truth = json.loads(
                    pathlib.Path(task.ground_truth_path).read_text("utf-8")
                )
            except Exception as e:
                logger.warning("Could not load ground truth for %s: %s", task.instance_id, e)

        det_eval = DeterministicEvaluator()
        proc_eval = ProcessAuditor()
        risk_eval = RiskAssessor()
        trace_grounding_eval = TraceGroundingVerifier()
        aggregator = ScoreAggregator()

        det_score = det_eval.evaluate(task, trace, final_output, ground_truth)
        proc_score = proc_eval.evaluate(task, trace, final_output, ground_truth)
        risk_score = risk_eval.evaluate(task, trace, final_output, ground_truth)
        trace_grounding_score = trace_grounding_eval.evaluate(task, trace, final_output, ground_truth)
        metrics, failure = aggregator.aggregate(
            task, trace, det_score, proc_score, risk_score
        )

        # Build report
        reporter = JSONReporter()
        report = reporter.build(
            task, trace, final_output,
            det_score, proc_score, risk_score,
            metrics, failure,
            trace_grounding_score=trace_grounding_score,
        )
        report.experiment_condition = "clean" if level == 0 else "perturbed"
        report.perturbation_type = condition

        # Save
        out_path = self.output_dir / "reports" / task_id_suffix
        reporter.write(report, out_path)
        self.db.save_with_meta(
            report,
            task.task_metadata.domain.value,
            task.task_metadata.difficulty.value,
            model_id=agent_spec,
        )

        return report

    @staticmethod
    def _task_to_json(task: TaskInput) -> Dict[str, Any]:
        """Extract a mutable task_json dict from TaskInput."""
        return {
            "instance_id": task.instance_id,
            "context": {
                "problem_statement": task.context.problem_statement,
                "expert_knowledge": task.context.expert_knowledge,
                "data_files": task.context.data_files,
            },
            "task_metadata": {
                "domain": task.task_metadata.domain.value,
                "difficulty": task.task_metadata.difficulty.value,
                "tags": list(task.task_metadata.tags),
            },
        }
