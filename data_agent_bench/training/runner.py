from __future__ import annotations

import json
import logging
import pathlib
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from .adapters.base import BaseTrainingAdapter
from .schemas import TrainRecord

logger = logging.getLogger(__name__)


@dataclass
class TrainSummary:
    model_ref: str
    data_path: str
    total_examples: int
    total_batches: int
    consumed_examples: int
    wall_time_seconds: float
    status: str


class TrainingRunner:
    """Offline trainer that consumes JSONL SFT data and runs batch updates."""

    def __init__(self, adapter: BaseTrainingAdapter, batch_size: int = 32) -> None:
        self.adapter = adapter
        self.batch_size = max(1, int(batch_size))

    def train_from_jsonl(self, data_path: str, model_ref: str) -> TrainSummary:
        t0 = time.perf_counter()
        path = pathlib.Path(data_path)
        if not path.exists():
            raise FileNotFoundError(f"Training data not found: {data_path}")

        total = 0
        consumed = 0
        batches = 0
        batch: List[TrainRecord] = []

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except Exception:
                    continue

                record = self._to_train_record(payload, total)
                if record is None:
                    continue

                total += 1
                batch.append(record)
                if len(batch) >= self.batch_size:
                    result = self.adapter.train_batch(batch)
                    batches += 1
                    if result.success:
                        consumed += result.consumed
                    else:
                        logger.warning("Batch training failed: %s", result.error)
                    batch = []

        if batch:
            result = self.adapter.train_batch(batch)
            batches += 1
            if result.success:
                consumed += result.consumed
            else:
                logger.warning("Final batch training failed: %s", result.error)

        elapsed = time.perf_counter() - t0
        return TrainSummary(
            model_ref=model_ref,
            data_path=str(path),
            total_examples=total,
            total_batches=batches,
            consumed_examples=consumed,
            wall_time_seconds=elapsed,
            status="ok" if consumed > 0 else "no_effective_data",
        )

    def _to_train_record(self, payload: Dict[str, Any], idx: int) -> Optional[TrainRecord]:
        # OpenAI format
        if "messages" in payload and isinstance(payload["messages"], list):
            user_text = ""
            assistant_text = ""
            for msg in payload["messages"]:
                if not isinstance(msg, dict):
                    continue
                role = msg.get("role")
                content = str(msg.get("content", ""))
                if role == "user" and not user_text:
                    user_text = content
                elif role == "assistant":
                    assistant_text = content
            if user_text and assistant_text:
                return TrainRecord(
                    task_id=f"jsonl_{idx}",
                    instruction=user_text,
                    response=assistant_text,
                    quality_tier="gold",
                    verified=True,
                    metadata={"source": "openai_jsonl"},
                )

        # Alpaca format
        if "instruction" in payload and "output" in payload:
            instruction = str(payload.get("instruction", ""))
            extra_input = str(payload.get("input", ""))
            if extra_input:
                instruction = f"{instruction}\n\n{extra_input}".strip()
            response = str(payload.get("output", ""))
            if instruction and response:
                return TrainRecord(
                    task_id=f"jsonl_{idx}",
                    instruction=instruction,
                    response=response,
                    quality_tier="gold",
                    verified=True,
                    metadata={"source": "alpaca_jsonl"},
                )

        # ShareGPT format
        if "conversations" in payload and isinstance(payload["conversations"], list):
            human = ""
            gpt = ""
            for msg in payload["conversations"]:
                if not isinstance(msg, dict):
                    continue
                frm = msg.get("from")
                val = str(msg.get("value", ""))
                if frm == "human" and not human:
                    human = val
                elif frm == "gpt":
                    gpt = val
            if human and gpt:
                return TrainRecord(
                    task_id=f"jsonl_{idx}",
                    instruction=human,
                    response=gpt,
                    quality_tier="gold",
                    verified=True,
                    metadata={"source": "sharegpt_jsonl"},
                )

        return None
