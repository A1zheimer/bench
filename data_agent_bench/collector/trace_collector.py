from __future__ import annotations

import json
import logging
import pathlib
import threading
from typing import IO, Optional

from ..models.trace import AgentTrace, TraceStep

logger = logging.getLogger(__name__)


class TraceCollector:
    """
    Real-time trace recorder.

    - Appends steps to the in-memory AgentTrace
    - Streams each step as newline-delimited JSON to <run_dir>/trace.jsonl
    - Thread-safe: record() acquires a lock so monitor threads can safely
      read trace.steps concurrently
    """

    def __init__(self, trace: AgentTrace, run_dir: pathlib.Path) -> None:
        self._trace = trace
        self._run_dir = run_dir
        self._lock = threading.Lock()
        self._stream: Optional[IO[str]] = None

    def open(self) -> None:
        self._run_dir.mkdir(parents=True, exist_ok=True)
        self._stream = open(self._run_dir / "trace.jsonl", "w", encoding="utf-8")
        logger.debug("Trace stream opened: %s", self._run_dir / "trace.jsonl")

    def close(self) -> None:
        if self._stream:
            self._stream.flush()
            self._stream.close()
            self._stream = None

    def record(self, step: TraceStep) -> None:
        with self._lock:
            self._trace.steps.append(step)
            if self._stream:
                self._stream.write(
                    json.dumps(step.to_dict(), ensure_ascii=False, default=str)
                )
                self._stream.write("\n")
                self._stream.flush()
        logger.debug("Step %d recorded: %s", step.step, step.action_type.value)
