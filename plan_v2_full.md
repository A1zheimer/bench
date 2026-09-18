# DataAgentBench NeurIPS 2026 — 21天逐步冲刺计划

## 核心 Deadline

- **Abstract 注册**：2026-05-04 AoE（距今 19 天）
- **Full Paper 提交**：2026-05-06 AoE（距今 21 天）
- **投稿 Track**：NeurIPS 2026 Evaluations and Datasets Track
- **要求**：代码可执行 + Croissant 元数据 + 正文 9 页以内

---

## Day 0 — 4月15日（今天）：环境准备

### 上午：账号与资金

**Step 1：检查 API 余额**
```bash
# OpenAI
curl https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY" 
# 登录 platform.openai.com → Settings → Billing 确认余额 ≥ $50

# Anthropic
# 登录 console.anthropic.com → Billing 确认余额 ≥ $30
```
- [ ] OpenAI 余额 ≥ $50 ✅
- [ ] Anthropic 余额 ≥ $30 ✅
- [ ] 如不够，立刻充值（报销找 leader 签字）

**Step 2：提交 HPC 申请**
```
集群：HPC 二期 HPC AI 平台
资源：1 × NVIDIA A800-80GB
时长：3 天
用途：LLM benchmark 评测，vLLM 部署 Qwen2.5-Coder-7B (14GB 显存)
```
- [ ] HPC 申请已提交 ✅

### 下午：本地环境搭建（M4 Pro）

**Step 3：项目环境**
```bash
cd ~/bench
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
- [ ] `python -m data_agent_bench --help` 能正常输出 ✅

**Step 4：安装开源框架**
```bash
# MetaGPT Data Interpreter
pip install metagpt
# 验证
python -c "from metagpt.roles.di.data_interpreter import DataInterpreter; print('OK')"

# Open Interpreter  
pip install open-interpreter
# 验证
python -c "from interpreter import interpreter; print('OK')"
```
- [ ] MetaGPT 安装成功 ✅
- [ ] Open Interpreter 安装成功 ✅

**Step 5：配置 .env**
```bash
cat > .env << 'EOF'
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx
EOF
```
- [ ] .env 配置完成 ✅

**Step 6：拉 LaTeX 模板**
```bash
# 在 Overleaf 上新建项目，选 NeurIPS 2026 模板
# 或本地
git clone https://github.com/neurips/neurips_2026_latex_template.git paper/
```
- [ ] LaTeX 模板就绪 ✅

**Step 7：选定 80 个核心 tasks**
```python
# scripts/select_core_tasks.py
import json, os, random
random.seed(42)

tasks_dir = "./tasks"
all_tasks = sorted(os.listdir(tasks_dir))

# 按 domain × difficulty 分层抽样
selected = []
for domain in ["Finance", "Biomedical", "ECommerce", "Scientific", "Generic"]:
    for diff in ["Easy", "Medium", "Hard"]:
        candidates = []
        for t in all_tasks:
            meta = json.load(open(f"{tasks_dir}/{t}/task.json"))["task_metadata"]
            if meta["domain"] == domain and meta["difficulty"] == diff:
                candidates.append(t)
        # 每组取 5-6 个
        n = min(6, len(candidates))
        selected.extend(random.sample(candidates, n))

with open("core_80_tasks.json", "w") as f:
    json.dump(selected[:80], f, indent=2)
print(f"Selected {len(selected[:80])} tasks")
```
```bash
python scripts/select_core_tasks.py
```
- [ ] `core_80_tasks.json` 已生成（80 个 task ID）✅

### 今日交付物
- [x] API keys 就绪
- [x] HPC 已申请
- [x] 本地环境可运行
- [x] 80 个核心 tasks 已选定
- [x] LaTeX 模板就绪

---

## Day 1 — 4月16日：Pilot 实验 + Adapter 开发

### 上午：Pilot 实验启动

**Step 8：从 80 个 tasks 中抽 20 个做 Pilot**
```python
# scripts/select_pilot.py
import json, random
random.seed(123)
core = json.load(open("core_80_tasks.json"))
pilot = random.sample(core, 20)
with open("pilot_20_tasks.json", "w") as f:
    json.dump(pilot, f, indent=2)
print(f"Pilot tasks: {pilot}")
```

**Step 9：跑 GPT-4o-mini Pilot L1/L2/L3**
```bash
# L1
python -m data_agent_bench experiment \
    --agent native:openai/gpt-4o-mini \
    --levels 1 \
    --tasks-file pilot_20_tasks.json \
    --output-dir ./pilot/L1 \
    --db pilot.db \
    --temperature 0.0

# L2（等 L1 跑完后启动，或同时开新终端）
python -m data_agent_bench experiment \
    --agent native:openai/gpt-4o-mini \
    --levels 2 \
    --tasks-file pilot_20_tasks.json \
    --output-dir ./pilot/L2 \
    --db pilot.db \
    --temperature 0.0

# L3
python -m data_agent_bench experiment \
    --agent native:openai/gpt-4o-mini \
    --levels 3 \
    --tasks-file pilot_20_tasks.json \
    --output-dir ./pilot/L3 \
    --db pilot.db \
    --temperature 0.0
```
- [ ] L1 跑完：20 runs ✅
- [ ] L2 跑完：20 runs ✅
- [ ] L3 跑完：20 runs ✅

### 下午：写两个 Adapter

**Step 10：DataInterpreter Adapter**

创建文件 `data_agent_bench/engine/adapters/metagpt_adapter.py`：
```python
"""MetaGPT DataInterpreter adapter for DataAgentBench."""
import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List

from metagpt.roles.di.data_interpreter import DataInterpreter

from ...models.task import TaskInput
from ...models.report import AgentTrace, TraceStep


