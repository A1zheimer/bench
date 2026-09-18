# DataAgentBench 项目进度汇报与 SIGMOD 投稿规划

**汇报对象**：导师组会 / 阶段性讨论  
**汇报日期**：2026-05-18  
**目标 venue**：SIGMOD 2027 Research Track, E&A / Benchmarks and Datasets  
**项目定位**：面向 Data Science / Data Engineering Agents 的过程感知 benchmark 与语义扰动鲁棒性评测

---

## 1. 一句话结论

DataAgentBench 目前已经具备投稿 SIGMOD E&A / Benchmarks and Datasets 的基础形态：已有 121 个真实数据分析任务、可运行的 agent evaluation 框架、过程质量与安全评分、GPT-4o-mini 全量初始结果，以及 clean/L1/L2/L3 语义扰动鲁棒性主线。  

但距离 SIGMOD 可投版本，核心差距仍在三点：**多模型、多扰动实验尚未补齐；benchmark construction 和 artifact 需要按 SIGMOD 规范整理；论文叙事必须从“LLM benchmark”进一步收敛到“data management lifecycle / data quality / metadata robustness / systems for AI”问题。**

我的判断是：如果以 **SIGMOD 2027 R3, 2026-07-17** 为目标，可以冲刺一版 E&A benchmark paper，但风险较高；如果把 **SIGMOD 2027 R4, 2026-10-17** 作为保底窗口，则有更充分时间做完整多模型实验、artifact release 和论文打磨。

---

## 2. SIGMOD 要求与项目匹配

根据 SIGMOD 2027 Research Track 官方 CFP，目前最相关的是 **Experimental Analysis (E&A) Studies: Benchmarks and Datasets**。这一类论文强调新的 workloads、benchmark data、benchmark methods、生成方法、benchmark 使用方式，以及基于 benchmark 的实验结果。若按该类型投稿，标题需要带 `: [Experiments & Analysis]` 后缀。

### 2.1 关键投稿约束

| 要求 | SIGMOD 2027 规则 | 对本项目的影响 |
|---|---|---|
| 论文类型 | Research Track, E&A / Benchmarks and Datasets | DataAgentBench 应包装为 benchmark/evaluation paper |
| 页数 | 12 pages excluding references | 必须压缩叙事，主文只放核心实验和图表 |
| 匿名性 | Double-anonymous | artifact、代码仓库、数据路径、README 都要匿名化 |
| Artifact | benchmark/data/scripts 需提供匿名仓库供评审 | 不能只有论文，需要可复现实验子集和脚本 |
| Scope | 必须清楚属于 database/data management community | 叙事要围绕 data lifecycle、metadata、data quality、workflow execution |
| 截止时间 R3 | Abstract/COI: 2026-07-10, Paper: 2026-07-17 | 从今天起约 8 周，需要极高执行密度 |
| 截止时间 R4 | Abstract/COI: 2026-10-10, Paper: 2026-10-17 | 更稳，可作为保底 |

### 2.2 与 SIGMOD scope 的对齐方式

本项目不能只说“评测 LLM agent”，否则容易被认为更适合 NLP/AI venue。SIGMOD 口径应写成：

> We study the reliability of autonomous data agents as executors of end-to-end data management and analytical workflows, focusing on data semantics, schema perturbation, data quality handling, process reliability, and reproducible benchmark construction.

对应到 SIGMOD CFP 的 topic：

- Data warehousing, OLAP, Analytics
- Data exploration, visualization, query languages, and user interfaces
- Data integration, schema matching, metadata management
- Data quality and data cleaning
- Data management and metadata for ML pipelines
- Systems for AI

---

## 3. 当前项目进度

### 3.1 已完成的 benchmark 基础

当前项目已构建 **121 个 realistic analytical tasks**，覆盖 5 个 domain 和 3 个难度等级。

| Domain | Tasks |
|---|---:|
| Finance | 29 |
| Biomedical | 27 |
| Scientific | 27 |
| ECommerce | 25 |
| Generic | 13 |

