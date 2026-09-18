# DataAgentBench 论文初版补全草案

## 0. Paper Positioning

**Working Title**

DataAgentBench: Benchmarking Data Science Agents under Realistic Analytical Workflows and Semantic Perturbations

**Target Venue Positioning**

- 主投：SIGMOD E&A / Benchmarks and Datasets
- 备选：CIKM Resource Track
- 论文类型：Benchmark / Evaluation / Resource Paper
- 叙事重点：data science agents as end-to-end data workflow executors, not generic LLM chatbots

**One-sentence Problem Formulation**

We study the problem of evaluating whether data science agents can reliably complete realistic analytical workflows under semantic perturbations, considering not only final-answer accuracy but also process quality, safety, cost, and robustness.

---

## 1. Background / Why / Problem

Real-world data science workflows require much more than producing a final textual answer. A data science agent must read files, infer column semantics, write and execute analysis code, handle noisy or anomalous data, recover from execution errors, and finally report a trustworthy numerical or statistical conclusion. Existing LLM and agent benchmarks often focus on final-answer correctness or general reasoning ability, leaving unclear whether an agent can actually behave as a reliable data analyst in realistic analytical workflows.

DataAgentBench targets this gap by evaluating data agents as **end-to-end data workflow executors**. The benchmark currently contains **121 realistic analytical tasks** across **5 domains**: Finance, Biomedical, ECommerce, Scientific, and Generic. The tasks are stratified into **Easy / Medium / Hard** difficulty levels and require agents to perform operations such as aggregation, time-series analysis, statistical testing, curve fitting, data cleaning, and anomaly handling.

### Core Gaps

1. **Final-answer-only evaluation is insufficient.** Existing benchmarks often reward only the final answer, but data science agents may fail through poor data loading, redundant tool use, weak error recovery, unsafe execution, or inefficient process behavior.

2. **Semantic shortcut reliance is under-tested.** Many agents depend heavily on column names, domain descriptions, and business context. Existing benchmarks rarely test whether agents can still solve the task when these semantic cues are removed or corrupted.

3. **Robustness lacks matched-pair evaluation.** Without clean-vs-perturbed task pairs, it is difficult to distinguish genuine data reasoning from superficial reliance on task wording or schema semantics.

---

## 2. Running Example: Finance Price Analysis

**Selected Task:** `DS_TASK_054`

**Domain:** Finance  
**Difficulty:** Easy  
**Primary Task Type:** Time-Series & Forecasting / 时间序列与预测分析  
**Secondary Task Types:** Descriptive & Aggregation Analysis / 描述统计与聚合分析; Data Quality & Robustness Handling / 数据质量与鲁棒性处理  
**Challenge Dimensions:** heteroskedasticity, outlier handling, semantic perturbation  
**Ground Truth:** `average_price = 104.56994551077256`

### Clean Version

The clean task gives semantically meaningful columns:

```text
Date, Price, TradeVolume
2020-01-01, 102.48, 575.39
2020-01-02,  99.63, 873.81
...
```

Problem statement:

> Given the time series dataset representing daily financial data, compute the average price over the period. The dataset includes heteroskedasticity in the price values. You must handle this aspect and compute the average price accurately.

In this version, an agent can rely on familiar semantic cues such as `Date`, `Price`, and `TradeVolume`.

### L1: Column Obfuscation

The same dataset is transformed with deterministic opaque column names:

```text
Date        -> var_d36f
Price       -> var_fbca
TradeVolume -> var_69e1
```

The mathematical task remains the same, but the agent must correctly use the provided mapping or infer the target column without relying on natural column names.

### L2: Statistical Traps

The L1 version is further perturbed with realistic data quality traps, such as:

- anomalous value clusters,
- type or encoding inconsistencies,
- misleading columns,
- schema drift,
- noisy or heteroskedastic distributions.

The goal is to test whether an agent can perform appropriate data inspection and avoid brittle assumptions.