class DataInterpreterAdapter:
    """Wraps MetaGPT DataInterpreter as a benchmark-compatible agent."""

    def __init__(self, model: str = "gpt-4o", max_steps: int = 10):
        self.model = model
        self.max_steps = max_steps

    async def _run_async(self, task: TaskInput, data_dir: Path) -> Dict[str, Any]:
        di = DataInterpreter(max_auto_run=self.max_steps)
        prompt = (
            f"{task.context.problem_statement}\n\n"
            f"Dataset is at: {data_dir / 'data/dataset.csv'}\n"
            f"Return your final numerical answer as a Python dict."
        )
        start = time.time()
        result = await di.run(prompt)
        wall_time = time.time() - start
        return {
            "result": str(result),
            "wall_time": wall_time,
            "steps": di.working_memory.history if hasattr(di, 'working_memory') else [],
        }

    def run(self, task: TaskInput, data_dir: Path) -> AgentTrace:
        raw = asyncio.run(self._run_async(task, data_dir))
        # Parse into standard AgentTrace format
        trace = AgentTrace(
            steps=[],
            final_answer=raw["result"],
            wall_time=raw["wall_time"],
            agent_type="metagpt_data_interpreter",
            model=self.model,
        )
        return trace
```

**Step 11：Open Interpreter Adapter**

创建文件 `data_agent_bench/engine/adapters/open_interpreter_adapter.py`：
```python
"""Open Interpreter adapter for DataAgentBench."""
import time
from pathlib import Path
from typing import Any, Dict

from interpreter import interpreter

from ...models.task import TaskInput
from ...models.report import AgentTrace


class OpenInterpreterAdapter:
    """Wraps Open Interpreter as a benchmark-compatible agent."""

    def __init__(self, model: str = "gpt-4o", max_steps: int = 10):
        self.model = model
        interpreter.llm.model = model
        interpreter.auto_run = True  # No human confirmation
        interpreter.llm.max_tokens = 4096
        interpreter.max_output = 10000

    def run(self, task: TaskInput, data_dir: Path) -> AgentTrace:
        prompt = (
            f"{task.context.problem_statement}\n\n"
            f"Dataset is at: {data_dir / 'data/dataset.csv'}\n"
            f"Write Python code to analyze the data. "
            f"Print your final numerical answer as a Python dict."
        )
        start = time.time()
        messages = interpreter.chat(prompt, display=False)
        wall_time = time.time() - start

        # Extract final answer from last message
        final_answer = ""
        for msg in reversed(messages):
            if msg.get("role") == "assistant" and msg.get("type") == "message":
                final_answer = msg.get("content", "")
                break

        interpreter.messages = []  # Reset for next task

        trace = AgentTrace(
            steps=[],
            final_answer=final_answer,
            wall_time=wall_time,
            agent_type="open_interpreter",
            model=self.model,
        )
        return trace
```

**Step 12：注册 adapter 到 agent factory**

在 `data_agent_bench/engine/agents.py` 中添加：
```python
def build_agent(spec: str, **kwargs):
    if spec.startswith("metagpt:"):
        from .adapters.metagpt_adapter import DataInterpreterAdapter
        model = spec.split(":")[1] if ":" in spec else "gpt-4o"
        return DataInterpreterAdapter(model=model, **kwargs)
    elif spec.startswith("open-interpreter:"):
        from .adapters.open_interpreter_adapter import OpenInterpreterAdapter
        model = spec.split(":")[1] if ":" in spec else "gpt-4o"
        return OpenInterpreterAdapter(model=model, **kwargs)
    # ... existing native agent logic
```

**Step 13：冒烟测试两个 adapter**
```bash
# 用 1 个 task 测试 DataInterpreter
python -m data_agent_bench run \
    --tasks DS_TASK_051 \
    --agent metagpt:gpt-4o \
    --output-dir ./test_di \
    --db test.db

# 用 1 个 task 测试 Open Interpreter
python -m data_agent_bench run \
    --tasks DS_TASK_051 \
    --agent open-interpreter:gpt-4o \
    --output-dir ./test_oi \
    --db test.db
```
- [ ] DataInterpreter adapter 冒烟测试通过 ✅
- [ ] Open Interpreter adapter 冒烟测试通过 ✅

### 今日交付物
- [x] Pilot L1/L2/L3 × 20 tasks = 60 runs 完成
- [x] 两个 adapter 代码完成并通过冒烟测试

---

## Day 2 — 4月17日：Pilot 分析 + Go/No-Go

### 上午：Pilot 统计分析

**Step 14：汇总 Pilot 数据**
```python
# scripts/analyze_pilot.py
import json
import numpy as np
from scipy.stats import wilcoxon
from pathlib import Path

# 加载 clean baseline (从 bench_runs_4omini 提取对应 20 个 tasks)
pilot_tasks = json.load(open("pilot_20_tasks.json"))

cas_clean = []
cas_L1 = []
cas_L2 = []
cas_L3 = []

for task_id in pilot_tasks:
    # 读取 clean report
    clean_report = json.load(open(f"bench_runs_4omini/{task_id}/report.json"))
    m = clean_report["metrics"]
    cas_c = 0.40 * m["result_accuracy"] + 0.35 * m["process_quality"] + 0.25 * m["safety_score"]
    cas_clean.append(cas_c)

    # 读取 L1/L2/L3
    for level, cas_list in [("L1", cas_L1), ("L2", cas_L2), ("L3", cas_L3)]:
        report = json.load(open(f"pilot/{level}/{task_id}/report.json"))
        m = report["metrics"]
        cas = 0.40 * m["result_accuracy"] + 0.35 * m["process_quality"] + 0.25 * m["safety_score"]
        cas_list.append(cas)

# 计算 delta
for level, cas_perturbed in [("L1", cas_L1), ("L2", cas_L2), ("L3", cas_L3)]:
    delta = np.array(cas_clean) - np.array(cas_perturbed)
    mean_delta = np.mean(delta)
    std_delta = np.std(delta)
    cohens_d = mean_delta / std_delta if std_delta > 0 else 0
    stat, p = wilcoxon(delta, alternative='greater')
    print(f"{level}: ΔCAS = {mean_delta:.4f} ± {std_delta:.4f}, "
          f"Cohen's d = {cohens_d:.3f}, Wilcoxon p = {p:.4f}")

print(f"\nClean CAS mean: {np.mean(cas_clean):.4f}")
print(f"Trend check: L1 < L2 < L3 ? "
      f"{np.mean(cas_L1):.4f} > {np.mean(cas_L2):.4f} > {np.mean(cas_L3):.4f}")
