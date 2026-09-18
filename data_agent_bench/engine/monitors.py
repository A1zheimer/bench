from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import List, Optional

from ..models.task import EnvironmentConfig
from ..models.trace import ActionType, AgentTrace, TerminationInfo, TraceStep

logger = logging.getLogger(__name__)


class SystemMonitor:
    """
    Daemon thread that monitors a running benchmark for anomalies.

    Checks (every POLL_INTERVAL_SECONDS):
      1. Dead loop: last DEAD_LOOP_WINDOW steps all have identical (action_type, action)
      2. Budget overrun: trace.total_cost_usd >= config.budget
      3. Timeout: elapsed wall time > config.timeout_seconds

    Also exposes observe(step) called synchronously after each step
    for immediate anomaly detection (token spike heuristics).
    """

    POLL_INTERVAL_SECONDS = 0.5
    DEAD_LOOP_WINDOW = 5
    TOKEN_SPIKE_FACTOR = 5.0

    def __init__(
        self,
        config: EnvironmentConfig,
        trace: AgentTrace,
        stop_event: threading.Event,
    ) -> None:
        self._config = config
        self._trace = trace
        self._stop_event = stop_event
        self._termination: Optional[TerminationInfo] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._token_history: List[int] = []

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def observe(self, step: TraceStep) -> None:
        """Called synchronously after each step for immediate anomaly detection."""
        step_tokens = step.tokens_in + step.tokens_out
        self._token_history.append(step_tokens)

        if len(self._token_history) >= 3:
            window = self._token_history[-3:]
            moving_avg = sum(window[:-1]) / (len(window) - 1)
            if moving_avg > 0 and step_tokens > moving_avg * self.TOKEN_SPIKE_FACTOR:
                info = TerminationInfo(
                    reason="anomaly",
                    forced=True,
                    details=f"Token spike at step {step.step}: {step_tokens} tokens "
                            f"vs moving avg {moving_avg:.0f}",
                )
                self._trigger(info)

    def get_termination_info(self) -> Optional[TerminationInfo]:
        return self._termination

    def _trigger(self, info: TerminationInfo) -> None:
        if not self._stop_event.is_set():
            self._termination = info
            self._stop_event.set()
            logger.warning("Monitor triggered: %s — %s", info.reason, info.details)

    def _monitor_loop(self) -> None:
        start = datetime.utcnow()
        while self._running and not self._stop_event.is_set():
            time.sleep(self.POLL_INTERVAL_SECONDS)

            # Budget check
            if self._trace.total_cost_usd >= self._config.budget:
                self._trigger(TerminationInfo(
                    reason="budget_exceeded",
                    forced=True,
                    details=f"Cost ${self._trace.total_cost_usd:.4f} >= budget ${self._config.budget}",
                ))
                break

            # Timeout check
            elapsed = (datetime.utcnow() - start).total_seconds()
            if elapsed > self._config.timeout_seconds:
                self._trigger(TerminationInfo(
                    reason="timeout",
                    forced=True,
                    details=f"Elapsed {elapsed:.1f}s > timeout {self._config.timeout_seconds}s",
                ))
                break

            # Dead loop check
            steps = self._trace.steps
            if len(steps) >= self.DEAD_LOOP_WINDOW:
                recent = steps[-self.DEAD_LOOP_WINDOW:]
                signatures = [(s.action_type, s.action[:50]) for s in recent]
                if len(set(signatures)) == 1:
                    self._trigger(TerminationInfo(
                        reason="dead_loop",
                        forced=True,
                        details=f"Last {self.DEAD_LOOP_WINDOW} steps are identical: {signatures[0]}",
                    ))
                    break
