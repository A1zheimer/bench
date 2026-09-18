from __future__ import annotations

from datetime import datetime

from data_agent_bench.evaluation.answer_extractor import AnswerExtractor
from data_agent_bench.models.task import Difficulty, Domain, EnvironmentConfig, TaskContext, TaskInput, TaskMetadata
from data_agent_bench.models.trace import ActionType, AgentTrace, TerminationInfo, TraceStep


def _task() -> TaskInput:
    return TaskInput(
        instance_id="DS_TASK_TEST",
        task_metadata=TaskMetadata(domain=Domain.FINANCE, difficulty=Difficulty.EASY),
        context=TaskContext(problem_statement="Compute average price.", dataset_preview="dataset.csv"),
        environment_config=EnvironmentConfig(image="python:3.11", max_steps=5, budget=1.0),
    )


def _step(step: int, output: str) -> TraceStep:
    return TraceStep(
        step=step,
        timestamp=datetime.utcnow(),
        action_type=ActionType.CODE_EXEC,
        action="Execute Code",
        observation=output,
        thought="print result",
        tool_name="python_repl",
        tool_args={"code": "print('result')"},
        tool_result=output,
    )


def _trace(*steps: TraceStep) -> AgentTrace:
    return AgentTrace(
        instance_id="DS_TASK_TEST",
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow(),
        steps=list(steps),
        termination=TerminationInfo(reason="completed", forced=False),
    )


def test_extracts_final_answer_json() -> None:
    result = AnswerExtractor().extract(
        _task(),
        _trace(),
        {"raw_agent_output": 'FINAL ANSWER: {"key_values": {"average_price": 104.57}}'},
        {"key_values": {"average_price": 104.57}},
    )
    assert result["key_values"]["average_price"] == 104.57
    assert result["source"] == "final_json"
    assert result["extraction_confidence"] == 1.0


def test_extracts_labeled_stdout_with_alias() -> None:
    result = AnswerExtractor().extract(
        _task(),
        _trace(),
        {"execution_result": "avg price = 104.57"},
        {
            "key_values": {"average_price": 104.57},
            "key_aliases": {"average_price": ["avg price"]},
        },
    )
    assert result["key_values"]["average_price"] == 104.57
    assert result["source"] == "labeled_stdout"


def test_extracts_labeled_trace_step_with_source_step() -> None:
    result = AnswerExtractor().extract(
        _task(),
        _trace(_step(2, "average price: 104.57")),
        {"execution_result": "done"},
        {
            "key_values": {"average_price": 104.57},
            "key_aliases": {"average_price": ["average price"]},
        },
    )
    assert result["key_values"]["average_price"] == 104.57
    assert result["source"] == "trace_numeric_match"
    assert result["source_steps"] == [2]


def test_unlabeled_numbers_are_not_high_confidence_extracted() -> None:
    result = AnswerExtractor().extract(
        _task(),
        _trace(_step(1, "104.57")),
        {"execution_result": "104.57"},
        {"key_values": {"average_price": 104.57}},
    )
    assert result["key_values"] == {}
    assert result["extraction_confidence"] == 0.0
