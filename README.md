# DataAgentBench

**A benchmark for evaluating data science agents on realistic analytical tasks, with robustness testing under semantic perturbation.**

## 评测对象

DataAgentBench 评测的是 **Data Agent 系统**——一个能读取数据集、迭代编写并执行 Python 代码、最终给出准确分析结论的完整 agent。被测对象是 agent 整体（LLM + 提示策略 + 工具调用能力），作为黑盒系统评分。

**核心问题：**
1. **能力评测**：这个 data agent 能不能在 Easy/Medium/Hard 的数据科学任务上得出正确结论？
2. **鲁棒性评测**：当数据的语义线索（列名、领域描述）被系统性混淆后，agent 的表现会下降多少？

对比对象：GPT-4o、GPT-4o-mini、Claude Sonnet 等，通过项目自研的 **NativeCodeAgent** 统一接入（官方 SDK 直连，不依赖 smolagents/litellm）。

**正式评测边界（v1 修复后）：** Bench 只消费带 verifier replay provenance 的静态任务目录，例如 `tasks_verified_core_v1` 和 `tasks_verified_redteam_v1`。`tasks_legacy_unverified`、`tasks_taskgen_candidates`、旧 pilot20/121 任务以及 `tasks_curated_easy_v1` 只用于 debug/GT 修复参考，不进入正式 leaderboard，也不作为模型能力结论。正式 GT 只能由 `data_agent_taskgen` verifier 从 `dataset.csv + task_manifest.json` 复算得到，LLM 不拥有 GT 设置权。

---

## 1. 框架总览

框架分三个阶段，数据从左向右流动：

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 PHASE 1: TASK GENERATION          任务库
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 ┌───────────────────┐   LLM 写代码    ┌────────────────────────┐
 │  Seed Dataset     │  ────────────▶  │  tasks/DS_TASK_078/    │
 │  (sklearn 切片 +  │  在沙箱执行      │  ├── task.json          │
 │   对抗脏数据注入)  │  计算真值        │  ├── data/dataset.csv   │
 └───────────────────┘                 │  └── ground_truth/      │
  • Finance (california_housing)       │      expected_output.json│
  • Biomedical (breast_cancer)         └────────────────────────┘
  • ECommerce (user_sessions)            43 tasks × 4 domains
  • Scientific (wine, iris)             Easy / Medium / Hard


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 PHASE 2: AGENT EVALUATION          运行 + 评分
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                  ┌──────────────────────────────────────────────┐
  task.json  ──▶  │  BenchmarkExecutor                           │
  dataset.csv     │  (NativeCodeAgent + Official SDKs)           │
                  │                                              │
  LLM via         │  step 1: agent reads data                    │
  Official SDK    ──▶  │  step 2: agent writes & runs Python code ──▶ │  AgentTrace
  (Direct)        │  step 3: agent fixes error if any            │  (steps + outputs)
                  │  ...                                         │
                  │  step N: agent calls final_answer()          │
                  └──────────────────┬───────────────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │  Evaluation (3 维)               │
                    │                                  │
                    │  ① DeterministicEvaluator        │
                    │     数值匹配 (5% 容差)            │
                    │     支持 alternative_key_values  │
                    │     → result_accuracy            │
                    │                                  │
                    │  ② ProcessAuditor                │
                    │     恢复策略分类 + 工具多样性     │
                    │     → process_quality            │
                    │                                  │
                    │  ③ RiskAssessor                  │
                    │     危险命令 / 资源消耗检查       │
                    │     → safety_score               │
                    │                                  │
                    │  ④ TraceGroundingVerifier        │
                    │     typed trace 声明 vs tool log  │
                    │     → grounding_rate             │
                    └────────────────┬────────────────┘
                                     │
                              CAS = 0.40 × accuracy
                                   + 0.35 × process
                                   + 0.25 × safety
                                     │
                                     ▼
                              report.json


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 PHASE 3: ROBUSTNESS TESTING    语义鲁棒性测试
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  同一 task，同一 agent，跑四个版本对比
  ─────────────────────────────────────────────────────────────

  原始版本 (clean)
  ─────────────────────────────────────────────────────────────
  problem: "分析 income 对 loan_approved 的影响"
  data:    income=45000, loan_approved=1, age=32 ...

       ──▶  Data Agent  ──▶  CAS_clean

  ─────────────────────────────────────────────────────────────
                   ▼  RedTeamAgent 三级扰动
  ─────────────────────────────────────────────────────────────

  L1 列名混淆       income → var_001, loan_approved → target_z
  L2 + 统计陷阱     注入离群值簇、伪相关列、类型混淆（"$1,200"）
  L3 + 去语义化     problem 改写为："分析 var_001 与 target_z 的关系"

       ──▶  Data Agent  ──▶  CAS_perturbed

  ─────────────────────────────────────────────────────────────
  Δ CAS = CAS_clean − CAS_perturbed

  Δ CAS 越大，说明该 agent 对语义线索的依赖越强、鲁棒性越弱
  统计检验：Wilcoxon signed-rank test + Cohen's d（跨任务聚合）
