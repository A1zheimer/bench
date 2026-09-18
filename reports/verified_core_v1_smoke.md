# Verified Core V1 Smoke Report

- generated_at: `2026-05-21T03:54:20.969011+00:00`
- output_dir: `/Users/bytedance/Desktop/bench/tasks_verified_core_v1`
- tasks_file: `/Users/bytedance/Desktop/bench/tasks_verified_core_v1_tasks.json`
- total_tasks: `12`
- bench_repo_verified_load_count: `12`
- gt_replay: `PASS`

Formal note: legacy pilot20/121 and taskgen candidate tasks are excluded from formal model conclusions.

## Template Distribution

| Value | Count |
|---|---:|
| correlation_pair_v1 | 2 |
| crosstab_prevalence_v1 | 2 |
| filtered_mean_v1 | 2 |
| groupby_aggregation_v1 | 2 |
| iqr_outlier_count_v1 | 2 |
| model_eval_metric_v1 | 2 |

## Domain Distribution

| Value | Count |
|---|---:|
| Biomedical | 2 |
| ECommerce | 3 |
| Finance | 4 |
| Generic | 1 |
| Scientific | 2 |

## Difficulty Distribution

| Value | Count |
|---|---:|
| Easy | 4 |
| Hard | 2 |
| Medium | 6 |

## Tasks

| Task | Template | Domain | Difficulty | Keys | Replay | Dataset SHA256 |
|---|---|---|---|---:|---|---|
| DS_TASK_000001 | filtered_mean_v1 | ECommerce | Easy | 1 | PASS | `aeda49dab7c5...` |
| DS_TASK_000002 | filtered_mean_v1 | Finance | Medium | 1 | PASS | `e227544d2119...` |
| DS_TASK_000003 | groupby_aggregation_v1 | ECommerce | Easy | 6 | PASS | `f3b76058c726...` |
| DS_TASK_000004 | groupby_aggregation_v1 | Finance | Medium | 4 | PASS | `32dd29357a2e...` |
| DS_TASK_000005 | correlation_pair_v1 | Scientific | Easy | 1 | PASS | `1479c5dd092d...` |
| DS_TASK_000006 | correlation_pair_v1 | Finance | Medium | 1 | PASS | `c862926450fe...` |
| DS_TASK_000007 | iqr_outlier_count_v1 | Generic | Medium | 3 | PASS | `22df4ad5dc6e...` |
| DS_TASK_000008 | iqr_outlier_count_v1 | Scientific | Hard | 3 | PASS | `fa26ec991dd7...` |
| DS_TASK_000009 | crosstab_prevalence_v1 | Biomedical | Easy | 3 | PASS | `921d7b5d29bb...` |
| DS_TASK_000010 | crosstab_prevalence_v1 | ECommerce | Medium | 3 | PASS | `b5d72248085a...` |
| DS_TASK_000011 | model_eval_metric_v1 | Biomedical | Medium | 1 | PASS | `55fe7ac5955a...` |
| DS_TASK_000012 | model_eval_metric_v1 | Finance | Hard | 2 | PASS | `0d91f694fe65...` |
