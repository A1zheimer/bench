# DataAgentBench Benchmark 论文五要素对照与补强方案

**目的**：参考 Benchmark/Evaluation 论文写作范式，重新检查 DataAgentBench 的 gap、motivation、benchmark design、evaluation framework、empirical findings 和投稿准备。  
**核心结论**：DataAgentBench 应明确走 **Benchmark / Evaluation Paper** 路线，而不是 Technique Paper 路线。当前最重要的不是提出一个新 agent，而是把“为什么需要这个 benchmark”讲透，并用系统实验证明现有 data agents 在真实数据分析 workflow 中存在可测量、可复现、可诊断的可靠性缺口。

---

## 1. Benchmark Paper 与 Technique Paper 的定位差异

### Technique Paper 的主轴

Technique Paper 通常围绕：

```text
Problem -> New Method / Mechanism -> Why It Works -> Experiments Prove Better
```

重点是一个新的算法、模型、系统机制或训练方法。

### Benchmark / Evaluation Paper 的主轴

Benchmark Paper 应围绕：

```text
Evaluation Gap -> Benchmark Design -> Evaluation Framework -> Empirical Findings -> Research Opportunities
```

重点不是“我提出了一个最强方法”，而是：

- 现有评估体系漏掉了什么关键能力？
- 为什么这个能力在真实场景中重要？
- 新 benchmark 如何系统、可扩展、可信地衡量它？
- 当前模型在这个维度上到底差在哪里？
- 这个 benchmark 能推动后续哪些研究？

### DataAgentBench 的正确定位

DataAgentBench 不应该主打“我们造了一个更强的 agent”。更合适的核心主张是：

> Existing agent and data analysis benchmarks do not adequately evaluate whether autonomous data agents can reliably execute realistic data workflows under schema, metadata, and semantic perturbations. DataAgentBench fills this gap by providing a process-aware, perturbation-aware benchmark with matched robustness tests and fine-grained diagnostic metrics.

对应中文说法：

> 现有 benchmark 不能系统评估 data agent 在真实数据工作流中的可靠性，尤其无法衡量 agent 对 schema/metadata/业务语义线索的依赖程度。DataAgentBench 通过真实数据分析任务、过程感知评分和 clean/L1/L2/L3 成对扰动实验，补齐这一评估盲区。

---

## 2. 建议压缩成 3 个核心 Gap

Introduction 中的 gap 不宜太多，建议控制在 3 个，每个都对应一个设计和一个实验。

### Gap 1: Workflow Reliability Blind Spot

现有 benchmark 多关注最终答案、代码生成或单步推理，不能评估 data agent 作为完整 workflow executor 的可靠性。

具体盲区：

- 是否正确加载和检查数据？
- 是否选对列、过滤条件、分组对象？
- 是否正确处理缺失、异常、类型转换？
- 是否能从执行错误中恢复？
- 是否有冗余重试、无效工具调用或不安全行为？

对应设计：

- process-aware evaluation
- result accuracy + process quality + safety score + cost
- component accuracy

对应实验：

- overall performance
- component accuracy
- failure taxonomy
- process-quality case studies

### Gap 2: Schema / Metadata Semantic Robustness Blind Spot

很多 data agents 依赖可读列名、领域描述和业务语义线索。现有 benchmark 通常默认 schema 和 task statement 是语义清晰的，无法判断模型是真的理解数据，还是借助表面语义捷径。

具体盲区：

- column names 被混淆后是否还能定位目标字段？
- task statement 去掉业务语义后是否还能完成分析？
- 加入伪相关列、异常值、类型混淆后是否会被误导？
- agent 是否会在 metadata 不完整时产生自信但错误的结论？

对应设计：

- clean/L1/L2/L3 semantic perturbation protocol
- matched-pair robustness testing
- paired delta metrics

对应实验：

- clean vs L1/L2/L3 result accuracy drop
- CAS degradation
- Wilcoxon signed-rank test
- robustness by task type / difficulty

### Gap 3: Diagnostic Evaluation Blind Spot