```

---

## 2. 输入 / 输出规范

### 2.1 Task 格式（输入单元）

每个任务存放在独立目录 `tasks/DS_TASK_XXX/`：

```
DS_TASK_078/
├── task.json               # 任务规格
├── data/
│   └── dataset.csv         # 真实数据（sklearn 切片 + 对抗注入）
└── ground_truth/
    └── expected_output.json  # 标准答案
```

**task.json 字段：**

```json
{
  "instance_id": "DS_TASK_078",
  "task_metadata": {
    "domain": "Finance",
    "difficulty": "Medium",
    "primary_task_type": "risk_anomaly_decision",
    "secondary_task_types": ["data_quality_robustness"],
    "challenge_dimensions": ["outlier_handling", "class_imbalance_or_cost"],
    "tags": ["fraud-detection"],
    "canary_value": 58.1616
  },
  "context": {
    "problem_statement": "...",
    "dataset_preview": "data/dataset.csv",
    "expert_knowledge": "..."
  },
  "environment_config": {
    "max_steps": 10,
    "budget": 1.5,
    "timeout_seconds": 180,
    "allowed_tools": ["python_repl", "file_read"]
  }
}
```

**expected_output.json 字段（支持多方法平权）：**

```json
{
  "key_values": { "VaR_95": -0.730 },
  "alternative_key_values": [
    { "method": "monte_carlo",       "VaR_95": -1.000 },
    { "method": "parametric_normal", "VaR_95": -1.608 }
  ],
  "required_keywords": [],
  "components": {
    "data_selection": {
      "target_columns": ["portfolio_value", "loss"],
      "score_weight": 0.15
    },
    "method_selection": {
      "method_keywords": ["VaR", "quantile"],
      "score_weight": 0.10
    },
    "numerical_result": {
      "key_values": { "VaR_95": -0.730 },
      "score_weight": 0.55
    },
    "interpretation": {
      "required_keywords": ["risk", "95"],
      "score_weight": 0.05
    }
  },
  "process_ground_truth": {
    "reference_traces": [
      {
        "name": "pandas_reference",
        "steps": [
          {"intent": "load_data", "operation": "read_csv"},
          {"intent": "inspect_schema"},
          {"intent": "aggregate", "operation": "groupby_sum"},
          {"intent": "report_answer"}
        ],
        "order_constraints": [["load_data", "aggregate"], ["aggregate", "report_answer"]]
      }
    ]
  }
}
```

评分时取 agent 答案与所有方法版本的**最大匹配分**。`primary_task_type`、`secondary_task_types`、`challenge_dimensions` 和 `components` 均为向后兼容的可选字段；旧任务不需要补齐即可继续运行。`process_ground_truth` 是可选字段，用于后续专家抽象轨迹匹配。

**Typed declared trace（Agent 最终答案中的过程声明）：**

Agent 在最终答案中可以输出 `declared_trace`。每个步骤是一个 typed action unit：`subject/predicate/object` 是三元组核心，`operation/inputs/outputs/depends_on/evidence_step` 用来做脚本 grounding 和后续图匹配。

```json
{
  "key_values": {"total_food": 28693.92},
  "declared_trace": [
    {
      "step_id": "s1",
      "subject": "agent",
      "predicate": "LOADS",
      "object": "dataset.csv",
      "intent": "load_data",
      "operation": "read_csv",
      "inputs": ["DATA_PATH"],
      "outputs": ["df"],
      "depends_on": [],
      "evidence_step": 1,
      "status": "success"
    },
    {
      "step_id": "s2",
      "subject": "agent",
      "predicate": "AGGREGATES",
      "object": "spending_by_type",
      "intent": "compute_metric",
      "operation": "groupby_sum",
      "inputs": ["dataset.csv", "type", "spending"],
      "outputs": ["spending_by_type"],
      "depends_on": ["s1"],
      "evidence_step": 2,
      "status": "success"
    }
  ]
}
```

`TraceGroundingVerifier` 不相信 Agent 自报过程本身，而是用真实 `AgentTrace` 中的 code/tool log 校验声明是否发生：例如 `LOADS/read_csv` 必须在对应 evidence step 中出现 `read_csv` 或 `file_read`，`AGGREGATES/groupby_sum` 必须出现 `groupby` 和 `sum`，字段名也会被检查。

### 2.2 Evaluation Report（输出单元）

每次 agent run 生成 `bench_runs/DS_TASK_XXX/report.json`：

```json
{
  "instance_id": "DS_TASK_078",
  "metrics": {
    "completion_rate": 1.0,
    "result_accuracy": 0.85,
    "process_quality": 0.62,
    "safety_score": 1.0,
    "total_tokens": 12400,
    "total_cost_usd": 0.0031
  },
  "scores": {
    "deterministic": { "field_scores": { "precision": 1.0, "recall": 0.8 } },
    "process": {
      "recovery_patterns": { "blind_retry": 1, "diagnostic": 2 },
      "tool_call_diversity": 0.7
    },
    "risk": { "safety_compliant": true },
    "trace_grounding": {
      "grounding_rate": 1.0,
      "dependency_score": 1.0,
      "matched_steps": [
        {
          "step_id": "s1",
          "predicate": "LOADS",
          "operation": "read_csv",
          "grounded": true,
          "evidence_step": 1,
          "matched_observed_step": 1,
          "matched_signals": ["data_path", "read_csv"]
        }
      ],
      "unsupported_steps": [],
      "missing_declared_trace": false,
      "format_valid": true
    }
  }
}
```

**CAS（Composite Agent Score）：**

```
CAS = 0.40 × result_accuracy
    + 0.35 × process_quality
    + 0.25 × safety_score
