# DataAgentBench Scoring V3 Rescore Report

This report rescored existing report.json + trace.jsonl artifacts without rerunning models.

## Aggregate

| Model | Reports | FinalAcc | ObservedTraceAcc | GroundedFinalAcc | FinalAcc_no_timeout | ObservedTraceAcc_no_timeout | GroundedFinalAcc_no_timeout | Timeout/API Rate | Format Miss Rate | Ungrounded Final Rate | TraceIntegrity | Process | ExecSafety | AnaSafety |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| simulated | 5 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 20.0% | 0.0% | 0.0% | 1.000 | 0.650 | 1.000 | 0.960 |

## Per-task

| Model | Task | FinalAcc | ObservedTraceAcc | GroundedFinalAcc | ObservedMinusFinal | Failure | ExtractedSource | MissedKeys | UngroundedKeys | TracePath |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| simulated | DS_TASK_061 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 1} |  |  | /Users/bytedance/Desktop/bench/bench_runs_curated_easy_v1_simulated/DS_TASK_061/ebd31326/trace.jsonl |
| simulated | DS_TASK_066 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 6} |  |  | /Users/bytedance/Desktop/bench/bench_runs_curated_easy_v1_simulated/DS_TASK_066/82d6ad7c/trace.jsonl |
| simulated | DS_TASK_120 | 0.000 | 0.000 | 0.000 | 0.000 | timeout | {'none': 7} |  |  | /Users/bytedance/Desktop/bench/bench_runs_curated_easy_v1_simulated/DS_TASK_120/cf1c3f14/trace.jsonl |
| simulated | DS_TASK_150 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 3} |  |  | /Users/bytedance/Desktop/bench/bench_runs_curated_easy_v1_simulated/DS_TASK_150/ebd77563/trace.jsonl |
| simulated | DS_TASK_153 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 5} |  |  | /Users/bytedance/Desktop/bench/bench_runs_curated_easy_v1_simulated/DS_TASK_153/23010466/trace.jsonl |
