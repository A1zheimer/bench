from __future__ import annotations

from datetime import datetime

from data_agent_bench.evaluation.trace_grounding import TraceGroundingVerifier
from data_agent_bench.models.report import TraceGroundingScore
from data_agent_bench.models.trace import ActionType, AgentTrace, TraceStep


def _trace(*steps: TraceStep) -> AgentTrace:
    return AgentTrace(
        instance_id="DS_TASK_001",
        start_time=datetime.utcnow(),
        end_time=None,
        steps=list(steps),
        termination=None,
    )


def _code_step(step: int, code: str, result: str = "ok") -> TraceStep:
    return TraceStep(
        step=step,
        timestamp=datetime.utcnow(),
        action_type=ActionType.CODE_EXEC,
        action="Execute Code",
        observation=result,
        thought="",
        tool_name="python_repl",
        tool_args={"code": code},
        tool_result=result,
    )


def test_read_csv_declared_step_is_grounded() -> None:
    trace = _trace(_code_step(1, "import pandas as pd\ndf = pd.read_csv(DATA_PATH)"))
    score = TraceGroundingVerifier().evaluate(
        task=None,  # type: ignore[arg-type]
        trace=trace,
        final_output={
            "final_answer": '{"declared_trace": [{"step_id":"s1","predicate":"LOADS","operation":"read_csv","inputs":["DATA_PATH"],"evidence_step":1,"status":"success"}]}'
        },
        ground_truth=None,
    )
    assert isinstance(score, TraceGroundingScore)
    assert score.grounding_rate == 1.0
    assert score.matched_steps[0]["matched_observed_step"] == 1


def test_groupby_sum_declared_step_is_grounded() -> None:
    trace = _trace(_code_step(2, 'result = df.groupby("type")["spending"].sum()'))
    score = TraceGroundingVerifier().evaluate(
        task=None,  # type: ignore[arg-type]
        trace=trace,
        final_output={
            "final_answer": '{"declared_trace": [{"step_id":"s2","predicate":"AGGREGATES","operation":"groupby_sum","inputs":["type","spending"],"evidence_step":2,"status":"success"}]}'
        },
        ground_truth=None,
    )
    assert score.grounding_rate == 1.0
    assert "groupby_sum" in score.matched_steps[0]["matched_signals"]


def test_missing_evidence_step_is_unsupported() -> None:
    trace = _trace(_code_step(1, "df = pd.read_csv(DATA_PATH)"))
    score = TraceGroundingVerifier().evaluate(
        task=None,  # type: ignore[arg-type]
        trace=trace,
        final_output={
            "final_answer": '{"declared_trace": [{"step_id":"s1","predicate":"LOADS","operation":"read_csv","evidence_step":99,"status":"success"}]}'
        },
        ground_truth=None,
    )
    assert score.grounding_rate == 0.0
    assert "not found" in score.unsupported_steps[0]["reason"]


def test_missing_dependency_lowers_dependency_score() -> None:
    trace = _trace(_code_step(1, "df = pd.read_csv(DATA_PATH)"))
    score = TraceGroundingVerifier().evaluate(
        task=None,  # type: ignore[arg-type]
        trace=trace,
        final_output={
            "final_answer": '{"declared_trace": [{"step_id":"s1","predicate":"LOADS","operation":"read_csv","evidence_step":1,"status":"success"},{"step_id":"s2","predicate":"REPORTS","operation":"final_answer","depends_on":["missing"],"evidence_step":1,"status":"success"}]}'
        },
        ground_truth=None,
    )
    assert score.dependency_score == 0.0


def test_missing_declared_trace_does_not_crash() -> None:
    trace = _trace(_code_step(1, "df = pd.read_csv(DATA_PATH)"))
    score = TraceGroundingVerifier().evaluate(
        task=None,  # type: ignore[arg-type]
        trace=trace,
        final_output={"execution_result": "done"},
        ground_truth=None,
    )
    assert score.missing_declared_trace is True
    assert score.format_valid is False