| Difficulty | Tasks |
|---|---:|
| Easy | 40 |
| Medium | 41 |
| Hard | 40 |

任务覆盖的能力包括：

- 描述统计与聚合分析
- 统计推断与假设检验
- 时间序列与预测分析
- 预测建模与模型评估
- 异常、风险与决策分析
- 数据质量与鲁棒性处理
- 专业领域分析方法

目前代码层面已支持新的 taxonomy schema：

- `primary_task_type`
- `secondary_task_types`
- `challenge_dimensions`
- `tags`

这使 benchmark 不再把综合型 data science workflow 强行归为单一任务，而是能同时分析主任务、辅助步骤和横向挑战维度。

### 3.2 已完成的 evaluation 框架

项目已具备可运行的 agent evaluation pipeline：

- `BenchmarkExecutor`：运行 agent，记录 tool calls、执行结果和 final answer。
- `DeterministicEvaluator`：数值答案匹配，支持 alternative ground truth。
- `ProcessAuditor`：评估工具使用、过程质量、错误恢复和冗余行为。
- `RiskAssessor`：检查危险命令、资源使用和安全合规。
- `TraceGroundingVerifier`：验证 agent 声明过程是否有工具日志支撑。
- `Composite Agent Score (CAS)`：综合 result accuracy、process quality、safety score。

当前 CAS 公式：

```text
CAS = 0.40 * result_accuracy
    + 0.35 * process_quality
    + 0.25 * safety_score
```

近期也已加入 component-level accuracy 设计，便于诊断综合型任务中的具体失败环节：

| Component | 含义 |
|---|---|
| `data_selection` | 是否选对列、过滤条件、分组对象 |
| `preprocessing` | 是否正确处理缺失、异常、类型转换 |
| `method_selection` | 是否选对统计方法或模型 |
| `numerical_result` | 最终数值是否接近 ground truth |
| `interpretation` | 结论解释是否与结果一致 |
| `output_format` | 是否按要求输出结构化答案 |

### 3.3 已有 baseline 结果

目前已有 **GPT-4o-mini 在 121 个 clean tasks 上的全量结果**。

| Metric | Mean | Median | Min | Max |
|---|---:|---:|---:|---:|
| Completion Rate | 0.7005 | 0.7015 | 0.1069 | 1.0000 |
| Result Accuracy | 0.3901 | 0.4056 | 0.0021 | 1.0000 |
| Process Quality | 0.3862 | 0.3783 | 0.0952 | 0.8333 |
| Safety Score | 0.9008 | 1.0000 | 0.7000 | 1.0000 |
| Total Tokens | 15303.25 | 16117 | 414 | 73128 |
| Cost USD | 0.0042 | 0.0035 | 0.0000 | 0.0316 |

初步现象：

- agent 经常能完成部分流程，但 final result accuracy 和 process quality 仍明显不足。
- safety score 较高，说明当前主要瓶颈不是危险操作，而是分析正确性、过程纪律和鲁棒性。
- Easy/Medium/Hard 之间已有一定区分度，但还需要更细的 task-type 和 challenge-dimension 分析。

### 3.4 Running Example 已确定

当前选定 `DS_TASK_054` 作为贯穿全文的 Running Example。

| 字段 | 内容 |
|---|---|
| Domain | Finance |
| Difficulty | Easy |
| Primary Task Type | Time-Series & Forecasting / 时间序列与预测分析 |
| Secondary Task Types | 描述统计与聚合分析；数据质量与鲁棒性处理 |
| Challenge Dimensions | heteroskedasticity, outlier handling, semantic perturbation |
| Ground Truth | `average_price = 104.56994551077256` |
| Clean Columns | `Date`, `Price`, `TradeVolume` |
| L1 Mapping | `Date -> var_d36f`, `Price -> var_fbca`, `TradeVolume -> var_69e1` |

该例子适合放在 Figure 1 中展示 clean/L1/L2/L3 四级变化，并回到 case study 说明 agent 为什么在语义扰动下失效。

