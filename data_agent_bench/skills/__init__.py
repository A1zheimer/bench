"""
Skills: structured output schemas enforced via tool_use + tool_choice.

A Skill wraps a JSON Schema as a tool definition. When passed to an LLM
with forced tool_choice, the response is guaranteed to conform to the schema.
Provider-agnostic: one schema works for both Anthropic and OpenAI APIs.
"""
from .base import Skill
from .judge_skill import JUDGE_SKILL, parse_judge_verdict
from .taskgen_skill import TASKGEN_SKILL, parse_generated_task
from .reviewer_skill import REVIEWER_SKILL, compute_match_from_review

__all__ = [
    "Skill",
    "JUDGE_SKILL",
    "parse_judge_verdict",
    "TASKGEN_SKILL",
    "parse_generated_task",
    "REVIEWER_SKILL",
    "compute_match_from_review",
]
