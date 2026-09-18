from __future__ import annotations

import abc
from typing import Any, Dict, Optional

from ..models.task import TaskInput
from ..models.trace import AgentTrace


class BaseEvaluator(abc.ABC):
    """All evaluators share this interface. Evaluators are stateless."""

    @abc.abstractmethod
    def evaluate(
        self,
        task: TaskInput,
        trace: AgentTrace,
        final_output: Dict[str, Any],
        ground_truth: Optional[Dict[str, Any]],
    ) -> Any:
        """Return evaluator-specific score dataclass."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Evaluator name."""
