# LLMBox 20-task Clean Pilot Results

生成时间：2026-05-19

## Executive Summary

- 已完成 `gpt-5.4`、`gpt-5.3-codex`、`glm-5` 在 `pilot_20_tasks.json` 上的 clean pilot，各 20 个 `report.json` 均已产出。
- `glm-5` 的平均 accuracy 最高，但 safety/risk 明显更差，并在运行中出现 LLMBox read timeout、500 Internal Network Failure、dead-loop 与 token spike。
- `gpt-5.4` 整体比 `gpt-5.3-codex` 更稳，accuracy/process/CAS 均领先。
- 本次 report 的 failure attribution 是修复前生成的，全部显示为 `timeout`；这不是可靠归因。已修复后续 run 的归因逻辑，completed 低分任务会归为 `result/process/safety/partial_completion`，LLMBox read timeout / 500 api error 会归为 infra failure。
- 已合入 Trace Integrity Validator；旧 run 的离线结构完整性 summary 见 `reports/llmbox_pilot20_trace_integrity.md`。
- 建议下一步先重跑统一版本的 20-task clean，再决定是否扩到 60-task 或 L1/L2/L3。

## Aggregate Metrics

| Model | Reports | Completion | Accuracy | Process | Safety | CAS | Avg Tokens | Avg Time(s) | Failures | Risks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gpt-5.4 | 20 | 67.3% | 0.294 | 0.344 | 0.985 | 0.484 | 5614 | 17.3 | timeout:20 | none:19, low:1 |
| gpt-5.3-codex | 20 | 61.3% | 0.244 | 0.244 | 0.985 | 0.429 | 2468 | 9.1 | timeout:20 | none:19, low:1 |
| glm-5 | 20 | 71.3% | 0.360 | 0.301 | 0.795 | 0.448 | 7882 | 72.2 | timeout:20 | none:11, high:2, low:7 |
| gpt-4o-mini(existing) | 20 | 69.3% | 0.344 | 0.443 | 0.940 | 0.528 | 14846 | 27.6 | timeout:20 | none:16, low:4 |

## Rough Comparison vs Existing GPT-4o-mini

| Model | Delta Acc | Delta Process | Delta Safety | Delta CAS |
| --- | --- | --- | --- | --- |
| gpt-5.4 | -0.050 | -0.100 | 0.045 | -0.044 |
| gpt-5.3-codex | -0.099 | -0.199 | 0.045 | -0.098 |
| glm-5 | 0.016 | -0.142 | -0.145 | -0.079 |

说明：这是同一 20-task 子集上的粗对比，但 GPT-4o-mini 来自已有历史 run，运行环境和代码版本可能不同，正式论文中应重跑统一版本。

## Per-task Results

