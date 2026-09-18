# DataAgentBench Validity Repair Implementation

## Status

The validity repair sprint has been implemented in both the main project and the LLMBox-enabled project copy.

Implemented scope:

- Evaluation Protocol V2 with `evaluation_protocol = "v2"`.
- Top-level `raw_agent_output` and `benchmark_extracted_answer` in every new report.
- Deterministic `AnswerExtractor` for final JSON, labeled stdout, and trace-grounded numeric candidates.
- `DeterministicEvaluator` now scores extracted answers first and keeps `raw_field_scores` for old-style extraction comparison.
- `ScorerAudit` flags cases where a trace contains a ground-truth-compatible value that scoring would otherwise miss.
- `ProcessAuditor` is diagnostic-only and no longer heavily penalizes concise one-step successful solutions.
- Failure attribution now separates `primary_failure` from `diagnostic_warnings`.
- Fixed safety rubric is preserved as `execution_safety` and `analytical_safety`.
- `validity_repair_report.py` summarizes raw accuracy, trace-grounded accuracy, scorer audit hit rate, trace integrity, safety, extraction source, and failure taxonomy.

## Local Verification

Unit tests:

```text
/Users/bytedance/Desktop/bench-llmbox: 36 passed
/Users/bytedance/Desktop/bench: targeted validity repair tests passed
```

Local smoke:

```text
simulated agent on glm5_pilot_5_tasks.json: 5 report.json files generated
```

Generated smoke report:

```text
/Users/bytedance/Desktop/bench/reports/validity_repair_simulated_5task.md
```

## Remaining Blocker

The controlled LLMBox rerun is ready but not executed yet because it requires sending local benchmark task content to the LLMBox endpoint. Run it only after explicit approval.

Planned real-model rerun:

```text
native:llmbox/gpt-5.4
native:llmbox/gpt-5.3-codex
native:llmbox/glm-5
```

`gpt-4o-mini` is not listed in the local LLMBox model cache, so it should be rerun through `native:openai/gpt-4o-mini` only if the OpenAI native credentials are available.

## Acceptance Criteria Mapping

- Reports have `benchmark_extracted_answer`: done.
- Reports have `scorer_audit`: done.
- Reports have `trace_integrity`: done.
- Reports expose `execution_safety` and `analytical_safety`: done.
- Process is diagnostic, not primary ranking: done.
- Same-runner controlled comparison: pending real-model approval.
- Scale-up gate if scorer misses exceed 10%: implemented in report, pending real-model data.