```
```bash
python scripts/analyze_pilot.py
```

**Step 15：Go/No-Go 决策**

| 条件 | Go | No-Go 应对 |
|------|-----|-----------|
| ΔCAS(L3) > 0.05 | ✅ 继续 | 加强 L3 扰动策略，增加更多统计陷阱 |
| ΔCAS(L3) p < 0.10 | ✅ 继续 | 扩大 pilot 到 40 tasks 重新检验 |
| L3 > L2 > L1 趋势 | ✅ 继续 | 合并 L1+L2 为一级，只保留 clean vs merged vs L3 |

- [ ] **Go/No-Go 决策完成** → Go ✅

### 下午：如果 Go，开始准备全量实验

**Step 16：准备全量实验脚本**
```bash
# scripts/run_all_experiments.sh

#!/bin/bash
set -e

TASKS_FILE="core_80_tasks.json"
DB="bench_neurips.db"

echo "=== Phase 1: NativeAgent / GPT-4o ==="
python -m data_agent_bench run \
    --tasks-file $TASKS_FILE \
    --agent native:openai/gpt-4o \
    --output-dir ./runs/native_gpt4o/clean \
    --db $DB --temperature 0.0

for level in 1 2 3; do
    python -m data_agent_bench experiment \
        --agent native:openai/gpt-4o \
        --levels $level \
        --tasks-file $TASKS_FILE \
        --output-dir ./runs/native_gpt4o/L${level} \
        --db $DB --temperature 0.0
done

echo "=== Phase 2: NativeAgent / Claude ==="
python -m data_agent_bench run \
    --tasks-file $TASKS_FILE \
    --agent native:anthropic/claude-sonnet-4-6 \
    --output-dir ./runs/native_claude/clean \
    --db $DB --temperature 0.0

for level in 1 2 3; do
    python -m data_agent_bench experiment \
        --agent native:anthropic/claude-sonnet-4-6 \
        --levels $level \
        --tasks-file $TASKS_FILE \
        --output-dir ./runs/native_claude/L${level} \
        --db $DB --temperature 0.0
done

echo "=== Phase 3: NativeAgent / GPT-4o-mini (只跑 L1/L2/L3，clean 已有) ==="
for level in 1 2 3; do
    python -m data_agent_bench experiment \
        --agent native:openai/gpt-4o-mini \
        --levels $level \
        --tasks-file $TASKS_FILE \
        --output-dir ./runs/native_4omini/L${level} \
        --db $DB --temperature 0.0
done

echo "=== Phase 4: DataInterpreter / GPT-4o ==="
python -m data_agent_bench run \
    --tasks-file $TASKS_FILE \
    --agent metagpt:gpt-4o \
    --output-dir ./runs/data_interpreter/clean \
    --db $DB --temperature 0.0

for level in 1 2 3; do
    python -m data_agent_bench experiment \
        --agent metagpt:gpt-4o \
        --levels $level \
        --tasks-file $TASKS_FILE \
        --output-dir ./runs/data_interpreter/L${level} \
        --db $DB --temperature 0.0
done

echo "=== Phase 5: Open Interpreter / GPT-4o ==="
python -m data_agent_bench run \
    --tasks-file $TASKS_FILE \
    --agent open-interpreter:gpt-4o \
    --output-dir ./runs/open_interpreter/clean \
    --db $DB --temperature 0.0

for level in 1 2 3; do
    python -m data_agent_bench experiment \
        --agent open-interpreter:gpt-4o \
        --levels $level \
        --tasks-file $TASKS_FILE \
        --output-dir ./runs/open_interpreter/L${level} \
        --db $DB --temperature 0.0
done

echo "✅ ALL DONE"
```

### 今日交付物
- [x] Pilot 统计结果 + Go/No-Go 决策
- [x] 全量实验脚本准备完成

---

## Day 3 — 4月18日：全量实验 Round 1

### 全天：GPT-4o + Claude 并行跑

**Step 17：启动 GPT-4o（终端 1）**
```bash
# 终端 1
source .venv/bin/activate
python -m data_agent_bench run \
    --tasks-file core_80_tasks.json \
    --agent native:openai/gpt-4o \
    --output-dir ./runs/native_gpt4o/clean \
    --db bench_neurips.db --temperature 0.0

# 预计 2-3 小时完成
```

**Step 18：启动 Claude（终端 2）**
```bash
# 终端 2
source .venv/bin/activate
python -m data_agent_bench run \
    --tasks-file core_80_tasks.json \
    --agent native:anthropic/claude-sonnet-4-6 \
    --output-dir ./runs/native_claude/clean \
    --db bench_neurips.db --temperature 0.0
```

**Step 19：等 clean 跑完后，立刻启动 L1/L2/L3**
```bash
# 终端 1（GPT-4o L1/L2/L3，串行）
for level in 1 2 3; do
    python -m data_agent_bench experiment \
        --agent native:openai/gpt-4o --levels $level \
        --tasks-file core_80_tasks.json \
        --output-dir ./runs/native_gpt4o/L${level} \
        --db bench_neurips.db --temperature 0.0
done

# 终端 2（Claude L1/L2/L3，串行）
for level in 1 2 3; do
    python -m data_agent_bench experiment \
        --agent native:anthropic/claude-sonnet-4-6 --levels $level \
        --tasks-file core_80_tasks.json \
        --output-dir ./runs/native_claude/L${level} \
        --db bench_neurips.db --temperature 0.0
done
```

**Step 20：定期检查进度**
```bash
# 每小时检查一下
for d in runs/native_gpt4o/*/  runs/native_claude/*/; do
    count=$(find "$d" -name "report.json" 2>/dev/null | wc -l)
    echo "$d: $count / 80 done"
done
```

### 检查点（晚上）
- [ ] GPT-4o clean 80 runs ✅
- [ ] GPT-4o L1 80 runs ✅ （可能还在跑）
- [ ] Claude clean 80 runs ✅
- [ ] Claude L1 80 runs ✅ （可能还在跑）

---

## Day 4 — 4月19日：全量实验 Round 2 + HPC

### 上午：GPT-4o-mini L1/L2/L3 + 开源框架

**Step 21：GPT-4o-mini L1/L2/L3（终端 3）**
```bash
for level in 1 2 3; do
    python -m data_agent_bench experiment \
        --agent native:openai/gpt-4o-mini --levels $level \
        --tasks-file core_80_tasks.json \
        --output-dir ./runs/native_4omini/L${level} \
        --db bench_neurips.db --temperature 0.0
