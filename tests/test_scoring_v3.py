from __future__ import annotations

from data_agent_bench.evaluation.scoring_v3 import rescore_report_v3, score_numeric_value
from scripts.rescore_v3_reports import _aggregate


GROUND_TRUTH = {
    "key_values": {"average_price": 100.0},
    "key_aliases": {"average_price": ["average price"]},
}


def test_numeric_tolerance_plateau_scores_full_credit() -> None:
    score, rel_err = score_numeric_value(104.8, 100.0)
    assert round(rel_err, 3) == 0.048
    assert score == 1.0


def test_numeric_soft_partial_credit_between_tolerance_and_cap() -> None:
    score, rel_err = score_numeric_value(115.0, 100.0)
    assert round(rel_err, 2) == 0.15
    assert round(score, 2) == 0.5


def test_numeric_error_above_soft_cap_scores_zero() -> None:
    score, rel_err = score_numeric_value(130.0, 100.0)
    assert round(rel_err, 2) == 0.30
    assert score == 0.0


def test_trace_value_recovers_when_final_answer_has_no_value() -> None:
    report = {
        "instance_id": "DS_TASK_TEST",
        "raw_agent_output": "FINAL ANSWER: I could not finish.",
        "execution_result": "average price = 100.0",
        "metrics": {"process_quality": 0.5},
        "scores": {},
    }
    result = rescore_report_v3(report, [], GROUND_TRUTH)
    assert result.final_answer.accuracy == 0.0
    assert result.trace_grounded.accuracy == 1.0
    assert result.format_miss_keys() == ["average_price"]


def test_final_answer_wrong_but_trace_value_correct_creates_delta() -> None:
    report = {
        "instance_id": "DS_TASK_TEST",
        "raw_agent_output": "FINAL ANSWER: average price: 130.0",
        "execution_result": "",
        "metrics": {"process_quality": 0.5},
        "scores": {},
    }
    trace_steps = [{"step": 2, "observation": "average price = 100.0"}]
    result = rescore_report_v3(report, trace_steps, GROUND_TRUTH)
    assert result.final_answer.accuracy == 0.0
    assert result.trace_grounded.accuracy == 1.0
    assert result.trace_grounded.field_scores["average_price"].source == "trace_labeled_output"


def test_semantic_json_key_variant_is_extracted_without_explicit_alias() -> None:
    ground_truth = {"key_values": {"average_stay_duration_readmitted": 100.0}}
    report = {
        "instance_id": "DS_TASK_TEST",
        "raw_agent_output": (
            "FINAL ANSWER: {\"key_values\": "
            "{\"average_hospital_stay_duration_readmitted\": 100.0}}"
        ),
        "execution_result": "",
        "metrics": {"process_quality": 0.5},
        "scores": {},
    }
    result = rescore_report_v3(report, [], ground_truth)
    assert result.final_answer.accuracy == 1.0
    assert result.trace_grounded.accuracy == 0.0
    assert result.ungrounded_final_keys() == ["average_stay_duration_readmitted"]
    assert (
        result.final_answer.field_scores["average_stay_duration_readmitted"].matched_label
        == "average_hospital_stay_duration_readmitted"
    )


def test_semantic_labeled_trace_line_is_extracted_without_unlabeled_fallback() -> None:
    ground_truth = {"key_values": {"average_stay_duration_readmitted": 100.0}}
    report = {
        "instance_id": "DS_TASK_TEST",
        "raw_agent_output": "FINAL ANSWER: incomplete",
        "execution_result": "Average hospital stay days for readmitted patients: 100.0",
        "metrics": {"process_quality": 0.5},
        "scores": {},
    }
    result = rescore_report_v3(report, [], ground_truth)
    assert result.final_answer.accuracy == 0.0
    assert result.trace_grounded.accuracy == 1.0


def test_single_key_unlabeled_numeric_trace_can_support_final_answer() -> None:
    ground_truth = {"key_values": {"average_stay_duration_readmitted": 7.397163120567376}}
    report = {
        "instance_id": "DS_TASK_TEST",
        "raw_agent_output": "FINAL ANSWER: {\"key_values\": {\"average_stay_duration_readmitted\": 7.4}}",
        "execution_result": "np.float64(7.397163120567376)",
        "metrics": {"process_quality": 0.5},
        "scores": {},
    }
    result = rescore_report_v3(report, [], ground_truth)
    assert result.final_answer.accuracy == 1.0
    assert result.trace_grounded.accuracy == 1.0
    assert result.grounded_final.accuracy == 1.0


def test_single_key_numeric_fallback_ignores_dataframe_preview_numbers() -> None:
    ground_truth = {"key_values": {"average_stay_duration_readmitted": 7.397163120567376}}
    report = {
        "instance_id": "DS_TASK_TEST",
        "raw_agent_output": "FINAL ANSWER: {\"key_values\": {\"average_stay_duration_readmitted\": 8.0}}",
        "execution_result": (
            "patient_id age hospital_stay_days\n"
            "0 1 68 6\n"
            "1 2 58 5\n"
            "2 3 44 14\n"
            "[5 rows x 7 columns]"
        ),
        "metrics": {"process_quality": 0.5},
        "scores": {},
    }
    result = rescore_report_v3(report, [], ground_truth)
    assert result.final_answer.accuracy > 0.0
    assert result.trace_grounded.accuracy == 0.0
    assert result.grounded_final.accuracy == 0.0