现有 benchmark 往往只能告诉我们模型“对或错”，但不能解释为什么错。对于 data agent，这不够，因为同样的错误答案可能来自不同原因：数据选择错、预处理错、方法错、数值计算错、解释错或格式错。

具体盲区：

- 错误来自字段理解还是统计方法？
- 是最终数值错，还是过程质量差？
- 是数据清洗失败，还是输出格式导致自动评分失败？
- 不同 task type 和 challenge dimension 下的失败模式是否不同？

对应设计：

- primary task type + secondary task types + challenge dimensions
- component-level accuracy
- failure attribution
- error taxonomy

对应实验：

- task-type fine-grained analysis
- challenge-dimension analysis
- component accuracy table
- qualitative case studies

---

## 3. Benchmark 论文五大核心要素对照

| 核心要素 | Benchmark 论文要求 | DataAgentBench 当前状态 | 主要不足 | 下一步 |
|---|---|---|---|---|
| Research Gap | 明确一个现有评估体系无法覆盖的关键能力 | 已提出 workflow reliability、semantic perturbation、process-aware evaluation | gap 还偏口号化，缺 Table 1 与 related work 证据支撑 | 写 Introduction v1；完成 benchmark comparison table |
| Construction Pipeline | 系统说明数据如何高质量、可扩展、低成本构建 | 已有 121 tasks、seed datasets、task.json、expected_output.json、evaluation reports | pipeline 没有论文级图和 input/output/operation 说明；GT validation 不够强 | 画 Figure 2；补 design goals、QC、人工审核方案 |
| Evaluation Framework | 整体指标 + 细粒度 taxonomy + 诊断能力 | 已有 CAS、result/process/safety、taxonomy、component accuracy 设计 | 121 tasks 尚未全量 taxonomy annotation；components 大多未标注 | 生成 task statistics；补核心任务 component labels |
| Empirical Findings | 不止 leaderboard，要有多角度洞察 | 已有 GPT-4o-mini 121 clean baseline | 没有多模型、扰动实验、统计检验、case studies | 跑 3 models × 60 tasks × 4 conditions pilot |
| Optional Method | 可选：提出优化方法证明 benchmark 能促进能力提升 | 当前没有专门方法 | R3 时间紧，不建议强行加复杂方法 | 可选做 robust prompting / schema-aware prompting 作为轻量 baseline，不作为主贡献 |

---

## 4. Introduction 应该怎么写

Benchmark paper 的 Introduction 应该是全文压缩版，不是方法论文的 key idea 展开。建议使用下面结构。

### Paragraph 1: 真实需求与重要性

讲 data agents 正在成为数据分析和数据工程 workflow 的自动执行者：

- 读取表格和文件；
- 理解 schema 和 metadata；
- 编写并执行分析代码；
- 处理脏数据、异常和类型问题；
- 输出可用于决策的统计结论。

SIGMOD 口径要强调：这是 data lifecycle、analytics workflow、metadata robustness、data quality 和 systems for AI 的问题。

### Paragraph 2: 现有评估盲区

用 3 个 gap 收束：

1. final-answer-only evaluation 无法评估 workflow reliability；
2. 现有 benchmark 很少测试 schema/metadata semantic robustness；
3. 缺少 paired perturbation 和 component-level diagnostic evaluation。

这里要避免泛泛地说“现有 benchmark 不好”，而是要说清楚“它们评估了什么，但漏掉了什么”。

### Paragraph 3: Running Example

引入 `DS_TASK_054`：

- clean: `Date`, `Price`, `TradeVolume`
- L1: `Date -> var_d36f`, `Price -> var_fbca`, `TradeVolume -> var_69e1`
- L2: 加异常值、类型混淆、伪相关列
- L3: 去掉 finance 语义，只保留 opaque schema

要让审稿人 30 秒内明白：

> 同一个分析任务，agent 在 clean version 中可能看起来会做，但在 schema/metadata 语义被系统性削弱后会暴露真实可靠性问题。

