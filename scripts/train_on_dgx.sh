#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "============================================================"
echo "DataAgentBench - TaskGen LoRA Training on DGX Spark"
echo "============================================================"

ARCH=$(uname -m)
echo "Architecture: $ARCH"
echo "Python: $(python3 --version 2>&1)"

if command -v nvidia-smi &>/dev/null; then
    echo "GPU:"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo "  (nvidia-smi available but query failed)"
fi

echo ""
echo "=== Step 1/4: Installing dependencies ==="
pip install --upgrade pip

if [[ "$ARCH" == "aarch64" ]]; then
    echo "  Detected ARM64 (DGX Spark / Grace CPU)"
    pip install torch torchvision
else
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
fi

pip install 'transformers>=4.46.0' 'peft>=0.14.0' 'trl>=0.12.0' 'datasets>=3.0.0' 'accelerate>=1.0.0'
pip install pandas tabulate

if [[ "$ARCH" == "aarch64" ]]; then
    echo "  Skipping bitsandbytes on ARM64 (optional, may need source build)"
    pip install bitsandbytes 2>/dev/null || echo "  Warning: bitsandbytes install failed, --quantize flag will not work"
else
    pip install 'bitsandbytes>=0.44.0'
fi

pip install -e . 2>/dev/null || echo "  Warning: editable install failed, continuing..."

echo ""
echo "=== Step 2/4: Verifying PyTorch + CUDA ==="
python3 -c "
import torch
print(f'  PyTorch version: {torch.__version__}')
print(f'  CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'  GPU: {torch.cuda.get_device_name(0)}')
    print(f'  VRAM: {torch.cuda.get_device_properties(0).total_mem / 1e9:.1f} GB')
    print(f'  bf16 support: {torch.cuda.is_bf16_supported()}')
else:
    print('  WARNING: No CUDA GPU detected. Training will use CPU (very slow)')
"

echo ""
echo "=== Step 3/4: Exporting SFT training data ==="
mkdir -p sft_data models
python3 scripts/export_taskgen_sft.py \
    --tasks-dir ./tasks \
    --output ./sft_data/taskgen_train.jsonl

RECORD_COUNT=$(wc -l < sft_data/taskgen_train.jsonl | tr -d ' ')
echo "  Exported $RECORD_COUNT training records"

if [ "$RECORD_COUNT" -lt 5 ]; then
    echo "ERROR: Too few training records ($RECORD_COUNT). Need at least 5."
    exit 1
fi

echo ""
echo "=== Step 4/4: Starting LoRA fine-tuning ==="
echo "  Model: Qwen/Qwen2.5-Coder-7B-Instruct"
echo "  Data: $RECORD_COUNT records"
echo "  Config: LoRA r=16, alpha=32, epochs=3, lr=2e-4, bf16"
echo ""

python3 scripts/train_taskgen_lora.py \
    --model Qwen/Qwen2.5-Coder-7B-Instruct \
    --data ./sft_data/taskgen_train.jsonl \
    --output ./models/taskgen-lora \
    --epochs 3 \
    --batch-size 1 \
    --grad-accum 4 \
    --lr 2e-4 \
    --max-seq-length 8192 \
    --lora-r 16 \
    --merge-and-save

echo ""
echo "============================================================"
echo "Training complete!"
echo "============================================================"
echo ""
echo "Output files:"
echo "  LoRA adapter:  ./models/taskgen-lora/"
echo "  Merged model:  ./models/taskgen-lora/merged/"
echo "  Training data: ./sft_data/taskgen_train.jsonl"
echo ""
echo "Next steps:"
echo "  1. Copy merged model to your dev machine:"
echo "     scp -r <dgx>:$(pwd)/models/taskgen-lora/merged/ ./models/taskgen-lora-merged/"
echo ""
echo "  2. Use as task generator (via vLLM):"
echo "     python -m data_agent_bench generate --agent vllm:./models/taskgen-lora/merged"
echo ""
echo "  3. Or push to HuggingFace Hub:"
echo "     huggingface-cli upload <org>/taskgen-qwen2.5-coder-7b-lora ./models/taskgen-lora/merged/"