---

## 4. 当前与 SIGMOD 可投版本的差距

### 4.1 论文主线还需要进一步 SIGMOD 化

当前叙事仍容易被理解为“LLM agent benchmark”。SIGMOD 版本需要强调：

- 数据生命周期中的 agent reliability。
- schema semantics 和 metadata perturbation 对分析正确性的影响。
- data quality traps 下的 workflow robustness。
- benchmark construction pipeline 的可复现性和可扩展性。
- 对 database/data management 社区的实证 insight。

建议论文 working title：

> DataAgentBench: Benchmarking Data Agents for Reliable Analytical Workflows under Semantic Perturbations: [Experiments & Analysis]

### 4.2 多模型、多扰动实验不足

目前已有 GPT-4o-mini clean 全量结果，但 SIGMOD 需要更系统的实验闭环。至少需要：

- GPT-4o-mini, GPT-4o, Claude/Gemini/Qwen 中至少 3 个模型。
- Clean, L1, L2, L3 四种条件。
- paired clean-vs-perturbed delta 分析。
- domain × difficulty × task-type 细粒度结果。
- failure taxonomy 和 case studies。

最小可投实验矩阵建议：

| Scope | Model Count | Task Count | Conditions | Runs |
|---|---:|---:|---:|---:|
| R3 minimum | 3 | 60 core tasks | Clean/L1/L2/L3 | 720 |
| R3 preferred | 3 | 121 tasks | Clean/L1/L2/L3 | 1452 |
| R4 strong | 4 | 121 tasks | Clean/L1/L2/L3 | 1936 |

### 4.3 Benchmark construction 需要可发表化

SIGMOD benchmark/dataset paper 不能只给结果，还要解释 benchmark 如何构建。需要补齐：

- Design goals：realism, verifiability, robustness, process-awareness, reproducibility。
- Construction pipeline：seed datasets、task generation、ground-truth verification、perturbation generation、quality control。
- Data quality and validation：自动校验、人工抽样审核、GT 可靠性、多解平权。
- Dataset statistics：domain、difficulty、task type、challenge dimension、数据规模分布。
- Complete task example：task.json、dataset snippet、expected_output.json、trace/report。

### 4.4 Artifact 需要按匿名审稿整理

需要准备 anonymous artifact repository，至少包含：

- 任务子集和完整 metadata。
- 运行脚本和 quick-start。
- scoring scripts。
- statistics/table generation scripts。
- subset reproduction。
- model/version/config 记录。
- 数据来源说明、license、ethics/reproducibility note。

若 R3 投稿，artifact 必须在 2026-07-17 前已经能被 reviewer 运行一个 small subset。

---

## 5. 论文结构规划

12 页主文建议分配：

| Section | Pages | 内容 |
|---|---:|---|
| Abstract + Introduction | 1.5 | 问题、gap、running example、贡献 |
| Related Work | 1.0 | agent benchmark、data benchmark、robustness evaluation |
| Benchmark Design | 2.0 | taxonomy、task format、design goals、running example |
| Construction Pipeline | 1.5 | task generation、GT validation、semantic perturbations |
| Evaluation Protocol | 1.5 | accuracy、component accuracy、process quality、safety、CAS |
| Experiments | 2.5 | baselines、overall、robustness、fine-grained |
| Analysis and Case Studies | 1.0 | error taxonomy、case studies、findings |
| Limitations and Conclusion | 1.0 | scope、bias、artifact、future research |

核心图表规划：

| 编号 | 内容 | 状态 |
|---|---|---|
| Figure 1 | Running Example: Clean/L1/L2/L3 | 待画 |
| Figure 2 | Benchmark construction and evaluation pipeline | 待画 |
| Figure 3 | Overall performance by model | 待实验 |
| Figure 4 | Domain/difficulty/task-type analysis | 待分析 |
| Figure 5 | Semantic perturbation robustness delta | 待实验 |
| Table 1 | Related benchmark comparison | 待补真实 related work |
| Table 2 | Dataset/task statistics | 可快速生成 |
| Table 3 | Overall model performance | 需多模型实验 |
| Table 4 | Task taxonomy/challenge distribution | 需全量 annotation |
| Table 5 | Component accuracy and failure taxonomy | 需 component scoring 与 trace 分析 |