### Paragraph 4: DataAgentBench 的设计

说明 DataAgentBench：

- 121 realistic analytical tasks；
- 5 domains；
- Easy/Medium/Hard；
- multi-label task taxonomy；
- process-aware evaluation；
- clean/L1/L2/L3 matched perturbation；
- component-level accuracy。

### Paragraph 5: Research Questions

建议 3 个 RQ：

**RQ1.** How well do current data agents perform on realistic analytical workflows across domains, difficulty levels, and task types?

**RQ2.** How robust are data agents under schema, metadata, and semantic perturbations?

**RQ3.** What failure patterns explain performance degradation beyond final-answer accuracy?

### Paragraph 6: Contributions

贡献点必须和 RQ、章节结构对应：

1. **Benchmark**：121 tasks, multi-domain, multi-difficulty, workflow-oriented。
2. **Construction and perturbation protocol**：clean/L1/L2/L3 matched semantic perturbation。
3. **Evaluation framework**：result accuracy, process quality, safety, cost, component accuracy。
4. **Empirical findings**：multi-model robustness and failure analysis。

注意：第 4 点现在还没有实验支撑，必须在后续补齐。

---

## 5. 主干章节应如何落到 DataAgentBench

### Section 2: The Proposed Benchmark

这是 DataAgentBench 的核心章节，应替代 Technique Paper 的 Method 章节。

#### 2.1 Design Goals & Task Scope

建议写 5 个 design goals：

| Goal | 内容 |
|---|---|
| G1 Realistic workflows | 任务应模拟真实数据分析流程，而非孤立问答 |
| G2 Verifiable outputs | 每个任务有可验证 ground truth 或多解平权机制 |
| G3 Process observability | 评估不仅看结果，也看数据加载、代码执行、错误恢复 |
| G4 Semantic robustness | 支持 clean/L1/L2/L3 成对扰动 |
| G5 Fine-grained diagnosis | 支持 task taxonomy、challenge dimensions、component accuracy |

任务边界也要说清楚：

- 评估 tabular/dataframe-oriented analytical workflows。
- 评估 agent system，而不是单独评估 base LLM。
- 重点是 analysis reliability，不是前端可视化美观，也不是数据库查询优化。
- 不把完全开放式科研建模作为主任务，因为 ground truth 难以验证。

#### 2.2 Benchmark Construction Pipeline

Figure 2 应包含下面流程：

| Step | Input | Operation | Output |
|---|---|---|---|
| Seed Data Collection | public/curated datasets | select domains and data slices | seed tables |
| Task Synthesis | seed tables + task templates/LLM generation | generate problem statements and analysis goals | candidate tasks |
| Ground Truth Generation | candidate tasks + reference code | execute reference solutions; record numeric answers | expected_output.json |
| Quality Control | task + data + GT | schema validation, execution validation, sanity checks, manual audit | validated tasks |
| Taxonomy Annotation | task metadata + problem statement | assign primary/secondary/challenge labels | task taxonomy |
| Perturbation Generation | clean task | L1 column obfuscation, L2 statistical traps, L3 de-semanticization | matched task variants |
| Evaluation Packaging | tasks + evaluator | create run scripts and reports | reproducible benchmark artifact |

当前不足：

- 这张 Figure 2 还没画。
- 每一步的质量控制还没写细。
- 人工审核比例和规则还没定。

#### 2.3 Benchmark Characteristics

需要至少展示：

- domain distribution；
- difficulty distribution；
- primary task type distribution；
- secondary task type distribution；
- challenge dimension distribution；
- dataset size distribution；
- output type distribution；
- clean/L1/L2/L3 perturbation examples。

当前已有 domain/difficulty，task-type 可以通过 annotation script 生成，但需要全量确认。

### Section 3: Specialized Method / Optional

这个章节可选。对 R3 来说，不建议强行做一个复杂新模型，因为会分散主线。

可选轻量方案：

- Schema-aware prompting baseline；
- Robust data inspection prompt；
- Trace-aware self-checking baseline；
- 简单的 perturbation-aware agent instruction。

