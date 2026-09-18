from __future__ import annotations

from datetime import datetime

from data_agent_bench.evaluation.aggregator import ScoreAggregator
from data_agent_bench.evaluation.deterministic import DeterministicEvaluator
from data_agent_bench.models.report import ProcessScore, RiskScore
from data_agent_bench.models.task import TaskInput
from data_agent_bench.models.trace import ActionType, AgentTrace, TerminationInfo, TraceStep
from data_agent_bench.repository.schema_validator import SchemaValidator


def _task_dict() -> dict:
    return {
        "instance_id": "DS_TASK_999",
        "task_metadata": {
            "domain": "Finance",
            "difficulty": "Easy",
            "primary_task_type": "time_series_forecasting",
            "secondary_task_types": [
                "descriptive_aggregation",
                "data_quality_robustness",
            ],
            "challenge_dimensions": [
                "heteroskedasticity",
                "outlier_handling",
                "semantic_perturbation",
            ],
            "tags": ["time-series", "forecasting"],
        },
        "context": {
            "problem_statement": "Compute average price.",
            "dataset_preview": "data/dataset.csv",
        },
        "environment_config": {"image": "ds-agent-v1", "max_steps": 10, "budget": 1.0},
    }


def _trace(code: str, result: str) -> AgentTrace:
    return AgentTrace(
        instance_id="DS_TASK_999",
        start_time=datetime.utcnow(),
        end_time=None,
        steps=[
            TraceStep(
                step=1,
                timestamp=datetime.utcnow(),
                action_type=ActionType.CODE_EXEC,
                action="Call python_repl",
                observation=result,
                tool_name="python_repl",
                tool_args={"code": code},
            )
        ],
        termination=TerminationInfo(reason="completed", forced=False),
        total_tokens=100,
    )


def test_task_metadata_taxonomy_roundtrip() -> None:
    task = TaskInput.from_dict(_task_dict())
    meta = task.task_metadata

    assert meta.primary_task_type == "time_series_forecasting"
    assert "descriptive_aggregation" in meta.secondary_task_types
    assert "semantic_perturbation" in meta.challenge_dimensions
    assert task.to_dict()["task_metadata"]["primary_task_type"] == "time_series_forecasting"


def test_schema_validator_accepts_optional_taxonomy_and_components() -> None:
    SchemaValidator.validate_task_input(_task_dict())
    SchemaValidator.validate_ground_truth(
        {
            "execution_result": "average_price = 104.57",
            "key_values": {"average_price": 104.57},
            "components": {
                "data_selection": {
                    "target_columns": ["Price"],
                    "score_weight": 0.15,
                },
                "numerical_result": {
                    "key_values": {"average_price": 104.57},
                    "score_weight": 0.55,
                },
            },
        }
    )


def test_component_accuracy_is_reported_and_weighted() -> None:
    task = TaskInput.from_dict(_task_dict())
    trace = _trace(
        code="df = pd.read_csv(DATA_PATH)\nanswer = df['Price'].mean()",
        result="average_price = 104.57",
    )
    det = DeterministicEvaluator().evaluate(
        task=task,
        trace=trace,
        final_output={"execution_result": "average_price = 104.57"},
        ground_truth={
            "execution_result": "average_price = 104.57",
            "key_values": {"average_price": 104.57},
            "components": {
                "data_selection": {
                    "target_columns": ["Price"],
                    "score_weight": 0.15,
                },
                "numerical_result": {
                    "key_values": {"average_price": 104.57},
                    "score_weight": 0.55,
                },
            },
        },
    )

    assert det.component_scores["data_selection"] == 1.0
    assert det.component_scores["numerical_result"] == 1.0
    metrics, _ = ScoreAggregator().aggregate(
        task=task,
        trace=trace,
        det=det,
        proc=ProcessScore(
            planning_score=1.0,
            tool_efficiency=1.0,
            error_recovery_score=1.0,
            feedback_loop_score=1.0,
            step_utilization=1.0,
            redundant_action_ratio=0.0,
        ),
        risk=RiskScore(
            safety_compliant=True,
            violations=[],
            high_freq_tool_calls=False,
            resource_within_budget=True,
            risky_patterns=[],
            risk_level="none",
        ),
    )
    assert metrics.result_accuracy == 1.0


def test_legacy_ground_truth_keeps_numeric_scoring() -> None:
    task = TaskInput.from_dict(_task_dict())
    trace = _trace(code="answer = 104.57", result="104.57")
    det = DeterministicEvaluator().evaluate(
        task=task,
        trace=trace,
        final_output={"execution_result": "average_price = 104.57"},
        ground_truth={
            "execution_result": "average_price = 104.57",
            "key_values": {"average_price": 104.57},
        },
    )

    assert det.numeric_match is True
    assert det.component_scores == {}
