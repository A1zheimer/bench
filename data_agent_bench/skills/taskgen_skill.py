"""
TaskGenSkill: structured output schema for the Task Generator Agent.

Forces the generator to call ``submit_task`` with a complete task
specification — problem definition, data description, environment config,
ground truth, and the code used to generate data and solve the task.

The schema mirrors :class:`TaskInput` + ground truth format so that the
pipeline can directly package the output into the standard task folder.
"""
from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Optional

from .base import Skill
from ..models.task import Domain

# ---------------------------------------------------------------------------
# Valid enum values (derived from models.task)
# ---------------------------------------------------------------------------

_DOMAIN_VALUES = [d.value for d in Domain]
_DIFFICULTY_VALUES = ["Easy", "Medium", "Hard"]
_TOOL_VALUES = ["python_repl", "file_read", "web_search"]

# ---------------------------------------------------------------------------
# Skill definition
# ---------------------------------------------------------------------------

TASKGEN_SKILL = Skill(
    name="submit_task",
    description=(
        "Submit the complete generated task specification including problem "
        "statement, dataset description, environment configuration, ground "
        "truth answer, data generation code, and solution code. "
        "Call this exactly once when the task is fully designed, data is "
        "generated, and ground truth is verified."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "task_metadata": {
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "enum": _DOMAIN_VALUES,
                        "description": "Target domain for the task.",
                    },
                    "difficulty": {
                        "type": "string",
                        "enum": _DIFFICULTY_VALUES,
                        "description": "Difficulty level.",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "maxItems": 6,
                        "description": "Descriptive tags (e.g. 'anova', 'missing-values').",
                    },
                    "contamination_risk": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "Risk of dataset appearing in LLM training data.",
                    },
                },
                "required": ["domain", "difficulty", "tags"],
            },
            "context": {
                "type": "object",
                "properties": {
                    "problem_statement": {
                        "type": "string",
                        "minLength": 50,
                        "maxLength": 3000,
                        "description": (
                            "Clear, unambiguous task description specifying "
                            "exactly what the agent must compute or produce."
                        ),
                    },
                    "dataset_description": {
                        "type": "string",
                        "description": (
                            "Description of the generated dataset: columns, "
                            "types, row counts, distributions, any special properties."
                        ),
                    },
                    "expert_knowledge": {
                        "type": "string",
                        "description": (
                            "Domain-specific hints, methodology references, "
                            "or statistical guidance for the task."
                        ),
                    },
                },
                "required": ["problem_statement", "dataset_description", "expert_knowledge"],
            },
            "environment_config": {
                "type": "object",
                "properties": {
                    "max_steps": {
                        "type": "integer",
                        "minimum": 5,
                        "maximum": 30,
                        "description": "Maximum execution steps for the agent.",
                    },
                    "budget": {
                        "type": "number",
                        "minimum": 0.5,
                        "maximum": 5.0,
                        "description": "USD cost budget for the agent.",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "minimum": 60,
                        "maximum": 600,
                        "description": "Maximum wall-clock seconds.",
                    },
                    "allowed_tools": {
                        "type": "array",
                        "items": {"type": "string", "enum": _TOOL_VALUES},
                        "description": "Tools available to the evaluated agent.",
                    },
                },
                "required": ["max_steps", "budget"],
            },
            "ground_truth": {
                "type": "object",
                "properties": {
                    "execution_result": {
                        "type": "string",
                        "description": "Expected textual summary of the correct answer.",
                    },
                    "key_values_list": {
                        "type": "array",
                        "description": (
                            "List of labeled numeric results. YOU MUST PROVIDE AT LEAST ONE ITEM. "
                            "Example: [{\"key\": \"p_value\", \"value\": 0.034}, {\"key\": \"f_statistic\", \"value\": 4.2}]"
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "key": {"type": "string"},
                                "value": {"type": "number"}
                            },
                            "required": ["key", "value"]
                        },
                        "minItems": 1
                    },
                    "required_keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Keywords that must appear in the agent's answer.",
                    },
                    "partial_credit_rubric": {
                        "type": "object",
                        "description": (
                            "Rubric items with weights and descriptions for "
                            "partial credit scoring."
                        ),
                        "additionalProperties": {
                            "type": "object",
                            "properties": {
                                "weight": {
                                    "type": "number",
                                    "minimum": 0,
                                    "maximum": 1,
                                },
                                "description": {"type": "string"},
                            },
                            "required": ["weight", "description"],
                        },
                    },
                },
                "required": ["execution_result", "key_values_list", "required_keywords"],
            },
            "data_generation_code": {
                "type": "string",
                "description": (
                    "Complete Python code that generates the synthetic dataset. "
                    "Must use numpy.random with an explicit seed for reproducibility. "
                    "Must save data to a file (CSV or SQL)."
                ),
            },
            "solution_code": {
                "type": "string",
                "description": (
                    "Complete Python code that solves the task and produces "
                    "the ground truth values. Must print key_values as labeled output."
                ),
            },
        },
        "required": [
            "task_metadata",
            "context",
            "environment_config",
            "ground_truth",
            "data_generation_code",
            "solution_code",
        ],
    },
)