如果做，就把它当作小节或 appendix，不要让论文变成 Technique Paper。

### Section 4: Experiments & Empirical Findings

实验章节必须围绕 RQ 展开。

#### 4.1 Experimental Setup

要明确：

- baselines：GPT-4o-mini、GPT-4o、Claude/Gemini/Qwen，最好包含一个开源模型；
- settings：temperature、max steps、timeout、tool set；
- conditions：Clean、L1、L2、L3；
- metrics：result accuracy、process quality、safety、CAS、component accuracy、cost；
- statistical tests：paired tests for clean vs perturbed。

#### 4.2 Overall Performance

需要一张大表：

| Model | Accuracy | Process | Safety | CAS | Tokens | Cost |
|---|---:|---:|---:|---:|---:|---:|

当前只有 GPT-4o-mini clean，因此不够。

#### 4.3 Fine-grained Analysis

建议按 RQ 组织：

- RQ1: performance by domain / difficulty / task type；
- RQ2: clean vs L1/L2/L3 robustness；
- RQ3: component accuracy / error taxonomy / process failure。

每个重要分析后写：

> **Finding X.** ...

这类 Finding 是 Benchmark 论文非常重要的写法。

#### 4.4 Case Studies

至少 2 到 4 个：

- `DS_TASK_054`：Running Example，展示 semantic perturbation；
- 一个 ECommerce task：展示业务指标或 groupby/filter 错误；
- 一个 Biomedical/Scientific Medium/Hard task：展示统计方法或数据质量处理失败；
- 可选一个成功 case：展示高质量 agent workflow。

### Section 5: Discussion & Research Opportunities

需要把 findings 转成 research opportunities：

- schema/metadata-robust data agents；
- process-supervised agent training；
- data-quality-aware tool use；
- benchmark-driven agent debugging；
- human-in-the-loop validation for high-risk analytics；
- reusable artifact and reproducible agent evaluation。

### Section 6: Related Work

必须有对比表。建议维度：

| Benchmark | Data Workflow | Code Execution | Process Quality | Semantic Perturbation | Paired Robustness | Component Diagnosis | Data Management Scope |
|---|---|---|---|---|---|---|---|

要把 DataAgentBench 和 DS-1000、MLAgentBench、Spider/BIRD、generic agent benchmarks、data analysis benchmarks 区分开。

---

## 6. 按新 Checklist 重新打分

### Introduction Checklist

| 项目 | 状态 | 说明 |
|---|---|---|
| Running Example / Figure 1 | 部分完成 | 已选 `DS_TASK_054`，但 Figure 1 未画，L2/L3 未真实落地 |
| 关键盲区不超过 3 点 | 部分完成 | 已有 3 个 gap，但需要更 SIGMOD 化 |
| Benchmark 对比表 Table 1 | 未完成 | 当前只有维度草案，缺真实 related work |
| 2-3 个 Research Questions | 已完成初稿 | RQ1/RQ2/RQ3 已比较清楚 |
| Design Considerations | 部分完成 | 已有设计方向，需写成 G1-G5 |
| Contributions 对应 RQ 和章节 | 部分完成 | 前 3 点可以，empirical analysis 需要实验支撑 |

### Benchmark 章节 Checklist

| 项目 | 状态 | 说明 |
|---|---|---|
| Design Goals | 部分完成 | 建议采用 G1-G5 |
| Pipeline Figure 2 | 未完成 | 必须画 |
| 每步输入/输出/操作 | 未完成 | 需要 pipeline table |
| 质量控制策略 | 部分完成 | schema validator 有，但人工审核和 GT validation 需要补 |
| 数据集统计图表 | 部分完成 | domain/difficulty 有，task-type/challenge 还需生成 |
| 数据示例 | 部分完成 | `DS_TASK_054` 可用，但需视觉化 |

### 实验章节 Checklist

