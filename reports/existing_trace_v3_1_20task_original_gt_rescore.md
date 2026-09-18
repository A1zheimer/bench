# DataAgentBench Scoring V3 Rescore Report

This report rescored existing report.json + trace.jsonl artifacts without rerunning models.

Task filter: `all reports in each run directory`.

## Aggregate

| Model | Reports | FinalAcc | ObservedTraceAcc | GroundedFinalAcc | FinalAcc_no_timeout | ObservedTraceAcc_no_timeout | GroundedFinalAcc_no_timeout | Timeout/API Rate | Format Miss Rate | Ungrounded Final Rate | TraceIntegrity | Process | ExecSafety | AnaSafety |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gpt-4o-mini | 20 | 0.048 | 0.048 | 0.048 | 0.088 | 0.088 | 0.088 | 45.0% | 0.0% | 0.0% | 1.000 | 0.642 | 0.840 | 0.960 |
| gpt-4o | 20 | 0.091 | 0.041 | 0.041 | 0.260 | 0.117 | 0.117 | 65.0% | 0.0% | 5.0% | 1.000 | 0.634 | 0.770 | 0.980 |
| gpt-5.4 | 20 | 0.044 | 0.048 | 0.041 | 0.047 | 0.051 | 0.043 | 5.0% | 5.0% | 5.0% | 1.000 | 0.693 | 0.880 | 0.960 |
| gpt-5.3-codex | 20 | 0.060 | 0.000 | 0.000 | 0.060 | 0.000 | 0.000 | 0.0% | 0.0% | 10.0% | 1.000 | 0.698 | 1.000 | 0.960 |

## Per-task

