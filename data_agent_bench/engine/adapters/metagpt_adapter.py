"""MetaGPT DataInterpreter adapter — calls Docker container via HTTP."""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

import urllib.request
import urllib.error

from ...models.task import TaskInput
from ...models.trace import ActionType, TraceStep
from ..agent_interface import AgentAction, AgentInterface

logger = logging.getLogger(__name__)

METAGPT_URL = os.environ.get("METAGPT_URL", "http://localhost:8100")


class MetaGPTAdapter(AgentInterface):
    """Wraps MetaGPT DataInterpreter running in a Docker container."""

    def __init__(self, model_id: str = "gpt-4o", temperature: float = 0.0) -> None:
        self.model_id = model_id
        self.temperature = temperature
        self._done: bool = False
        self._prompt: str = ""
        self._dataset_preview: str = ""
        self._expert_knowledge: str = ""
        self._task_id: str = ""
        self._ran: bool = False
        self._data_path: Optional[str] = None

    def reset(self, task: TaskInput) -> None:
        self._task_id = task.instance_id
        self._prompt = task.context.problem_statement
        self._dataset_preview = task.context.dataset_preview or ""
        self._expert_knowledge = task.context.expert_knowledge or ""
        # 容器内数据挂载在 /data/tasks/<task_id>/data/
        self._data_path = f"/data/tasks/{task.instance_id}/data/dataset.csv"
        self._done = False
        self._ran = False

    def act(
        self,
        step_number: int,
        observation: str,
        trace_so_far: List[TraceStep],
    ) -> AgentAction:
        if not self._ran:
            payload = json.dumps({
                "task_id": self._task_id,
                "problem_statement": self._prompt,
                "dataset_preview": self._dataset_preview,
                "expert_knowledge": self._expert_knowledge,
                "data_path": self._data_path,
            }).encode("utf-8")

            url = f"{METAGPT_URL}/run_task"
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            try:
                with urllib.request.urlopen(req, timeout=300) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
            except urllib.error.URLError as e:
                self._ran = True
                self._done = True
                return AgentAction(
                    action_type=ActionType.ERROR,
                    action=f"MetaGPT container unreachable: {e}",
                    thought="Is the container running? Try: docker compose up metagpt",
                )

            self._ran = True
            self._done = True

            if result.get("status") == "error":
                return AgentAction(
                    action_type=ActionType.ERROR,
                    action=f"MetaGPT error: {result.get('error', 'unknown')}",
                    thought=result.get("error", ""),
                )

            return AgentAction(
                action_type=ActionType.FINAL_ANSWER,
                action=result.get("final_answer", ""),
                thought=f"DataInterpreter completed with {len(result.get('steps', []))} steps",
            )

        self._done = True
        return AgentAction(
            action_type=ActionType.FINAL_ANSWER,
            action="DataInterpreter already finished",
            thought="No further actions.",
        )

    def is_done(self) -> bool:
        return self._done
