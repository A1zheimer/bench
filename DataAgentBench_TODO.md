# DataAgentBench Todo List

更新时间：2026-05-21

## Current Status

- [x] Paper type fixed as Benchmark / Evaluation / Resource paper.
- [x] Primary venue framing: SIGMOD / CIKM style benchmark and resource paper.
- [x] Legacy pilot20/121 results reclassified as debug only, not formal model conclusions.
- [x] Bench / TaskGen same-repo modular separation completed.
- [x] Bench defaults to verified task loading.
- [x] TaskGen owns manifest sampling, deterministic dataset building, verifier replay, packaging, and paired redteam generation.
- [x] Added GT generation method comparison: LLM direct GT, trace-derived GT, human annotation, deterministic verifier, hybrid pipeline.
- [x] Generated `tasks_verified_core_v1`: 12 clean verified tasks, 12/12 replay pass.
- [x] Generated `tasks_verified_redteam_v1`: 15 paired redteam verified tasks, 15/15 replay pass.
- [x] Added smoke reports:
  - `reports/verified_core_v1_smoke.md`
  - `reports/verified_core_v1_replay.md`
  - `reports/verified_redteam_v1_smoke.md`
  - `reports/verified_redteam_v1_replay.md`
- [x] Full tests pass: 65 passed.

## P0: Verified Model Sanity Check

Goal: only compare models on verified GT tasks.

- [ ] Run `gpt-4o-mini` on `tasks_verified_core_v1`.
- [ ] Run `gpt-5.4` on `tasks_verified_core_v1`.
- [ ] Run `gpt-5.3-codex` on `tasks_verified_core_v1`.
- [ ] Run the same three models on `tasks_verified_redteam_v1`.
- [ ] Add a strategy-level sanity check on one model:
  - Direct Answer
  - Code Agent
  - Schema-aware Code Agent
  - Validation-aware Agent
  - Robustness-aware Agent
- [ ] Report `FinalAcc`, `ObservedTraceAcc`, `GroundedFinalAcc`, `Timeout/API Rate`, `TraceIntegrity`.
- [ ] Compute clean vs redteam paired robustness retention.
- [ ] Inspect any strong-model anomaly before scaling.
- [ ] Write `reports/verified_core_v1_model_sanity.md`.
- [ ] Write `reports/verified_redteam_v1_model_sanity.md`.

## P1: Expand Verified Benchmark Pilot

Goal: build paper-usable pilot, not just pipeline smoke.

- [ ] Expand to 60 clean verified tasks.
- [ ] Expand to 60 paired redteam verified tasks.
- [ ] Ensure each verifier template has at least 8 tasks.
- [ ] Ensure each domain has at least 8 tasks.
- [ ] Balance Easy / Medium / Hard as much as possible.
- [ ] Generate construction report: `reports/verified_benchmark_v1_construction.md`.
- [ ] Generate task statistics:
  - domain x difficulty
  - verifier template distribution
  - primary task type distribution
  - redteam attack type distribution
  - key-value count distribution
- [ ] Replay verifier for 100% of formal tasks before any model run.

## P2: Improve Task Realism

Goal: reduce synthetic-only risk.

- [ ] Add `seed_csv_copy_v1` builder to formal TaskGen flow.
- [ ] Add `seed_csv_light_transform_v1` builder.
- [ ] Build domain-specific manifest samplers for Finance, Biomedical, ECommerce, Scientific.
- [ ] Add verifier templates:
  - `time_series_metric_v1`
  - `hypothesis_test_v1`
  - `missing_value_imputation_v1`
  - `multi_table_join_aggregation_v1`
- [ ] Keep GT rule unchanged: verifier owns GT; LLM never writes formal GT.

## P3: Redteam and Robustness Metrics

- [x] Implement `schema_obfuscation` with invariant GT.
- [x] Implement `distractor_columns` with invariant GT.
- [x] Implement `dirty_data` with recomputed GT.
- [ ] Add stronger attack levels L2/L3 after smoke sanity check.
- [ ] Define robustness metrics:
  - `CleanAcc`
  - `RedTeamAcc`
  - `RobustnessRetention = RedTeamAcc / CleanAcc`
  - `PerturbationDelta = CleanAcc - RedTeamAcc`
  - per-attack-type degradation
- [ ] Add paired significance tests once sample size is large enough.

## P3.5: Strategy-Level Baselines

Goal: compare different methods of handling the same data problem, not only different foundation models.

- [ ] Implement or configure `direct_answer` baseline.
- [ ] Keep current native code agent as `code_agent` baseline.
- [ ] Add `schema_aware_code_agent` prompt/profile policy.
- [ ] Add `validation_aware_agent` prompt policy with self-check requirements.
- [ ] Add `robustness_aware_agent` prompt policy for schema obfuscation, distractors, and dirty data.
- [ ] Add oracle/verifier upper-bound row for task/scorer validation only.
- [ ] Produce strategy ablation table:
  - Strategy
  - CleanAcc
  - RedTeamAcc
  - RobustnessRetention
  - GroundedFinalAcc
  - TraceIntegrity
  - Timeout/API Rate

## P4: Paper Figures and Tables

- [ ] Figure 1: verified running example with clean/redteam variants.
- [ ] Figure 2: verified construction pipeline.
- [ ] Figure 3: model sanity / pilot overall performance.
- [ ] Figure 4: robustness retention by attack type.
- [ ] Table 1: related benchmark comparison.
- [ ] Table 2: verified task statistics.
- [ ] Table 3: overall model performance.
- [ ] Table 4: fine-grained template/domain/difficulty analysis.
- [ ] Table 5: GT generation method comparison and quality-control gates.
- [ ] Table 6: strategy-level baseline / handling-method ablation.
- [ ] Appendix: verifier specs and complete task metadata.

## P5: Paper Writing

- [ ] Rewrite Introduction around verified construction pipeline, not old 121 tasks.
- [ ] Update problem statement:
  - final-answer-only evaluation gap
  - GT verifiability gap
  - paired robustness gap
- [ ] Write Benchmark Design section:
  - design goals
  - GT generation method comparison
  - manifest schema
  - verifier registry
  - task packaging
  - redteam GT policy
- [ ] Write Evaluation Protocol section:
  - final accuracy
  - trace-grounded accuracy
  - grounded-final accuracy
  - process/safety/trace integrity diagnostics
  - model-level vs strategy-level baseline design
- [ ] Write Limitations:
  - pilot size
  - synthetic data risk
  - verifier template coverage
  - no human baseline yet
- [ ] Write Reproducibility section:
  - task folder contract
  - dataset SHA256
  - verifier replay
  - seeds
  - model versions and dates

## Immediate Next 3 Days

1. Run model sanity check on `tasks_verified_core_v1`.
2. Run model sanity check on `tasks_verified_redteam_v1`.
3. Inspect all anomalous low scores with trace viewer.
4. Decide whether current 6 verifier templates are enough for the first 60-task expansion.
5. Add seed CSV builder before expanding if realism looks too weak.
6. Draft Figure 2 from the implemented pipeline.
