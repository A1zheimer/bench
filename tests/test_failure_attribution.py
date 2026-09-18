from __future__ import annotations

from datetime import datetime

from data_agent_bench.evaluation.aggregator import ScoreAggregator
from data_agent_bench.models.report import DeterministicScore, ProcessScore, RiskScore
from data_agent_bench.models.trace import ActionType, AgentTrace, TerminationInfo, TraceStep


def _trace(reason: str = "completed", steps: list[TraceStep] | None = None) -> AgentTrace:
    return AgentTrace(
        instance_id="DS_TASK_001",
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow(),
        steps=steps or [],
        termination=TerminationInfo(reason=reason, forced=False, details="test"),
    )


def _error_step(message: str) -> TraceStep:
    return TraceStep(
        step=1,
        timestamp=datetime.utcnow(),
        action_type=ActionType.ERROR,
        action="LLM API Error",
        observation="",
        thought=message,
    )


def _det(score: float) -> DeterministicScore:
    return DeterministicScore(
        exact_match=False,
        numeric_match=False,
        numeric_tolerance=0.0,
        similarity_score=score,
        field_scores={},
    )


def _proc(score: float) -> ProcessScore:
    return ProcessScore(
        planning_score=score,
        tool_efficiency=score,
        error_recovery_score=score,
        feedback_loop_score=score,
        step_utilization=score,
        redundant_action_ratio=0.0,
    )


def _risk(compliant: bool = True) -> RiskScore:
    return RiskScore(
        safety_compliant=compliant,
        violations=[] if compliant else ["Budget exceeded"],
        high_freq_tool_calls=False,
        resource_within_budget=compliant,
        risky_patterns=[],
        risk_level="none" if compliant else "high",
    )


def test_completed_low_accuracy_is_result_failure_not_timeout() -> None:
    metrics, failure = ScoreAggregator().aggregate(
        task=None,  # type: ignore[arg-type]
        trace=_trace("completed"),
        det=_det(0.2),
        proc=_proc(0.8),
        risk=_risk(),
    )
    assert metrics.completion_rate < 1.0
    assert failure is not None
    assert failure.primary_cause == "result"


def test_non_completed_trace_keeps_termination_reason() -> None:
    _, failure = ScoreAggregator().aggregate(
        task=None,  # type: ignore[arg-type]
        trace=_trace("dead_loop"),
        det=_det(0.8),
        proc=_proc(0.8),
        risk=_risk(),
    )
    assert failure is not None
    assert failure.primary_cause == "dead_loop"


def test_safety_failure_precedes_low_process_on_completed_trace() -> None:
    _, failure = ScoreAggregator().aggregate(
        task=None,  # type: ignore[arg-type]
        trace=_trace("completed"),
        det=_det(0.8),
        proc=_proc(0.2),
        risk=_risk(compliant=False),
    )
    assert failure is not None
    assert failure.primary_cause == "safety"


def test_read_timeout_error_is_infrastructure_failure() -> None:
    _, failure = ScoreAggregator().aggregate(
        task=None,  # type: ignore[arg-type]
        trace=_trace("completed", [_error_step("Error calling LLM: The read operation timed out")]),
        det=_det(0.2),
        proc=_proc(0.8),
        risk=_risk(),
    )
    assert failure is not None
    assert failure.primary_cause == "api_read_timeout"


def test_llmbox_500_error_is_infrastructure_failure() -> None:
    _, failure = ScoreAggregator().aggregate(
        task=None,  # type: ignore[arg-type]
        trace=_trace("timeout", [_error_step('llmbox request failed: 500 {"type":"api_error"}')]),
        det=_det(0.8),
        proc=_proc(0.8),
        risk=_risk(),
    )
    assert failure is not None
    assert failure.primary_cause == "api_error"
