"""
System prompts for the Task Generator Agent and Reviewer Agent.
Loaded dynamically from JSON file to enforce version control for Paper submission.

The TASK_GENERATOR_SYSTEM_PROMPT template contains these placeholders:
  {domain}, {difficulty}, {tag_guidance}, {difficulty_constraints}
"""
from __future__ import annotations

import json
import pathlib

_PROMPT_FILE = pathlib.Path(__file__).parent.parent / "prompts" / "generation_prompts_v1.json"

def _load_prompts():
    if not _PROMPT_FILE.exists():
        raise FileNotFoundError(f"Prompt file not found: {_PROMPT_FILE}")
    with open(_PROMPT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

_prompts = _load_prompts()

TASK_GENERATOR_SYSTEM_PROMPT = _prompts["TASK_GENERATOR_SYSTEM_PROMPT"]
TASK_GENERATOR_TAG_GUIDANCE = _prompts["TASK_GENERATOR_TAG_GUIDANCE"]
TASK_GENERATOR_NO_TAG_GUIDANCE = _prompts["TASK_GENERATOR_NO_TAG_GUIDANCE"]
REVIEWER_SYSTEM_PROMPT = _prompts["REVIEWER_SYSTEM_PROMPT"]

