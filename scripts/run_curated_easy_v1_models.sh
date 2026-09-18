#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/bytedance/Desktop/bench"
PY="/Users/bytedance/.pyenv/versions/3.11.9/bin/python3"
TASKS_DIR="$ROOT/tasks_curated_easy_v1"
TASKS_FILE="$ROOT/curated_easy5_tasks.json"

run_model() {
  local label="$1"
  local agent="$2"
  local output_dir="$ROOT/bench_runs_curated_easy_v1_${label}_api"
  local db_path="$ROOT/bench_curated_easy_v1_${label}_api.db"

  echo "==> Running ${label}: ${agent}"
  "$PY" -m data_agent_bench.cli run \
    --tasks-dir "$TASKS_DIR" \
    --tasks-file "$TASKS_FILE" \
    --agent "$agent" \
    --output-dir "$output_dir" \
    --db "$db_path" \
    --env local \
    --temperature 0 \
    --runs 1
}

cd "$ROOT"

run_model "4omini" "native:openai/gpt-4o-mini"
run_model "4o" "native:openai/gpt-4o"
run_model "gpt54" "native:llmbox/gpt-5.4"
run_model "gpt53codex" "native:llmbox/gpt-5.3-codex"

"$PY" scripts/rescore_v3_reports.py \
  --tasks-dir "$TASKS_DIR" \
  --run "gpt-4o-mini=$ROOT/bench_runs_curated_easy_v1_4omini_api" \
  --run "gpt-4o=$ROOT/bench_runs_curated_easy_v1_4o_api" \
  --run "gpt-5.4=$ROOT/bench_runs_curated_easy_v1_gpt54_api" \
  --run "gpt-5.3-codex=$ROOT/bench_runs_curated_easy_v1_gpt53codex_api" \
  --output "$ROOT/reports/curated_easy_v1_rescore.md"

echo "==> Wrote $ROOT/reports/curated_easy_v1_rescore.md"
