#!/bin/bash
# run_all_baselines.sh — Week 1: Run all model baselines
# Usage: bash scripts/run_all_baselines.sh
# Prerequisites: .env with API keys configured

set -e
cd "$(dirname "$0")/.."

echo "============================================"
echo "DataAgentBench — Baseline Data Collection"
echo "============================================"

# Load .env
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
    echo "✅ .env loaded"
else
    echo "❌ .env not found! Copy .env.example and fill in API keys."
    exit 1
fi

TASKS_FILE="./core_80_tasks.json"
DB="bench_neurips.db"
TEMP="0.0"

# --- Closed-source API Models ---

echo ""
echo ">>> [1/7] NativeAgent / GPT-4o-mini..."
python -m data_agent_bench run \
    --tasks-file "$TASKS_FILE" \
    --agent native:openai/gpt-4o-mini \
    --output-dir ./runs/native_4omini/clean \
    --db "$DB" --temperature "$TEMP"

echo ""
echo ">>> [2/7] NativeAgent / GPT-4o..."
python -m data_agent_bench run \
    --tasks-file "$TASKS_FILE" \
    --agent native:openai/gpt-4o \
    --output-dir ./runs/native_gpt4o/clean \
    --db "$DB" --temperature "$TEMP"

echo ""
echo ">>> [3/7] NativeAgent / Claude Sonnet..."
python -m data_agent_bench run \
    --tasks-file "$TASKS_FILE" \
    --agent native:anthropic/claude-sonnet-4-5 \
    --output-dir ./runs/native_claude/clean \
    --db "$DB" --temperature "$TEMP"

echo ""
echo ">>> [4/7] NativeAgent / DeepSeek-V3..."
python -m data_agent_bench run \
    --tasks-file "$TASKS_FILE" \
    --agent native:deepseek/deepseek-chat \
    --output-dir ./runs/native_deepseek/clean \
    --db "$DB" --temperature "$TEMP"

# --- Open-source via vLLM (requires HPC/local vLLM server) ---

echo ""
echo ">>> [5/7] NativeAgent / Qwen2.5-Coder-7B (vLLM)..."
if curl -s http://localhost:8000/v1/models > /dev/null 2>&1; then
    OPENAI_BASE_URL=http://localhost:8000/v1 OPENAI_API_KEY=dummy \
    python -m data_agent_bench run \
        --tasks-file "$TASKS_FILE" \
        --agent native:vllm/Qwen2.5-Coder-7B-Instruct \
        --output-dir ./runs/native_qwen7b/clean \
        --db "$DB" --temperature "$TEMP"
else
    echo "    ⚠️  vLLM server not detected. Skipping. Start with:"
    echo "    python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-Coder-7B-Instruct --port 8000"
fi

# --- Third-party Agent Frameworks (requires Docker containers) ---

echo ""
echo ">>> [6/7] MetaGPT DataInterpreter / GPT-4o..."
if curl -s http://localhost:8100/health > /dev/null 2>&1; then
    python -m data_agent_bench run \
        --tasks-file "$TASKS_FILE" \
        --agent metagpt:gpt-4o \
        --output-dir ./runs/data_interpreter/clean \
        --db "$DB" --temperature "$TEMP"
else
    echo "    ⚠️  MetaGPT container not running. Start with: docker compose up -d metagpt"
fi

echo ""
echo ">>> [7/7] Open Interpreter / GPT-4o..."
if curl -s http://localhost:8101/health > /dev/null 2>&1; then
    python -m data_agent_bench run \
        --tasks-file "$TASKS_FILE" \
        --agent open-interpreter:gpt-4o \
        --output-dir ./runs/open_interpreter/clean \
        --db "$DB" --temperature "$TEMP"
else
    echo "    ⚠️  Open Interpreter container not running. Start with: docker compose up -d open-interpreter"
fi

echo ""
echo "============================================"
echo "✅ All baselines completed!"
echo "Results DB: $DB"
echo "============================================"