done
```

**Step 22：DataInterpreter 启动（终端 4）**
```bash
python -m data_agent_bench run \
    --tasks-file core_80_tasks.json \
    --agent metagpt:gpt-4o \
    --output-dir ./runs/data_interpreter/clean \
    --db bench_neurips.db --temperature 0.0
```

### 下午：HPC 部署 Qwen

**Step 23：SSH 到 HPC 节点，部署 vLLM**
```bash
# 在 HPC A800 节点上
ssh gpu-node-xxx

# 安装 vLLM
pip install vllm

# 下载模型（从 ModelScope）
python -c "
from modelscope import snapshot_download
snapshot_download('zechlei/taskgen-lora-119', cache_dir='./models')
# 或者用 merged 的 Qwen2.5-Coder-7B
snapshot_download('Qwen/Qwen2.5-Coder-7B-Instruct', cache_dir='./models')
"

# 启动 vLLM 服务
python -m vllm.entrypoints.openai.api_server \
    --model ./models/Qwen2.5-Coder-7B-Instruct \
    --host 0.0.0.0 --port 8000 \
    --tensor-parallel-size 1 \
    --max-model-len 8192 \
    --gpu-memory-utilization 0.85

# 验证
curl http://localhost:8000/v1/models
```

**Step 24：在 HPC 上跑 Qwen Agent**
```bash
# 新开一个 tmux session
OPENAI_BASE_URL=http://localhost:8000/v1 \
OPENAI_API_KEY=dummy \
python -m data_agent_bench run \
    --tasks-file core_80_tasks.json \
    --agent native:vllm/Qwen2.5-Coder-7B \
    --output-dir ./runs/native_qwen7b/clean \
    --db bench_neurips.db --temperature 0.0

# 跑完 clean 后跑 L1/L2/L3
for level in 1 2 3; do
    OPENAI_BASE_URL=http://localhost:8000/v1 \
    OPENAI_API_KEY=dummy \
    python -m data_agent_bench experiment \
        --agent native:vllm/Qwen2.5-Coder-7B --levels $level \
        --tasks-file core_80_tasks.json \
        --output-dir ./runs/native_qwen7b/L${level} \
        --db bench_neurips.db --temperature 0.0
done
```

### 检查点（晚上）
- [ ] GPT-4o L1/L2/L3 全部完成 ✅
- [ ] Claude L1/L2/L3 全部完成 ✅
- [ ] GPT-4o-mini L1/L2/L3 开始跑 ✅
- [ ] DataInterpreter clean 开始跑 ✅
- [ ] HPC vLLM 部署成功 ✅

---

## Day 5 — 4月20日：实验收尾 + 质量抽检

### 上午：继续跑剩余实验

**Step 25：Open Interpreter 启动（终端 5）**
```bash
python -m data_agent_bench run \
    --tasks-file core_80_tasks.json \
    --agent open-interpreter:gpt-4o \
    --output-dir ./runs/open_interpreter/clean \
    --db bench_neurips.db --temperature 0.0
```

**Step 26：DataInterpreter L1/L2/L3**
```bash
for level in 1 2 3; do
    python -m data_agent_bench experiment \
        --agent metagpt:gpt-4o --levels $level \
        --tasks-file core_80_tasks.json \
        --output-dir ./runs/data_interpreter/L${level} \
        --db bench_neurips.db --temperature 0.0
done
```

### 下午：质量抽检

**Step 27：抽检 10 个 GPT-4o reports**
```python
# scripts/quality_check.py
import json, random
from pathlib import Path

random.seed(42)
reports_dir = Path("runs/native_gpt4o/clean")
all_reports = list(reports_dir.glob("*/report.json"))
sample = random.sample(all_reports, 10)

for rpath in sample:
    r = json.load(open(rpath))
    task_id = r["instance_id"]
    acc = r["metrics"]["result_accuracy"]
    proc = r["metrics"]["process_quality"]
    safety = r["metrics"]["safety_score"]
    cas = 0.4 * acc + 0.35 * proc + 0.25 * safety
    steps = len(r.get("trajectory_summary", []))
    
    # 加载 GT 看是否合理
    gt = json.load(open(f"tasks/{task_id}/ground_truth/expected_output.json"))
    gt_keys = list(gt.get("key_values", {}).keys())
    
    print(f"{task_id}: CAS={cas:.3f} (acc={acc:.3f}, proc={proc:.3f}, safe={safety:.3f})")
    print(f"  Steps: {steps}, GT keys: {gt_keys}")
    print(f"  Final answer: {r.get('execution_result', '')[:100]}...")
    print()
```
```bash
python scripts/quality_check.py
```

逐个检查：
- [ ] accuracy 为 0 的 case，是 GT 问题还是 agent 问题？
- [ ] accuracy 为 1 的 case，确认不是 trivial/泄漏
- [ ] process_quality 分布是否合理？

**Step 28：修复发现的 GT 问题（如有）**
- 如果发现某些 task 的 GT 有误，修复后重跑该 task
- 记录问题 task ID，在论文 Appendix 中说明质控流程

### 检查点（晚上）
- [ ] 所有 API Agent 实验完成或即将完成 ✅
- [ ] 质量抽检通过，无系统性问题 ✅

---

## Day 6-7 — 4月21-22日：实验扫尾

### Day 6：Open Interpreter L1/L2/L3 + 查漏补缺

**Step 29：Open Interpreter L1/L2/L3**
```bash
for level in 1 2 3; do
    python -m data_agent_bench experiment \
        --agent open-interpreter:gpt-4o --levels $level \
        --tasks-file core_80_tasks.json \
        --output-dir ./runs/open_interpreter/L${level} \
        --db bench_neurips.db --temperature 0.0
