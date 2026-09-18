"""
ReviewerAgent: independently validates a generated benchmark task.

The reviewer receives a task as if it were a test-taker, solves it
independently, and compares its answer against the provided ground truth.
If match_score < threshold, the task is flagged as ambiguous or rejected.

Uses the ``submit_review`` Skill (forced tool_choice) to guarantee
structured output — no regex parsing of free-text results.
"""
from __future__ import annotations

import contextlib
import io
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..skills.reviewer_skill import REVIEWER_SKILL, compute_match_from_review
from .generation_prompts import REVIEWER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


@dataclass
class ReviewResult:
    """Outcome of a reviewer's independent validation."""
    passed: bool
    match_score: float        # 0-1, how close reviewer's answer is to ground truth
    reviewer_answer: Dict[str, Any]
    notes: str
    latency_ms: float = 0.0
    tokens_used: int = 0


class ReviewerAgent:
    """
    Independent agent that validates a generated task by attempting to solve it.

    Uses the same LLM providers as the generator but runs independently
    to check if the task is solvable and the ground truth is reproducible.

    Output is guaranteed structured via forced ``submit_review`` tool_choice.
    """

    MAX_REVIEW_STEPS = 6
    PASS_THRESHOLD = 0.5  # minimum match_score to pass

    def __init__(
        self,
        provider: str,
        model_id: str,
        temperature: float = 0.0,
        api_key: Optional[str] = None,
    ) -> None:
        self.provider = provider
        self.model_id = model_id
        self.temperature = temperature
        self._api_key = api_key

    def review(
        self,
        task_json: Dict[str, Any],
        ground_truth: Dict[str, Any],
        data_path: Optional[str] = None,
    ) -> ReviewResult:
        """
        Independently solve the task and compare with ground truth.

        Workflow:
          Steps 1..N-1: tool_choice="auto" — reviewer uses python_repl/file_read
          Final step:   forced tool_choice=submit_review — structured output

        Args:
            task_json: The task.json content.
            ground_truth: The expected_output.json content.
            data_path: Path to the data directory (if data was written to disk).

        Returns:
            ReviewResult with pass/fail and match score.
        """
        t0 = time.perf_counter()

        context = task_json.get("context", {})
        problem = context.get("problem_statement", "")
        expert = context.get("expert_knowledge", "")
        domain = task_json.get("task_metadata", {}).get("domain", "")
        difficulty = task_json.get("task_metadata", {}).get("difficulty", "")

        # Tell reviewer what keys to compute so submit_review is well-populated
        key_names = list(ground_truth.get("key_values", {}).keys())
        required_kw = ground_truth.get("required_keywords", [])

        user_msg = (
            f"## Task ({domain}, {difficulty})\n{problem}\n\n"
            f"## Expert Knowledge\n{expert}\n\n"
            f"## Instructions\n"
            f"Solve this task using python_repl. "
            f"Compute these specific values: {key_names}.\n"
        )
        if required_kw:
            user_msg += f"Also check for these keywords: {required_kw}.\n"
        if data_path:
            user_msg += f"\nData is available at: {data_path}\n"
        user_msg += (
            "\nAfter solving, call the `submit_review` tool with your results."
        )

        messages: List[Dict[str, Any]] = [{"role": "user", "content": user_msg}]
        total_tokens = 0
        review_args: Optional[Dict[str, Any]] = None

        for step in range(self.MAX_REVIEW_STEPS):
            is_final = (step == self.MAX_REVIEW_STEPS - 1)

            if is_final and review_args is None:
                # Force submit_review on last step
                result = self._forced_review_call(
                    REVIEWER_SYSTEM_PROMPT, messages
                )
                review_args = result[0]
                total_tokens += result[1] + result[2]
                break

            # Normal step: tool_choice=auto, reviewer can use python_repl or submit_review
            content, tool_name, tool_args, t_in, t_out = self._llm_call(
                REVIEWER_SYSTEM_PROMPT, messages
            )
            total_tokens += t_in + t_out

            if tool_name == "submit_review":
                # Reviewer voluntarily submitted — great
                review_args = tool_args or {}
                break
            elif tool_name == "python_repl":
                exec_result = self._execute_python(
                    tool_args.get("code", "") if tool_args else ""
                )
                messages.append({"role": "assistant", "content": content or ""})
                messages.append({"role": "user", "content": f"Output:\n{exec_result}"})
            elif tool_name == "file_read" and data_path:
                import pathlib
                path = (tool_args or {}).get("path", "")
                try:
                    file_content = pathlib.Path(path).read_text("utf-8")[:2000]
                except Exception:
                    file_content = "(file not found)"
                messages.append({"role": "assistant", "content": content or ""})
                messages.append({"role": "user", "content": file_content})
            else:
                # No tool call — text response
                if "FINAL" in (content or "").upper():
                    # Reviewer thinks it's done but didn't call submit_review
                    # Force it on next iteration
                    messages.append({"role": "assistant", "content": content or ""})
                    messages.append({
                        "role": "user",
                        "content": (
                            "Now submit your results using the `submit_review` tool. "
                            "Include your computed numeric values and quality assessment."
                        ),
                    })
                else:
                    messages.append({"role": "assistant", "content": content or ""})
                    messages.append({
                        "role": "user",
                        "content": "Continue solving. When done, call `submit_review`.",
                    })

        latency = (time.perf_counter() - t0) * 1000

        # Compute match score from structured output
        if review_args is None:
            review_args = {}

        match_score = compute_match_from_review(review_args, ground_truth)

        return ReviewResult(
            passed=match_score >= self.PASS_THRESHOLD,
            match_score=match_score,
            reviewer_answer=review_args,
            notes=(
                f"Reviewer match_score={match_score:.2f} "
                f"({'PASS' if match_score >= self.PASS_THRESHOLD else 'FAIL'})"
                + (f"; issues: {review_args.get('issues', '')}"
                   if review_args.get("issues") else "")
            ),
            latency_ms=latency,
            tokens_used=total_tokens,
        )

    # ------------------------------------------------------------------
    # Provider calls — auto mode (python_repl + submit_review available)
    # ------------------------------------------------------------------

    def _get_work_tools(self) -> list:
        """Tools available during solving: python_repl + submit_review."""
        return [
            {
                "name": "python_repl",
                "description": "Execute Python code to solve the task.",
                "input_schema": {
                    "type": "object",
                    "properties": {"code": {"type": "string"}},
                    "required": ["code"],
                },
            },
            REVIEWER_SKILL.to_anthropic_tool(),
        ]

    def _get_work_tools_openai(self) -> list:
        """OpenAI format tools for solving: python_repl + submit_review."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "python_repl",
                    "description": "Execute Python code to solve the task.",
                    "parameters": {
                        "type": "object",
                        "properties": {"code": {"type": "string"}},
                        "required": ["code"],
                    },
                },
            },
            REVIEWER_SKILL.to_openai_tool(),
        ]

    def _llm_call(self, system: str, messages: List[Dict[str, Any]]):
        """Auto tool_choice call — reviewer chooses python_repl or submit_review."""
        if self.provider == "anthropic":
            return self._anthropic_call(system, messages)
        elif self.provider == "openai":
            return self._openai_call(system, messages)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def _forced_review_call(
        self, system: str, messages: List[Dict[str, Any]]
    ) -> tuple:
        """Forced tool_choice=submit_review — guarantees structured output."""
        if self.provider == "anthropic":
            return self._anthropic_forced(system, messages)
        elif self.provider == "openai":
            return self._openai_forced(system, messages)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    # ---------- Anthropic ----------

    def _anthropic_call(self, system: str, messages: List[Dict[str, Any]]):
        import anthropic
        client = anthropic.Anthropic(api_key=self._api_key)

        api_messages = [{"role": m["role"], "content": m["content"]} for m in messages]
        resp = client.messages.create(
            model=self.model_id,
            max_tokens=4096,
            temperature=self.temperature,
            system=system,
            tools=self._get_work_tools(),
            messages=api_messages,
        )

        text = ""
        tool_name = None
        tool_args = None
        for block in resp.content:
            if block.type == "text":
                text += block.text
            elif block.type == "tool_use":
                tool_name = block.name
                tool_args = block.input

        return text, tool_name, tool_args, resp.usage.input_tokens, resp.usage.output_tokens

    def _anthropic_forced(self, system: str, messages: List[Dict[str, Any]]):
        """Force submit_review via tool_choice."""
        import anthropic
        client = anthropic.Anthropic(api_key=self._api_key)

        # Only submit_review tool, forced
        tools = [REVIEWER_SKILL.to_anthropic_tool()]
        api_messages = [{"role": m["role"], "content": m["content"]} for m in messages]

        # Add instruction to finalize
        api_messages.append({
            "role": "user",
            "content": (
                "Now submit your final review using the `submit_review` tool. "
                "Include all numeric values you computed and your quality assessment."
            ),
        })

        resp = client.messages.create(
            model=self.model_id,
            max_tokens=4096,
            temperature=self.temperature,
            system=system,
            tools=tools,
            tool_choice=REVIEWER_SKILL.anthropic_tool_choice(),
            messages=api_messages,
        )

        review_args = {}
        for block in resp.content:
            if block.type == "tool_use" and block.name == "submit_review":
                review_args = block.input
                break

        return review_args, resp.usage.input_tokens, resp.usage.output_tokens

    # ---------- OpenAI ----------

    def _openai_call(self, system: str, messages: List[Dict[str, Any]]):
        import openai
        client = openai.OpenAI(api_key=self._api_key)

        api_messages = [{"role": "system", "content": system}]
        api_messages.extend({"role": m["role"], "content": m["content"]} for m in messages)

        resp = client.chat.completions.create(
            model=self.model_id,
            max_tokens=4096,
            temperature=self.temperature,
            tools=self._get_work_tools_openai(),
            messages=api_messages,
        )

        msg = resp.choices[0].message
        content = msg.content or ""
        tool_name = None
        tool_args = None

        if msg.tool_calls:
            tc = msg.tool_calls[0]
            tool_name = tc.function.name
            try:
                tool_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                tool_args = {}

        t_in = resp.usage.prompt_tokens if resp.usage else 0
        t_out = resp.usage.completion_tokens if resp.usage else 0
        return content, tool_name, tool_args, t_in, t_out

    def _openai_forced(self, system: str, messages: List[Dict[str, Any]]):
        """Force submit_review via tool_choice."""
        import openai
        client = openai.OpenAI(api_key=self._api_key)

        api_messages = [{"role": "system", "content": system}]
        api_messages.extend({"role": m["role"], "content": m["content"]} for m in messages)
        api_messages.append({
            "role": "user",
            "content": (
                "Now submit your final review using the `submit_review` tool. "
                "Include all numeric values you computed and your quality assessment."
            ),
        })

        resp = client.chat.completions.create(
            model=self.model_id,
            max_tokens=4096,
            temperature=self.temperature,
            tools=[REVIEWER_SKILL.to_openai_tool()],
            tool_choice=REVIEWER_SKILL.openai_tool_choice(),
            messages=api_messages,
        )

        review_args = {}
        msg = resp.choices[0].message
        if msg.tool_calls:
            tc = msg.tool_calls[0]
            if tc.function.name == "submit_review":
                try:
                    review_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    review_args = {}

        t_in = resp.usage.prompt_tokens if resp.usage else 0
        t_out = resp.usage.completion_tokens if resp.usage else 0
        return review_args, t_in, t_out

    # ------------------------------------------------------------------
    # Python execution
    # ------------------------------------------------------------------

    @staticmethod
    def _execute_python(code: str) -> str:
        # In a fully dockerized environment, this could also use the DockerSandboxEnvironment
        # For the Reviewer, local execution might be acceptable, but for consistency we use a similar sandbox pattern
        import tempfile
        import subprocess
        import os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_path = f.name
            
        try:
            # We execute it locally with a timeout for simplicity, or we could spin up a docker
            # For pure DataCritic / Reviewer tasks, we assume the code is generated by our own agent
            # But let's use a safe subprocess call
            result = subprocess.run(
                ["python", temp_path],
                capture_output=True, text=True, timeout=30
            )
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"
            return output[:2000] or "(no output)"
        except subprocess.TimeoutExpired:
            return "ERROR: Execution timed out"
        except Exception as exc:
            return f"ERROR: {exc}"
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
