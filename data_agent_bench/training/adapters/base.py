from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from ..schemas import TrainRecord, TrainResult


class BaseTrainingAdapter(ABC):
    """Adapter interface for batch training updates."""

    @abstractmethod
    def train_batch(self, records: List[TrainRecord]) -> TrainResult:
        raise NotImplementedError
