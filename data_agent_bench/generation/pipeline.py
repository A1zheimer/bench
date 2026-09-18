"""
GenerationPipeline: orchestrates batch task generation with retries,
validation, and optional reviewer verification.
"""
from __future__ import annotations

import glob
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .task_generator_agent import TaskGeneratorAgent, GeneratedTask
from .reviewer_agent import ReviewerAgent
from .data_critic_agent import DataCriticAgent
from .red_team_agent import RedTeamAgent
from .quality_gate import GenerationQualityGate, GenerationGateResult

logger = logging.getLogger(__name__)


@dataclass
class GenerationSpec:
    """Specification for a batch of tasks to generate."""
    domain: str
    difficulty: str
    count: int
    tags: List[str] = field(default_factory=list)


@dataclass
class GenerationReport:
    """Summary of a batch generation run."""
    total_requested: int
    total_generated: int
    total_verified: int
    total_reviewed: int
    total_review_passed: int
    total_rejected: int
    failed_tasks: List[Dict[str, str]]
    task_ids: List[str]
    task_paths: List[str]

    def summary(self) -> str:
        lines = [
            f"Generation Report",
            f"  Requested:      {self.total_requested}",
            f"  Generated:      {self.total_generated}",
            f"  Verified:       {self.total_verified}",
        ]
        if self.total_reviewed > 0:
            lines.append(f"  Reviewed:       {self.total_reviewed}")
            lines.append(f"  Review Passed:  {self.total_review_passed}")
        if self.failed_tasks:
            lines.append(f"  Failed:         {len(self.failed_tasks)}")
            for ft in self.failed_tasks[:5]:
                lines.append(f"    - {ft.get('id', '?')}: {ft.get('error', '?')}")
        if self.total_rejected:
            lines.append(f"  Quality Rejected: {self.total_rejected}")
        lines.append(f"  Task IDs:       {', '.join(self.task_ids[:10])}")
        if len(self.task_ids) > 10:
            lines.append(f"                  ... and {len(self.task_ids) - 10} more")
        return "\n".join(lines)