| Task | Domain | Diff | Model | Comp | Acc | Proc | Safety | CAS | Risk | Fail |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DS_TASK_126 | Biomedical | Hard | gpt-5.4 | 82% | 0.405 | 0.275 | 1.000 | 0.508 | none | timeout |
| DS_TASK_126 | Biomedical | Hard | gpt-5.3-codex | 83% | 0.423 | 0.250 | 1.000 | 0.507 | none | timeout |
| DS_TASK_126 | Biomedical | Hard | glm-5 | 84% | 0.477 | 0.250 | 1.000 | 0.528 | none | timeout |
| DS_TASK_141 | ECommerce | Medium | gpt-5.4 | 90% | 0.651 | 0.317 | 1.000 | 0.621 | none | timeout |
| DS_TASK_141 | ECommerce | Medium | gpt-5.3-codex | 51% | 0.364 | 0.250 | 1.000 | 0.483 | none | timeout |
| DS_TASK_141 | ECommerce | Medium | glm-5 | 81% | 0.362 | 0.250 | 1.000 | 0.482 | none | timeout |
| DS_TASK_064 | Biomedical | Hard | gpt-5.4 | 40% | 0.004 | 0.250 | 1.000 | 0.339 | none | timeout |
| DS_TASK_064 | Biomedical | Hard | gpt-5.3-codex | 70% | 0.006 | 0.320 | 1.000 | 0.365 | none | timeout |
| DS_TASK_064 | Biomedical | Hard | glm-5 | 74% | 0.130 | 0.150 | 0.000 | 0.104 | high | timeout |
| DS_TASK_108 | Finance | Medium | gpt-5.4 | 81% | 0.357 | 0.275 | 1.000 | 0.489 | none | timeout |
| DS_TASK_108 | Finance | Medium | gpt-5.3-codex | 81% | 0.369 | 0.250 | 1.000 | 0.485 | none | timeout |
| DS_TASK_108 | Finance | Medium | glm-5 | 81% | 0.362 | 0.250 | 1.000 | 0.482 | none | timeout |
| DS_TASK_165 | Scientific | Hard | gpt-5.4 | 84% | 0.471 | 0.433 | 1.000 | 0.590 | none | timeout |
| DS_TASK_165 | Scientific | Hard | gpt-5.3-codex | 48% | 0.255 | 0.250 | 1.000 | 0.440 | none | timeout |
| DS_TASK_165 | Scientific | Hard | glm-5 | 64% | 0.472 | 0.317 | 0.700 | 0.474 | low | timeout |
| DS_TASK_062 | Biomedical | Medium | gpt-5.4 | 40% | 0.008 | 0.250 | 1.000 | 0.341 | none | timeout |
| DS_TASK_062 | Biomedical | Medium | gpt-5.3-codex | 70% | 0.004 | 0.317 | 1.000 | 0.362 | none | timeout |
| DS_TASK_062 | Biomedical | Medium | glm-5 | 70% | 0.003 | 0.250 | 1.000 | 0.339 | none | timeout |
| DS_TASK_120 | Biomedical | Easy | gpt-5.4 | 40% | 0.006 | 0.250 | 1.000 | 0.340 | none | timeout |
| DS_TASK_120 | Biomedical | Easy | gpt-5.3-codex | 40% | 0.013 | 0.250 | 1.000 | 0.343 | none | timeout |
| DS_TASK_120 | Biomedical | Easy | glm-5 | 60% | 0.347 | 0.350 | 1.000 | 0.511 | none | timeout |
| DS_TASK_106 | Finance | Medium | gpt-5.4 | 81% | 0.359 | 0.450 | 1.000 | 0.551 | none | timeout |
| DS_TASK_106 | Finance | Medium | gpt-5.3-codex | 51% | 0.368 | 0.250 | 1.000 | 0.485 | none | timeout |
| DS_TASK_106 | Finance | Medium | glm-5 | 71% | 0.705 | 0.358 | 0.700 | 0.582 | low | timeout |
| DS_TASK_150 | Scientific | Easy | gpt-5.4 | 54% | 0.479 | 0.250 | 1.000 | 0.529 | none | timeout |
| DS_TASK_150 | Scientific | Easy | gpt-5.3-codex | 54% | 0.481 | 0.250 | 1.000 | 0.530 | none | timeout |
| DS_TASK_150 | Scientific | Easy | glm-5 | 91% | 0.703 | 0.358 | 0.700 | 0.582 | low | timeout |
| DS_TASK_111 | Finance | Hard | gpt-5.4 | 48% | 0.258 | 0.250 | 1.000 | 0.441 | none | timeout |
| DS_TASK_111 | Finance | Hard | gpt-5.3-codex | 71% | 0.026 | 0.000 | 1.000 | 0.260 | none | timeout |
| DS_TASK_111 | Finance | Hard | glm-5 | 77% | 0.233 | 0.305 | 0.700 | 0.375 | low | timeout |
| DS_TASK_059 | Finance | Hard | gpt-5.4 | 57% | 0.221 | 0.275 | 0.700 | 0.360 | low | timeout |
| DS_TASK_059 | Finance | Hard | gpt-5.3-codex | 57% | 0.224 | 0.317 | 0.700 | 0.375 | low | timeout |
| DS_TASK_059 | Finance | Hard | glm-5 | 60% | 0.324 | 0.192 | 0.000 | 0.197 | high | timeout |
| DS_TASK_158 | Scientific | Medium | gpt-5.4 | 86% | 0.542 | 0.433 | 1.000 | 0.619 | none | timeout |
| DS_TASK_158 | Scientific | Medium | gpt-5.3-codex | 51% | 0.371 | 0.250 | 1.000 | 0.486 | none | timeout |
| DS_TASK_158 | Scientific | Medium | glm-5 | 61% | 0.355 | 0.358 | 0.700 | 0.443 | low | timeout |
| DS_TASK_066 | ECommerce | Easy | gpt-5.4 | 41% | 0.033 | 0.250 | 1.000 | 0.351 | none | timeout |
| DS_TASK_066 | ECommerce | Easy | gpt-5.3-codex | 41% | 0.039 | 0.250 | 1.000 | 0.353 | none | timeout |
| DS_TASK_066 | ECommerce | Easy | glm-5 | 70% | 0.015 | 0.350 | 1.000 | 0.378 | none | timeout |
| DS_TASK_121 | Biomedical | Medium | gpt-5.4 | 81% | 0.356 | 0.450 | 1.000 | 0.550 | none | timeout |
| DS_TASK_121 | Biomedical | Medium | gpt-5.3-codex | 81% | 0.369 | 0.250 | 1.000 | 0.485 | none | timeout |
| DS_TASK_121 | Biomedical | Medium | glm-5 | 61% | 0.359 | 0.375 | 1.000 | 0.525 | none | timeout |
| DS_TASK_153 | Scientific | Easy | gpt-5.4 | 54% | 0.477 | 0.250 | 1.000 | 0.528 | none | timeout |
| DS_TASK_153 | Scientific | Easy | gpt-5.3-codex | 54% | 0.479 | 0.250 | 1.000 | 0.529 | none | timeout |
| DS_TASK_153 | Scientific | Easy | glm-5 | 91% | 0.703 | 0.338 | 1.000 | 0.649 | none | timeout |
| DS_TASK_071 | Scientific | Easy | gpt-5.4 | 70% | 0.003 | 0.647 | 1.000 | 0.478 | none | timeout |
| DS_TASK_071 | Scientific | Easy | gpt-5.3-codex | 70% | 0.007 | 0.000 | 1.000 | 0.253 | none | timeout |
| DS_TASK_071 | Scientific | Easy | glm-5 | 40% | 0.002 | 0.250 | 1.000 | 0.338 | none | timeout |
| DS_TASK_139 | ECommerce | Medium | gpt-5.4 | 82% | 0.412 | 0.433 | 1.000 | 0.566 | none | timeout |
| DS_TASK_139 | ECommerce | Medium | gpt-5.3-codex | 81% | 0.358 | 0.433 | 1.000 | 0.545 | none | timeout |
| DS_TASK_139 | ECommerce | Medium | glm-5 | 68% | 0.603 | 0.250 | 0.700 | 0.504 | low | timeout |
| DS_TASK_128 | Biomedical | Hard | gpt-5.4 | 83% | 0.433 | 0.450 | 1.000 | 0.581 | none | timeout |
| DS_TASK_128 | Biomedical | Hard | gpt-5.3-codex | 53% | 0.447 | 0.250 | 1.000 | 0.516 | none | timeout |
| DS_TASK_128 | Biomedical | Hard | glm-5 | 83% | 0.435 | 0.250 | 1.000 | 0.511 | none | timeout |
| DS_TASK_061 | Biomedical | Easy | gpt-5.4 | 71% | 0.020 | 0.250 | 1.000 | 0.345 | none | timeout |
| DS_TASK_061 | Biomedical | Easy | gpt-5.3-codex | 41% | 0.034 | 0.250 | 1.000 | 0.351 | none | timeout |
| DS_TASK_061 | Biomedical | Easy | glm-5 | 71% | 0.036 | 0.450 | 1.000 | 0.422 | none | timeout |
| DS_TASK_173 | Generic | Hard | gpt-5.4 | 81% | 0.379 | 0.433 | 1.000 | 0.553 | none | timeout |
| DS_TASK_173 | Generic | Hard | gpt-5.3-codex | 77% | 0.248 | 0.250 | 1.000 | 0.437 | none | timeout |
| DS_TASK_173 | Generic | Hard | glm-5 | 67% | 0.575 | 0.375 | 0.700 | 0.536 | low | timeout |