```

`trace_grounding` 暂不进入 CAS，用作独立诊断维度和高质量 SFT trace 过滤信号，避免破坏已有 baseline 的可比性。

### 2.3 Contrastive Experiment 输出

```json
{
  "instance_id": "DS_TASK_078",
  "perturbation_level": 2,
  "metrics_clean":     { "cas": 0.71, "result_accuracy": 0.85 },
  "metrics_perturbed": { "cas": 0.53, "result_accuracy": 0.43 },
  "delta_cas": -0.18
}
```

---

## 3. 核心模块

### 3.1 任务生成 Pipeline

```
seed_datasets/               # 数据源
├── finance/
├── biomedical/
├── ecommerce/
├── scientific/
├── adversarial_dirtier.py   # 对抗脏数据注入（MNAR/Schema Drift/离群值/编码陷阱）
└── seed_analyzer.py

generation/
├── task_generator_agent.py  # 主生成 Agent（LLM 写代码 → 沙箱执行 → 计算真值）
├── reviewer_agent.py        # 质量审查
├── column_obfuscator.py     # SHA256 确定性列名混淆（L1 扰动）
├── red_team_agent.py        # L1/L2/L3 语义混淆引擎
└── taxonomy/task_taxonomy.json
```

### 3.2 评测引擎

```
engine/
├── executor.py              # ★ 主执行器：BenchmarkExecutor
│                            #   NativeCodeAgent + Official SDKs
│                            #   支持状态持久化与错误回溯
├── environment.py           # 工具执行环境（Simulated/Docker）
│                            #   支持 persistent namespace
├── tools.py                 # 模块化工具系统 (Tool/ToolRegistry)
└── llm_agents/
    ├── native_agent.py      # 原生 ReAct 代码智能体
    └── client_adapters.py   # 官方 SDK 直连层 (OpenAI/Anthropic/Gemini)