### L3: De-semanticized Problem

The problem statement is rewritten to remove business and financial context:

> Given a time-indexed table containing `var_d36f`, `var_fbca`, and `var_69e1`, compute the average value of the relevant measurement over the full period while accounting for abnormal variation in the values.

At this level, the agent must solve the task using statistical reasoning and the task specification rather than relying on domain semantics.

### Why This Example Matters

This example can anchor the whole paper:

- Introduction: shows why semantic cues make data-agent evaluation fragile.
- Benchmark Construction: demonstrates clean-to-perturbed task transformation.
- Evaluation Protocol: illustrates result accuracy, process quality, safety, and cost.
- Case Study: shows how an agent may succeed on clean data but fail through semantic confusion, blind retries, or incorrect anomaly handling under perturbation.

---

## 3. Task Taxonomy

Realistic data science workflows are often composite: a single task may require data selection, cleaning, aggregation, modeling, interpretation, and robust execution. Therefore, DataAgentBench should not force each task into a single mutually exclusive class. Instead, each task is annotated with:

```json
{
  "primary_task_type": "time_series_forecasting",
  "secondary_task_types": [
    "descriptive_aggregation",
    "data_quality_robustness"
  ],
  "challenge_dimensions": [
    "heteroskedasticity",
    "outlier_handling",
    "semantic_perturbation"
  ],
  "tags": ["time-series", "forecasting", "heteroskedasticity"]
}
```

### Analytical Task Types

| Slug | English Label | 中文名 |
|---|---|---|
| `descriptive_aggregation` | Descriptive & Aggregation Analysis | 描述统计与聚合分析 |
| `statistical_inference` | Statistical Inference & Hypothesis Testing | 统计推断与假设检验 |
| `time_series_forecasting` | Time-Series & Forecasting | 时间序列与预测分析 |
| `predictive_modeling` | Predictive Modeling & Model Evaluation | 预测建模与模型评估 |
| `risk_anomaly_decision` | Risk, Anomaly & Decision Analysis | 异常、风险与决策分析 |
| `data_quality_robustness` | Data Quality & Robustness Handling | 数据质量与鲁棒性处理 |
| `specialized_domain_analysis` | Specialized Domain Analysis | 专业领域分析方法 |

### Challenge Dimensions

Challenge dimensions are orthogonal to task type. They capture why a task is difficult or what perturbation tests:

- missing values and imputation,
- outlier or anomaly handling,
- heteroskedasticity and noisy distributions,
- schema drift or type confusion,
- semantic obfuscation,
- right censoring,
- class imbalance or cost-sensitive decisions.

This design supports both a clean primary-task distribution table and a multi-label fine-grained analysis over secondary task types and challenge dimensions.

---

## 4. What DataAgentBench Evaluates

DataAgentBench evaluates **data agents as complete analytical systems**, not merely LLMs answering natural-language questions. The evaluated system includes the LLM, prompting strategy, tool execution behavior, code-writing ability, error recovery, and final answer reporting.

### Core Capabilities

- **Analytical correctness:** whether the agent computes the expected numerical or statistical result.
- **Workflow execution quality:** whether the agent loads data, inspects it, writes useful code, and avoids redundant actions.
- **Robustness:** whether performance remains stable under semantic perturbations.
- **Safety and cost discipline:** whether the agent avoids unsafe commands, excessive resource use, and unnecessary tokens or tool calls.

### Evaluation Metrics

DataAgentBench currently records:

- `completion_rate`
- `result_accuracy`
- `process_quality`
- `safety_score`
- `token_efficiency`
- `wall_time_seconds`
- `total_tokens`
- `total_cost_usd`

Composite Agent Score (CAS):

```text
CAS = 0.40 * result_accuracy
    + 0.35 * process_quality
    + 0.25 * safety_score
```

### Hierarchical Accuracy

Because DataAgentBench tasks are composite workflows, `result_accuracy` should be interpreted as an overall score rather than the only diagnostic. The benchmark supports a hierarchical accuracy view:

