from __future__ import annotations

from datetime import datetime

from data_agent_bench.evaluation.trace_integrity import TraceIntegrityValidator
from data_agent_bench.models.report import TraceIntegrityScore
from data_agent_bench.models.trace import ActionType, AgentTrace, TerminationInfo, TraceStep


def _code_step(step: int, code: str, result: str = "ok") -> TraceStep:
    return TraceStep(
        step=step,
        timestamp=datetime.utcnow(),
        action_type=ActionType.CODE_EXEC,
        action="Execute Code",
        observation=result,
        tool_name="python_repl",
        tool_args={"code": code},
        tool_result=result,
        tokens_in=10,
        tokens_out=5,
        cost_usd=0.01,
    )


def _trace(*steps: TraceStep) -> AgentTrace:
    trace = AgentTrace(
        instance_id="DS_TASK_001",
        start_time=datetime.utcnow(),
        end_time=None,
        steps=list(steps),
        termination=TerminationInfo(reason="completed", forced=False),
    )
    trace.finalize()
    return trace


def test_valid_trace_has_full_integrity() -> None:
    trace = _trace(_code_step(1, "import pandas as pd"), _code_step(2, "print(42)"))
    score = TraceIntegrityValidator().evaluate(
        task=None,  # type: ignore[arg-type]
        trace=trace,
        final_output={"execution_result": "answer: 42"},
        ground_truth=None,
    )
    assert isinstance(score, TraceIntegrityScore)
    assert score.integrity_score == 1.0
    assert score.step_sequence_valid is True
    assert score.required_fields_valid is True
    assert score.metric_consistency_valid is True
    assert score.final_answer_supported is True


def test_non_contiguous_steps_are_flagged() -> None:
    trace = _trace(_code_step(1, "x = 1"), _code_step(3, "print(x)"))
    score = TraceIntegrityValidator().evaluate(
        task=None,  # type: ignore[arg-type]
        trace=trace,
        final_output={"execution_result": "1"},
        ground_truth=None,
    )
    assert score.step_sequence_valid is False
    assert any(issue["check"] == "step_sequence" for issue in score.issues)


def test_missing_tool_fields_are_flagged() -> None:
    trace = _trace(
        TraceStep(
            step=1,
            timestamp=datetime.utcnow(),
            action_type=ActionType.CODE_EXEC,
            action="Execute Code",
            observation="",
        )
    )
    score = TraceIntegrityValidator().evaluate(
        task=None,  # type: ignore[arg-type]
        trace=trace,
        final_output={"execution_result": "done"},
        ground_truth=None,
    )
    assert score.required_fields_valid is False
    assert any(issue["check"] == "required_fields" for issue in score.issues)


def test_metric_mismatch_is_flagged() -> None:
    trace = _trace(_code_step(1, "print(1)"))
    trace.total_tokens += 1
    score = TraceIntegrityValidator().evaluate(
        task=None,  # type: ignore[arg-type]
        trace=trace,
        final_output={"execution_result": "1"},
        ground_truth=None,
    )
    assert score.metric_consistency_valid is False
    assert any(issue["check"] == "metric_consistency" for issue in score.issues)


def test_completed_trace_without_final_output_is_flagged() -> None:
    trace = _trace(_code_step(1, "print(1)"))
    score = TraceIntegrityValidator().evaluate(
        task=None,  # type: ignore[arg-type]
        trace=trace,
        final_output={},
        ground_truth=None,
    )
    assert score.final_answer_supported is False
    assert any(issue["check"] == "final_answer_support" for issue in score.issues)