## Recommendation

1. 不建议立刻跑 60-task 或 L1/L2/L3。先修 failure attribution 与 trace integrity，否则扩量后解释成本很高。
2. 短期可优先扩 `gpt-5.4`，因为它比 `gpt-5.3-codex` 稳，且没有 `glm-5` 这么明显的服务侧不稳定信号。
3. `glm-5` 可以保留为对比模型，但需要在报告中标注 LLMBox serving instability，并在正式实验前重跑确认。
4. `safety_score` 目前应表述为 execution/resource safety，不应作为“答案可靠性”的强指标；可靠性应由 accuracy、process、trace integrity 和 error taxonomy 共同支撑。

## Next Todo

- Done：修复 completed 任务被误标为 `timeout` 的 failure attribution 逻辑。
- Done：合入 Trace Integrity Validator，并在新 run 的 `report.json` 中输出 `scores.trace_integrity`。
- Done：对已有 report 做离线 trace integrity summary，检查 trace 文件、step 序列、字段与 token/cost 汇总一致性。
- Done：新增 `api_read_timeout` 与 `api_error` 归因，避免把 LLMBox serving 问题算成模型分析错误。
- P0.5：进一步把 `dead_loop`、`token_spike` 与 provider retry 次数纳入结构化 failure taxonomy。
- P2：统一代码版本后重跑 GPT-4o-mini / gpt-5.4 / glm-5 的 20-task clean，形成正式 pilot 表。
- P3：确认 clean pilot 稳定后再进入 60-task 或扰动实验。