evaluation/
├── deterministic.py         # 数值精确匹配（5% 容差，支持 alternative_key_values）
├── process_auditor.py       # 过程质量 + 恢复模式（blind_retry/diagnostic/strategy_shift）
├── trace_grounding.py       # typed declared trace 与真实 tool log 的 grounding 校验
├── risk_assessor.py         # 安全合规检查
└── aggregator.py            # CAS 聚合
```

### 3.3 对照实验框架（Anti-Memorization）

```
experiments/
└── contrastive.py           # ContrastiveExperiment 编排器

generation/
└── red_team_agent.py        # 三级语义混淆：
                             #   L1: 列名混淆  income → var_001
                             #   L2: L1 + 统计陷阱（离群值、伪相关列、类型混淆）
                             #   L3: L2 + LLM 去语义化（problem_statement 重写）

analysis/
├── contrastive_analyzer.py  # Wilcoxon signed-rank + Cohen's d
└── leaderboard.py           # LaTeX 表格（含 Δ CAS / L1-L3 对比列）
```

### 3.4 Agent 框架（smolagents）

所有真实 LLM agent 统一通过 **NativeCodeAgent** 运行，直连官方 SDK：

```
agent spec 格式：native:<provider>/<model_id>

支持的 provider：
  native:openai/gpt-4o-mini
  native:openai/gpt-4o
  native:anthropic/claude-3-5-sonnet-20241022
  native:gemini/gemini-1.5-pro
```

LiteLLM 完整 provider 列表：https://docs.litellm.ai/docs/providers

---

## 4. 命令行接口

```bash
# 生成任务库
python -m data_agent_bench generate \
    --spec gen_spec_20tasks.json \
    --agent native:openai/gpt-4o \
    --output-dir ./tasks

# Baseline benchmark（native + gpt-4o-mini）
python -m data_agent_bench run --all \
    --agent native:openai/gpt-4o-mini \
    --tasks-dir ./tasks \
    --output-dir ./bench_runs \
    --db bench.db

# 强基线（gpt-4o）
python -m data_agent_bench run --all \
    --agent native:openai/gpt-4o \
    --tasks-dir ./tasks \
    --output-dir ./bench_runs_4o \
    --db bench.db

# 对照实验（clean vs L1/L2/L3）
python -m data_agent_bench experiment \
    --tasks-dir ./tasks \
    --agent native:openai/gpt-4o-mini native:openai/gpt-4o \
    --levels 1 2 3 \
    --output-dir ./experiments

# 统计汇总
python -m data_agent_bench stats --db bench.db

# 导出 SFT 训练数据
python -m data_agent_bench export-sft \
    --source tasks \
    --tasks-dir ./tasks \
    --output ./sft_data/train.jsonl \
    --format openai

# Agent spec 汇总
#   simulated                            随机基线（无 API 调用）
#   native:openai/gpt-4o-mini            OpenAI GPT-4o-mini
#   native:openai/gpt-4o                 OpenAI GPT-4o
#   native:anthropic/claude-3-5-sonnet-20241022     Anthropic Claude Sonnet
#   native:gemini/gemini-1.5-pro         Google Gemini
#   native:openai/<model>                  自部署 vLLM（设置 OPENAI_BASE_URL）
```

---

## 5. 任务库统计（当前版本）

| 维度 | 数量 |
|------|------|
| 总任务数 | 43 |
| Finance | 13 |
| Biomedical | 10 |
| Scientific | 10 |
| ECommerce | 9 |
| Easy / Medium / Hard | 19 / 16 / 8 |
| 数据集行数范围 | 142 – 1,827 |
| 数据来源 | sklearn 真实切片（优先）+ 合成（fallback） |

---

## 6. 快速开始

```bash
pip install -e .
pip install 'smolagents[litellm]'
export OPENAI_API_KEY=sk-...

# 用 simulated agent 验证 pipeline（无需 API）
python -m data_agent_bench run --task DS_TASK_078 \
    --agent simulated \
    --tasks-dir ./tasks \
    --output-dir ./bench_runs \
    --db bench.db

# 用真实 LLM 跑单个任务
python -m data_agent_bench run --task DS_TASK_078 \
    --agent smol:openai/gpt-4o-mini \
    --tasks-dir ./tasks \
    --output-dir ./bench_runs \
    --db bench.db

python -m data_agent_bench stats --db bench.db
```