done
```

**Step 30：汇总实验完成度**
```bash
# scripts/check_completion.sh
echo "=== Experiment Completion Status ==="
for agent_dir in runs/*/; do
    agent=$(basename $agent_dir)
    for cond_dir in ${agent_dir}*/; do
        cond=$(basename $cond_dir)
        count=$(find "$cond_dir" -name "report.json" 2>/dev/null | wc -l)
        status="✅"
        [ "$count" -lt 80 ] && status="⚠️ INCOMPLETE"
        echo "$agent/$cond: $count/80 $status"
    done
done
```

**Step 31：重跑失败的 tasks**
```bash
# 找出失败的 tasks（没有 report.json 的）
python -c "
import json
core = json.load(open('core_80_tasks.json'))
from pathlib import Path
for agent_dir in Path('runs').iterdir():
    for cond_dir in agent_dir.iterdir():
        missing = [t for t in core if not (cond_dir / t / 'report.json').exists()]
        if missing:
            print(f'{agent_dir.name}/{cond_dir.name}: {len(missing)} missing: {missing[:5]}...')
"
```

### Day 7：HPC Qwen 结果回收 + 最终汇总

**Step 32：从 HPC 拷贝 Qwen 结果**
```bash
scp -r gpu-node-xxx:~/bench/runs/native_qwen7b/ ./runs/native_qwen7b/
```

**Step 33：生成完整实验矩阵验证**
```bash
python scripts/check_completion.sh
# 确认所有 6 agents × 4 conditions × 80 tasks = 1920 reports 都存在
```

### Day 7 交付物
- [x] **全部 1920 runs 完成** ✅
- [x] 数据质量抽检通过 ✅
- [x] HPC GPU 释放 ✅

## Day 8 — 4月23日：核心统计分析

### 上午：计算所有 ΔCAS 和统计检验

**Step 34：汇总所有结果到一张大表**
```python
# scripts/aggregate_results.py
import json
import pandas as pd
from pathlib import Path

core_tasks = json.load(open("core_80_tasks.json"))
agents = [
    ("native_gpt4o", "NativeAgent/GPT-4o"),
    ("native_claude", "NativeAgent/Claude"),
    ("native_4omini", "NativeAgent/GPT-4o-mini"),
    ("native_qwen7b", "NativeAgent/Qwen-7B"),
    ("data_interpreter", "DataInterpreter/GPT-4o"),
    ("open_interpreter", "OpenInterpreter/GPT-4o"),
]
conditions = ["clean", "L1", "L2", "L3"]

rows = []
for agent_dir, agent_name in agents:
    for task_id in core_tasks:
        for cond in conditions:
            rpath = Path(f"runs/{agent_dir}/{cond}/{task_id}/report.json")
            if not rpath.exists():
                continue
            r = json.load(open(rpath))
            m = r["metrics"]
            cas = 0.4 * m["result_accuracy"] + 0.35 * m["process_quality"] + 0.25 * m["safety_score"]
            rows.append({
                "agent": agent_name,
                "task_id": task_id,
                "condition": cond,
                "CAS": cas,
                "accuracy": m["result_accuracy"],
                "process": m["process_quality"],
                "safety": m["safety_score"],
                "tokens": m.get("total_tokens", 0),
                "cost": m.get("total_cost_usd", 0),
                "wall_time": m.get("wall_time_seconds", 0),
            })

df = pd.DataFrame(rows)
df.to_csv("results/all_results.csv", index=False)
print(f"Total records: {len(df)}")
print(df.groupby(["agent", "condition"])["CAS"].agg(["mean", "std", "count"]))
```
```bash
mkdir -p results
python scripts/aggregate_results.py
```

**Step 35：Wilcoxon test + Cohen's d**
```python
# scripts/statistical_tests.py
import pandas as pd
import numpy as np
from scipy.stats import wilcoxon

df = pd.read_csv("results/all_results.csv")

print("=" * 80)
print("Table 3: ΔCAS Degradation Matrix")
print("=" * 80)

results = []
for agent in df["agent"].unique():
    clean = df[(df["agent"] == agent) & (df["condition"] == "clean")].set_index("task_id")["CAS"]
    for level in ["L1", "L2", "L3"]:
        perturbed = df[(df["agent"] == agent) & (df["condition"] == level)].set_index("task_id")["CAS"]
        # 对齐 tasks
        common = clean.index.intersection(perturbed.index)
        delta = clean[common] - perturbed[common]
        
        mean_d = delta.mean()
        std_d = delta.std()
        cohens_d = mean_d / std_d if std_d > 0 else 0
        
        try:
            stat, p = wilcoxon(delta, alternative="greater")
        except:
            p = 1.0
        
        sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "†" if p < 0.10 else ""
        
        results.append({
            "Agent": agent,
            "Level": level,
            "ΔCAS": f"{mean_d:.3f}",
            "Cohen's d": f"{cohens_d:.2f}",
            "p-value": f"{p:.4f}",
            "Sig": sig,
        })
        print(f"{agent:30s} {level}: ΔCAS={mean_d:.4f}, d={cohens_d:.3f}, p={p:.4f} {sig}")

result_df = pd.DataFrame(results)
result_df.to_csv("results/degradation_matrix.csv", index=False)
print("\nSaved to results/degradation_matrix.csv")
```
```bash
python scripts/statistical_tests.py
```
- [ ] degradation_matrix.csv 生成 ✅
- [ ] 确认 L3 > L2 > L1 趋势成立 ✅
- [ ] 确认至少有 * (p < 0.05) 显著性 ✅

### 下午：生成 Table 2（Overall Leaderboard）

**Step 36：生成 Table 2**
```python
# scripts/make_table2.py
import pandas as pd

df = pd.read_csv("results/all_results.csv")
clean = df[df["condition"] == "clean"]

table2 = clean.groupby("agent").agg(
    CAS=("CAS", "mean"),
    Accuracy=("accuracy", "mean"),
    Process=("process", "mean"),
    Safety=("safety", "mean"),
    Tokens=("tokens", "mean"),
    Cost=("cost", "sum"),
    Time=("wall_time", "mean"),
).round(3).sort_values("CAS", ascending=False)

print("Table 2: Overall Performance (Clean Condition)")
print(table2.to_markdown())
table2.to_csv("results/table2_leaderboard.csv")
```

**Step 37：生成 Table 4（架构对比）**
```python
# scripts/make_table4.py
import pandas as pd

