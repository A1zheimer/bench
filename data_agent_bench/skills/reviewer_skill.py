"""
ReviewerSkill: structured output schema for the Reviewer Agent.

Replaces regex-based numeric extraction from free-text output with a
forced tool_use call to ``submit_review``.  The reviewer is required to
call this tool after solving the task, guaranteeing structured results.
"""
from __future__ import annotations

from typing import Any, Dict

from .base import Skill

# ---------------------------------------------------------------------------
# Skill definition
# ---------------------------------------------------------------------------

REVIEWER_SKILL = Skill(
    name="submit_review",
    description=(
        "Submit your review results after independently solving the task. "
        "You MUST call this tool exactly once after completing your analysis. "
        "Report the numeric values you computed and your assessment of task quality."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "computed_values": {
                "type": "object",
                "additionalProperties": {"type": "number"},
                "description": (
                    "Key-value pairs of the numeric results you computed. "
                    "Use the SAME keys as specified in the task's expected output "
                    "(e.g., {\"p_value\": 0.034, \"f_statistic\": 4.21})."
                ),
            },
            "keywords_found": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "List of required keywords from the ground truth that "
                    "you confirmed are relevant to the solution."
                ),
            },
            "problem_clarity": {
                "type": "number",
                "minimum": 0,
                "maximum": 4,
                "description": (
                    "0-4: Is the problem statement clear and unambiguous? "
                    "4 = perfectly clear, 0 = incomprehensible."
                ),
            },
            "data_quality": {
                "type": "number",
                "minimum": 0,
                "maximum": 4,
                "description": (
                    "0-4: Does the dataset match the description and support the task? "
                    "4 = excellent, 0 = unusable or mismatched."
                ),
            },
            "reproducibility": {
                "type": "number",
                "minimum": 0,
                "maximum": 4,
                "description": (
                    "0-4: Can the ground truth be reproduced from the data? "
                    "4 = exact match, 2 = approximate, 0 = cannot reproduce."
                ),
            },
            "difficulty_appropriate": {
                "type": "boolean",
                "description": "Is the stated difficulty level appropriate for the task?",
            },
            "issues": {
                "type": "string",
                "description": (
                    "Description of any issues found: ambiguity, data problems, "
                    "ground truth errors, or difficulty mismatch. Empty if none."
                ),
            },
        },
        "required": [
            "computed_values",
            "problem_clarity",
            "data_quality",
            "reproducibility",
            "difficulty_appropriate",
            "issues",
        ],
    },
)


# ---------------------------------------------------------------------------
# Parser: tool_args dict -> match_score + structured ReviewResult fields
# ---------------------------------------------------------------------------

def compute_match_from_review(
    review_args: Dict[str, Any],
    ground_truth: Dict[str, Any],
    tolerance: float = 0.1,
) -> float:
    """
    Compute match_score by comparing the reviewer's structured output
    against the ground truth, replacing regex-based extraction.

    Args:
        review_args: The structured output from submit_review tool call.
        ground_truth: The expected_output.json content.
        tolerance: Relative error tolerance (default 10%).

    Returns:
        Score in [0, 1].
    """
    key_values = ground_truth.get("key_values", {})
    computed = review_args.get("computed_values", {})

    if not key_values:
        # No numeric targets -- check keywords only
        keywords = ground_truth.get("required_keywords", [])
        if not keywords:
            return 0.5  # can't evaluate
        found = review_args.get("keywords_found", [])
        found_lower = {kw.lower() for kw in found}
        matched = sum(1 for kw in keywords if kw.lower() in found_lower)
        return matched / len(keywords)

    matched = 0
    total = 0

    for key, expected in key_values.items():
        if not isinstance(expected, (int, float)):
            continue
        total += 1
        actual = computed.get(key)
        if actual is None:
            # Try case-insensitive key match
            for ck, cv in computed.items():
                if ck.lower() == key.lower() and isinstance(cv, (int, float)):
                    actual = cv
                    break
        if actual is not None and isinstance(actual, (int, float)):
            rel_err = abs(actual - expected) / max(abs(expected), 1e-10)
            if rel_err < tolerance:
                matched += 1

    return matched / total if total > 0 else 0.0