class GenerationPipeline:
    """
    Orchestrates batch task generation:
      1. Auto-detect starting task number from existing tasks
      2. Generate tasks via TaskGeneratorAgent
      3. Optionally validate via ReviewerAgent
      4. Write to disk
      5. Report results
    """

    def __init__(
        self,
        generator: TaskGeneratorAgent,
        reviewer: Optional[ReviewerAgent] = None,
        critic: Optional[DataCriticAgent] = None,
        red_team: Optional[RedTeamAgent] = None,
        max_retries_per_task: int = 3,
        quality_gate: Optional[GenerationQualityGate] = None,
        enforce_quality_gate: bool = True,
    ) -> None:
        self.generator = generator
        self.reviewer = reviewer
        self.critic = critic
        self.red_team = red_team
        self.max_retries_per_task = max_retries_per_task
        self.quality_gate = quality_gate or GenerationQualityGate.formal()
        self.enforce_quality_gate = enforce_quality_gate

    def run(self, specs: List[GenerationSpec]) -> GenerationReport:
        """
        Generate all tasks specified in ``specs``.

        Args:
            specs: List of GenerationSpec, each specifying domain/difficulty/count.

        Returns:
            GenerationReport with counts and task IDs.
        """
        # Auto-detect starting task number
        task_number = self._detect_next_task_number()

        total_requested = sum(s.count for s in specs)
        generated: List[GeneratedTask] = []
        failed: List[Dict[str, str]] = []
        task_paths: List[str] = []
        rejected_count = 0

        import json
        import pathlib
        taxonomy_path = pathlib.Path(__file__).parent / "taxonomy" / "task_taxonomy.json"
        taxonomy = {}
        if taxonomy_path.exists():
            try:
                with open(taxonomy_path, "r", encoding="utf-8") as f:
                    taxonomy = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load taxonomy: {e}")

        for spec in specs:
            logger.info(
                "Generating %d tasks: %s / %s",
                spec.count, spec.domain, spec.difficulty,
            )
            
            # Fetch tags from taxonomy if none provided
            domain_tags = taxonomy.get(spec.domain, taxonomy.get("Generic", []))
            
            for i in range(spec.count):
                current_tags = spec.tags if spec.tags else []
                if not current_tags and domain_tags:
                    import random
                    current_tags = [random.choice(domain_tags)]
                    logger.info("  Selected taxonomy paradigm: %s", current_tags[0])
                
                task = self._generate_with_retry(
                    domain=spec.domain,
                    difficulty=spec.difficulty,
                    task_number=task_number,
                    tags=current_tags if current_tags else None,
                )
                if task is not None:
                    gate_result = self.quality_gate.evaluate(task)
                    task.ground_truth.setdefault("generation_quality", gate_result.to_dict())
                    if not gate_result.accepted:
                        rejected_count += 1
                        logger.warning(
                            "  Quality gate rejected %s: %s",
                            task.instance_id, "; ".join(gate_result.issues),
                        )
                        if self.enforce_quality_gate:
                            failed.append({
                                "id": task.instance_id,
                                "error": "quality_gate_rejected: " + "; ".join(gate_result.issues),
                            })
                            task_number += 1
                            continue

                    # Write to disk
                    try:
                        path = self.generator.package_to_disk(task)
                        
                        if self.critic:
                            import pathlib
                            data_path = pathlib.Path(path) / "data" / "dataset.csv"
                            if data_path.exists():
                                preview = data_path.read_text(encoding="utf-8")[:1000]
                            else:
                                preview = task.task_json.get("context", {}).get("dataset_preview", "")
                            is_valid = self.critic.evaluate_data(task.task_json, preview)
                            if not is_valid:
                                logger.warning("  DataCritic rejected task %s", task.instance_id)
                        
                        task_paths.append(path)
                        generated.append(task)
                        logger.info(
                            "  [%d/%d] %s (verified=%s)",
                            i + 1, spec.count, task.instance_id, task.verified,
                        )
                    except Exception as exc:
                        logger.error("  Packaging failed for task %d: %s", task_number, exc)
                        failed.append({"id": f"task_{task_number}", "error": str(exc)})
                else:
                    failed.append({
                        "id": f"task_{task_number}",
                        "error": f"Generation failed after {self.max_retries_per_task} retries",
                    })

                task_number += 1

        # Optional reviewer pass
        reviewed_count = 0
        review_passed_count = 0
        if self.reviewer and generated:
            logger.info("Running reviewer on %d generated tasks...", len(generated))
            for task in generated:
                try:
                    result = self.reviewer.review(
                        task_json=task.task_json,
                        ground_truth=task.ground_truth,
                    )
                    reviewed_count += 1
                    if result.passed:
                        review_passed_count += 1
                    else:
                        logger.warning(
                            "  Reviewer FAILED %s: score=%.2f",
                            task.instance_id, result.match_score,
                        )
                except Exception as exc:
                    logger.warning("  Reviewer error for %s: %s", task.instance_id, exc)

        return GenerationReport(
            total_requested=total_requested,
            total_generated=len(generated),
            total_verified=sum(1 for t in generated if t.verified),
            total_reviewed=reviewed_count,
            total_review_passed=review_passed_count,
            total_rejected=rejected_count,
            failed_tasks=failed,
            task_ids=[t.instance_id for t in generated],
            task_paths=task_paths,
        )

    def _generate_with_retry(
        self,
        domain: str,
        difficulty: str,
        task_number: int,
        tags: Optional[List[str]],
    ) -> Optional[GeneratedTask]:
        """Try generating a task up to max_retries times."""
        for attempt in range(self.max_retries_per_task):
            try:
                task = self.generator.generate(
                    domain=domain,
                    difficulty=difficulty,
                    task_number=task_number,
                    tags=tags,
                )
                
                return task

            except Exception as exc:
                logger.warning(
                    "  Attempt %d/%d failed for task %d: %s",
                    attempt + 1, self.max_retries_per_task, task_number, exc,
                )
        return None

    def _detect_next_task_number(self) -> int:
        """Scan existing task directories to find the next available number."""
        output_root = str(self.generator.output_root)
        existing = glob.glob(f"{output_root}/DS_TASK_*")
        max_num = 0
        for path in existing:
            match = re.search(r"DS_TASK_(\d+)", path)
            if match:
                num = int(match.group(1))
                max_num = max(max_num, num)
        return max_num + 1