| Model | Task | FinalAcc | ObservedTraceAcc | GroundedFinalAcc | ObservedMinusFinal | Failure | ExtractedSource | MissedKeys | UngroundedKeys | TracePath |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gpt-4o-mini | DS_TASK_059 | 0.000 | 0.000 | 0.000 | 0.000 | format_extraction_issue | {'none': 3} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4omini/DS_TASK_059/8788bbda/trace.jsonl |
| gpt-4o-mini | DS_TASK_061 | 0.818 | 0.816 | 0.818 | -0.002 | result | {'execution_numeric_match': 1} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4omini/DS_TASK_061/c7579d47/trace.jsonl |
| gpt-4o-mini | DS_TASK_062 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 2} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4omini/DS_TASK_062/a472d123/trace.jsonl |
| gpt-4o-mini | DS_TASK_064 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 3} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4omini/DS_TASK_064/99ff8d5f/trace.jsonl |
| gpt-4o-mini | DS_TASK_066 | 0.148 | 0.148 | 0.148 | 0.000 | format_extraction_issue | {'labeled_stdout': 1} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4omini/DS_TASK_066/6a13dd73/trace.jsonl |
| gpt-4o-mini | DS_TASK_071 | 0.000 | 0.000 | 0.000 | 0.000 | timeout | {'none': 1} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4omini/DS_TASK_071/916b0c33/trace.jsonl |
| gpt-4o-mini | DS_TASK_106 | 0.000 | 0.000 | 0.000 | 0.000 | timeout | {'none': 2} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4omini/DS_TASK_106/7d6faa31/trace.jsonl |
| gpt-4o-mini | DS_TASK_108 | 0.000 | 0.000 | 0.000 | 0.000 | timeout | {'none': 2} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4omini/DS_TASK_108/b207de5b/trace.jsonl |
| gpt-4o-mini | DS_TASK_111 | 0.000 | 0.000 | 0.000 | 0.000 | timeout | {'none': 3} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4omini/DS_TASK_111/9a32ce42/trace.jsonl |
| gpt-4o-mini | DS_TASK_120 | 0.000 | 0.000 | 0.000 | 0.000 | format_extraction_issue | {'none': 1} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4omini/DS_TASK_120/238ef0bd/trace.jsonl |
| gpt-4o-mini | DS_TASK_121 | 0.000 | 0.000 | 0.000 | 0.000 | timeout | {'none': 2} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4omini/DS_TASK_121/e9b7c7ed/trace.jsonl |
| gpt-4o-mini | DS_TASK_126 | 0.000 | 0.000 | 0.000 | 0.000 | timeout | {'none': 3} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4omini/DS_TASK_126/b161046d/trace.jsonl |
| gpt-4o-mini | DS_TASK_128 | 0.000 | 0.000 | 0.000 | 0.000 | timeout | {'none': 3} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4omini/DS_TASK_128/f1fd6325/trace.jsonl |
| gpt-4o-mini | DS_TASK_139 | 0.000 | 0.000 | 0.000 | 0.000 | partial_completion | {'none': 2} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4omini/DS_TASK_139/115d771f/trace.jsonl |
| gpt-4o-mini | DS_TASK_141 | 0.000 | 0.000 | 0.000 | 0.000 | partial_completion | {'none': 2} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4omini/DS_TASK_141/c237cf8c/trace.jsonl |
| gpt-4o-mini | DS_TASK_150 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 1} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4omini/DS_TASK_150/a98885e0/trace.jsonl |
| gpt-4o-mini | DS_TASK_153 | 0.000 | 0.000 | 0.000 | 0.000 | timeout | {'none': 1} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4omini/DS_TASK_153/14bfd30f/trace.jsonl |
| gpt-4o-mini | DS_TASK_158 | 0.000 | 0.000 | 0.000 | 0.000 | partial_completion | {'none': 2} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4omini/DS_TASK_158/f7dc67b6/trace.jsonl |
| gpt-4o-mini | DS_TASK_165 | 0.000 | 0.000 | 0.000 | 0.000 | timeout | {'none': 3} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4omini/DS_TASK_165/7023cbfe/trace.jsonl |
| gpt-4o-mini | DS_TASK_173 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 3} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4omini/DS_TASK_173/2645a6ee/trace.jsonl |
| gpt-4o | DS_TASK_059 | 0.000 | 0.000 | 0.000 | 0.000 | timeout | {'none': 3} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4o_resume/DS_TASK_059/0ae58ab7/trace.jsonl |
| gpt-4o | DS_TASK_061 | 0.818 | 0.816 | 0.818 | -0.002 | result | {'execution_numeric_match': 1} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4o_resume/DS_TASK_061/1a2a65ff/trace.jsonl |
| gpt-4o | DS_TASK_062 | 0.000 | 0.000 | 0.000 | 0.000 | timeout | {'none': 2} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4o_resume/DS_TASK_062/4feef8e8/trace.jsonl |
| gpt-4o | DS_TASK_064 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 3} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4o_resume/DS_TASK_064/29ae01ad/trace.jsonl |
| gpt-4o | DS_TASK_066 | 0.000 | 0.000 | 0.000 | 0.000 | timeout | {'none': 3} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4o_resume/DS_TASK_066/6bd38e89/trace.jsonl |
| gpt-4o | DS_TASK_071 | 1.000 | 0.000 | 0.000 | -1.000 | format_extraction_issue | {'none': 1} |  | interaction_p_value | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4o_resume/DS_TASK_071/e2f84fc6/trace.jsonl |
| gpt-4o | DS_TASK_106 | 0.000 | 0.000 | 0.000 | 0.000 | timeout | {'none': 2} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4o_resume/DS_TASK_106/9ee4594e/trace.jsonl |
| gpt-4o | DS_TASK_108 | 0.000 | 0.000 | 0.000 | 0.000 | timeout | {'none': 2} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4o_resume/DS_TASK_108/db63a9ca/trace.jsonl |
| gpt-4o | DS_TASK_111 | 0.000 | 0.000 | 0.000 | 0.000 | timeout | {'none': 3} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4o_resume/DS_TASK_111/55f71d06/trace.jsonl |
| gpt-4o | DS_TASK_120 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 1} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4o_resume/DS_TASK_120/5883c352/trace.jsonl |
| gpt-4o | DS_TASK_121 | 0.000 | 0.000 | 0.000 | 0.000 | timeout | {'none': 2} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4o_resume/DS_TASK_121/c4542c2c/trace.jsonl |
| gpt-4o | DS_TASK_126 | 0.000 | 0.000 | 0.000 | 0.000 | timeout | {'none': 3} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4o_resume/DS_TASK_126/b5875ff7/trace.jsonl |
| gpt-4o | DS_TASK_128 | 0.000 | 0.000 | 0.000 | 0.000 | timeout | {'none': 3} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4o_resume/DS_TASK_128/98bffbfd/trace.jsonl |
| gpt-4o | DS_TASK_139 | 0.000 | 0.000 | 0.000 | 0.000 | partial_completion | {'none': 2} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4o_resume/DS_TASK_139/6eeef06d/trace.jsonl |
| gpt-4o | DS_TASK_141 | 0.000 | 0.000 | 0.000 | 0.000 | timeout | {'none': 2} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4o_resume/DS_TASK_141/0cfe492e/trace.jsonl |
| gpt-4o | DS_TASK_150 | 0.000 | 0.000 | 0.000 | 0.000 | timeout | {'none': 1} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4o_resume/DS_TASK_150/d17e761c/trace.jsonl |
| gpt-4o | DS_TASK_153 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 1} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4o_resume/DS_TASK_153/da1b0faf/trace.jsonl |
| gpt-4o | DS_TASK_158 | 0.000 | 0.000 | 0.000 | 0.000 | partial_completion | {'none': 2} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4o_resume/DS_TASK_158/aa14ee61/trace.jsonl |
| gpt-4o | DS_TASK_165 | 0.000 | 0.000 | 0.000 | 0.000 | timeout | {'none': 3} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4o_resume/DS_TASK_165/55b7fc69/trace.jsonl |
| gpt-4o | DS_TASK_173 | 0.000 | 0.000 | 0.000 | 0.000 | timeout | {'none': 3} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_4o_resume/DS_TASK_173/654d4164/trace.jsonl |
| gpt-5.4 | DS_TASK_059 | 0.068 | 0.000 | 0.000 | -0.068 | format_extraction_issue | {'none': 3} |  | RMSE | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt54/DS_TASK_059/3b0550ba/trace.jsonl |
| gpt-5.4 | DS_TASK_061 | 0.816 | 0.816 | 0.816 | 0.000 | result | {'labeled_stdout': 1} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt54/DS_TASK_061/b031a4ed/trace.jsonl |
| gpt-5.4 | DS_TASK_062 | 0.000 | 0.000 | 0.000 | 0.000 | safety | {'none': 2} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt54/DS_TASK_062/5347c791/trace.jsonl |
| gpt-5.4 | DS_TASK_064 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 3} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt54/DS_TASK_064/7da78343/trace.jsonl |
| gpt-5.4 | DS_TASK_066 | 0.000 | 0.148 | 0.000 | 0.148 | format_extraction_issue | {'labeled_stdout': 1} | total_revenue_clothing |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt54/DS_TASK_066/bd5d13d2/trace.jsonl |
| gpt-5.4 | DS_TASK_071 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 1} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt54/DS_TASK_071/c41eaf36/trace.jsonl |
| gpt-5.4 | DS_TASK_106 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 2} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt54/DS_TASK_106/b898dc44/trace.jsonl |
| gpt-5.4 | DS_TASK_108 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 2} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt54/DS_TASK_108/057d728d/trace.jsonl |
| gpt-5.4 | DS_TASK_111 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 3} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt54/DS_TASK_111/748f1957/trace.jsonl |
| gpt-5.4 | DS_TASK_120 | 0.000 | 0.000 | 0.000 | 0.000 | safety | {'none': 1} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt54/DS_TASK_120/2c0b99fd/trace.jsonl |
| gpt-5.4 | DS_TASK_121 | 0.000 | 0.000 | 0.000 | 0.000 | timeout | {'none': 2} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt54/DS_TASK_121/79b2bfd1/trace.jsonl |
| gpt-5.4 | DS_TASK_126 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 3} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt54/DS_TASK_126/913e2ba4/trace.jsonl |
| gpt-5.4 | DS_TASK_128 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 3} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt54/DS_TASK_128/9098ef4b/trace.jsonl |
| gpt-5.4 | DS_TASK_139 | 0.000 | 0.000 | 0.000 | 0.000 | safety | {'none': 2} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt54/DS_TASK_139/8cbf32df/trace.jsonl |
| gpt-5.4 | DS_TASK_141 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 2} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt54/DS_TASK_141/67cdb92a/trace.jsonl |
| gpt-5.4 | DS_TASK_150 | 0.000 | 0.000 | 0.000 | 0.000 | partial_completion | {'none': 1} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt54/DS_TASK_150/17679f54/trace.jsonl |
| gpt-5.4 | DS_TASK_153 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 1} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt54/DS_TASK_153/cb1c0300/trace.jsonl |
| gpt-5.4 | DS_TASK_158 | 0.000 | 0.000 | 0.000 | 0.000 | partial_completion | {'none': 2} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt54/DS_TASK_158/3e682588/trace.jsonl |
| gpt-5.4 | DS_TASK_165 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 3} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt54/DS_TASK_165/5c3bdeb5/trace.jsonl |
| gpt-5.4 | DS_TASK_173 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 3} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt54/DS_TASK_173/bccedfcf/trace.jsonl |
| gpt-5.3-codex | DS_TASK_059 | 0.000 | 0.000 | 0.000 | 0.000 | format_extraction_issue | {'none': 3} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt53codex/DS_TASK_059/e343cc20/trace.jsonl |
| gpt-5.3-codex | DS_TASK_061 | 1.000 | 0.000 | 0.000 | -1.000 | format_extraction_issue | {'none': 1} |  | average_stay_duration_readmitted | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt53codex/DS_TASK_061/8a3bc187/trace.jsonl |
| gpt-5.3-codex | DS_TASK_062 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 2} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt53codex/DS_TASK_062/5d338aec/trace.jsonl |
| gpt-5.3-codex | DS_TASK_064 | 0.199 | 0.000 | 0.000 | -0.199 | result | {'none': 3} |  | hazard_ratio_BMI | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt53codex/DS_TASK_064/8df26752/trace.jsonl |
| gpt-5.3-codex | DS_TASK_066 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 3} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt53codex/DS_TASK_066/8f8cb4eb/trace.jsonl |
| gpt-5.3-codex | DS_TASK_071 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 1} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt53codex/DS_TASK_071/b9eaab7d/trace.jsonl |
| gpt-5.3-codex | DS_TASK_106 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 2} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt53codex/DS_TASK_106/37cd03f9/trace.jsonl |
| gpt-5.3-codex | DS_TASK_108 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 2} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt53codex/DS_TASK_108/a5638abc/trace.jsonl |
| gpt-5.3-codex | DS_TASK_111 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 3} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt53codex/DS_TASK_111/cf131b24/trace.jsonl |
| gpt-5.3-codex | DS_TASK_120 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 1} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt53codex/DS_TASK_120/288ff372/trace.jsonl |
| gpt-5.3-codex | DS_TASK_121 | 0.000 | 0.000 | 0.000 | 0.000 | safety | {'none': 2} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt53codex/DS_TASK_121/a5cd8de3/trace.jsonl |
| gpt-5.3-codex | DS_TASK_126 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 3} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt53codex/DS_TASK_126/a276fbcc/trace.jsonl |
| gpt-5.3-codex | DS_TASK_128 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 3} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt53codex/DS_TASK_128/861a3529/trace.jsonl |
| gpt-5.3-codex | DS_TASK_139 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 2} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt53codex/DS_TASK_139/4668d4ec/trace.jsonl |
| gpt-5.3-codex | DS_TASK_141 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 2} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt53codex/DS_TASK_141/1f5b9405/trace.jsonl |
| gpt-5.3-codex | DS_TASK_150 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 1} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt53codex/DS_TASK_150/723c1c94/trace.jsonl |
| gpt-5.3-codex | DS_TASK_153 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 1} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt53codex/DS_TASK_153/2de4bba2/trace.jsonl |
| gpt-5.3-codex | DS_TASK_158 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 2} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt53codex/DS_TASK_158/23aa5d6f/trace.jsonl |
| gpt-5.3-codex | DS_TASK_165 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 3} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt53codex/DS_TASK_165/45dcf62d/trace.jsonl |
| gpt-5.3-codex | DS_TASK_173 | 0.000 | 0.000 | 0.000 | 0.000 | result | {'none': 3} |  |  | /Users/bytedance/Desktop/bench/bench_runs_validity_v2_20task_20260520_112725_gpt53codex/DS_TASK_173/5ceee8f6/trace.jsonl |