# ---------------------------------------------------------------------------
# Parser: tool_args -> task dict + ground_truth dict
# ---------------------------------------------------------------------------

def generate_canary_value(instance_id: str) -> float:
    """Generate a unique canary value from the instance_id and current time."""
    raw = hashlib.sha256(f"{instance_id}:{time.time()}".encode()).hexdigest()[:8]
    return round(int(raw, 16) / 0xFFFFFFFF * 100, 4)


def parse_generated_task(
    tool_args: Dict[str, Any],
    instance_id: str,
) -> Dict[str, Any]:
    """
    Convert raw tool_args from ``submit_task`` into separate task.json
    and ground_truth dicts ready for disk serialization.

    Returns::

        {
            "task_json": { ... },          # -> task.json
            "ground_truth": { ... },       # -> ground_truth/expected_output.json
            "data_generation_code": "...", # Python code to produce dataset
            "solution_code": "...",        # Python code to produce ground truth
        }
    """
    meta = tool_args.get("task_metadata", {})
    ctx = tool_args.get("context", {})
    env = tool_args.get("environment_config", {})
    gt = tool_args.get("ground_truth", {})

    canary = generate_canary_value(instance_id)
    difficulty = meta.get("difficulty", "Medium")

    # Build environment config and clamp to difficulty constraints
    from ..generation.difficulty_spec import clamp_env_config
    env_config = {
        "image": "ds-agent-v1:latest",
        "max_steps": env.get("max_steps", 15),
        "budget": env.get("budget", 2.0),
        "timeout_seconds": env.get("timeout_seconds", 300),
        "allowed_tools": env.get("allowed_tools", _TOOL_VALUES),
    }
    env_config = clamp_env_config(env_config, difficulty)

    task_json = {
        "instance_id": instance_id,
        "task_metadata": {
            "domain": meta.get("domain", "Generic"),
            "difficulty": difficulty,
            "tags": meta.get("tags", []),
            "contamination_risk": meta.get("contamination_risk", "low"),
            "canary_value": canary,
        },
        "context": {
            "problem_statement": ctx.get("problem_statement", ""),
            "dataset_preview": "data/dataset.csv",
            "expert_knowledge": ctx.get("expert_knowledge", ""),
        },
        "environment_config": env_config,
    }

    # Convert key_values_list back to dict
    kv_list = gt.get("key_values_list", [])
    if gt.get("key_values"):  # Fallback if the model still generated dict
        raw_kv = gt.get("key_values")
    else:
        raw_kv = {item["key"]: item["value"] for item in kv_list if "key" in item and "value" in item}

    if not isinstance(raw_kv, dict) or not raw_kv:
        import logging
        logging.getLogger(__name__).error(f"Invalid key_values received: {raw_kv}. Ground truth: {gt}")
        raise ValueError("key_values in ground_truth must be a non-empty dictionary of numeric values.")

    ground_truth = {
        "execution_result": gt.get("execution_result", ""),
        "key_values": raw_kv,
        "required_keywords": gt.get("required_keywords", []),
    }
    if "partial_credit_rubric" in gt:
        ground_truth["partial_credit_rubric"] = gt["partial_credit_rubric"]

    # Post-validate ground truth against difficulty constraints
    from ..generation.difficulty_spec import validate_ground_truth
    gt_issues = validate_ground_truth(ground_truth, difficulty)
    if gt_issues:
        import logging
        logger = logging.getLogger(__name__)
        for issue in gt_issues:
            logger.warning("Ground truth validation: %s", issue)
        # Only hard-fail on key_values count — rubric is a soft warning
        kv_issues = [i for i in gt_issues if "key_values" in i]
        if kv_issues:
            raise ValueError(f"Ground truth does not meet {difficulty} requirements: {kv_issues[0]}")

    return {
        "task_json": task_json,
        "ground_truth": ground_truth,
        "data_generation_code": tool_args.get("data_generation_code", ""),
        "solution_code": tool_args.get("solution_code", ""),
        "canary_value": canary,
    }