df = pd.read_csv("results/all_results.csv")

# 只看 GPT-4o 驱动的 3 种架构
arch_agents = ["NativeAgent/GPT-4o", "DataInterpreter/GPT-4o", "OpenInterpreter/GPT-4o"]
arch_df = df[df["agent"].isin(arch_agents)]

table4 = arch_df.groupby(["agent", "condition"]).agg(
    CAS=("CAS", "mean"),
    Accuracy=("accuracy", "mean"),
    Process=("process", "mean"),
).round(3).unstack("condition")

print("Table 4: Architecture Comparison (same LLM, different scaffolding)")
print(table4.to_markdown())
table4.to_csv("results/table4_architecture.csv")
```

### 今日交付物
- [x] all_results.csv（完整数据表）
- [x] degradation_matrix.csv（核心贡献数据）
- [x] table2_leaderboard.csv
- [x] table4_architecture.csv

---

## Day 9 — 4月24日：可视化

### 上午：核心 Figure

**Step 38：Figure 3 — ΔCAS 退化曲线**
```python
# scripts/plot_degradation.py
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

df = pd.read_csv("results/all_results.csv")

fig, ax = plt.subplots(figsize=(8, 5))
levels = ["clean", "L1", "L2", "L3"]
colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]

for i, agent in enumerate(df["agent"].unique()):
    means = []
    for cond in levels:
        m = df[(df["agent"] == agent) & (df["condition"] == cond)]["CAS"].mean()
        means.append(m)
    ax.plot(levels, means, marker="o", label=agent, color=colors[i % len(colors)], linewidth=2)

ax.set_xlabel("Perturbation Level", fontsize=12)
ax.set_ylabel("CAS Score", fontsize=12)
ax.set_title("Semantic Robustness: CAS Degradation Under Perturbation", fontsize=13)
ax.legend(fontsize=9, loc="lower left")
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("results/fig3_degradation.pdf", dpi=300)
plt.savefig("results/fig3_degradation.png", dpi=300)
print("Saved fig3_degradation.pdf")
```

**Step 39：Figure 4 — Radar Chart**
```python
# scripts/plot_radar.py
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

df = pd.read_csv("results/all_results.csv")
clean = df[df["condition"] == "clean"]

categories = ["Accuracy", "Process", "Safety", "Efficiency", "Robustness"]
N = len(categories)
angles = [n / float(N) * 2 * np.pi for n in range(N)] + [0]

fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))

for agent in clean["agent"].unique():
    agent_data = clean[clean["agent"] == agent]
    
    acc = agent_data["accuracy"].mean()
    proc = agent_data["process"].mean()
    safe = agent_data["safety"].mean()
    efficiency = 1 - (agent_data["tokens"].mean() / agent_data["tokens"].max())  # normalized
    
    # Robustness = 1 - mean ΔCAS(L3)
    l3 = df[(df["agent"] == agent) & (df["condition"] == "L3")]
    if len(l3) > 0:
        delta = clean[clean["agent"] == agent].set_index("task_id")["CAS"].mean() - l3.set_index("task_id")["CAS"].mean()
        robustness = max(0, 1 - delta * 2)  # scale
    else:
        robustness = 0.5
    
    values = [acc, proc, safe, efficiency, robustness] + [acc]
    ax.plot(angles, values, linewidth=2, label=agent)
    ax.fill(angles, values, alpha=0.1)

ax.set_xticks(angles[:-1])
ax.set_xticklabels(categories)
ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=8)
plt.tight_layout()
plt.savefig("results/fig4_radar.pdf", dpi=300)
print("Saved fig4_radar.pdf")
```

### 下午：分层分析 + Case Study

**Step 40：按 Domain 和 Difficulty 分层**
```python
# scripts/fine_grained_analysis.py
import pandas as pd
import json

df = pd.read_csv("results/all_results.csv")

# 加载 task metadata
task_meta = {}
for task_id in json.load(open("core_80_tasks.json")):
    meta = json.load(open(f"tasks/{task_id}/task.json"))["task_metadata"]
    task_meta[task_id] = {"domain": meta["domain"], "difficulty": meta["difficulty"]}

df["domain"] = df["task_id"].map(lambda x: task_meta.get(x, {}).get("domain", "?"))
df["difficulty"] = df["task_id"].map(lambda x: task_meta.get(x, {}).get("difficulty", "?"))

print("=== CAS by Domain (Clean) ===")
print(df[df["condition"]=="clean"].groupby(["agent", "domain"])["CAS"].mean().unstack().round(3).to_markdown())

print("\n=== CAS by Difficulty (Clean) ===")
print(df[df["condition"]=="clean"].groupby(["agent", "difficulty"])["CAS"].mean().unstack().round(3).to_markdown())

print("\n=== ΔCAS(L3) by Domain ===")
for domain in df["domain"].unique():
    print(f"\n--- {domain} ---")
    for agent in df["agent"].unique():
        c = df[(df["agent"]==agent) & (df["condition"]=="clean") & (df["domain"]==domain)]["CAS"].mean()
        l3 = df[(df["agent"]==agent) & (df["condition"]=="L3") & (df["domain"]==domain)]["CAS"].mean()
        print(f"  {agent:30s}: ΔCAS = {c-l3:.4f}")
```

**Step 41：选 2-3 个 Case Study**
```
选择标准：
1. 一个 GPT-4o clean 做对但 L3 做错的 case（说明语义依赖）
2. 一个 DataInterpreter L3 做对但 Open Interpreter L3 做错的 case（说明架构影响）
3. 一个所有 agent L3 都做错的 Hard task（说明 benchmark 有区分度）

对每个 case：
- 截取 clean trace 和 L3 trace 的关键步骤对比
- 放入论文 §4.5 或 Appendix
```

### 今日交付物
- [x] fig3_degradation.pdf（退化曲线）
- [x] fig4_radar.pdf（雷达图）
- [x] 分层分析结果
- [x] 2-3 个 Case Study 初稿

---

## Day 10-11 — 4月25-26日：写 §4 Experiments

### Step 42：§4 写作大纲

```latex
\section{Experiments}

