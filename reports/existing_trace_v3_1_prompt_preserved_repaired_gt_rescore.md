# DataAgentBench Scoring V3 Rescore Report

This report rescored existing report.json + trace.jsonl artifacts without rerunning models.

Interpretation note: this is a scoring/trace diagnostic report, not a leaderboard. Small task filters, repaired ground truth, old traces, and timeout-heavy runs should not be used for model ranking.

Task filter: `DS_TASK_061, DS_TASK_066`.

## Aggregate

| Model | Reports | FinalAcc | ObservedTraceAcc | GroundedFinalAcc | FinalAcc_no_timeout | ObservedTraceAcc_no_timeout | GroundedFinalAcc_no_timeout | Timeout/API Rate | Format Miss Rate | Ungrounded Final Rate | TraceIntegrity | Process | ExecSafety | AnaSafety |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gpt-4o-mini | 2 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.0% | 0.0% | 0.0% | 1.000 | 0.684 | 1.000 | 1.000 |
| gpt-4o | 2 | 0.500 | 0.500 | 0.500 | 1.000 | 1.000 | 1.000 | 50.0% | 0.0% | 0.0% | 1.000 | 0.659 | 0.900 | 1.000 |
| gpt-5.4 | 2 | 0.583 | 1.000 | 0.583 | 0.583 | 1.000 | 0.583 | 0.0% | 50.0% | 0.0% | 1.000 | 0.725 | 1.000 | 1.000 |
| gpt-5.3-codex | 2 | 0.421 | 0.000 | 0.000 | 0.421 | 0.000 | 0.000 | 0.0% | 0.0% | 50.0% | 1.000 | 0.719 | 1.000 | 1.000 |

## Per-task

| Model | Task | FinalAcc | ObservedTraceAcc | GroundedFinalAcc | ObservedMinusFinal | Failure | ExtractedSource | MissedKeys | UngroundedKeys | TracePath |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gpt-4o-mini | DS_TASK_061 | 1.000 | 1.000 | 1.000 | 0.000 | result | {'execution_numeric_match': 1} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4omini/DS_TASK_061/c7579d47/trace.jsonl |
| gpt-4o-mini | DS_TASK_066 | 1.000 | 1.000 | 1.000 | 0.000 | format_extraction_issue | {'labeled_stdout': 6} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4omini/DS_TASK_066/6a13dd73/trace.jsonl |
| gpt-4o | DS_TASK_061 | 1.000 | 1.000 | 1.000 | 0.000 | result | {'execution_numeric_match': 1} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4o_resume/DS_TASK_061/1a2a65ff/trace.jsonl |
| gpt-4o | DS_TASK_066 | 0.000 | 0.000 | 0.000 | 0.000 | timeout | {'none': 6} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4o_resume/DS_TASK_066/6bd38e89/trace.jsonl |
| gpt-5.4 | DS_TASK_061 | 1.000 | 1.000 | 1.000 | 0.000 | result | {'labeled_stdout': 1} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt54/DS_TASK_061/b031a4ed/trace.jsonl |
| gpt-5.4 | DS_TASK_066 | 0.167 | 1.000 | 0.167 | 0.833 | format_extraction_issue | {'labeled_stdout': 6} | total_revenue_books, total_revenue_clothing, total_revenue_food, total_revenue_home, total_revenue_sports |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt54/DS_TASK_066/bd5d13d2/trace.jsonl |
| gpt-5.3-codex | DS_TASK_061 | 0.843 | 0.000 | 0.000 | -0.843 | format_extraction_issue | {'none': 1} |  | average_stay_duration_readmitted | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt53codex/DS_TASK_061/8a3bc187/trace.jsonl |
| gpt-5.3-codex | DS_TASK_066 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 6} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt53codex/DS_TASK_066/8f8cb4eb/trace.jsonl |
