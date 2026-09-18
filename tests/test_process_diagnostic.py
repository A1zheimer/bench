from __future__ import annotations

from datetime import datetime

from data_agent_bench.evaluation.aggregator import ScoreAggregator
from data_agent_bench.evaluation.process_auditor import ProcessAuditor
from data_agent_bench.evaluation.risk_assessor import RiskAssessor
from data_agent_bench.models.report import DeterministicScore
from data_agent_bench.models.task import Difficulty, Domain, EnvironmentConfig, TaskContext, TaskInput, TaskMetadata
from data_agent_bench.models.trace import ActionType, AgentTrace, TerminationInfo, TraceStep


def _task() -> TaskInput:
    return TaskInput(
        instance_id="DS_TASK_TEST",
        task_metadata=TaskMetadata(domain=Domain.GENERIC, difficulty=Difficulty.EASY),
        context=TaskContext(problem_statement="Compute mean.", dataset_preview="dataset.csv"),
        environment_config=EnvironmentConfig(image="python:3.11", max_steps=5, budget=1.0),
    )


def _code_step(step: int, code: str, result: str = "mean_value=10") -> TraceStep:
    return TraceStep(
        step=step,
        timestamp=datetime.utcnow(),
        action_type=ActionType.CODE_EXEC,
        action="Execute Code",
        observation=result,
        thought=code,
        tool_name="python_repl",
        tool_args={"code": code},
        tool_result=result,
    )


def _trace(*steps: TraceStep) -> AgentTrace:
    return AgentTrace(
        instance_id="DS_TASK_TEST",
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow(),
        steps=list(steps),
        termination=TerminationInfo(reason="completed", forced=False),
    )


def test_one_step_success_is_not_heavily_penalized_by_process() -> None:
    task = _task()
    trace = _trace(_code_step(1, "import pandas as pd\ndf=pd.read_csv(DATA_PATH)\nprint(df.mean())"))
    proc = ProcessAuditor().evaluate(task, trace, {"execution_result": "mean_value=10"}, None)
    quality = ScoreAggregator()._process_quality(proc)
    assert quality >= 0.65


def test_low_process_high_accuracy_is_diagnostic_not_primary_failure() -> None:
    task = _task()
    trace = _trace(_code_step(1, "print(10)", "mean_value=10"))
    det = DeterministicScore(False, True, 0.05, 0.0, {"mean_value": 1.0})
    proc = ProcessAuditor().evaluate(task, trace, {"execution_result": "mean_value=10"}, None)
    risk = RiskAssessor().evaluate(task, trace, {"execution_result": "mean_value=10"}, None)
    metrics, failure = ScoreAggregator().aggregate(task, trace, det, proc, risk)
    assert metrics.result_accuracy == 1.0
    if failure is not None:
        assert failure.primary_cause != "process"


def test_repeated_actions_emit_diagnostic_warning() -> None:
    task = _task()
    trace = _trace(*[_code_step(i, "print(1)", "1") for i in range(1, 6)])
    det = DeterministicScore(False, True, 0.05, 0.0, {"mean_value": 1.0})
    proc = ProcessAuditor().evaluate(task, trace, {"execution_result": "mean_value=10"}, None)
    risk = RiskAssessor().evaluate(task, trace, {"execution_result": "mean_value=10"}, None)
    _, failure = ScoreAggregator().aggregate(task, trace, det, proc, risk)
    assert failure is not None
    assert "repeated_action" in failure.diagnostic_warnings