- **Overall Result Accuracy:** the leaderboard-facing score used by CAS.
- **Component Accuracy:** diagnostic scores for data selection, preprocessing, method selection, numerical result, interpretation, and output format.
- **Task-Type Accuracy:** aggregated performance by primary and secondary analytical task types.
- **Robustness Accuracy:** clean vs L1/L2/L3 accuracy and CAS degradation.

The standard component set is:

| Component | Meaning | Default Weight |
|---|---|---:|
| `data_selection` | Correct columns, filters, groups, or target variables | 0.15 |
| `preprocessing` | Missing values, outliers, type conversion, cleaning | 0.10 |
| `method_selection` | Appropriate statistical method or model | 0.10 |
| `numerical_result` | Numerical answer close to ground truth | 0.55 |
| `interpretation` | Explanation consistent with computed result | 0.05 |
| `output_format` | Required structured output or answer format | 0.05 |

For leaderboard stability, CAS keeps using `result_accuracy`, `process_quality`, and `safety_score`. Component accuracy is used for fine-grained diagnosis and appendix-level analysis.

---

## 5. How DataAgentBench Works

### Contribution 1: Realistic Analytical Task Suite

DataAgentBench contains **121 tasks** across 5 domains:

| Domain | Number of Tasks |
|---|---:|
| Finance | 29 |
| Biomedical | 27 |
| Scientific | 27 |
| ECommerce | 25 |
| Generic | 13 |

Difficulty distribution:

| Difficulty | Number of Tasks |
|---|---:|
| Easy | 40 |
| Medium | 41 |
| Hard | 40 |

### Contribution 2: Process-aware Evaluation Protocol

Instead of evaluating only the final answer, DataAgentBench combines:

- deterministic numerical matching,
- soft completion milestones,
- process auditing,
- risk assessment,
- token and cost tracking.

This makes it possible to distinguish several cases that final-answer accuracy alone would collapse:

- correct answer but inefficient process,
- partial progress without final submission,
- wrong answer despite substantial work,
- safe but unproductive execution,
- unsafe or resource-heavy behavior.

### Contribution 3: Semantic Perturbation Robustness Testing

DataAgentBench includes a matched-pair robustness framework:

- **Clean:** original task and dataset.
- **L1:** semantic column names replaced by opaque labels.
- **L2:** L1 plus statistical traps and data quality perturbations.
- **L3:** L2 plus de-semanticized problem statement.

This design tests whether agents genuinely reason over data or exploit surface-level semantic cues.

### Contribution 4: Empirical Analysis of Data Agent Failures

Initial GPT-4o-mini results over 121 reports show:

| Metric | Mean | Median | Min | Max |
|---|---:|---:|---:|---:|
| Completion Rate | 0.7005 | 0.7015 | 0.1069 | 1.0000 |
| Result Accuracy | 0.3901 | 0.4056 | 0.0021 | 1.0000 |
| Process Quality | 0.3862 | 0.3783 | 0.0952 | 0.8333 |
| Safety Score | 0.9008 | 1.0000 | 0.7000 | 1.0000 |
| Total Tokens | 15303.25 | 16117 | 414 | 73128 |
| Cost USD | 0.0042 | 0.0035 | 0.0000 | 0.0316 |

These preliminary results suggest that current agents can often make progress, but their final correctness, process quality, and robustness remain far from reliable.

---

## 6. Research Questions

**RQ1: How well do current data science agents perform on realistic analytical tasks across domains and difficulty levels?**

This asks whether agents can complete real data workflows, not just answer isolated questions.

**RQ2: How robust are data agents under semantic perturbations such as column obfuscation, statistical traps, and de-semanticized task descriptions?**

This asks whether agents truly reason over data or rely on schema and domain wording.

**RQ3: What failure patterns explain agent performance degradation beyond final-answer accuracy?**

