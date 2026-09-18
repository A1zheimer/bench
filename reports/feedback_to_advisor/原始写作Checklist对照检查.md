# DataAgentBench 原始写作 Checklist 对照检查

**检查依据**：最初截图中的论文构思 checklist：Background / Why / Problem、Running Example、What、How、So What，以及实验闭环要求。  
**当前判断**：项目已经从“论文包装模板”推进到“DataAgentBench benchmark/evaluation paper 初版方案”，但目前仍处在 **paper story + framework prototype + single-model clean baseline** 阶段，距离 SIGMOD 可投版本还缺完整实验闭环和 artifact 证明。

---

## 1. 总体结论

已经做得比较扎实的是：

- 明确了论文方向：Data Science / Data Engineering Agents 的 Benchmark/Evaluation Paper。
- 明确了目标 venue 口径：SIGMOD E&A / Benchmarks and Datasets。
- 已有 121 个任务、5 个领域、3 个难度等级。
- 已有 GPT-4o-mini clean setting 的 121 个全量结果。
- 已经提出 clean/L1/L2/L3 semantic perturbation 的核心主线。
- 已经完成 task taxonomy 和 hierarchical/component accuracy 的框架设计与部分代码支持。
- 已经选定 `DS_TASK_054` 作为 Running Example。

做得还不够好的地方：

- 目前故事已经成型，但“证据链”不够完整：多模型、多扰动、统计显著性、case study 都还没补齐。
- SIGMOD 口味还需要更强：不能只像 LLM benchmark，要更强调 data lifecycle、schema semantics、metadata robustness、data quality、workflow reliability。
- Benchmark construction 讲得还不够细：任务怎么生成、真值怎么验证、扰动怎么构造、质量怎么控制，需要可发表化。
- 当前结果主要是 GPT-4o-mini clean baseline，还不能支撑“semantic perturbation robustness”这一主贡献。

---

## 2. 对照最初 Checklist 的完成情况

| Checklist 要点 | 当前已做 | 做得不够好的地方 | 优先级 |
|---|---|---|---|
| Background / Why / Problem | 已明确研究对象是 data agents as end-to-end analytical workflow executors；已写出 problem formulation；已总结 final-answer-only、semantic shortcut、缺 paired robustness 三个 gap | 还缺真实应用场景的强叙事；related work 尚未具体化；gap 目前偏“主张”，缺现有 benchmark 对比证据；problem formulation 还没有形式化定义 | P0 |
| Running Example | 已选 `DS_TASK_054`；已有 clean columns、L1 mapping、ground truth、taxonomy、challenge dimensions | Figure 1 还没画；L2/L3 具体样例还没落到数据和问题文本；还没展示 agent 在 clean 成功但 perturbed 失败的真实 trace | P0 |
| What：别人干不了什么，你能干什么 | 已定义评估对象：端到端 data agent；已定义核心能力：accuracy、process quality、robustness、safety/cost；已设计 7 类任务 taxonomy | 技术挑战还需要更尖锐：schema semantics reliance、dirty data handling、process observability、paired robustness；与现有 benchmark 的差异还需要真实 Table 1 支撑 | P0 |
| How：具体怎么做 | 已有 121 tasks、evaluation pipeline、CAS、component accuracy schema、taxonomy script、schema validator 改动 | Construction pipeline 没有写成论文级；GT validation、人工审核、扰动生成、质量控制、数据统计还不完整；Figure 2 还没画 | P0/P1 |
| So What：做了有什么发现 | 已有 GPT-4o-mini clean baseline：completion 0.7005、accuracy 0.3901、process 0.3862、safety 0.9008 | 只有 clean baseline，不能支撑鲁棒性 finding；还缺 clean vs L1/L2/L3 delta、多模型对比、failure taxonomy、case studies、统计检验 | P1 |
| Experiments 闭环 | 已有单模型 121 clean reports；已有指标体系和 report 格式 | 缺至少 3 个 baseline；缺 perturbation 实验；缺 domain × difficulty × task-type 分析；缺消融/敏感性；缺人工或自动 error taxonomy | P1 |
| Contributions | 已整理 4 点贡献：benchmark、process-aware evaluation、semantic perturbation、empirical analysis | 贡献还需要从“想法”变成“结果支撑”；第 4 点 empirical analysis 目前证据不足；component accuracy 还没有成为实验结果 | P0/P1 |
| Artifact / Reproducibility | repo 中已有任务、代码、reports、README；已有 schema 和 scripts 雏形 | 还未整理匿名 artifact；缺 quick-start subset；缺一键复现 tables/figures；缺 model version、seed、cost card、dataset card | P2 |

---

## 3. Background / Why / Problem 检查

### 已经完成

目前已经能回答“这篇论文要干什么”：

> We study the problem of evaluating whether data science agents can reliably complete realistic analytical workflows under semantic perturbations, considering not only final-answer accuracy but also process quality, safety, cost, and robustness.

