"""
agents.py — LLM-backed data analysis agents.

All providers in one file for easy auditing.
Zero extra dependencies beyond the official provider SDKs:
  openai>=1.0          (pip install openai)
  anthropic>=0.25      (pip install anthropic)
  google-generativeai  (pip install google-generativeai)

Entry point:
    from .agents import build_agent
    agent = build_agent("openai:gpt-4o-mini")
    agent = build_agent("anthropic:claude-sonnet-4-6")
    agent = build_agent("gemini:gemini-1.5-pro")
    agent = build_agent("vllm:Qwen2.5-7B-Instruct")   # OpenAI-compat endpoint
    agent = build_agent("simulated")                   # random baseline
"""
from __future__ import annotations

import abc
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .agent_interface import AgentAction, AgentInterface, SimulatedAgent
from ..models.task import TaskInput
from ..models.trace import ActionType, TraceStep

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool schemas (OpenAI function-calling format — converted per provider below)
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: Dict[str, Dict] = {
    "python_repl": {
        "name": "python_repl",
        "description": (
            "Execute Python code in a sandboxed REPL. "
            "Use this to load data, compute statistics, run tests, and produce results. "
            "stdout is captured and returned."
        ),
        "parameters": {
            "type": "object",
            "properties": {"code": {"type": "string", "description": "Python code to execute."}},
            "required": ["code"],
        },
    },
    "file_read": {
        "name": "file_read",
        "description": "Read a file from the task data directory. Returns file contents as text.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Relative path to the file."}},
            "required": ["path"],
        },
    },
}

_SYSTEM_PROMPT = """\
You are a data analysis agent operating in a sandboxed environment.

## Task
{problem_statement}

## Data
{dataset_preview}

## Domain Knowledge
{expert_knowledge}

## Tools available
{tool_list}

## Rules
1. Think step by step before calling any tool.
2. Verify intermediate results before drawing conclusions.
3. Output key numerical results with explicit labels (e.g. p_value = 0.034).
4. Never use os.system(), subprocess, eval(), or destructive operations.
5. When finished, respond with a JSON object after FINAL_ANSWER containing:
   - "key_values": labeled numeric results
   - "declared_trace": typed action units grounded in your actual work
   Each declared trace step should include step_id, subject, predicate, object,
   intent, operation, inputs, outputs, depends_on, evidence_step, and status.
   Example step: {"step_id":"s3","subject":"agent","predicate":"AGGREGATES","object":"metric_by_group","intent":"compute_metric","operation":"groupby_sum","inputs":["dataset.csv","group","amount"],"outputs":["metric_by_group"],"depends_on":["s1"],"evidence_step":3,"status":"success"}.
"""

# ---------------------------------------------------------------------------
# Typed message history
# ---------------------------------------------------------------------------

@dataclass
class _Msg:
    """One turn in the conversation history."""
    role: str          # "user" | "assistant"
    content: str       # text content
    # Set only when the assistant called a tool:
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    tool_id: str = ""  # correlation id for tool result pairing
    # Set only for tool result messages (role="user" + is_result=True):
    is_result: bool = False


# ---------------------------------------------------------------------------
# Shared base
# ---------------------------------------------------------------------------