This asks whether poor performance comes from wrong computation, weak data inspection, redundant retries, path errors, unsafe execution, or poor final-answer formatting.

---

## 7. Expected Findings

**Finding 1. Data agents can solve many easy analytical tasks, but performance drops sharply on tasks requiring robust statistical reasoning, data cleaning, or multi-step analysis.**

This finding should be supported by domain x difficulty tables and fine-grained task-type analysis.

**Finding 2. Semantic perturbations expose strong dependence on column names and domain descriptions, especially under L2/L3 settings.**

This finding should be supported by clean vs L1/L2/L3 paired experiments.

**Finding 3. Final-answer accuracy alone hides important failures; process quality reveals blind retries, inefficient tool use, weak diagnostic recovery, and loop-like behavior.**

This finding should be supported by process audit metrics and case studies.

**Finding 4. Reliable data agents require not only stronger reasoning but also better execution discipline, including safety, cost control, and robust tool use.**

This finding should be supported by token/cost/safety analysis.

---

## 8. Draft Introduction Skeleton

Modern LLM-based agents are increasingly expected to operate as autonomous data analysts: they read datasets, write Python code, execute analysis, recover from errors, and report conclusions. However, evaluating such agents remains challenging. A correct final number does not necessarily imply reliable analytical behavior, while a failed final answer may still hide meaningful partial progress. Moreover, data agents often rely on semantic shortcuts from column names and task descriptions, making it unclear whether they truly reason over data or merely exploit surface cues.

To address this problem, we introduce **DataAgentBench**, a benchmark for evaluating data science agents on realistic analytical workflows under semantic perturbations. DataAgentBench contains 121 tasks across finance, biomedical, e-commerce, scientific, and generic domains, with balanced easy, medium, and hard difficulty levels. Each task requires an agent to interact with data through executable tools and produce verifiable analytical outputs.

DataAgentBench differs from prior agent benchmarks in two key ways. First, it evaluates the entire workflow, combining result accuracy, process quality, safety, token efficiency, and execution cost. Second, it introduces a matched-pair semantic perturbation protocol that transforms each task from clean data to progressively more challenging L1/L2/L3 variants, including column obfuscation, statistical traps, and de-semanticized problem statements. This protocol reveals whether agents can robustly reason over data when familiar semantic cues are removed or corrupted.

Our preliminary experiments show that current data agents can often make partial progress but remain unreliable as end-to-end analytical systems. For example, GPT-4o-mini achieves an average completion rate of 0.7005 but only 0.3901 result accuracy and 0.3862 process quality over 121 tasks. These results suggest a significant gap between apparent task progress and trustworthy analytical performance.

We make the following contributions:

1. We introduce DataAgentBench, a 121-task benchmark for evaluating data science agents across five domains and three difficulty levels.
2. We propose a process-aware evaluation protocol that combines result accuracy, process quality, safety, token efficiency, and execution cost.
3. We introduce semantic perturbation robustness testing through clean, L1, L2, and L3 matched task variants.
4. We provide empirical analysis and failure attribution for current data agents, revealing limitations in robustness, process quality, and execution discipline.

---

## 9. Table 1 Draft: Benchmark Comparison Dimensions

| Benchmark | Data Workflow Tasks | Code Execution | Process Quality | Safety/Cost | Semantic Perturbation | Domain Diversity | Paired Robustness |
|---|---|---|---|---|---|---|---|
| Generic LLM QA Benchmarks | No | No | No | No | No | Limited | No |
| Generic Agent Benchmarks | Partial | Partial | Partial | Rare | Rare | Mixed | Rare |
| Data/ML Task Benchmarks | Yes | Sometimes | No | No | No | Partial | No |
| Code Agent Benchmarks | Partial | Yes | Partial | Rare | No | Limited | No |
| **DataAgentBench** | Yes | Yes | Yes | Yes | Yes | Yes | Yes |

This table should be replaced with concrete related benchmarks after literature review, but these are the exact dimensions the paper should defend.
