from __future__ import annotations

from datetime import datetime

from data_agent_bench.evaluation.answer_extractor import AnswerExtractor
from data_agent_bench.evaluation.deterministic import DeterministicEvaluator
from data_agent_bench.evaluation.scorer_audit import ScorerAudit
from data_agent_bench.models.task import Difficulty, Domain, EnvironmentConfig, TaskContext, TaskInput, TaskMetadata
from data_agent_bench.models.trace import ActionType, AgentTrace, TerminationInfo, TraceStep


def _task() -> TaskInput:
    return TaskInput(
        instance_id="DS_TASK_TEST",
        task_metadata=TaskMetadata(domain=Domain.FINANCE, difficulty=Difficulty.EASY),
        context=TaskContext(problem_statement="Compute average price.", dataset_preview="dataset.csv"),
        environment_config=EnvironmentConfig(image="python:3.11", max_steps=5, budget=1.0),
    )


def _trace(output: str) -> AgentTrace:
    return AgentTrace(
        instance_id="DS_TASK_TEST",
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow(),
        steps=[
            TraceStep(
                step=1,
                timestamp=datetime.utcnow(),
                action_type=ActionType.CODE_EXEC,
                action="Execute Code",
                observation=output,
                thought="print result",
                tool_name="python_repl",
                tool_args={"code": "print(result)"},
                tool_result=output,
            )
        ],
        termination=TerminationInfo(reason="completed", forced=False),
    )


def test_correct_trace_value_wrong_format_is_recovered_by_extractor() -> None:
    task = _task()
    trace = _trace("average price = 104.57")
    ground_truth = {
        "key_values": {"average_price": 104.57},
        "key_aliases": {"average_price": ["average price"]},
    }
    final_output = {"execution_result": "done", "raw_agent_output": ""}
    final_output["benchmark_extracted_answer"] = AnswerExtractor().extract(task, trace, final_output, ground_truth)
    det = DeterministicEvaluator().evaluate(task, trace, final_output, ground_truth)
    assert det.field_scores["average_price"] == 1.0
    assert det.field_details["average_price"]["source"] == "trace_numeric_match"


def test_scorer_audit_flags_unlabeled_trace_value_when_score_low() -> None:
    task = _task()
    trace = _trace("104.57")
    ground_truth = {"key_values": {"average_price": 104.57}}
    final_output = {"execution_result": "no labeled result", "raw_agent_output": ""}
    final_output["benchmark_extracted_answer"] = AnswerExtractor().extract(task, trace, final_output, ground_truth)
    det = DeterministicEvaluator().evaluate(task, trace, final_output, ground_truth)
    audit = ScorerAudit().evaluate(task, trace, final_output, ground_truth, deterministic_score=det)
    assert det.field_scores["average_price"] < 0.5
    assert audit.missed_trace_value is True
    assert audit.format_extraction_issue is True
    assert audit.trace_value_hits[0]["source_step"] == 1


def test_scorer_audit_does_not_flag_when_no_near_gt_value_exists() -> None:
    task = _task()
    trace = _trace("average price = 90")
    ground_truth = {
        "key_values": {"average_price": 104.57},
        "key_aliases": {"average_price": ["average price"]},
    }
    final_output = {"execution_result": "average price = 90", "raw_agent_output": ""}
    final_output["benchmark_extracted_answer"] = AnswerExtractor().extract(task, trace, final_output, ground_truth)
    det = DeterministicEvaluator().evaluate(task, trace, final_output, ground_truth)
    audit = ScorerAudit().evaluate(task, trace, final_output, ground_truth, deterministic_score=det)
    assert audit.missed_trace_value is False
    assert audit.trace_value_hits == []