class DataAgent(AgentInterface):
    """
    Abstract base for all provider-backed agents.

    Subclasses implement _call(system, history, tool_schemas) and provider_name.
    Everything else — history management, retry, action parsing — lives here.
    """

    MAX_RETRIES = 3
    RETRY_DELAY = 2.0

    def __init__(self, model_id: str, temperature: float = 0.0) -> None:
        self.model_id = model_id
        self.temperature = temperature
        self._task: Optional[TaskInput] = None
        self._history: List[_Msg] = []
        self._done = False
        self._system = ""

    def reset(self, task: TaskInput) -> None:
        self._task = task
        self._history = []
        self._done = False
        allowed = task.environment_config.allowed_tools
        tool_list = "\n".join(
            f"- {name}: {TOOL_SCHEMAS[name]['description']}"
            for name in allowed if name in TOOL_SCHEMAS
        )
        self._system = _SYSTEM_PROMPT.format(
            problem_statement=task.context.problem_statement,
            dataset_preview=task.context.dataset_preview or "(none)",
            expert_knowledge=task.context.expert_knowledge or "None provided.",
            tool_list=tool_list,
        )

    def act(self, step_number: int, observation: str, trace_so_far: List[TraceStep]) -> AgentAction:
        # Append incoming observation
        if step_number == 1:
            self._history.append(_Msg(role="user", content=observation))
        else:
            last = next((m for m in reversed(self._history) if m.role == "assistant"), None)
            if last and last.tool_name:
                self._history.append(_Msg(
                    role="user", content=observation,
                    tool_id=last.tool_id, is_result=True,
                ))
            else:
                self._history.append(_Msg(role="user", content=f"Observation: {observation}"))

        allowed = self._task.environment_config.allowed_tools if self._task else []
        schemas = [TOOL_SCHEMAS[n] for n in allowed if n in TOOL_SCHEMAS]

        content, tool_name, tool_args, tokens_in, tokens_out = self._call_with_retry(schemas)

        tool_id = f"call_{len(self._history)}" if tool_name else ""
        self._history.append(_Msg(
            role="assistant", content=content or "",
            tool_name=tool_name, tool_args=tool_args, tool_id=tool_id,
        ))

        return self._to_action(content, tool_name, tool_args, tokens_in, tokens_out)

    def is_done(self) -> bool:
        return self._done

    # -- retry wrapper -------------------------------------------------------

    def _call_with_retry(
        self, schemas: List[Dict]
    ) -> Tuple[str, Optional[str], Optional[Dict], int, int]:
        for attempt in range(self.MAX_RETRIES):
            try:
                return self._call(self._system, self._history, schemas)
            except Exception as exc:
                if attempt < self.MAX_RETRIES - 1:
                    wait = self.RETRY_DELAY * (attempt + 1)
                    logger.warning("LLM attempt %d/%d failed: %s — retry in %.1fs",
                                   attempt + 1, self.MAX_RETRIES, exc, wait)
                    time.sleep(wait)
                else:
                    logger.error("LLM failed after %d attempts: %s", self.MAX_RETRIES, exc)
                    return (f"ERROR: {exc}", None, None, 0, 0)
        return ("", None, None, 0, 0)

    # -- action parser -------------------------------------------------------

    def _to_action(
        self,
        content: str,
        tool_name: Optional[str],
        tool_args: Optional[Dict],
        tokens_in: int,
        tokens_out: int,
    ) -> AgentAction:
        if tool_name:
            atype = {"python_repl": ActionType.CODE_EXEC,
                     "file_read": ActionType.FILE_READ}.get(tool_name, ActionType.TOOL_CALL)
            return AgentAction(
                action_type=atype, action=f"Call {tool_name}",
                thought=content or "", tool_name=tool_name, tool_args=tool_args or {},
                tokens_in=tokens_in, tokens_out=tokens_out,
            )
        low = (content or "").lower()
        if "final_answer:" in low or "final answer:" in low:
            self._done = True
            return AgentAction(
                action_type=ActionType.FINAL_ANSWER, action="Submit final answer",
                thought=content, tokens_in=tokens_in, tokens_out=tokens_out,
            )
        return AgentAction(
            action_type=ActionType.THINK, action="Think",
            thought=content or "(no response)", tokens_in=tokens_in, tokens_out=tokens_out,
        )

    # -- abstract ------------------------------------------------------------

    @abc.abstractmethod
    def _call(
        self,
        system: str,
        history: List[_Msg],
        tool_schemas: List[Dict],
    ) -> Tuple[str, Optional[str], Optional[Dict], int, int]:
        """
        Call the LLM. Return (content, tool_name, tool_args, tokens_in, tokens_out).
        tool_name / tool_args are None when the model replies with text only.
        """

    @property
    @abc.abstractmethod
    def provider_name(self) -> str: ...


# ---------------------------------------------------------------------------
# OpenAI  (also used for vLLM / any OpenAI-compatible endpoint)
# ---------------------------------------------------------------------------