---

## 6. 面向 R3 的 8 周计划

### Week 1: 2026-05-18 至 2026-05-24

目标：冻结 SIGMOD 叙事和最小可投范围。

- 完成 Introduction v1。
- 完成 Figure 1 Running Example。
- 完成 Table 1 related benchmark comparison 初稿。
- 运行 taxonomy dry run，人工审核低置信任务。
- 生成 Table 2 task statistics。
- 确认模型列表和预算。

交付物：

- 4 页组会版 mini draft。
- Figure 1 草图。
- Table 1/2 初稿。
- 实验矩阵和成本估计。

### Week 2: 2026-05-25 至 2026-05-31

目标：把 clean/L1/L2/L3 pipeline 跑通。

- 固化 L1/L2/L3 perturbation 生成规则。
- 选出 60 个 core tasks。
- 在 10 到 20 个任务上跑 pilot。
- 修复 perturbation 后 GT、评分和 task statement 的一致性问题。
- 生成 robustness pilot 结果。

交付物：

- Perturbation protocol 文档。
- 20-task pilot robustness 表。
- 2 个 failure case 初稿。

### Week 3: 2026-06-01 至 2026-06-07

目标：启动主实验和 benchmark construction 章节。

- 跑 GPT-4o-mini 和 GPT-4o 在 60 core tasks 上的 Clean/L1/L2/L3。
- 确定第三个模型，建议 Claude/Gemini/Qwen 三选一。
- 写 Benchmark Design 和 Construction Pipeline 初稿。
- 生成 Figure 2。

交付物：

- 2 模型 × 60 任务 × 4 条件初步结果。
- Section 3/4 初稿。
- Figure 2 草图。

### Week 4: 2026-06-08 至 2026-06-14

目标：补齐第三模型和细粒度分析。

- 跑第三个模型。
- 生成 domain × difficulty、task-type、challenge-dimension 结果。
- 计算 clean vs L1/L2/L3 paired delta。
- 做 Wilcoxon signed-rank test 和 effect size。
- 开始 failure taxonomy 标注。

交付物：

- Overall performance table。
- Robustness delta figure。
- 初版 Findings。

### Week 5: 2026-06-15 至 2026-06-21

目标：完成实验章节主体。

- 写 Experiments、Fine-grained Analysis、Case Studies。
- 完成 2 到 3 个 case study。
- 完成 error taxonomy。
- 对 component accuracy 做诊断分析。

交付物：

- 8 到 10 页论文初稿。
- Figure 3/4/5 初稿。
- Table 3/4/5 初稿。

### Week 6: 2026-06-22 至 2026-06-28

目标：完成 artifact 和可复现性材料。

- 建 anonymous artifact repo。
- 准备 quick-start subset。
- 准备 task statistics 和 evaluation reproduction scripts。
- 写 limitations、ethics、reproducibility。
- 统一模型版本、随机种子、运行日期。

交付物：

- 可运行 artifact v0。
- 论文完整初稿。
- 附录材料。

### Week 7: 2026-06-29 至 2026-07-05

目标：内部审稿和补实验。

- 根据导师反馈修改主线。
- 补缺失 baseline 或 sensitivity study。
- 压缩到 12 页。
- 检查匿名性和格式。

交付物：

- Submission candidate v1。
- 匿名 artifact candidate。

### Week 8: 2026-07-06 至 2026-07-17

目标：完成 SIGMOD R3 投稿。

- 2026-07-10 前提交 abstract 和 COI。
- 2026-07-17 前提交全文。
- 完成匿名 artifact link。
- 检查 PDF 10 MB、ACM two-column、12 页限制、double-anonymous。

