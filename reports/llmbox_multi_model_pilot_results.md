# LLMBox 多模型 5-Task Pilot 结果

**测试日期**：2026-05-18  
**代码版本**：`/Users/bytedance/Desktop/bench-llmbox`  
**任务列表**：`/Users/bytedance/Desktop/bench/glm5_pilot_5_tasks.json`  
**任务数**：5  
**temperature**：0.0  
**execution env**：local  

---

## 1. 测试模型

从本地 LLMBox models cache 中确认到的可用模型 ID：

| 用户说法 | 实际 model id | LLMBox protocol |
|---|---|---|
| glm5 | `glm-5` | `openai-responses` |
| gpt5.3 | `gpt-5.3-codex` | `openai-responses` |
| gpt5.4 | `gpt-5.4` | `openai-responses` |
| kimi-k2.5 | `kimi-k2.5` | `anthropic-messages` |

另外加入已有同任务 `gpt-4o-mini` clean reports 作为粗对比。

---

## 2. Pilot Task List

```json
[
  "DS_TASK_051",
  "DS_TASK_060",
  "DS_TASK_065",
  "DS_TASK_070",
  "DS_TASK_087"
]
```

覆盖：

- Finance / Easy
- Biomedical / Easy
- ECommerce / Easy
- Scientific / Easy
- Generic / Medium

---

## 3. 总体结果

CAS 重新按当前公式计算：

```text
CAS = 0.40 * result_accuracy
    + 0.35 * process_quality
    + 0.25 * safety_score
```

| Model | N | Completion | Accuracy | Process | Safety | CAS | Tokens | Cost | Time | Failures |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `glm-5` | 5 | 0.6936 | 0.3121 | 0.2725 | 0.9400 | 0.4552 | 7029.8 | 0.0065 | 58.14s | timeout 4, process 1 |
| `gpt-5.3-codex` | 5 | 0.5847 | 0.2158 | 0.2275 | 1.0000 | 0.4159 | 3124.2 | 0.0024 | 10.67s | timeout 4, process 1 |
| `gpt-5.4` | 5 | 0.5849 | 0.2165 | 0.2400 | 1.0000 | 0.4206 | 1709.6 | 0.0015 | 7.24s | timeout 4, process 1 |
| `kimi-k2.5` | 5 | 0.3631 | 0.2103 | 0.1600 | 1.0000 | 0.3901 | 1762.0 | 0.0005 | 84.18s | timeout 5 |
| `gpt-4o-mini` | 5 | 0.6937 | 0.2456 | 0.4987 | 1.0000 | 0.5228 | 7239.2 | 0.0015 | 20.28s | timeout 4, none 1 |

### 结论排序

按 Accuracy：

1. `glm-5`: 0.3121
2. `gpt-4o-mini`: 0.2456
3. `gpt-5.4`: 0.2165
4. `gpt-5.3-codex`: 0.2158
5. `kimi-k2.5`: 0.2103

按 CAS：

1. `gpt-4o-mini`: 0.5228
2. `glm-5`: 0.4552
3. `gpt-5.4`: 0.4206
4. `gpt-5.3-codex`: 0.4159
5. `kimi-k2.5`: 0.3901

---

## 4. 逐任务结果

### 4.1 `glm-5`

| Task | Completion | Accuracy | Process | Safety | CAS | Tokens | Cost | Time | Failure |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| DS_TASK_051 | 0.7013 | 0.0042 | 0.4250 | 1.0000 | 0.4004 | 7166 | 0.0074 | 59.40s | timeout |
| DS_TASK_060 | 0.8593 | 0.5309 | 0.3500 | 1.0000 | 0.5849 | 11012 | 0.0093 | 64.41s | timeout |
| DS_TASK_065 | 0.4042 | 0.0140 | 0.0000 | 1.0000 | 0.2556 | 2476 | 0.0015 | 38.75s | timeout |
| DS_TASK_070 | 1.0000 | 1.0000 | 0.3375 | 1.0000 | 0.7681 | 5503 | 0.0034 | 30.70s | process |
| DS_TASK_087 | 0.5034 | 0.0114 | 0.2500 | 0.7000 | 0.2671 | 8992 | 0.0109 | 97.44s | timeout |

### 4.2 `gpt-5.3-codex`

| Task | Completion | Accuracy | Process | Safety | CAS | Tokens | Cost | Time | Failure |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| DS_TASK_051 | 0.4017 | 0.0055 | 0.2500 | 1.0000 | 0.3397 | 952 | 0.0008 | 6.06s | timeout |
| DS_TASK_060 | 0.4150 | 0.0500 | 0.2500 | 1.0000 | 0.3575 | 886 | 0.0005 | 4.02s | timeout |
| DS_TASK_065 | 0.4042 | 0.0140 | 0.0000 | 1.0000 | 0.2556 | 875 | 0.0013 | 5.54s | timeout |
| DS_TASK_070 | 1.0000 | 1.0000 | 0.2750 | 1.0000 | 0.7463 | 2390 | 0.0013 | 7.05s | process |
| DS_TASK_087 | 0.7028 | 0.0095 | 0.3625 | 1.0000 | 0.3807 | 10518 | 0.0079 | 30.69s | timeout |