def _to_openai_messages(history: List[_Msg]) -> List[Dict]:
    """Convert _Msg history → OpenAI API message list."""
    out = []
    for msg in history:
        if msg.role == "user" and msg.is_result:
            # tool result — find the matching tool_call id from the previous assistant turn
            call_id = msg.tool_id or "call_0"
            for prev in reversed(out):
                if prev.get("role") == "assistant" and prev.get("tool_calls"):
                    call_id = prev["tool_calls"][0]["id"]
                    break
            out.append({"role": "tool", "tool_call_id": call_id, "content": msg.content})
        elif msg.role == "user":
            out.append({"role": "user", "content": msg.content})
        elif msg.role == "assistant" and msg.tool_name:
            call_id = msg.tool_id or f"call_{len(out)}"
            out.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [{
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": msg.tool_name,
                        "arguments": json.dumps(msg.tool_args or {}),
                    },
                }],
            })
        else:
            out.append({"role": "assistant", "content": msg.content})
    return out


class OpenAIAgent(DataAgent):
    """GPT-4o / GPT-4o-mini / any OpenAI-compatible endpoint (vLLM, relay)."""

    def __init__(
        self,
        model_id: str = "gpt-4.1-mini",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        super().__init__(model_id, temperature)
        self._max_tokens = max_tokens
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._base_url = base_url or os.environ.get("OPENAI_BASE_URL")
        self._client = None

    @property
    def provider_name(self) -> str:
        return "openai"

    def _get_client(self):
        if self._client is None:
            try:
                import openai
            except ImportError:
                raise ImportError("Run: pip install openai>=1.0.0")
            kw: Dict[str, Any] = {"api_key": self._api_key}
            if self._base_url:
                kw["base_url"] = self._base_url
            self._client = openai.OpenAI(**kw)
        return self._client

    def _call(
        self, system: str, history: List[_Msg], tool_schemas: List[Dict]
    ) -> Tuple[str, Optional[str], Optional[Dict], int, int]:
        messages = [{"role": "system", "content": system}] + _to_openai_messages(history)
        tools = [{"type": "function", "function": {
            "name": s["name"], "description": s["description"], "parameters": s["parameters"],
        }} for s in tool_schemas] or None

        kw: Dict[str, Any] = {
            "model": self.model_id,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self._max_tokens,
        }
        if tools:
            kw["tools"] = tools
            kw["tool_choice"] = "auto"

        resp = self._get_client().chat.completions.create(**kw)
        usage = resp.usage
        tokens_in = usage.prompt_tokens if usage else 0
        tokens_out = usage.completion_tokens if usage else 0
        msg = resp.choices[0].message
        content = msg.content or ""
        tool_name, tool_args = None, None
        if msg.tool_calls:
            tc = msg.tool_calls[0]
            tool_name = tc.function.name
            try:
                tool_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                tool_args = {"raw": tc.function.arguments}
        return content, tool_name, tool_args, tokens_in, tokens_out


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------

def _to_anthropic_messages(history: List[_Msg]) -> List[Dict]:
    """Convert _Msg history → Anthropic API message list."""
    out = []
    for msg in history:
        if msg.role == "user" and msg.is_result:
            # tool_result block — find the matching tool_use id
            tool_use_id = "tool_0"
            for prev in reversed(out):
                if prev.get("role") == "assistant":
                    for block in (prev["content"] if isinstance(prev.get("content"), list) else []):
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            tool_use_id = block["id"]
                    break
            out.append({"role": "user", "content": [{
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": msg.content,
            }]})
        elif msg.role == "user":
            out.append({"role": "user", "content": msg.content})
        elif msg.role == "assistant" and msg.tool_name:
            blocks: List[Dict] = []
            if msg.content:
                blocks.append({"type": "text", "text": msg.content})
            blocks.append({
                "type": "tool_use",
                "id": msg.tool_id or f"tool_{len(out)}",
                "name": msg.tool_name,
                "input": msg.tool_args or {},
            })
            out.append({"role": "assistant", "content": blocks})
        else:
            out.append({"role": "assistant", "content": msg.content})
    return out


class AnthropicAgent(DataAgent):
    """Claude Sonnet / Haiku / Opus with optional extended thinking."""

    def __init__(
        self,
        model_id: str = "claude-sonnet-4-6",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        thinking_budget: Optional[int] = None,   # enable extended thinking when set
    ) -> None:
        super().__init__(model_id, temperature)
        self._max_tokens = max_tokens
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._base_url = base_url or os.environ.get("ANTHROPIC_BASE_URL")
        self._thinking_budget = thinking_budget
        self._client = None

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError:
                raise ImportError("Run: pip install anthropic>=0.25.0")
            kw: Dict[str, Any] = {"api_key": self._api_key}
            if self._base_url:
                kw["base_url"] = self._base_url
            self._client = anthropic.Anthropic(**kw)
        return self._client

    def _call(
        self, system: str, history: List[_Msg], tool_schemas: List[Dict]
    ) -> Tuple[str, Optional[str], Optional[Dict], int, int]:
        messages = _to_anthropic_messages(history)
        tools = [{"name": s["name"], "description": s["description"],
                  "input_schema": s["parameters"]} for s in tool_schemas]

        kw: Dict[str, Any] = {
            "model": self.model_id,
            "max_tokens": self._max_tokens,
            "system": system,
            "messages": messages,
        }
        if tools:
            kw["tools"] = tools
        if self._thinking_budget:
            kw["thinking"] = {"type": "enabled", "budget_tokens": self._thinking_budget}
            kw["temperature"] = 1.0   # required when thinking is enabled
        else:
            kw["temperature"] = min(self.temperature, 1.0)

        resp = self._get_client().messages.create(**kw)
        tokens_in = resp.usage.input_tokens
        tokens_out = resp.usage.output_tokens

        text, thinking, tool_name, tool_args = "", "", None, None
        for block in resp.content:
            if block.type == "thinking":
                thinking = block.thinking
            elif block.type == "text":
                text += block.text
            elif block.type == "tool_use":
                tool_name = block.name
                tool_args = block.input if isinstance(block.input, dict) else {}

        content = (thinking + "\n" + text).strip() if thinking else text
        return content, tool_name, tool_args, tokens_in, tokens_out


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------

def _to_gemini_messages(history: List[_Msg]):
    """Convert _Msg history → Gemini SDK Content list."""
    from google.generativeai.types import content_types
    out = []
    for msg in history:
        if msg.role == "user" and msg.is_result:
            out.append(content_types.to_contents({
                "role": "user",
                "parts": [{"function_response": {
                    "name": "tool_result",
                    "response": {"content": msg.content},
                }}],
            }))
        elif msg.role == "user":
            out.append({"role": "user", "parts": [{"text": msg.content}]})
        elif msg.role == "assistant" and msg.tool_name:
            parts = []
            if msg.content:
                parts.append({"text": msg.content})
            parts.append({"function_call": {"name": msg.tool_name, "args": msg.tool_args or {}}})
            out.append({"role": "model", "parts": parts})
        else:
            out.append({"role": "model", "parts": [{"text": msg.content}]})
    return out


class GeminiAgent(DataAgent):
    """Google Gemini 1.5 Pro / Flash via google-generativeai SDK."""

    def __init__(
        self,
        model_id: str = "gemini-1.5-pro",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        api_key: Optional[str] = None,
    ) -> None:
        super().__init__(model_id, temperature)
        self._max_tokens = max_tokens
        self._api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        self._model = None

    @property
    def provider_name(self) -> str:
        return "gemini"

    def _get_model(self, tool_schemas: List[Dict]):
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError("Run: pip install google-generativeai")
        genai.configure(api_key=self._api_key)
        tools = [{
            "function_declarations": [{
                "name": s["name"],
                "description": s["description"],
                "parameters": s["parameters"],
            } for s in tool_schemas]
        }] if tool_schemas else None
        return genai.GenerativeModel(
            model_name=self.model_id,
            tools=tools,
            generation_config={"temperature": self.temperature, "max_output_tokens": self._max_tokens},
        )

    def _call(
        self, system: str, history: List[_Msg], tool_schemas: List[Dict]
    ) -> Tuple[str, Optional[str], Optional[Dict], int, int]:
        model = self._get_model(tool_schemas)
        # Gemini takes system instruction separately; prepend as first user turn if needed
        contents = _to_gemini_messages(history)
        resp = model.generate_content(
            contents,
            generation_config={"system_instruction": system},
        )
        usage = getattr(resp, "usage_metadata", None)
        tokens_in = getattr(usage, "prompt_token_count", 0) or 0
        tokens_out = getattr(usage, "candidates_token_count", 0) or 0

        content, tool_name, tool_args = "", None, None
        for part in resp.candidates[0].content.parts:
            if hasattr(part, "function_call") and part.function_call.name:
                tool_name = part.function_call.name
                tool_args = dict(part.function_call.args)
            elif hasattr(part, "text"):
                content += part.text
        return content, tool_name, tool_args, tokens_in, tokens_out


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_PROVIDERS = {
    "openai":     OpenAIAgent,
    "vllm":       OpenAIAgent,   # OpenAI-compatible endpoint; set OPENAI_BASE_URL
    "anthropic":  AnthropicAgent,
    "anthropic-thinking": lambda model_id, **kw: AnthropicAgent(
        model_id=model_id, thinking_budget=8192, max_tokens=16000, temperature=1.0, **kw
    ),
    "gemini":     GeminiAgent,
    "deepseek": lambda model_id="deepseek-chat", temperature=0.0, **kw: OpenAIAgent(
        model_id=model_id,
        temperature=temperature,
        base_url="https://api.deepseek.com",
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
        **kw,
    ),
    "simulated":  lambda **_: SimulatedAgent(),
}

def _build_native_agent(model_id: str, temperature: float = 0.0) -> AgentInterface:
    from .llm_agents.native_agent import NativeCodeAgent
    return NativeCodeAgent(model_id=model_id, temperature=temperature)

_PROVIDERS["native"] = _build_native_agent


def _build_metagpt_agent(model_id: str, temperature: float = 0.0) -> AgentInterface:
    from .adapters.metagpt_adapter import MetaGPTAdapter
    return MetaGPTAdapter(model_id=model_id, temperature=temperature)

_PROVIDERS["metagpt"] = _build_metagpt_agent


def _build_oi_agent(model_id: str, temperature: float = 0.0) -> AgentInterface:
    from .adapters.open_interpreter_adapter import OpenInterpreterAdapter
    return OpenInterpreterAdapter(model_id=model_id, temperature=temperature)

_PROVIDERS["open-interpreter"] = _build_oi_agent


def build_agent(agent_spec: str, temperature: float = 0.0) -> AgentInterface:
    """
    Parse '--agent' CLI flag and return a configured agent.

    Format:  '<provider>:<model_id>'   or   'simulated'
    Examples:
        simulated
        openai:gpt-4o-mini
        openai:gpt-4o
        anthropic:claude-sonnet-4-6
        anthropic-thinking:claude-sonnet-4-6
        gemini:gemini-1.5-pro
        vllm:Qwen2.5-7B-Instruct        (set OPENAI_BASE_URL to your vLLM endpoint)
    """
    if agent_spec == "simulated":
        return SimulatedAgent()

    if ":" not in agent_spec:
        raise ValueError(
            f"Invalid agent spec '{agent_spec}'. "
            f"Use 'simulated' or '<provider>:<model_id>'. "
            f"Supported providers: {', '.join(k for k in _PROVIDERS if k != 'simulated')}."
        )

    provider, model_id = agent_spec.split(":", 1)
    provider = provider.lower().strip()

    if provider not in _PROVIDERS:
        raise ValueError(
            f"Unknown provider '{provider}'. "
            f"Supported: {', '.join(k for k in _PROVIDERS if k != 'simulated')}."
        )

    cls = _PROVIDERS[provider]
    if provider == "simulated":
        return SimulatedAgent()
    if callable(cls) and not isinstance(cls, type):
        # lambda factory (e.g. anthropic-thinking)
        return cls(model_id=model_id, temperature=temperature)
    return cls(model_id=model_id, temperature=temperature)