\subsection{Experimental Setup}
% 被测 agents（Table 1）
% 条件矩阵（clean/L1/L2/L3）
% 80 tasks, 4 domains, 3 difficulties
% Evaluation protocol: CAS 三维评分
% Hardware: M4 Pro for API agents, 1×A800 for Qwen-7B

\subsection{Overall Performance (RQ1)}
% Table 2: Leaderboard
% Finding 1: GPT-4o achieves highest CAS of X in clean condition
% Finding 2: DataInterpreter outperforms on process quality

\subsection{Semantic Robustness (RQ2)}
% Table 3: ΔCAS Degradation Matrix （核心贡献表格！）
% Finding 3: All agents degrade under perturbation, L3 > L2 > L1
% Finding 4: Stronger models (GPT-4o) degrade less than weaker (GPT-4o-mini)
% Figure 3: Degradation curves

\subsection{Architecture Impact (RQ3)}
% Table 4: Architecture comparison
% Finding 5: Plan-and-Execute (DataInterpreter) most robust
% Finding 6: Direct Exec (Open Interpreter) least robust

\subsection{Fine-grained Analysis}
% By domain: which domain is hardest under perturbation?
% By difficulty: does Hard amplify degradation?

\subsection{Case Studies}
% Case 1: clean vs L3 trace comparison
% Case 2: architecture difference under L3
```

按大纲逐节写，每节 0.5-1 页。先填数据再补文字。

---

## Day 12 — 4月27日：写 §2 Benchmark Construction

### Step 43：§2 写作大纲

```latex
\section{DataAgentBench}

\subsection{Design Goals}
% G1: Realistic — real-world data science tasks with CSV + numerical answers
% G2: Fine-grained — 3-dimensional CAS scoring
% G3: Scalable — automated task generation pipeline
% G4: Anti-memorization — L1/L2/L3 systematic perturbation

\subsection{Task Construction Pipeline}
% Figure 2: Pipeline diagram (Seed → TaskGen → Reviewer → Critic → RedTeam)
% Seed datasets: sklearn slices (Finance, Biomedical, ECommerce, Scientific)
% LLM-based generation with GPT-4o
% Ground truth: solution_code execution → numerical key_values
% Alternative GT for method-sensitive tasks

\subsection{Semantic Perturbation Framework}
% Definition of L1/L2/L3 (formal)
% L1: Column renaming → var_001, var_002
% L2: + Statistical traps (outlier injection, spurious correlation, type confusion)
% L3: + Problem statement de-semanticization
% Table: examples of each level
% RedTeamAgent implementation

\subsection{Benchmark Statistics}
% Figure: task distribution (domain × difficulty)
% Table: dataset size statistics
% Comparison with existing benchmarks (KramaBench, DS-1000, MLE-bench)
```

### Step 44：画 Figure 2（Pipeline 图）

用 draw.io 或 TikZ 画：
```
Seed Datasets → [TaskGen LLM] → Draft Task
                                    ↓
                              [Reviewer LLM] → Validated Task
                                    ↓
                              [Critic LLM] → Refined Task
                                    ↓
                              [RedTeam Agent] → L1/L2/L3 Variants
                                    ↓
                              121 Tasks × 4 Conditions
```

---

## Day 13 — 4月28日：写 §3 + §5

### Step 45：§3 Evaluation Framework（1 页）

```latex
\section{Evaluation Framework}

\subsection{Composite Agent Score (CAS)}
% CAS = 0.4 × accuracy + 0.35 × process + 0.25 × safety
% Justify weights (ablation in appendix)

\subsection{Accuracy Scoring}
% DeterministicEvaluator: 5% relative tolerance
% Alternative GT matching: max over all valid methods

\subsection{Process Quality}
% ProcessAuditor: recovery patterns, tool diversity, planning
% Recovery classification: blind_retry / diagnostic / strategy_shift / give_up

\subsection{Safety Assessment}
% RiskAssessor: dangerous commands, budget compliance
```

### Step 46：§5 Related Work（1 页）

```latex
\section{Related Work}

\subsection{Data Science Benchmarks}
% DS-1000 (Lai et al., 2023): code generation, no agent, no robustness
% KramaBench (2025): data lake agent, no anti-memorization
% MLE-bench (Chan et al., 2024): Kaggle competitions, no perturbation
% DABstep (Together AI, 2025): structured/unstructured, no robustness testing
% StatQA (2024): statistical QA, not agent-based

\subsection{LLM Agent Evaluation}
% SWE-bench, WebArena, OSWorld — not data science specific
% MLAgentBench — ML experiments, not statistical analysis

\subsection{Robustness and Memorization}
% Data contamination detection (Golchin & Surdeanu, 2024)
% Benchmark contamination (Oren et al., 2024)
% Our contribution: first systematic perturbation framework for data agents
```

---

## Day 14 — 4月29日：写 §6 Discussion + §7 Conclusion

### Step 47：Discussion（0.5 页）
```
- Limitations: CAS weights are empirical; 80 tasks may not cover all scenarios
- The perturbation framework tests surface-level robustness, not deep reasoning
- Open question: can targeted fine-tuning improve robustness?
```

### Step 48：Conclusion（0.5 页）
```
- We presented DataAgentBench, a benchmark for evaluating semantic robustness
- Key findings: (1) all agents degrade under perturbation (2) architecture matters
  (3) stronger models are more robust but not immune
- 121 tasks, 6 agents, 4 conditions → first systematic study of agent robustness
```

---

## Day 15 — 4月30日：写 §1 Introduction + Abstract

### Step 49：Introduction（2 页）

```
Para 1: Data agents are increasingly deployed for CSV analysis...
Para 2: Existing benchmarks (DS-1000, KramaBench) only test clean conditions...
Para 3: We ask: how much do agents rely on semantic cues vs. actual reasoning?
Para 4: Figure 1 — Running Example (clean vs L3 comparison)
Para 5: Our contributions:
  (C1) A 121-task benchmark with systematic 3-level perturbation framework
  (C2) Multi-dimensional CAS scoring (accuracy + process + safety)
  (C3) First cross-architecture robustness study (3 agent types)
  (C4) Empirical findings: architecture impacts robustness; all agents vulnerable to L3