def test_category_revenue_bullets_and_table_are_extracted() -> None:
    ground_truth = {
        "key_values": {
            "total_revenue_books": 5411.86,
            "total_revenue_clothing": 12585.89,
        }
    }
    report = {
        "instance_id": "DS_TASK_TEST",
        "raw_agent_output": (
            "The total revenue generated by each product category is:\n"
            "- **Books**: $5,411.86\n"
            "- **Clothing**: $12,585.89\n"
        ),
        "execution_result": (
            "  product_category  total_revenue\n"
            "0            Books        5411.86\n"
            "1         Clothing       12585.89\n"
        ),
        "metrics": {"process_quality": 0.5},
        "scores": {},
    }
    result = rescore_report_v3(report, [], ground_truth)
    assert result.final_answer.accuracy == 1.0
    assert result.trace_grounded.accuracy == 1.0
    assert result.grounded_final.accuracy == 1.0


def test_nested_final_json_category_values_are_extracted() -> None:
    ground_truth = {
        "key_values": {
            "total_revenue_books": 5411.86,
            "total_revenue_clothing": 12585.89,
        }
    }
    report = {
        "instance_id": "DS_TASK_TEST",
        "raw_agent_output": (
            "FINAL ANSWER: {\"key_values\": {\"total_revenue_by_category\": "
            "{\"Books\": 5411.86, \"Clothing\": 12585.89}}}"
        ),
        "execution_result": (
            "  product_category  total_revenue\n"
            "0            Books        5411.86\n"
            "1         Clothing       12585.89\n"
        ),
        "metrics": {"process_quality": 0.5},
        "scores": {},
    }
    result = rescore_report_v3(report, [], ground_truth)
    assert result.final_answer.accuracy == 1.0
    assert result.trace_grounded.accuracy == 1.0
    assert result.grounded_final.accuracy == 1.0


def test_grounded_final_requires_final_value_to_be_supported_by_observed_trace() -> None:
    report = {
        "instance_id": "DS_TASK_TEST",
        "raw_agent_output": "FINAL ANSWER: average price: 100.0",
        "execution_result": "average price = 100.0",
        "metrics": {"process_quality": 0.5},
        "scores": {},
    }
    result = rescore_report_v3(report, [], GROUND_TRUTH)
    assert result.final_answer.accuracy == 1.0
    assert result.trace_grounded.accuracy == 1.0
    assert result.grounded_final.accuracy == 1.0
    assert result.ungrounded_final_keys() == []


def test_final_answer_ignores_code_before_final_answer_marker() -> None:
    report = {
        "instance_id": "DS_TASK_TEST",
        "raw_agent_output": "```python\naverage_price = 100.0\n```\nFINAL ANSWER: incomplete",
        "execution_result": "",
        "metrics": {"process_quality": 0.5},
        "scores": {},
    }
    result = rescore_report_v3(report, [], GROUND_TRUTH)
    assert result.final_answer.accuracy == 0.0
    assert result.trace_grounded.accuracy == 0.0


def test_timeout_excluded_aggregate_keeps_overall_and_no_timeout_separate() -> None:
    success = rescore_report_v3(
        {
            "instance_id": "DS_TASK_OK",
            "raw_agent_output": "FINAL ANSWER: average price: 100.0",
            "metrics": {"process_quality": 1.0},
            "scores": {},
            "failure_attribution": {"primary_failure": "none"},
        },
        [],
        GROUND_TRUTH,
    )
    timeout = rescore_report_v3(
        {
            "instance_id": "DS_TASK_TIMEOUT",
            "raw_agent_output": "",
            "metrics": {"process_quality": 0.0},
            "scores": {},
            "failure_attribution": {"primary_failure": "api_read_timeout"},
        },
        [],
        GROUND_TRUTH,
    )
    row = _aggregate("model", [success, timeout])
    assert row["FinalAcc"] == "0.500"
    assert row["FinalAcc_no_timeout"] == "1.000"
    assert row["ObservedTraceAcc"] == "0.000"
    assert row["ObservedTraceAcc_no_timeout"] == "0.000"
    assert row["GroundedFinalAcc"] == "0.000"
    assert row["GroundedFinalAcc_no_timeout"] == "0.000"
    assert row["Timeout/API Rate"] == "50.0%"


def test_existing_v2_report_can_be_rescored_without_rerun() -> None:
    report = {
        "instance_id": "DS_TASK_TEST",
        "evaluation_protocol": "v2",
        "raw_agent_output": "FINAL ANSWER: {\"key_values\": {\"average_price\": 100.0}}",
        "execution_result": "unused",
        "metrics": {"process_quality": 0.5},
        "scores": {"trace_integrity": {"integrity_score": 1.0}},
    }
    result = rescore_report_v3(report, [], GROUND_TRUTH)
    assert result.final_answer.accuracy == 1.0
    assert result.trace_grounded.accuracy == 0.0
    assert result.trace_integrity == 1.0
