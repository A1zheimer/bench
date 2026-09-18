# Verified Redteam V1 Smoke Report

- generated_at: `2026-05-21T03:54:52.408036+00:00`
- output_dir: `/Users/bytedance/Desktop/bench/tasks_verified_redteam_v1`
- tasks_file: `/Users/bytedance/Desktop/bench/tasks_verified_redteam_v1_tasks.json`
- total_tasks: `15`
- bench_repo_verified_load_count: `15`
- invariant/recomputed_checks: `PASS`

## Attack Distribution

| Value | Count |
|---|---:|
| dirty_data | 5 |
| distractor_columns | 5 |
| schema_obfuscation | 5 |

## GT Policy Distribution

| Value | Count |
|---|---:|
| invariant | 10 |
| recomputed | 5 |

## Tasks

| Task | Base Task | Template | Attack | GT Policy | Keys | Replay |
|---|---|---|---|---|---:|---|
| DS_TASK_900011 | DS_TASK_000001 | filtered_mean_v1 | schema_obfuscation | invariant | 1 | PASS |
| DS_TASK_900012 | DS_TASK_000001 | filtered_mean_v1 | distractor_columns | invariant | 1 | PASS |
| DS_TASK_900013 | DS_TASK_000001 | filtered_mean_v1 | dirty_data | recomputed | 1 | PASS |
| DS_TASK_900021 | DS_TASK_000003 | groupby_aggregation_v1 | schema_obfuscation | invariant | 6 | PASS |
| DS_TASK_900022 | DS_TASK_000003 | groupby_aggregation_v1 | distractor_columns | invariant | 6 | PASS |
| DS_TASK_900023 | DS_TASK_000003 | groupby_aggregation_v1 | dirty_data | recomputed | 6 | PASS |
| DS_TASK_900031 | DS_TASK_000005 | correlation_pair_v1 | schema_obfuscation | invariant | 1 | PASS |
| DS_TASK_900032 | DS_TASK_000005 | correlation_pair_v1 | distractor_columns | invariant | 1 | PASS |
| DS_TASK_900033 | DS_TASK_000005 | correlation_pair_v1 | dirty_data | recomputed | 1 | PASS |
| DS_TASK_900041 | DS_TASK_000007 | iqr_outlier_count_v1 | schema_obfuscation | invariant | 3 | PASS |
| DS_TASK_900042 | DS_TASK_000007 | iqr_outlier_count_v1 | distractor_columns | invariant | 3 | PASS |
| DS_TASK_900043 | DS_TASK_000007 | iqr_outlier_count_v1 | dirty_data | recomputed | 3 | PASS |
| DS_TASK_900051 | DS_TASK_000009 | crosstab_prevalence_v1 | schema_obfuscation | invariant | 3 | PASS |
| DS_TASK_900052 | DS_TASK_000009 | crosstab_prevalence_v1 | distractor_columns | invariant | 3 | PASS |
| DS_TASK_900053 | DS_TASK_000009 | crosstab_prevalence_v1 | dirty_data | recomputed | 3 | PASS |
