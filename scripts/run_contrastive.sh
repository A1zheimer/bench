#!/bin/bash
# run_contrastive.sh — Week 2: Run contrastive experiments (L1/L2/L3)
# Usage: bash scripts/run_contrastive.sh

set -e
cd "$(dirname "$0")/.."

echo "============================================"
echo "DataAgentBench — Contrastive Experiments"
echo "============================================"

if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

TASKS_FILE="./core_80_tasks.json"
DB="experiments_neurips.db"
TEMP="0.0"

# NativeAgent 系列 — L1/L2/L3 扰动实验
python -m data_agent_bench experiment \
    --agent \
        native:openai/gpt-4o-mini \
        native:openai/gpt-4o \
        native:anthropic/claude-sonnet-4-5 \
        native:deepseek/deepseek-chat \
    --levels 1 2 3 \
    --tasks-file "$TASKS_FILE" \
    --output-dir ./experiments/native \
    --db "$DB" \
    --temperature "$TEMP"

# MetaGPT DataInterpreter — 需 Docker 容器
if curl -s http://localhost:8100/health > /dev/null 2>&1; then
    python -m data_agent_bench experiment \
        --agent metagpt:gpt-4o \
        --levels 1 2 3 \
        --tasks-file "$TASKS_FILE" \
        --output-dir ./experiments/metagpt \
        --db "$DB" \
        --temperature "$TEMP"
else
    echo "⚠️  MetaGPT container not running. Skipping. Run: docker compose up -d metagpt"
fi

# Open Interpreter — 需 Docker 容器
if curl -s http://localhost:8101/health > /dev/null 2>&1; then
    python -m data_agent_bench experiment \
        --agent open-interpreter:gpt-4o \
        --levels 1 2 3 \
        --tasks-file "$TASKS_FILE" \
        --output-dir ./experiments/open_interpreter \
        --db "$DB" \
        --temperature "$TEMP"
else
    echo "⚠️  Open Interpreter container not running. Skipping. Run: docker compose up -d open-interpreter"
fi

# Qwen-7B via vLLM — 需 HPC 节点
if curl -s http://localhost:8000/v1/models > /dev/null 2>&1; then
    OPENAI_BASE_URL=http://localhost:8000/v1 OPENAI_API_KEY=dummy \
    python -m data_agent_bench experiment \
        --agent native:vllm/Qwen2.5-Coder-7B-Instruct \
        --levels 1 2 3 \
        --tasks-file "$TASKS_FILE" \
        --output-dir ./experiments/qwen7b \
        --db "$DB" \
        --temperature "$TEMP"
else
    echo "⚠️  vLLM server not running. Skipping Qwen-7B contrastive."
fi

echo ""
echo "============================================"
echo "✅ Contrastive experiments completed!"
echo "Results DB: $DB"
echo "============================================"
