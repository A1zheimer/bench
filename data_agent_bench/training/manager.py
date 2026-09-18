from __future__ import annotations

import json
import logging
import pathlib
import queue
import threading
import time
from typing import List, Optional

from .adapters.base import BaseTrainingAdapter
from .schemas import TrainRecord

logger = logging.getLogger(__name__)


class TrainingManager:
    """Async micro-batch training manager for generation-time updates."""

    def __init__(
        self,
        adapter: BaseTrainingAdapter,
        micro_batch_size: int = 8,
        flush_seconds: int = 60,
        max_queue: int = 1024,
        dead_letter_path: str = "./sft_data/dead_letter.jsonl",
    ) -> None:
        self.adapter = adapter
        self.micro_batch_size = max(1, int(micro_batch_size))
        self.flush_seconds = max(1, int(flush_seconds))
        self._queue: "queue.Queue[TrainRecord]" = queue.Queue(maxsize=max_queue)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._dead_letter_path = pathlib.Path(dead_letter_path)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._worker_loop, daemon=True, name="training-worker")
        self._thread.start()

    def enqueue(self, record: TrainRecord) -> None:
        try:
            self._queue.put_nowait(record)
        except queue.Full:
            logger.warning("Training queue full, dropping sample: %s", record.task_id)
            self._write_dead_letter(record, "queue_full")

    def flush_and_shutdown(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=30)
        self._drain_once(force=True)

    def _worker_loop(self) -> None:
        last_flush = time.time()
        while not self._stop_event.is_set():
            if self._queue.qsize() >= self.micro_batch_size:
                self._drain_once(force=False)
                last_flush = time.time()
                continue

            if (time.time() - last_flush) >= self.flush_seconds and not self._queue.empty():
                self._drain_once(force=True)
                last_flush = time.time()
                continue

            time.sleep(0.2)

    def _drain_once(self, force: bool) -> None:
        records: List[TrainRecord] = []
        target = self.micro_batch_size if not force else max(1, self._queue.qsize())

        while len(records) < target:
            try:
                records.append(self._queue.get_nowait())
            except queue.Empty:
                break

        if not records:
            return

        try:
            result = self.adapter.train_batch(records)
            if result.success:
                logger.info(
                    "Training batch consumed=%d latency_ms=%.1f",
                    result.consumed,
                    result.latency_ms,
                )
            else:
                logger.warning("Training batch failed: %s", result.error)
                for r in records:
                    self._write_dead_letter(r, result.error or "train_failed")
        except Exception as exc:
            logger.warning("Training adapter error: %s", exc)
            for r in records:
                self._write_dead_letter(r, str(exc))

    def _write_dead_letter(self, record: TrainRecord, reason: str) -> None:
        self._dead_letter_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "reason": reason,
            "task_id": record.task_id,
            "instruction": record.instruction,
            "response": record.response,
            "quality_tier": record.quality_tier,
            "verified": record.verified,
            "metadata": record.metadata,
            "created_at": record.created_at,
        }
        with open(self._dead_letter_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
