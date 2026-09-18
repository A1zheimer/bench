# DataAgentBench Task Generation Refactor Plan

## Problem

The current task generation system lets the LLM propose the task, mutate data, solve the task, and submit ground truth in one loop. Although the code attempts to verify the solution, failed generation traces and `verified=false` tasks can still be packaged, which allowed hallucinated or template-mismatched ground truth to enter pilot sets.

## Target Architecture

```text
Task Idea Spec
  -> Dataset Builder
  -> Deterministic Verifier
  -> Task Packager
  -> Red-team Perturber
  -> Batch Manifest
```

The LLM may propose task ideas, prompts, and candidate transformations. It must not be the final authority for ground truth. Ground truth must be computed by deterministic verifier code from `data/dataset.csv`.

## Non-negotiable Contract

- No deterministic verifier, no benchmark task.
- `verified=false` tasks do not enter formal sets.
- Generation trace errors do not enter formal sets.
- Forced submit after errors is rejected.
- GT must contain numeric `key_values`.
- Each GT must record provenance: formula, verifier, dataset SHA256, computed time, and canary policy.
- Red-team variants must record base task, perturbation type, attack level, invariant, and verifier result.

## GT Generation Method Comparison

| Method | Role | Strength | Failure Mode | Formal Use |
|---|---|---|---|---|
| LLM direct GT | Candidate generation | Fast and diverse | Hallucinated values, prompt/GT mismatch, forced submit after errors | No |
| LLM solution trace extraction | Audit signal | Shows an attempted computation path | Wrong code, timeout, trace errors, fragile extraction | Debug only |
| Human annotation | Spot-check / case study | High trust for complex tasks | Expensive and slow to scale | Sampling audit |
| Deterministic verifier | Formal GT authority | Recomputable, cheap, provenance-rich | Limited by verifier template coverage | Yes |
| Hybrid pipeline | Target construction flow | LLM diversity + verifier reliability + optional human audit | Requires maintaining template/verifier registry | Yes |

The adopted policy is hybrid but verifier-authoritative: the LLM may propose task ideas and prompt paraphrases, while GT is computed only by deterministic verifier replay.

## Strategy-Level Baseline Comparison

GT generation answers "what is the correct answer?" Strategy baselines answer "how does a tested agent handle the data problem?" Formal experiments should include both model-level comparisons and strategy-level ablations.

| Strategy | Definition | Diagnostic Purpose |
|---|---|---|
| Direct Answer | Return an answer without code execution | Measures shortcut/guessing behavior |
| Code Agent | Read CSV and compute with Python | Main data-workflow baseline |
| Schema-aware Code Agent | Inspect schema/profile before choosing columns and methods | Tests whether schema grounding reduces column errors |
| Validation-aware Agent | Add explicit post-computation checks | Tests whether self-checking improves grounded final answers |
| Robustness-aware Agent | Diagnose obfuscation, distractors, and dirty data before solving | Tests robustness under paired perturbations |
| Oracle Script / Verifier | Run trusted verifier or hand-written oracle | Upper bound and scorer sanity check, not a ranked agent |

This comparison should appear as a strategy ablation table, separate from the main model leaderboard.

## Refactor Phases

### P0: Quality Gate

Status: implemented.

- Added `GenerationQualityGate`.
- `GenerationPipeline` now evaluates generated tasks before packaging.
- Formal generation rejects unverified tasks by default.
- CLI escape hatch: `--allow-unverified` for debugging only.

### P1: Verifier Registry

Status: implemented for smoke v1.

Define task templates with explicit verifier functions:

```text
aggregation_by_group
filtered_mean
correlation_pair
iqr_outlier_count
crosstab_prevalence
model_eval_metric
```

Each verifier owns:

- required input columns
- task prompt template
- deterministic GT computation
- allowed aliases
- component scoring spec

### P2: Manifest-based Generation

Status: implemented for smoke v1.

Replace free-form generated GT with a manifest:

```json
{
  "template_id": "filtered_mean",
  "domain": "Biomedical",
  "dataset_builder": "hospital_readmission_v1",
  "target_columns": ["readmission", "hospital_stay_days"],
  "filter": "readmission == 1",
  "metric": "mean",
  "verifier": "filtered_mean_v1"
}
```

The packager creates `task.json` and `expected_output.json` from this manifest.

### P3: Red-team Paired Generation

Status: implemented for smoke v1.

Generate perturbations from verified clean tasks only:

- schema obfuscation
- distractor columns
- dirty data/statistical traps
- instruction conflict
- format stress

Every perturbation must declare whether GT is invariant or recomputed.

### P4: Batch Acceptance

Status: implemented for smoke v1.

A generated batch is accepted only if:

- clean pass rate from verifier is 100%
- red-team invariant checks pass
- no task has `generation_quality.accepted=false`
- domain/difficulty/type distribution matches the batch spec

## Current Implementation Snapshot

- `data_agent_taskgen.manifest`: `TaskManifest` schema.
- `data_agent_taskgen.dataset_builders`: deterministic dataset generation and dataset profile.
- `data_agent_taskgen.manifest_sampler`: legal manifest sampling by verifier capability.
- `data_agent_taskgen.verifiers`: deterministic GT registry.
- `data_agent_taskgen.packager`: static task packaging and verifier replay.
- `data_agent_taskgen.redteam_builder`: paired redteam tasks with invariant/recomputed GT policy.
- `data_agent_taskgen.cli`: `build-core`, `build-redteam`, and `replay`.

Generated verified smoke sets:

- `tasks_verified_core_v1`: 12 clean tasks, 12/12 replay pass.
- `tasks_verified_redteam_v1`: 15 paired redteam tasks, 15/15 replay pass.

Reports:

- `reports/verified_core_v1_smoke.md`
- `reports/verified_core_v1_replay.md`
- `reports/verified_redteam_v1_smoke.md`
- `reports/verified_redteam_v1_replay.md`

## Immediate Next Step

Run a controlled model sanity check on the verified smoke sets before scaling:

```text
models:
- gpt-4o-mini
- gpt-5.4
- gpt-5.3-codex

tasks:
- tasks_verified_core_v1
- tasks_verified_redteam_v1
```

If scorer/trace behavior is normal, expand to `60 clean + 60 redteam` and write the formal construction report.