当前背景主线也比较清楚：

- 真实数据分析工作流不只是回答问题，还包括读数据、理解 schema、写代码、执行代码、处理异常、修复错误、报告结论。
- 现有 LLM/agent benchmark 往往偏 final answer 或通用推理。
- DataAgentBench 评估的是完整 data agent 系统，而不是裸 LLM。

### 不够好的地方

这一部分还需要更像 SIGMOD 论文，而不是泛 AI benchmark：

- 要把问题落到 **data management lifecycle**：数据读取、schema semantics、metadata、data quality、workflow execution、reproducibility。
- 要说明为什么这是 database/data management 社区的问题，而不是纯 NLP/LLM 问题。
- 要加入真实场景，例如：
  - 企业分析师用 agent 跑经营报表；
  - 数据工程师让 agent 检查脏数据和异常；
  - BI/analytics workflow 中 agent 自动生成分析脚本；
  - schema 不透明或 metadata 缺失时 agent 容易误解字段。
- 要把 gap 和 related benchmark 一一对齐，不能只写“现有工作不足”。

### 下一步

- 写 Introduction v1。
- 完成 Table 1：DataAgentBench vs DS-1000 / MLAgentBench / Spider / BIRD / generic agent benchmarks / data analysis benchmarks。
- 把三个 gap 改成有证据支撑的版本。

---

## 4. Running Example 检查

### 已经完成

已经选定 `DS_TASK_054`：

- Domain: Finance
- Difficulty: Easy
- Clean columns: `Date`, `Price`, `TradeVolume`
- Ground truth: `average_price = 104.56994551077256`
- L1 mapping:
  - `Date -> var_d36f`
  - `Price -> var_fbca`
  - `TradeVolume -> var_69e1`
- Primary task type: 时间序列与预测分析
- Secondary task types: 描述统计与聚合分析；数据质量与鲁棒性处理
- Challenge dimensions: heteroskedasticity, outlier handling, semantic perturbation

这个例子能贯穿全文：

- Introduction：展示为什么 column semantics 会影响 agent。
- Benchmark Design：解释 clean/L1/L2/L3。
- Evaluation：展示 accuracy、process quality、safety、cost。
- Case Study：展示 agent 为什么失败。

### 不够好的地方

当前 Running Example 还只是“文字设定”，没有成为论文里的强视觉锚点：

- Figure 1 还没画。
- L2 统计陷阱还没有具体化到 dataset diff。
- L3 去语义化 problem statement 还没有最终版本。
- 还没有真实 agent behavior 对比：clean 下怎么做、L1/L2/L3 下具体错在哪里。
- 这个例子是 Easy task，作为主例子可以，但最好再补一个 Medium/Hard case study，避免 reviewer 觉得例子太简单。

### 下一步

- 画 Figure 1：Clean / L1 / L2 / L3 四栏。
- 加入一条真实 trace 摘要：agent 在 clean 里识别 `Price`，在 obfuscated setting 中误选列或错误处理 outlier。
- 另选 2 个 case studies：一个 ECommerce，一个 Biomedical/Scientific Medium 或 Hard。

---

## 5. What 检查

### 已经完成

目前已经说明 DataAgentBench 评估的不是简单问答，而是完整 data agent：

- analytical correctness
- workflow execution quality
- robustness under semantic perturbation
- safety and cost discipline

也已经把任务类型从“单一 task type”改成：

- `primary_task_type`
- `secondary_task_types`
- `challenge_dimensions`
- `tags`

这点是对最初 checklist 的一个重要增强，因为真实 data science workflow 往往是综合型任务。

### 不够好的地方

What 部分还需要更尖锐地回答“别人为什么干不了”：

- 现有 benchmark 为什么不能评估 process quality？
- 现有 benchmark 为什么不能判断 agent 是理解数据还是依赖 column names？
- 现有 benchmark 为什么缺 matched clean-vs-perturbed pair？
- DataAgentBench 的核心评估对象到底是“data agent reliability”还是“semantic robustness”？两者需要主次更清晰。

此外，accuracy 体系虽然改进了，但还需要在论文里讲清楚：

- Leaderboard 用 overall result accuracy 和 CAS。
- Fine-grained analysis 用 component accuracy。
- Robustness 用 clean vs L1/L2/L3 paired delta。
- Task-type analysis 用 taxonomy aggregation。

### 下一步

- 在论文里单独写 Evaluation Dimensions。
- 明确主指标和辅助指标，避免 reviewer 质疑 CAS 权重主观。
- 主文中报告单项指标，CAS 作为综合摘要或 appendix sensitivity。

---

## 6. How 检查

### 已经完成

工程上已有比较多基础：

- 121 个任务。
- 任务目录结构：`task.json`、`dataset.csv`、`expected_output.json`。
- evaluation pipeline。
- report.json。
- taxonomy schema。
- component scoring schema。
- deterministic scoring、process audit、risk assessment。
- GPT-4o-mini clean baseline reports。

