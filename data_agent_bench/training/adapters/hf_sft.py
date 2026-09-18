from __future__ import annotations

import time
from typing import List

from .base import BaseTrainingAdapter
from ..schemas import TrainRecord, TrainResult


class HFSFTTrainingAdapter(BaseTrainingAdapter):
    """
    Minimal stub adapter for async training integration.

    This adapter currently acts as a lightweight placeholder so the
    generation-time training pipeline can run end-to-end without requiring
    heavy runtime dependencies at this stage.
    """

    def __init__(self, model_ref: str) -> None:
        self.model_ref = model_ref

    def train_batch(self, records: List[TrainRecord]) -> TrainResult:
        t0 = time.perf_counter()
        # TODO: Replace with TRL/PEFT SFTTrainer update steps.
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return TrainResult(
            success=True,
            consumed=len(records),
            latency_ms=elapsed_ms,
            loss=None,
            error="",
        )
