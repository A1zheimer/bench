"""
LLMJudgeAgent: an Agent-as-Judge that evaluates a benchmark trajectory.

Unlike simple LLM-as-Judge (one-shot prompt -> score), this judge:
  - Has access to tools (python_repl, file_read) to VERIFY the agent's claims
  - Performs multi-step reasoning before committing to a score
  - Uses a forced ``submit_verdict`` Skill (tool_choice) to guarantee
    structured output -- no regex parsing needed
  - Produces a structured JudgeVerdict with confidence and provenance

Reference: "Agent as Judge" framing where the evaluator is itself an agentic loop.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .judge_prompts import (
    ADVERSARIAL_SYSTEM_PROMPT,
    JUDGE_SYSTEM_PROMPT,
    JUDGE_USER_TEMPLATE,
    format_ground_truth,
    format_trajectory,
)
from ..skills.judge_skill import JUDGE_SKILL, parse_judge_verdict

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model for judge output
# ---------------------------------------------------------------------------

@dataclass
class JudgeVerdict:
    judge_id: str                       # e.g. "anthropic:claude-sonnet-4-6[standard]"
    result_correctness: float           # 0-4
    process_quality: float              # 0-4
    code_quality: Optional[float]       # 0-4 or None
    safety: float                       # 0-4
    confidence: float                   # 0-1
    key_findings: str
    verification_performed: bool
    raw_response: str = field(repr=False, default="")
    latency_ms: float = 0.0
    tokens_used: int = 0
    error: Optional[str] = None

    # Normalized scores on [0, 1] scale
    @property
    def result_correctness_norm(self) -> float:
        return self.result_correctness / 4.0

    @property
    def process_quality_norm(self) -> float:
        return self.process_quality / 4.0

    @property
    def safety_norm(self) -> float:
        return self.safety / 4.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "judge_id": self.judge_id,
            "result_correctness": self.result_correctness,
            "process_quality": self.process_quality,
            "code_quality": self.code_quality,
            "safety": self.safety,
            "confidence": self.confidence,
            "key_findings": self.key_findings,
            "verification_performed": self.verification_performed,
            "latency_ms": self.latency_ms,
            "tokens_used": self.tokens_used,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Judge Agent
# ---------------------------------------------------------------------------

class LLMJudgeAgent:
    """
    A single judge agent. Supports 'standard' and 'adversarial' roles.

    Uses the JudgeSkill (``submit_verdict`` forced tool_choice) to guarantee
    structured output.  Falls back to legacy regex parsing if the skill-based
    path fails unexpectedly.

    provider: 'anthropic' | 'openai'
    model_id: e.g. 'claude-sonnet-4-6', 'gpt-4o'
    role: 'standard' | 'adversarial'
    """

    MAX_JUDGE_STEPS = 5   # judge can use tools up to this many times before forced verdict

    def __init__(
        self,
        provider: str,
        model_id: str,
        role: str = "standard",
        temperature: float = 0.2,
    ) -> None:
        self.provider = provider
        self.model_id = model_id
        self.role = role
        self.temperature = temperature
        self.judge_id = f"{provider}:{model_id}[{role}]"

    def evaluate(
        self,
        instance_id: str,
        domain: str,
        difficulty: str,
        problem_statement: str,
        expert_knowledge: str,
        trajectory: List[Dict[str, Any]],
        final_output: Dict[str, Any],
        ground_truth: Optional[Dict[str, Any]] = None,
        task_data_path: Optional[str] = None,
    ) -> JudgeVerdict:
        """
        Run the judge agentic loop: build context -> call LLM with tools ->
        force ``submit_verdict`` skill -> return structured JudgeVerdict.
        """
        system_prompt = (
            ADVERSARIAL_SYSTEM_PROMPT if self.role == "adversarial"
            else JUDGE_SYSTEM_PROMPT
        )
        user_message = JUDGE_USER_TEMPLATE.format(
            instance_id=instance_id,
            domain=domain,
            difficulty=difficulty,
            problem_statement=problem_statement,
            expert_knowledge=expert_knowledge,
            n_steps=len(trajectory),
            trajectory_text=format_trajectory(trajectory),
            final_output=json.dumps(final_output, indent=2, default=str)[:2000],
            ground_truth_text=format_ground_truth(ground_truth),
        )

        t0 = time.perf_counter()
        try:
            result = self._agentic_judge_loop(
                system_prompt, user_message, task_data_path
            )
        except Exception as exc:
            logger.warning("Judge %s failed: %s", self.judge_id, exc)
            return JudgeVerdict(
                judge_id=self.judge_id,
                result_correctness=0.0,
                process_quality=0.0,
                code_quality=None,
                safety=4.0,
                confidence=0.0,
                key_findings="",
                verification_performed=False,
                error=str(exc),
                latency_ms=(time.perf_counter() - t0) * 1000,
            )

        latency = (time.perf_counter() - t0) * 1000

        # Skill-based path: result is (verdict_dict, full_text, tokens)
        if isinstance(result, tuple) and len(result) == 3:
            verdict_dict, full_text, tokens = result
            if verdict_dict is not None:
                return parse_judge_verdict(
                    tool_args=verdict_dict,
                    judge_id=self.judge_id,
                    raw_response=full_text,
                    latency_ms=latency,
                    tokens_used=tokens,
                )
            # Skill extraction failed — fall back to legacy regex
            logger.warning(
                "Judge %s: submit_verdict not found, falling back to regex",
                self.judge_id,
            )
            return self._parse_verdict_legacy(full_text, tokens, latency)

        # Legacy path: result is (full_text, tokens)
        raw, tokens = result
        return self._parse_verdict_legacy(raw, tokens, latency)

    # ------------------------------------------------------------------
    # Provider-specific LLM calls (with Skill-based forced output)
    # ------------------------------------------------------------------

    def _agentic_judge_loop(
        self,
        system: str,
        user: str,
        task_data_path: Optional[str],
    ) -> tuple:
        """
        Run a short agentic loop where the judge can call verification tools
        (python_repl, file_read) freely, then is forced to call
        ``submit_verdict`` on the final step.

        Returns (verdict_dict | None, full_text, total_tokens).
        """
        if self.provider == "anthropic":
            return self._anthropic_judge_loop(system, user, task_data_path)
        elif self.provider == "openai":
            return self._openai_judge_loop(system, user, task_data_path)
        else:
            raise ValueError(f"Unsupported judge provider: {self.provider}")

    def _anthropic_judge_loop(
        self, system: str, user: str, task_data_path: Optional[str]
    ) -> tuple:
        import anthropic

        client = anthropic.Anthropic(
            base_url=os.environ.get("ANTHROPIC_BASE_URL") or None
        )
        verification_tools = self._judge_tools(task_data_path)
        skill_tool = JUDGE_SKILL.to_anthropic_tool()
        all_tools = verification_tools + [skill_tool]

        messages: list = [{"role": "user", "content": user}]
        total_tokens = 0
        full_text = ""

        for step in range(self.MAX_JUDGE_STEPS):
            is_final_step = (step == self.MAX_JUDGE_STEPS - 1)

            if is_final_step:
                # Force the verdict via JudgeSkill
                call_tools = [skill_tool]
                call_tool_choice = JUDGE_SKILL.anthropic_tool_choice()
            else:
                # Free agentic loop: judge chooses which tool to call
                call_tools = all_tools
                call_tool_choice = {"type": "auto"}

            resp = client.messages.create(
                model=self.model_id,
                max_tokens=2048,
                temperature=self.temperature,
                system=system,
                tools=call_tools,
                tool_choice=call_tool_choice,
                messages=messages,
            )
            total_tokens += resp.usage.input_tokens + resp.usage.output_tokens

            # Collect text blocks and tool calls
            text_parts: list = []
            tool_calls: list = []
            for block in resp.content:
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "tool_use":
                    tool_calls.append(block)

            full_text += "\n".join(text_parts)

            # Check if judge called submit_verdict (voluntarily or forced)
            for tc in tool_calls:
                if tc.name == "submit_verdict":
                    return (tc.input, full_text, total_tokens)

            # If no tool calls and stop_reason is end_turn, force verdict
            if resp.stop_reason == "end_turn" and not tool_calls:
                # One more call with forced skill
                messages.append({"role": "assistant", "content": resp.content})
                messages.append({
                    "role": "user",
                    "content": "Now submit your final verdict using the submit_verdict tool.",
                })
                resp2 = client.messages.create(
                    model=self.model_id,
                    max_tokens=2048,
                    temperature=self.temperature,
                    system=system,
                    tools=[skill_tool],
                    tool_choice=JUDGE_SKILL.anthropic_tool_choice(),
                    messages=messages,
                )
                total_tokens += resp2.usage.input_tokens + resp2.usage.output_tokens
                for block in resp2.content:
                    if block.type == "text":
                        full_text += block.text
                    elif block.type == "tool_use" and block.name == "submit_verdict":
                        return (block.input, full_text, total_tokens)
                # If still no verdict, return None to trigger fallback
                return (None, full_text, total_tokens)

            # Execute verification tool calls and continue loop
            messages.append({"role": "assistant", "content": resp.content})
            tool_results: list = []
            for tc in tool_calls:
                result = self._execute_judge_tool(tc.name, tc.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": str(result)[:1000],
                })
            messages.append({"role": "user", "content": tool_results})

        return (None, full_text, total_tokens)

    def _openai_judge_loop(
        self, system: str, user: str, task_data_path: Optional[str]
    ) -> tuple:
        import openai

        client = openai.OpenAI()
        verification_tools = self._openai_judge_tools(task_data_path)
        skill_tool = JUDGE_SKILL.to_openai_tool()
        all_tools = verification_tools + [skill_tool]

        messages: list = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        total_tokens = 0
        full_text = ""

        for step in range(self.MAX_JUDGE_STEPS):
            is_final_step = (step == self.MAX_JUDGE_STEPS - 1)

            if is_final_step:
                call_tools = [skill_tool]
                call_tool_choice = JUDGE_SKILL.openai_tool_choice()
            else:
                call_tools = all_tools
                call_tool_choice = "auto"

            resp = client.chat.completions.create(
                model=self.model_id,
                max_tokens=2048,
                temperature=self.temperature,
                tools=call_tools,
                tool_choice=call_tool_choice,
                messages=messages,
            )
            total_tokens += resp.usage.total_tokens
            msg = resp.choices[0].message
            full_text += msg.content or ""

            # Check if model called submit_verdict
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    if tc.function.name == "submit_verdict":
                        args = json.loads(tc.function.arguments)
                        return (args, full_text, total_tokens)

                # Other tool calls: execute and continue
                messages.append(msg)
                for tc in msg.tool_calls:
                    args = json.loads(tc.function.arguments)
                    result = self._execute_judge_tool(tc.function.name, args)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": str(result)[:1000],
                    })
            elif msg.content and not msg.tool_calls:
                # No tool calls, end_turn: force verdict
                messages.append(msg)
                messages.append({
                    "role": "user",
                    "content": "Now submit your final verdict using the submit_verdict function.",
                })
                resp2 = client.chat.completions.create(
                    model=self.model_id,
                    max_tokens=2048,
                    temperature=self.temperature,
                    tools=[skill_tool],
                    tool_choice=JUDGE_SKILL.openai_tool_choice(),
                    messages=messages,
                )
                total_tokens += resp2.usage.total_tokens
                msg2 = resp2.choices[0].message
                full_text += msg2.content or ""
                if msg2.tool_calls:
                    for tc in msg2.tool_calls:
                        if tc.function.name == "submit_verdict":
                            args = json.loads(tc.function.arguments)
                            return (args, full_text, total_tokens)
                return (None, full_text, total_tokens)

        return (None, full_text, total_tokens)

    # ------------------------------------------------------------------
    # Tool execution for the judge
    # ------------------------------------------------------------------

    @staticmethod
    def _execute_judge_tool(tool_name: str, args: Dict[str, Any]) -> str:
        """Execute a tool call made by the judge during verification."""
        if tool_name == "python_repl":
            code = args.get("code", "")
            try:
                import io, contextlib
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    exec(compile(code, "<judge_verify>", "exec"), {})  # noqa: S102
                return buf.getvalue() or "(no output)"
            except Exception as exc:
                return f"ERROR: {exc}"

        elif tool_name == "file_read":
            import pathlib
            path = args.get("path", "")
            try:
                return pathlib.Path(path).read_text("utf-8")[:2000]
            except Exception as exc:
                return f"ERROR: {exc}"

        return f"Unknown tool: {tool_name}"

    @staticmethod
    def _judge_tools(task_data_path: Optional[str]) -> list:
        """Anthropic tool schema for verification tools (not the verdict skill)."""
        return [
            {
                "name": "python_repl",
                "description": "Execute Python code to verify the agent's numerical claims.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Python code to run"}
                    },
                    "required": ["code"],
                },
            },
            {
                "name": "file_read",
                "description": "Read a file (CSV, JSON) from the task data directory to inspect raw data.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path to read"}
                    },
                    "required": ["path"],
                },
            },
        ]

    @staticmethod
    def _openai_judge_tools(task_data_path: Optional[str]) -> list:
        """OpenAI function-calling schema for verification tools."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "python_repl",
                    "description": "Execute Python code to verify the agent's numerical claims.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string"}
                        },
                        "required": ["code"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "file_read",
                    "description": "Read a file from the task data directory.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"}
                        },
                        "required": ["path"],
                    },
                },
            },
        ]

    # ------------------------------------------------------------------
    # Legacy fallback: regex-based verdict parsing
    # ------------------------------------------------------------------

    def _parse_verdict_legacy(
        self, raw_response: str, tokens: int, latency_ms: float
    ) -> JudgeVerdict:
        """Extract the JSON block from the judge's response (legacy regex path)."""
        json_match = re.search(
            r"```json\s*(\{.*?\})\s*```", raw_response, re.DOTALL
        )
        if not json_match:
            json_match = re.search(
                r"(\{[^{}]*\"result_correctness\"[^{}]*\})", raw_response, re.DOTALL
            )

        if not json_match:
            logger.warning("Judge %s: no JSON verdict found in response (legacy)", self.judge_id)
            return JudgeVerdict(
                judge_id=self.judge_id,
                result_correctness=0.0,
                process_quality=0.0,
                code_quality=None,
                safety=4.0,
                confidence=0.0,
                key_findings="Parse error: no JSON block found",
                verification_performed=False,
                raw_response=raw_response,
                latency_ms=latency_ms,
                tokens_used=tokens,
                error="no_json_verdict",
            )

        try:
            data = json.loads(json_match.group(1))
        except json.JSONDecodeError as exc:
            return JudgeVerdict(
                judge_id=self.judge_id,
                result_correctness=0.0,
                process_quality=0.0,
                code_quality=None,
                safety=4.0,
                confidence=0.0,
                key_findings=f"Parse error: {exc}",
                verification_performed=False,
                raw_response=raw_response,
                latency_ms=latency_ms,
                tokens_used=tokens,
                error=str(exc),
            )

        def _clip(v, lo=0, hi=4):
            return max(lo, min(hi, float(v))) if v is not None else None

        return JudgeVerdict(
            judge_id=self.judge_id,
            result_correctness=_clip(data.get("result_correctness", 0)),
            process_quality=_clip(data.get("process_quality", 0)),
            code_quality=_clip(data.get("code_quality")),
            safety=_clip(data.get("safety", 4)),
            confidence=max(0.0, min(1.0, float(data.get("confidence", 0.5)))),
            key_findings=str(data.get("key_findings", "")),
            verification_performed=bool(data.get("verification_performed", False)),
            raw_response=raw_response,
            latency_ms=latency_ms,
            tokens_used=tokens,
        )
