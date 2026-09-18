from __future__ import annotations

import dataclasses
import json
import logging
import pathlib
from typing import Dict, Iterator, List, Optional

from ..models.task import Difficulty, Domain, TaskInput
from .provenance import task_dir_is_verified
from .schema_validator import SchemaValidator

logger = logging.getLogger(__name__)


class TaskRepository:
    """
    Discovers, validates, and serves TaskInput objects from a tasks/ directory.

    Directory contract:
        <tasks_root>/<task_dir>/
            task.json              -- input protocol JSON
            data/                  -- dataset files referenced in context
            ground_truth/
                expected_output.json
    """

    def __init__(
        self,
        tasks_root: str,
        *,
        require_verified: bool = False,
        warn_unverified: bool = True,
    ) -> None:
        self._root = pathlib.Path(tasks_root)
        self._cache: Dict[str, TaskInput] = {}
        self.require_verified = require_verified
        self.warn_unverified = warn_unverified
        self.skipped_unverified: List[str] = []
        self._load_all()

    def _load_all(self) -> None:
        if not self._root.exists():
            logger.warning("Tasks root does not exist: %s", self._root)
            return

        for task_dir in sorted(self._root.iterdir()):
            if not task_dir.is_dir():
                continue
            task_file = task_dir / "task.json"
            if not task_file.exists():
                logger.warning("No task.json in %s, skipping", task_dir)
                continue
            if self.require_verified and not task_dir_is_verified(task_dir):
                self.skipped_unverified.append(task_dir.name)
                if self.warn_unverified:
                    logger.warning(
                        "Task %s is missing verified GT provenance; skipping formal load",
                        task_dir.name,
                    )
                continue
            try:
                raw = json.loads(task_file.read_text(encoding="utf-8"))
                SchemaValidator.validate_task_input(raw)
                task = TaskInput.from_dict(raw)
                # Inject ground truth path if present
                gt = task_dir / "ground_truth" / "expected_output.json"
                if gt.exists():
                    task = dataclasses.replace(task, ground_truth_path=str(gt))
                # Store task directory so executor can resolve data paths
                task = dataclasses.replace(task, task_dir=str(task_dir))
                self._cache[task.instance_id] = task
                logger.debug("Loaded task: %s", task.instance_id)
            except Exception as exc:
                logger.error("Failed to load task from %s: %s", task_dir, exc)

    def get(self, instance_id: str) -> TaskInput:
        if instance_id not in self._cache:
            raise KeyError(f"Task '{instance_id}' not found in repository")
        return self._cache[instance_id]

    def iter_all(self) -> Iterator[TaskInput]:
        yield from self._cache.values()

    def iter_by_domain(self, domain: Domain) -> Iterator[TaskInput]:
        for task in self._cache.values():
            if task.task_metadata.domain == domain:
                yield task

    def iter_by_difficulty(self, difficulty: Difficulty) -> Iterator[TaskInput]:
        for task in self._cache.values():
            if task.task_metadata.difficulty == difficulty:
                yield task

    def list_ids(self) -> List[str]:
        return sorted(self._cache.keys())

    def count(self) -> int:
        return len(self._cache)
