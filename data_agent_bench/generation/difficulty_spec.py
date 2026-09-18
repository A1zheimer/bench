"""
Difficulty Specification Module.

Defines hard constraints for each difficulty level. Used by:
1. Task generator prompts (as guidance for LLM)
2. parse_generated_task (post-validation / auto-correction)
3. Seed dataset selection (manifest filtering)

All thresholds are enforced programmatically, not just via prompt.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class DifficultyConstraints:
    """Hard constraints for a difficulty level."""

    # Environment config ranges
    max_steps_range: Tuple[int, int]       # (min, max)
    budget_range: Tuple[float, float]       # USD
    timeout_range: Tuple[int, int]          # seconds

    # Ground truth requirements
    min_key_values: int                     # minimum numeric KV pairs
    min_rubric_items: int                   # minimum partial credit rubric items

    # Seed data mutation level
    mutation_description: str               # what level of data transformation is expected

    # Defaults (used when LLM omits or gives out-of-range values)
    default_max_steps: int
    default_budget: float
    default_timeout: int


DIFFICULTY_SPECS: Dict[str, DifficultyConstraints] = {
    "Easy": DifficultyConstraints(
        max_steps_range=(5, 8),
        budget_range=(0.5, 1.0),
        timeout_range=(60, 120),
        min_key_values=1,
        min_rubric_items=2,
        mutation_description=(
            "Use a subset of the seed data (random sample or column selection). "
            "Rename columns for anti-contamination. No complex transformations."
        ),
        default_max_steps=6,
        default_budget=0.8,
        default_timeout=90,
    ),
    "Medium": DifficultyConstraints(
        max_steps_range=(8, 15),
        budget_range=(1.0, 2.0),
        timeout_range=(120, 300),
        min_key_values=2,
        min_rubric_items=2,
        mutation_description=(
            "Rename columns, inject additional noise/missing values, "
            "optionally merge with a generated secondary table. "
            "Add at least one data quality issue the agent must handle."
        ),
        default_max_steps=10,
        default_budget=1.5,
        default_timeout=180,
    ),
    "Hard": DifficultyConstraints(
        max_steps_range=(15, 25),
        budget_range=(2.0, 5.0),
        timeout_range=(300, 600),
        min_key_values=3,
        min_rubric_items=3,
        mutation_description=(
            "Significant data transformation: merge multiple seed tables, "
            "add correlated noise, introduce realistic outliers, "
            "create temporal or hierarchical structure. "
            "The resulting dataset should require multi-step analysis."
        ),
        default_max_steps=20,
        default_budget=3.0,
        default_timeout=480,
    ),
}


def clamp_env_config(env: dict, difficulty: str) -> dict:
    """
    Clamp environment_config values to the valid range for the given difficulty.
    Mutates and returns the dict.
    """
    spec = DIFFICULTY_SPECS.get(difficulty)
    if spec is None:
        return env

    ms = env.get("max_steps", spec.default_max_steps)
    env["max_steps"] = max(spec.max_steps_range[0], min(ms, spec.max_steps_range[1]))

    budget = env.get("budget", spec.default_budget)
    env["budget"] = max(spec.budget_range[0], min(budget, spec.budget_range[1]))

    timeout = env.get("timeout_seconds", spec.default_timeout)
    env["timeout_seconds"] = max(spec.timeout_range[0], min(timeout, spec.timeout_range[1]))

    return env


def validate_ground_truth(gt: dict, difficulty: str) -> list:
    """
    Validate ground truth meets difficulty requirements.
    Returns list of issues (empty = valid).
    """
    spec = DIFFICULTY_SPECS.get(difficulty)
    if spec is None:
        return []

    issues = []
    kv = gt.get("key_values", {})
    if len(kv) < spec.min_key_values:
        issues.append(
            f"key_values has {len(kv)} entries, minimum {spec.min_key_values} required for {difficulty}"
        )

    rubric = gt.get("partial_credit_rubric", {})
    if len(rubric) < spec.min_rubric_items:
        issues.append(
            f"partial_credit_rubric has {len(rubric)} items, minimum {spec.min_rubric_items} required for {difficulty}"
        )

    return issues


def get_prompt_constraints(difficulty: str) -> str:
    """
    Return a formatted string of constraints for injection into the system prompt.
    """
    spec = DIFFICULTY_SPECS.get(difficulty)
    if spec is None:
        return ""

    return (
        f"## Strict Difficulty Constraints for {difficulty}\n"
        f"- max_steps: {spec.max_steps_range[0]}-{spec.max_steps_range[1]} "
        f"(default: {spec.default_max_steps})\n"
        f"- budget: ${spec.budget_range[0]:.1f}-${spec.budget_range[1]:.1f} "
        f"(default: ${spec.default_budget:.1f})\n"
        f"- timeout: {spec.timeout_range[0]}-{spec.timeout_range[1]}s "
        f"(default: {spec.default_timeout}s)\n"
        f"- Minimum key_values entries: {spec.min_key_values}\n"
        f"- Minimum partial_credit_rubric items: {spec.min_rubric_items}\n"
        f"- Data mutation level: {spec.mutation_description}\n"
    )
