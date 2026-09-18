# DataAgentBench Pilot-20 Ground Truth Audit

This audit is read-only: it does not modify source tasks or reports.

## Summary

| Status | Count |
| --- | ---: |
| GT_VALUE_MISMATCH | 11 |
| PASS_RECOMPUTED | 3 |
| PROMPT_GT_MISMATCH | 2 |
| UNVERIFIABLE_GENERATION_TRACE | 4 |

## Per-task Audit

| Task | Domain | Diff | Generator | Verified | Errors | Forced | Status | GT | Recomputed | Issues |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- |
| DS_TASK_126 | Biomedical | Hard | dataagent:custom | False | 0 | False | PROMPT_GT_MISMATCH | {"correlation": 1.0, "mean_value": 14.3567, "outlier_count": 327} | {"correlation": 0.5301, "mean_value": 14.3567, "outlier_count": 327} | GT_VALUE_MISMATCH: correlation gt=1.0 recomputed=0.5301; PROMPT_GT_MISMATCH: template GT keys do not match advanced task tags; UNVERIFIED: generation_meta.verified=false |
| DS_TASK_141 | ECommerce | Medium | dataagent:custom | False | 0 | False | GT_VALUE_MISMATCH | {"max_correlation": 1.0, "total_missing": 940} | {"max_correlation": 0.8672, "total_missing": 940} | GT_VALUE_MISMATCH: max_correlation gt=1.0 recomputed=0.8672; UNVERIFIED: generation_meta.verified=false |
| DS_TASK_064 | Biomedical | Hard | openai:gpt-4o | False | 1 | True | UNVERIFIABLE_GENERATION_TRACE | {"cox_p_value": 0.03, "hazard_ratio_BMI": 1.15, "median_survival_time": 365} | {} | UNVERIFIED: generation_meta.verified=false; GENERATION_TRACE_ERRORS: 1; FORCED_SUBMIT: generation trace ended with forced submit |
| DS_TASK_108 | Finance | Medium | dataagent:custom | False | 0 | False | PROMPT_GT_MISMATCH | {"max_correlation": 1.0, "total_missing": 479} | {"max_correlation": 0.1321, "total_missing": 479} | GT_VALUE_MISMATCH: max_correlation gt=1.0 recomputed=0.1321; PROMPT_GT_MISMATCH: template GT keys do not match advanced task tags; UNVERIFIED: generation_meta.verified=false |
| DS_TASK_165 | Scientific | Hard | dataagent:custom | False | 0 | False | GT_VALUE_MISMATCH | {"correlation": 1.0, "mean_value": 38.1345, "outlier_count": 1193} | {"correlation": 0.6695, "mean_value": 38.1345, "outlier_count": 1193} | GT_VALUE_MISMATCH: correlation gt=1.0 recomputed=0.6695; UNVERIFIED: generation_meta.verified=false |
| DS_TASK_062 | Biomedical | Medium | openai:gpt-4o | False | 2 | True | UNVERIFIABLE_GENERATION_TRACE | {"r_squared": 0.65, "rmse": 15.3} | {} | UNVERIFIED: generation_meta.verified=false; GENERATION_TRACE_ERRORS: 2; FORCED_SUBMIT: generation trace ended with forced submit |
| DS_TASK_120 | Biomedical | Easy | dataagent:custom | False | 0 | False | PASS_RECOMPUTED | {"mean_value": 450.5463} | {"mean_value": 450.5463} | UNVERIFIED: generation_meta.verified=false |
| DS_TASK_106 | Finance | Medium | dataagent:custom | False | 0 | False | GT_VALUE_MISMATCH | {"max_correlation": 1.0, "total_missing": 508} | {"max_correlation": 0.1544, "total_missing": 508} | GT_VALUE_MISMATCH: max_correlation gt=1.0 recomputed=0.1544; UNVERIFIED: generation_meta.verified=false |
| DS_TASK_150 | Scientific | Easy | dataagent:custom | False | 0 | False | PASS_RECOMPUTED | {"mean_value": 6.0011} | {"mean_value": 6.0011} | UNVERIFIED: generation_meta.verified=false |
| DS_TASK_111 | Finance | Hard | dataagent:custom | False | 0 | False | GT_VALUE_MISMATCH | {"correlation": 1.0, "mean_value": 163.5068, "outlier_count": 1301} | {"correlation": 0.8295, "mean_value": 163.5068, "outlier_count": 1301} | GT_VALUE_MISMATCH: correlation gt=1.0 recomputed=0.8295; UNVERIFIED: generation_meta.verified=false |
| DS_TASK_059 | Finance | Hard | openai:gpt-4o | False | 4 | True | UNVERIFIABLE_GENERATION_TRACE | {"RMSE": 2.53, "forecast_value_Feb_2024": 106.8, "forecast_value_Jan_2024": 105.2} | {} | UNVERIFIED: generation_meta.verified=false; GENERATION_TRACE_ERRORS: 4; FORCED_SUBMIT: generation trace ended with forced submit |
| DS_TASK_158 | Scientific | Medium | dataagent:custom | False | 0 | False | GT_VALUE_MISMATCH | {"max_correlation": 1.0, "total_missing": 467} | {"max_correlation": 0.8271, "total_missing": 467} | GT_VALUE_MISMATCH: max_correlation gt=1.0 recomputed=0.8271; UNVERIFIED: generation_meta.verified=false |
| DS_TASK_066 | ECommerce | Easy | openai:gpt-4o | False | 1 | True | GT_VALUE_MISMATCH | {"total_revenue_clothing": 15000, "total_revenue_electronics": 21000, "total_revenue_home": 12000} | {"total_revenue_clothing": 12585.89, "total_revenue_electronics": 1062788.49, "total_revenue_home": 4442.07} | GT_VALUE_MISMATCH: total_revenue_clothing gt=15000 recomputed=12585.89; GT_VALUE_MISMATCH: total_revenue_electronics gt=21000 recomputed=1062788.49; GT_VALUE_MISMATCH: total_revenue_home gt=12000 recomputed=4442.07; UNVERIFIED: generation_meta.verified=false; GENERATION_TRACE_ERRORS: 1; FORCED_SUBMIT: generation trace ended with forced submit |
| DS_TASK_121 | Biomedical | Medium | dataagent:custom | False | 0 | False | GT_VALUE_MISMATCH | {"max_correlation": 1.0, "total_missing": 273} | {"max_correlation": 0.8214, "total_missing": 273} | GT_VALUE_MISMATCH: max_correlation gt=1.0 recomputed=0.8214; UNVERIFIED: generation_meta.verified=false |
| DS_TASK_153 | Scientific | Easy | dataagent:custom | False | 0 | False | PASS_RECOMPUTED | {"mean_value": 6.0001} | {"mean_value": 6.0001} | UNVERIFIED: generation_meta.verified=false |
| DS_TASK_071 | Scientific | Easy | openai:gpt-4o | False | 5 | True | UNVERIFIABLE_GENERATION_TRACE | {"interaction_p_value": 0.041} | {} | UNVERIFIED: generation_meta.verified=false; GENERATION_TRACE_ERRORS: 5; FORCED_SUBMIT: generation trace ended with forced submit |
| DS_TASK_139 | ECommerce | Medium | dataagent:custom | False | 0 | False | GT_VALUE_MISMATCH | {"max_correlation": 1.0, "total_missing": 918} | {"max_correlation": 0.8581, "total_missing": 918} | GT_VALUE_MISMATCH: max_correlation gt=1.0 recomputed=0.8581; UNVERIFIED: generation_meta.verified=false |
| DS_TASK_128 | Biomedical | Hard | dataagent:custom | False | 0 | False | GT_VALUE_MISMATCH | {"correlation": 1.0, "mean_value": 14.4578, "outlier_count": 349} | {"correlation": 0.5496, "mean_value": 14.4578, "outlier_count": 349} | GT_VALUE_MISMATCH: correlation gt=1.0 recomputed=0.5496; UNVERIFIED: generation_meta.verified=false |
| DS_TASK_061 | Biomedical | Easy | openai:gpt-4o | False | 3 | True | GT_VALUE_MISMATCH | {"average_stay_duration_readmitted": 8.1} | {"average_stay_duration_readmitted": 7.397163120567376} | GT_VALUE_MISMATCH: average_stay_duration_readmitted gt=8.1 recomputed=7.397163120567376; UNVERIFIED: generation_meta.verified=false; GENERATION_TRACE_ERRORS: 3; FORCED_SUBMIT: generation trace ended with forced submit |
| DS_TASK_173 | Generic | Hard | dataagent:custom | False | 0 | False | GT_VALUE_MISMATCH | {"correlation": 1.0, "mean_value": 420.2769, "outlier_count": 215} | {"correlation": 0.1055, "mean_value": 420.2769, "outlier_count": 215} | GT_VALUE_MISMATCH: correlation gt=1.0 recomputed=0.1055; UNVERIFIED: generation_meta.verified=false |