---

## 7. R4 保底规划

如果 R3 前出现以下情况，建议主动转 R4：

- 多模型实验不足 3 个模型。
- L1/L2/L3 只完成小样本 pilot，无法支撑主结论。
- Artifact 还不能匿名复现。
- 论文仍像 LLM benchmark，而不是 SIGMOD data management benchmark。

R4 的优势：

- 可以跑满 4 模型 × 121 任务 × 4 条件。
- 可以加入 open-source agent/model 作为更有说服力的 baseline。
- 可以系统做人工 GT validation 和 inter-annotator checks。
- 可以把 component accuracy 和 taxonomy annotation 做扎实。
- 可以补更强 related work 和 database relevance 论证。

R4 时间点：

- Abstract/COI: 2026-10-10
- Paper: 2026-10-17

---

## 8. 当前风险与应对

| 风险 | 影响 | 应对 |
|---|---|---|
| SIGMOD scope 不够明确 | 可能 desk reject 或低分 | 强调 data lifecycle、metadata、data quality、workflow reliability |
| 只像 LLM benchmark | 创新点被认为不属于 DB | 把贡献写成 benchmark workload、evaluation protocol、data semantics robustness |
| 扰动真实性不足 | L1/L2/L3 可能被质疑人为 | 给出设计原则、真实数据质量问题映射、case studies |
| GT 自动生成被质疑 | reviewer 不信评分 | 增加人工抽样审核、多解平权、验证脚本 |
| Process quality 主观 | CAS 权重被质疑 | 主表报告单项指标，CAS 作为综合摘要；做 sensitivity analysis |
| Artifact 不完善 | benchmark paper 说服力下降 | 优先保证 subset reproduction 和匿名 repo |
| 时间过紧 | R3 质量不足 | 设置 R3/R4 双路线，R3 冲刺但不牺牲质量底线 |

---

## 9. 希望导师拍板的问题

1. **投稿窗口**：是否以 SIGMOD 2027 R3 为正式目标，还是 R3 做 internal deadline、R4 做正式投稿？
2. **论文类型**：是否确认走 E&A / Benchmarks and Datasets，而不是 Regular Research 或 DI&DS Application？
3. **实验规模**：R3 最小实验矩阵是否接受 3 models × 60 core tasks × 4 conditions，还是必须全量 121 tasks？
4. **模型选择**：第三个 baseline 优先 Claude、Gemini、Qwen，还是必须包含 open-source agent/model？
5. **评分口径**：CAS 是否作为主指标，还是主表只报 result accuracy、process quality、safety，CAS 放辅助？
6. **人工审核**：GT validation 和 failure taxonomy 需要多少人工抽样比例才足够有说服力？
7. **Related work**：希望老师建议 5 到 8 篇最应该对标的 SIGMOD/VLDB/ICDE 或 agent benchmark 工作。

---

## 10. 下一次组会前的具体交付

建议下一次组会前交付以下材料：

1. **1 页项目摘要**：问题、贡献、当前结果、目标 venue。
2. **Figure 1**：`DS_TASK_054` Clean/L1/L2/L3 Running Example。
3. **Table 1**：与 DS-1000、MLAgentBench、Spider/BIRD、现有 agent benchmark 的对比。
4. **Table 2**：121 tasks 的 domain/difficulty/task-type/challenge statistics。
5. **Pilot robustness result**：20 core tasks 上 clean/L1/L2/L3 的初步 delta。
6. **Introduction v1**：按 SIGMOD 口径写完整，不再停留在模板。
7. **Artifact checklist**：匿名 repo 需要包含什么、哪些已经有、哪些缺失。

---

## 11. 参考信息

- SIGMOD 2027 Call for Research Papers: https://2027.sigmod.org/calls_papers_sigmod_research.shtml
- SIGMOD 2027 Important Dates: R3 abstract/COI 2026-07-10, R3 paper 2026-07-17; R4 abstract/COI 2026-10-10, R4 paper 2026-10-17。