已经可以形成 4 个贡献点：

1. DataAgentBench task suite。
2. Process-aware evaluation protocol。
3. Semantic perturbation robustness testing。
4. Empirical analysis of data agent failures。

### 不够好的地方

How 部分最大问题是“论文级方法描述不够完整”：

- Task construction pipeline 还没有完整 Figure 2。
- Seed dataset 来源、任务生成策略、真值生成方式没有系统描述。
- 自动校验和人工审核方案没有落地。
- 121 个任务的 taxonomy annotation 还没全量写入任务文件，目前只有 Running Example 明确落地。
- component accuracy 代码有了，但旧任务大多还没有 components 标注。
- L2/L3 perturbation 还需要稳定、可复现、可解释。

### 下一步

- 写 Benchmark Construction section。
- 生成 dataset/task statistics。
- 完成 121 tasks taxonomy annotation。
- 先给 20 到 30 个核心任务补 component labels，支撑 fine-grained analysis。
- 做 artifact quick-start。

---

## 7. So What 检查

### 已经完成

已有一个初步 empirical signal：

- GPT-4o-mini 在 121 个 clean tasks 上：
  - completion rate mean: 0.7005
  - result accuracy mean: 0.3901
  - process quality mean: 0.3862
  - safety score mean: 0.9008

这可以初步支持：

- agent 能做部分流程，但不够可靠。
- final correctness 和 process quality 都有明显提升空间。
- safety 不是当前主要瓶颈。

### 不够好的地方

So What 目前还没有形成实验闭环：

- 没有多模型对比，所以不能说“current data agents”的普遍现象。
- 没有 L1/L2/L3 结果，所以不能支撑“semantic perturbation robustness”主论点。
- 没有 paired delta，所以不能证明扰动导致性能下降。
- 没有 statistical test，所以 SIGMOD 审稿人可能认为只是 anecdotal。
- 没有 error taxonomy，所以还不能解释“为什么错”。
- 没有 case study，所以 findings 缺直观证据。

### 下一步

最少补齐：

- 3 models × 60 core tasks × Clean/L1/L2/L3。
- paired clean-vs-perturbed delta。
- domain × difficulty × task-type 分析。
- 2 到 3 个 case studies。
- failure taxonomy。
- Wilcoxon signed-rank test + effect size。

---

## 8. 按最初图片的实验要求逐项检查

| 实验要求 | 当前状态 | 评价 |
|---|---|---|
| Overall Performance | 只有 GPT-4o-mini clean 全量 | 不够，需要多模型 |
| 至少 3 个代表性数据集/任务组 | 有 5 domains 和 121 tasks | 数量够，但统计表还需生成 |
| 与强 baseline 公平对比 | 未完成 | 缺 GPT-4o、Claude/Gemini/Qwen |
| Ablation Study | 未完成 | 可做 CAS 权重、component removal、perturbation level 对比 |
| In-depth Analysis | 部分具备数据基础 | 还缺 task-type/challenge/component 分析 |
| Case Study | 已选 DS_TASK_054 | 还缺图和真实失败案例 |
| Provide Insights | 只有预期 findings | 还缺实验结果支撑 |
| Motivation 与实验闭环对应 | 设计上对应 | 证据还不够完整 |

---

## 9. 当前最应该补的 10 件事

1. 完成 Figure 1：`DS_TASK_054` Clean/L1/L2/L3。
2. 写 Introduction v1。
3. 完成 Table 1：related benchmark comparison。
4. 生成 Table 2：domain/difficulty/task-type/challenge statistics。
5. 全量或半自动完成 121 tasks taxonomy annotation。
6. 固化 L1/L2/L3 perturbation protocol。
7. 选 60 个 core tasks 跑 3-model pilot。
8. 做 clean vs L1/L2/L3 paired delta。
9. 标注 2 到 3 个 case studies。
10. 整理 anonymous artifact checklist 和 quick-start subset。

---

## 10. 给导师的简短说法

目前项目已经完成了 benchmark paper 的骨架：任务库、评测框架、初步结果和论文主线都有了；但还没有完成 SIGMOD 最看重的“实验证据闭环”。下一阶段不应该继续扩写模板，而应该集中补三类东西：

1. **实验闭环**：多模型 + clean/L1/L2/L3 + paired robustness。
2. **benchmark 可信度**：construction pipeline + GT validation + artifact。
3. **SIGMOD 叙事**：把问题包装成 data management workflow reliability，而不是泛 LLM benchmark。

如果 6 月中旬前能拿到 3 个模型、60 个核心任务、4 个扰动条件的稳定结果，SIGMOD R3 可以尝试；如果实验或 artifact 不够完整，则建议把 R3 当 internal deadline，正式冲 SIGMOD R4。