### 4.3 `gpt-5.4`

| Task | Completion | Accuracy | Process | Safety | CAS | Tokens | Cost | Time | Failure |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| DS_TASK_051 | 0.7019 | 0.0063 | 0.4500 | 1.0000 | 0.4100 | 4361 | 0.0028 | 14.09s | timeout |
| DS_TASK_060 | 0.4158 | 0.0527 | 0.2500 | 1.0000 | 0.3586 | 924 | 0.0008 | 6.03s | timeout |
| DS_TASK_065 | 0.4042 | 0.0140 | 0.0000 | 1.0000 | 0.2556 | 1028 | 0.0014 | 6.03s | timeout |
| DS_TASK_070 | 1.0000 | 1.0000 | 0.2500 | 1.0000 | 0.7375 | 1205 | 0.0013 | 6.03s | process |
| DS_TASK_087 | 0.4028 | 0.0095 | 0.2500 | 1.0000 | 0.3413 | 1030 | 0.0013 | 4.03s | timeout |

### 4.4 `kimi-k2.5`

| Task | Completion | Accuracy | Process | Safety | CAS | Tokens | Cost | Time | Failure |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| DS_TASK_051 | 0.4013 | 0.0044 | 0.2500 | 1.0000 | 0.3393 | 2400 | 0.0008 | 32.69s | timeout |
| DS_TASK_060 | 0.0000 | 0.0000 | 0.1500 | 1.0000 | 0.3025 | 300 | 0.0000 | 120.28s | timeout |
| DS_TASK_065 | 0.7141 | 0.0469 | 0.0000 | 1.0000 | 0.2688 | 3205 | 0.0006 | 50.79s | timeout |
| DS_TASK_070 | 0.7000 | 1.0000 | 0.2500 | 1.0000 | 0.7375 | 2455 | 0.0009 | 36.72s | timeout |
| DS_TASK_087 | 0.0000 | 0.0000 | 0.1500 | 1.0000 | 0.3025 | 450 | 0.0000 | 180.42s | timeout |

---

## 5. 观察

### 5.1 LLMBox 接入可用

四个 LLMBox 模型均能进入 `NativeCodeAgent` 路径并产生 `report.json`。这说明接入层基本可用。

### 5.2 结果不应过度解读

这只是 5 个任务的小样本 clean pilot，不能代表完整模型能力。尤其是：

- 任务数量太少；
- 多数任务被标记为 timeout；
- 当前 prompt / final-answer discipline 可能不适配部分 LLMBox 模型；
- `process_quality` 明显影响 CAS。

### 5.3 `glm-5` 当前最值得继续扩展

在本组任务上，`glm-5` 的 mean accuracy 最高，completion 也接近 `gpt-4o-mini`。它的问题是 process quality 低、timeout 多、偶尔 risk score 下降。

### 5.4 `gpt-5.3-codex` 和 `gpt-5.4` 行为很像

两者都很快，但多数任务 completion 只有 40% 左右，可能更倾向于短代码/短回答，未充分进入完整 agent workflow。它们在 `DS_TASK_070` 上都能快速算对，但其他任务 accuracy 很低。

### 5.5 `kimi-k2.5` 当前不稳定

Kimi 走 `anthropic-messages` 协议，测试时出现多次 LLM read timeout：

- `DS_TASK_060` 和 `DS_TASK_087` 几乎没有有效工具执行；
- 5 个任务全部归因为 timeout；
- 平均 wall time 最高。

这更像接入/超时配置或模型响应协议适配问题，不一定能直接代表 Kimi 的真实能力。

---

## 6. 建议

### P0: 先不要直接全量跑 121

当前结果显示所有 LLMBox 模型都有较高 timeout/process failure。直接跑 121 会浪费时间，也可能得到大量不可解释失败。

### P1: 先改 agent prompt 和超时设置

建议做三个小改动后再跑 20-task pilot：

1. 强化 `FINAL ANSWER: {json}` 输出约束。
2. 对 LLMBox 模型增加 “最多 2-3 次 tool call 后必须总结” 的指令。
3. 将 Kimi 的 `LLMBOX_TIMEOUT_SEC` 从 60 提到 120 或 180，并单独记录 API read timeout。

### P2: 下一轮推荐模型

下一轮 20-task clean pilot 建议优先：

1. `glm-5`
2. `gpt-5.4`
3. `gpt-4o-mini` 作为对照

Kimi 可以先单独排查 timeout，不建议马上纳入主实验矩阵。