| 项目 | 状态 | 说明 |
|---|---|---|
| Baseline 覆盖开源/闭源/不同规模 | 未完成 | 只有 GPT-4o-mini clean |
| Overall Performance 大表 | 未完成 | 需多模型 |
| Fine-grained Analysis | 未完成 | 需 domain/difficulty/task-type/challenge/component |
| Error Taxonomy / 行为偏差 | 未完成 | 需从 traces 标注 |
| Human vs LLM | 可选 | 对 DataAgentBench 不是必须，除非想证明任务人类可解 |
| Case Studies | 部分完成 | 已选 Running Example，但未写真实案例 |
| Finding X 总结 | 未完成 | 需要实验结果后提炼 |
| Research Opportunities | 部分完成 | 有方向，缺 findings 支撑 |

### 整体 Checklist

| 项目 | 状态 | 说明 |
|---|---|---|
| Gap -> Benchmark -> Evaluation -> Insights -> Opportunities | 部分完成 | 前三段有，Insights 还弱 |
| 开源代码和数据链接 | 未完成 | 需要匿名 artifact |
| Limitations and Future Work | 未完成 | 可写但应基于最终实验 |
| Appendix 补充材料 | 未完成 | 需要 full task list、prompt、GT validation、更多结果 |

---

## 7. 最需要修改提升的 5 个点

### 1. Gap 要更具体、更可证伪

不要只说“现有 benchmark 不够真实”。要说：

- 它们是否缺 process observability；
- 是否缺 schema/metadata perturbation；
- 是否缺 matched-pair robustness；
- 是否缺 component-level diagnosis。

### 2. Running Example 要承担全文锚点

`DS_TASK_054` 不能只放在文字里，需要成为 Figure 1，并且在 Introduction、Benchmark、Experiment、Case Study 中反复出现。

### 3. Pipeline 要写成一个贡献

Benchmark 论文的 construction pipeline 本身就是贡献之一。要把任务生成、GT 验证、扰动生成、taxonomy annotation、quality control 写得像一个可复用方法。

### 4. Findings 必须来自真实实验

现在的 Finding 仍然是预期。要尽快用 pilot experiment 把它们变成真实结果。

建议先做：

- 3 models；
- 60 core tasks；
- Clean/L1/L2/L3；
- paired delta；
- 2-3 case studies。

### 5. Optional Method 不要喧宾夺主

如果时间紧，R3 不强求 specialized model。可以做一个轻量 robust prompting baseline，但主线仍然是 benchmark/evaluation。

---

## 8. 下一步改稿顺序

### 48 小时内

1. 写 Introduction v1。
2. 画 Figure 1 Running Example。
3. 写 G1-G5 Design Goals。
4. 画 Figure 2 Pipeline 草图。
5. 做 Table 1 benchmark comparison 草表。

### 1 周内

1. 生成 Table 2 task statistics。
2. 完成 121 tasks taxonomy annotation。
3. 选 60 core tasks。
4. 固化 L1/L2/L3 perturbation protocol。
5. 跑 20-task pilot。

### 2-4 周内

1. 跑 3 models × 60 tasks × 4 conditions。
2. 生成 overall performance table。
3. 生成 clean-vs-perturbed robustness figure。
4. 做 task-type/challenge/component analysis。
5. 写 2-3 个 case studies。

---

## 9. 给导师的压缩版说法

参考 Benchmark 论文范式后，我认为 DataAgentBench 的主线应进一步收敛为：

> 现有 data/agent benchmark 无法系统评估 data agents 在真实数据工作流中的可靠性，特别是面对 schema、metadata 和业务语义扰动时的鲁棒性。DataAgentBench 通过 121 个真实分析任务、过程感知评分、component-level diagnosis 和 clean/L1/L2/L3 成对扰动实验，定义并测量这个新的评估维度。

当前已经有 benchmark 原型和单模型 clean baseline，但距离 SIGMOD 还缺三个关键证据：

1. 多模型、多扰动实验；
2. 论文级 construction pipeline 和质量控制；
3. 从结果中提炼出的 Finding X 与 Research Opportunities。