```

### Step 50：Abstract（250 words）

写完全文后最后写 Abstract，概括：
- 问题：data agents 在语义扰动下的鲁棒性未知
- 方法：DataAgentBench + L1/L2/L3 框架
- 结果：GPT-4o CAS 从 X 降到 Y (p < 0.001)；Plan-and-Execute 最 robust
- 意义：first benchmark for semantic robustness of data agents

---

## Day 16 — 5月1日：Appendix + 补充实验

### Step 51：CAS 权重 Ablation
```python
# scripts/ablation_cas_weights.py
import pandas as pd
import itertools

df = pd.read_csv("results/all_results.csv")
clean = df[df["condition"] == "clean"]

# 尝试不同权重组合
weight_sets = [
    (0.4, 0.35, 0.25),  # default
    (0.5, 0.3, 0.2),
    (0.6, 0.2, 0.2),
    (0.33, 0.33, 0.34),
    (0.5, 0.5, 0.0),    # no safety
]

print("CAS Weight Sensitivity Analysis")
for wa, wp, ws in weight_sets:
    clean_copy = clean.copy()
    clean_copy["CAS_alt"] = wa * clean_copy["accuracy"] + wp * clean_copy["process"] + ws * clean_copy["safety"]
    ranking = clean_copy.groupby("agent")["CAS_alt"].mean().sort_values(ascending=False)
    print(f"\nWeights ({wa}/{wp}/{ws}): {list(ranking.index)}")
```
- [ ] 验证排名在不同权重下基本稳定 ✅

### Step 52：Appendix 整理
```
Appendix A: Complete CAS Formula and Implementation Details
Appendix B: Full Task Statistics (121 tasks)
Appendix C: All Agent Traces for Case Studies
Appendix D: CAS Weight Sensitivity Analysis
Appendix E: Per-task Results Table
```

---

## Day 17 — 5月2日：GT 验证 + 代码整理

### Step 53：人工抽检 30 个 GT
```
从 80 个核心 tasks 中抽 30 个
对每个 task：
1. 读 problem_statement
2. 人工用 pandas 验证 key_values 是否正确
3. 标记：✅ 正确 / ⚠️ 近似正确 / ❌ 错误

目标：≥ 90% 标记为 ✅ 或 ⚠️
```

### Step 54：GitHub 仓库整理
```
DataAgentBench/
├── README.md
├── LICENSE (MIT)
├── tasks/              # 121 task definitions
├── data_agent_bench/   # framework code
├── scripts/            # experiment scripts
├── results/            # tables and figures
├── paper/              # LaTeX source
└── croissant.json      # dataset metadata
```

### Step 55：生成 Croissant 元数据
```python
# scripts/generate_croissant.py
# 参考 https://github.com/mlcommons/croissant
croissant = {
    "@context": {"@vocab": "https://schema.org/", "cr": "https://mlcommons.org/croissant/"},
    "@type": "cr:Dataset",
    "name": "DataAgentBench",
    "description": "A benchmark for evaluating semantic robustness of data science agents",
    "license": "MIT",
    "distribution": [...],
    "recordSet": [...],
}
```

---

## Day 18 — 5月3日：全文通读润色

### Step 56：第一轮通读 Checklist
- [ ] 所有 Table/Figure 编号正确且被引用
- [ ] 所有数据与 CSV 源文件一致
- [ ] 所有 p-value 和 Cohen's d 值无误
- [ ] Related Work 没有遗漏关键论文
- [ ] Abstract 中的数字与正文一致
- [ ] 参考文献格式统一（NeurIPS style）
- [ ] 正文 ≤ 9 页（不含参考文献和 Appendix）

### Step 57：Grammarly / 语法检查
```bash
# 或用 Grammarly / ChatGPT 润色英文
# 重点检查：
# - 时态一致性（实验描述用过去时，结论用现在时）
# - 被动语态不要过度使用
# - 技术术语拼写统一
```

---

## Day 19 — 5月4日：⚠️ Abstract 截止日

### Step 58：提交 Abstract 到 OpenReview
```
1. 登录 https://openreview.net/group?id=NeurIPS.cc/2026/Evaluations_and_Datasets_Track
2. 选择 "Evaluations & Datasets Track"
3. 填写：
   - Title
   - Abstract (250 words)
   - Keywords: benchmark, data science agent, robustness, evaluation
   - TL;DR (一句话)
4. 提交
```
- [ ] **Abstract 已提交** ✅⚠️ 硬 deadline！

---

## Day 20 — 5月5日：终审

### Step 59：终审 Checklist
- [ ] PDF 编译无报错
- [ ] 所有 Figure 清晰（300dpi+）
- [ ] 代码仓库 URL 填入论文（匿名版用 Anonymous GitHub）
- [ ] Croissant JSON 上传到 OpenReview
- [ ] Supplementary Material 打包（Appendix PDF + 代码 ZIP）
- [ ] 合作者 review 完成（至少 1 人通读）

---

## Day 21 — 5月6日：🚀 提交日

### Step 60：最终提交

```
1. 最后一次 PDF 编译
2. 检查页数（正文 ≤ 9 页）
3. 上传到 OpenReview：
   - Main paper PDF
   - Supplementary PDF (Appendix)
   - Code ZIP 或 GitHub URL
   - Croissant JSON
4. 确认所有 co-author 信息
5. 提交！
```
- [ ] **Full Paper 已提交** 🚀🎉

---

## 附录：紧急情况应对表

| 场景 | 应对 |
|------|------|
| Day 2 Pilot 趋势不成立 | 加强 L3 扰动；或改为测 domain-specific memorization |
| HPC 排队超 5 天 | 放弃 Qwen，论文用 5 agents；Limitation 中说明 |
| 某个开源框架完全跑不通 | 砍到 1 个开源框架；或换 smolagents（你之前用过） |
| API rate limit 严重 | 降低并发数；申请 higher tier；分散到多天跑 |
| Day 15 写作进度落后 | 砍 Related Work 到半页；砍 Case Study；先保证核心 §2+§4 |
| Day 19 Abstract 写不完 | Abstract 可以先提交简版，Full Paper 截止前可修改 |
