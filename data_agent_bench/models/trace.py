from __future__ import annotations

import dataclasses
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ActionType(str, Enum):
    THINK = "think"
    TOOL_CALL = "tool_call"
    CODE_EXEC = "code_exec"
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    WEB_SEARCH = "web_search"
    FINAL_ANSWER = "final_answer"
    ERROR = "error"


@dataclasses.dataclass
class TraceStep:
    step: int
    timestamp: datetime
    action_type: ActionType
    action: str
    observation: str
    thought: str = ""
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    tool_result: Optional[Any] = None
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "timestamp": self.timestamp.isoformat(),
            "action_type": self.action_type.value,
            "action": self.action,
            "observation": self.observation,
            "thought": self.thought,
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "tool_result": self.tool_result,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "latency_ms": self.latency_ms,
            "cost_usd": self.cost_usd,
            "metadata": self.metadata,
        }


@dataclasses.dataclass
class TerminationInfo:
    reason: str  # "completed", "max_steps", "budget_exceeded", "timeout", "dead_loop", "anomaly"
    forced: bool
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"reason": self.reason, "forced": self.forced, "details": self.details}


@dataclasses.dataclass
class AgentTrace:
    instance_id: str
    start_time: datetime
    end_time: Optional[datetime]
    steps: List[TraceStep]
    termination: Optional[TerminationInfo]
    wall_time_seconds: float = 0.0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def finalize(self) -> None:
        self.end_time = datetime.utcnow()
        self.wall_time_seconds = (self.end_time - self.start_time).total_seconds()
        self.total_tokens = sum(s.tokens_in + s.tokens_out for s in self.steps)
        self.total_cost_usd = sum(s.cost_usd for s in self.steps)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "steps": [s.to_dict() for s in self.steps],
            "termination": self.termination.to_dict() if self.termination else None,
            "wall_time_seconds": self.wall_time_seconds,
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost_usd,
        }
