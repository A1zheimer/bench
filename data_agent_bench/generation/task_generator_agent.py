"""
TaskGeneratorAgent: LLM-backed agent that dynamically generates benchmark tasks.

Pipeline per task:
  1. Plan task concept (LLM + optional web_search)
  2. Generate synthetic dataset via python_repl
  3. Solve the task to produce ground truth
  4. Verify solution by re-running in fresh namespace
  5. Submit structured output via TaskGenSkill (forced tool_choice)
  6. Package to disk as standard task folder

Uses the ``submit_task`` Skill to guarantee well-formed output.
"""
from __future__ import annotations

import contextlib
import io
import json
import logging
import os
import pathlib
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..models.task import TaskInput
from ..skills.taskgen_skill import TASKGEN_SKILL, generate_canary_value, parse_generated_task
from .generation_prompts import (
    TASK_GENERATOR_SYSTEM_PROMPT,
    TASK_GENERATOR_TAG_GUIDANCE,
    TASK_GENERATOR_NO_TAG_GUIDANCE,
)

logger = logging.getLogger(__name__)


@dataclass
class GeneratedTask:
    """Result of a successful task generation."""
    instance_id: str
    task_json: Dict[str, Any]
    ground_truth: Dict[str, Any]
    data_files: List[str]
    data_generation_code: str
    solution_code: str
    canary_value: float
    verified: bool
    generation_trace: List[Dict[str, Any]] = field(default_factory=list)


class TaskGeneratorAgent:
    """
    LLM-backed agent that generates benchmark tasks using a multi-step
    agentic pipeline with forced structured output via TaskGenSkill.

    Supports 'anthropic' and 'openai' providers.
    """

    MAX_GENERATION_STEPS = 8  # max LLM calls per task generation

    def __init__(
        self,
        provider: str,
        model_id: str,
        temperature: float = 0.7,
        output_root: str = "./tasks",
        api_key: Optional[str] = None,
    ) -> None:
        self.provider = provider
        self.model_id = model_id
        self.temperature = temperature
        self.output_root = pathlib.Path(output_root)
        self._api_key = api_key

    def generate(
        self,
        domain: str,
        difficulty: str,
        task_number: int,
        tags: Optional[List[str]] = None,
    ) -> GeneratedTask:
        """
        Generate a single benchmark task.

        Args:
            domain: Target domain (e.g. "Finance", "Biomedical").
            difficulty: "Easy", "Medium", or "Hard".
            task_number: Numeric ID for the task (used in instance_id).
            tags: Optional topic constraints.

        Returns:
            GeneratedTask with all data ready for disk serialization.
        """
        trace: List[Dict[str, Any]] = []

        # Build system prompt with difficulty constraints
        from .difficulty_spec import get_prompt_constraints

        tag_guidance = (
            TASK_GENERATOR_TAG_GUIDANCE.format(tags=", ".join(tags))
            if tags
            else TASK_GENERATOR_NO_TAG_GUIDANCE.format(domain=domain)
        )
        difficulty_constraints = get_prompt_constraints(difficulty)
        system_prompt = TASK_GENERATOR_SYSTEM_PROMPT.format(
            domain=domain,
            difficulty=difficulty,
            tag_guidance=tag_guidance,
            difficulty_constraints=difficulty_constraints,
        )

        # Build initial user message
        user_msg = (
            f"Generate a {difficulty} difficulty benchmark task for the {domain} domain.\n"
        )
        if tags:
            user_msg += f"Focus on these topics: {', '.join(tags)}.\n"

        # Select seed dataset from manifest (domain + difficulty aware)
        seed_info = self._select_seed_dataset(domain, difficulty)
        # Resolve a temp workspace dir for this generation run
        import tempfile, shutil
        _gen_tmpdir = pathlib.Path(tempfile.mkdtemp(prefix="dab_gen_"))
        self._gen_tmpdir = _gen_tmpdir  # save for cleanup

        if seed_info:
            seed_path, seed_meta = seed_info
            try:
                import pandas as pd
                df = pd.read_csv(seed_path, nrows=5)
                preview = df.to_markdown(index=False)
                # Copy seed file to tmpdir as 'seed_data.csv' so LLM can use a simple path
                seed_local = _gen_tmpdir / "seed_data.csv"
                shutil.copy2(seed_path, seed_local)

                # Include task suggestions from manifest for this difficulty
                suggestions = seed_meta.get("example_tasks", {}).get(difficulty, [])
                suggestion_text = ""
                if suggestions:
                    suggestion_text = (
                        f"\nSuggested task ideas for {difficulty} difficulty:\n"
                        + "\n".join(f"  - {s}" for s in suggestions) + "\n"
                        "You may use one of these or design a similar task.\n"
                    )
                user_msg += (
                    f"\n## Seed Data (REQUIRED)\n"
                    f"The seed dataset is available at: `seed_data.csv` (already in your working directory)\n"
                    f"Load it with: `pd.read_csv('seed_data.csv')`\n"
                    f"Columns: {', '.join(seed_meta.get('columns', []))}\n"
                    f"Rows: {seed_meta.get('rows', '?')}\n"
                    f"Preview:\n{preview}\n"
                    f"{suggestion_text}"
                    f"\nTransform this data by renaming columns, injecting noise/canary values, "
                    f"and applying difficulty-appropriate mutations. "
                    f"Save result as `dataset.csv`.\n"
                )
            except Exception as e:
                logger.warning("Could not load seed dataset %s: %s", seed_path, e)
        else:
            logger.warning("No seed dataset found for domain=%s difficulty=%s", domain, difficulty)

        user_msg += (
            "\nWorkflow:\n"
            "1. First use python_repl to load the seed data and mutate it into dataset.csv\n"
            "2. Then use python_repl to solve the task and get ground truth values\n"
            "3. Finally call submit_task with the complete specification\n"
        )

        # Run the agentic generation loop
        messages: List[Dict[str, Any]] = [{"role": "user", "content": user_msg}]

        verification_tools = self._verification_tools()
        skill_tool_args = None

        for step in range(self.MAX_GENERATION_STEPS):
            is_final_step = (step == self.MAX_GENERATION_STEPS - 1)

            if is_final_step:
                # Force structured output via TaskGenSkill
                messages.append({
                    "role": "user",
                    "content": (
                        "Now submit the complete task using the submit_task tool. "
                        "Include all fields: task_metadata, context, environment_config, "
                        "ground_truth, data_generation_code, and solution_code."
                    ),
                })
                result = self._call_with_forced_skill(system_prompt, messages)
                skill_tool_args = result
                trace.append({"step": step + 1, "action": "submit_task", "forced": True})
                break

            # Normal step: LLM can use tools or submit voluntarily
            content, tool_name, tool_args, t_in, t_out = self._llm_call(
                system_prompt, messages, verification_tools
            )

            if tool_name == "submit_task":
                # Agent voluntarily submitted — use as structured output
                skill_tool_args = tool_args
                trace.append({"step": step + 1, "action": "submit_task", "forced": False})
                break

            if tool_name:
                # Execute verification tool
                tool_result = self._execute_tool(tool_name, tool_args or {})
                trace_entry = {
                    "step": step + 1,
                    "action": tool_name,
                    "args_preview": str(tool_args)[:200] if tool_args else "",
                    "result_preview": str(tool_result)[:200],
                }
                # Store full code for python_repl so we can recover data_generation_code
                if tool_name == "python_repl" and tool_args:
                    trace_entry["full_code"] = tool_args.get("code", "")
                trace.append(trace_entry)
                # Add assistant + tool result to conversation
                messages.append({"role": "assistant", "content": content or ""})
                messages.append({
                    "role": "user",
                    "content": f"Tool result ({tool_name}):\n{tool_result}",
                })
            else:
                # Text-only response (thinking)
                trace.append({
                    "step": step + 1,
                    "action": "think",
                    "content_preview": (content or "")[:200],
                })
                messages.append({"role": "assistant", "content": content or ""})
                messages.append({
                    "role": "user",
                    "content": "Continue. When ready, call submit_task.",
                })

        if skill_tool_args is None:
            raise RuntimeError("Task generation failed: no submit_task call produced")

        # instance_id must match [A-Z][A-Z0-9_]*_\d+ (end with digits)
        instance_id = f"DS_TASK_{task_number:03d}"
        parsed = parse_generated_task(skill_tool_args, instance_id)

        # Collect all successful python_repl executions from trace
        successful_codes = [
            entry.get("full_code", "")
            for entry in trace
            if entry.get("action") == "python_repl"
            and "ERROR" not in entry.get("result_preview", "ERROR")
            and entry.get("full_code", "").strip()
        ]

        # Fallback: if data_generation_code is empty, use first successful code block
        if not parsed["data_generation_code"].strip() and successful_codes:
            parsed["data_generation_code"] = successful_codes[0]
            logger.info("Extracted data_generation_code from trace for %s", instance_id)

        # Fallback: if solution_code is empty, use last successful code block
        # (heuristic: the last executed code most likely computed the ground truth)
        if not parsed["solution_code"].strip() and successful_codes:
            parsed["solution_code"] = successful_codes[-1]
            logger.info("Extracted solution_code from last trace step for %s", instance_id)

        # Verify by re-running solution code
        verified = self._verify_solution(
            parsed["data_generation_code"],
            parsed["solution_code"],
            parsed["ground_truth"]["key_values"],
        )

        return GeneratedTask(
            instance_id=instance_id,
            task_json=parsed["task_json"],
            ground_truth=parsed["ground_truth"],
            data_files=[],
            data_generation_code=parsed["data_generation_code"],
            solution_code=parsed["solution_code"],
            canary_value=parsed["canary_value"],
            verified=verified,
            generation_trace=trace,
        )

    def package_to_disk(self, task: GeneratedTask) -> str:
        """
        Write a GeneratedTask to the standard folder structure.

        Returns the path to the task directory.
        """
        task_dir = self.output_root / task.instance_id
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "data").mkdir(exist_ok=True)
        (task_dir / "ground_truth").mkdir(exist_ok=True)

        # Write task.json
        task_json_path = task_dir / "task.json"
        with open(task_json_path, "w", encoding="utf-8") as f:
            json.dump(task.task_json, f, indent=2, ensure_ascii=False)

        # Write ground truth
        gt_path = task_dir / "ground_truth" / "expected_output.json"
        with open(gt_path, "w", encoding="utf-8") as f:
            json.dump(task.ground_truth, f, indent=2, ensure_ascii=False)

        # Generate data by executing the data generation code
        data_path = task_dir / "data" / "dataset.csv"

        # Check if dataset.csv was already produced in tmpdir during the generation loop
        import shutil as _shutil
        _gen_tmpdir = getattr(self, "_gen_tmpdir", None)
        _tmpdir_dataset = _gen_tmpdir / "dataset.csv" if _gen_tmpdir else None
        _copied_from_tmpdir = False
        if _tmpdir_dataset and _tmpdir_dataset.exists() and _tmpdir_dataset.stat().st_size > 0:
            _shutil.copy2(_tmpdir_dataset, data_path)
            task.data_files.append(str(data_path))
            logger.info("Copied dataset.csv from generation tmpdir to %s", data_path)
            _copied_from_tmpdir = True
        try:
            _shutil.rmtree(str(_gen_tmpdir))
        except Exception:
            pass

        if not _copied_from_tmpdir:
            # Fall back to re-executing data_generation_code
            try:
                namespace = {"__file_path__": str(data_path)}
                # Rewrite any .to_csv('...') calls to write to 'data/dataset.csv'
                patched_code = re.sub(
                    r"""\.to_csv\(\s*['"][^'"]+['"]\s*""",
                    ".to_csv('data/dataset.csv'",
                    task.data_generation_code,
                )
                # Fix deprecated pandas date offset aliases (pandas >= 2.2)
                for old_freq, new_freq in [("'M'", "'ME'"), ('"M"', '"ME"'),
                                            ("'Y'", "'YE'"), ('"Y"', '"YE"'),
                                            ("'Q'", "'QE'"), ('"Q"', '"QE"'),
                                            ("'A'", "'YE'"), ('"A"', '"YE"')]:
                    patched_code = patched_code.replace(
                        f"freq={old_freq}", f"freq={new_freq}"
                    ).replace(
                        f"freq = {old_freq}", f"freq = {new_freq}"
                    )
                # Run in the task directory so relative paths work
                prev_cwd = os.getcwd()
                os.chdir(str(task_dir))
                try:
                    code = (
                        "import os; os.makedirs('data', exist_ok=True)\n"
                        "_OUTPUT_PATH = 'data/dataset.csv'\n"
                        + patched_code
                    )
                    # If code doesn't save to CSV at all, append auto-save
                    if "to_csv" not in task.data_generation_code:
                        code += "\nimport pandas as _pd\n"
                        code += "for _v in list(locals().values()):\n"
                        code += "    if isinstance(_v, _pd.DataFrame):\n"
                        code += "        _v.to_csv('data/dataset.csv', index=False); break\n"
                    exec(compile(code, "<data_gen>", "exec"), namespace)  # noqa: S102
                finally:
                    os.chdir(prev_cwd)
                if data_path.exists() and data_path.stat().st_size > 0:
                    task.data_files.append(str(data_path))
                else:
                    logger.warning("Data generation ran but %s is empty/missing", data_path)
            except Exception as exc:
                logger.warning("Data generation failed for %s: %s", task.instance_id, exc)
                # Write the code as reference
                code_path = task_dir / "data" / "generate_data.py"
                code_path.write_text(task.data_generation_code, encoding="utf-8")
                task.data_files.append(str(code_path))

        # Write generation metadata
        meta_path = task_dir / "generation_meta.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "generator": f"{self.provider}:{self.model_id}",
                "temperature": self.temperature,
                "canary_value": task.canary_value,
                "verified": task.verified,
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "solution_code": task.solution_code,
                "data_generation_code": task.data_generation_code,
                "trace": task.generation_trace,
            }, f, indent=2)

        return str(task_dir)

    # ------------------------------------------------------------------
    # Provider-specific LLM calls
    # ------------------------------------------------------------------

    def _llm_call(
        self,
        system: str,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> Tuple[str, Optional[str], Optional[Dict], int, int]:
        """Call LLM with tools (auto choice). Returns (content, tool_name, tool_args, t_in, t_out)."""
        if self.provider == "anthropic":
            return self._anthropic_call(system, messages, tools)
        elif self.provider == "openai":
            return self._openai_call(system, messages, tools)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def _call_with_forced_skill(
        self,
        system: str,
        messages: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Call LLM with forced TaskGenSkill. Returns the tool_args dict."""
        if self.provider == "anthropic":
            return self._anthropic_forced_skill(system, messages)
        elif self.provider == "openai":
            return self._openai_forced_skill(system, messages)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def _anthropic_call(
        self, system: str, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]
    ) -> Tuple[str, Optional[str], Optional[Dict], int, int]:
        import anthropic
        client = anthropic.Anthropic(api_key=self._api_key, base_url=os.environ.get("ANTHROPIC_BASE_URL") or None)

        anthropic_tools = [
            {"name": t["name"], "description": t["description"],
             "input_schema": t.get("input_schema", t.get("parameters", {}))}
            for t in tools
        ]
        # Add submit_task as a voluntary option
        anthropic_tools.append(TASKGEN_SKILL.to_anthropic_tool())

        api_messages = [{"role": m["role"], "content": m["content"]} for m in messages]
        resp = client.messages.create(
            model=self.model_id,
            max_tokens=4096,
            temperature=self.temperature,
            system=system,
            tools=anthropic_tools,
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

    def _anthropic_forced_skill(
        self, system: str, messages: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        import anthropic
        client = anthropic.Anthropic(api_key=self._api_key, base_url=os.environ.get("ANTHROPIC_BASE_URL") or None)

        api_messages = [{"role": m["role"], "content": m["content"]} for m in messages]
        resp = client.messages.create(
            model=self.model_id,
            max_tokens=4096,
            temperature=self.temperature,
            system=system,
            tools=[TASKGEN_SKILL.to_anthropic_tool()],
            tool_choice=TASKGEN_SKILL.anthropic_tool_choice(),
            messages=api_messages,
        )

        for block in resp.content:
            if block.type == "tool_use" and block.name == "submit_task":
                return block.input

        raise RuntimeError("Forced submit_task but no tool_use block in response")

    def _openai_call(
        self, system: str, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]
    ) -> Tuple[str, Optional[str], Optional[Dict], int, int]:
        import openai
        client = openai.OpenAI(api_key=self._api_key, base_url=os.environ.get("OPENAI_BASE_URL"))

        openai_tools = [
            {"type": "function", "function": {
                "name": t["name"], "description": t["description"],
                "parameters": t.get("parameters", t.get("input_schema", {})),
            }}
            for t in tools
        ]
        openai_tools.append(TASKGEN_SKILL.to_openai_tool())

        api_messages = [{"role": "system", "content": system}]
        api_messages.extend({"role": m["role"], "content": m["content"]} for m in messages)

        resp = client.chat.completions.create(
            model=self.model_id,
            max_tokens=4096,
            temperature=self.temperature,
            tools=openai_tools,
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

    def _openai_forced_skill(
        self, system: str, messages: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        import openai
        client = openai.OpenAI(api_key=self._api_key, base_url=os.environ.get("OPENAI_BASE_URL"))

        api_messages = [{"role": "system", "content": system}]
        api_messages.extend({"role": m["role"], "content": m["content"]} for m in messages)

        resp = client.chat.completions.create(
            model=self.model_id,
            max_tokens=4096,
            temperature=self.temperature,
            tools=[TASKGEN_SKILL.to_openai_tool()],
            tool_choice=TASKGEN_SKILL.openai_tool_choice(),
            messages=api_messages,
        )

        msg = resp.choices[0].message
        if msg.tool_calls:
            for tc in msg.tool_calls:
                if tc.function.name == "submit_task":
                    return json.loads(tc.function.arguments)

        raise RuntimeError("Forced submit_task but no tool call in response")

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Execute a tool call made by the generator agent."""
        if tool_name == "python_repl":
            code = args.get("code", "")
            try:
                buf = io.StringIO()
                # Run in tmpdir so seed_data.csv and dataset.csv are accessible
                tmpdir = getattr(self, "_gen_tmpdir", None)
                prev_cwd = os.getcwd()
                if tmpdir and tmpdir.exists():
                    os.chdir(str(tmpdir))
                try:
                    with contextlib.redirect_stdout(buf):
                        exec(compile(code, "<task_gen>", "exec"), {})  # noqa: S102
                finally:
                    os.chdir(prev_cwd)
                return buf.getvalue() or "(no output)"
            except Exception as exc:
                return f"ERROR: {exc}"

        elif tool_name == "web_search":
            query = args.get("query", "")
            return f"(web_search simulated for: {query} — use domain expertise instead)"

        return f"Unknown tool: {tool_name}"

    @staticmethod
    def _verification_tools() -> List[Dict[str, Any]]:
        """Tools available during the generation loop."""
        return [
            {
                "name": "python_repl",
                "description": "Execute Python code to generate data or solve the task.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Python code to execute"}
                    },
                    "required": ["code"],
                },
            },
            {
                "name": "web_search",
                "description": "Search for domain-specific methodology or statistical references.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"}
                    },
                    "required": ["query"],
                },
            },
        ]

    # ------------------------------------------------------------------
    # Seed dataset selection
    # ------------------------------------------------------------------

    def _select_seed_dataset(
        self, domain: str, difficulty: str
    ) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Select a seed dataset from manifest.json based on domain and difficulty.

        Returns (absolute_path, metadata_dict) or None if no match.
        Prioritizes exact domain match, falls back to cross-domain datasets.
        """
        seed_dir = pathlib.Path(__file__).parent.parent.parent / "seed_datasets"
        manifest_path = seed_dir / "manifest.json"
        if not manifest_path.exists():
            return None

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception:
            return None

        import random

        # Filter: matching domain + difficulty in range
        candidates = []
        for rel_path, meta in manifest.items():
            if meta.get("domain", "") != domain:
                continue
            if difficulty not in meta.get("difficulty_range", []):
                continue
            abs_path = str(seed_dir / rel_path)
            if pathlib.Path(abs_path).exists():
                candidates.append((abs_path, meta))

        # Fallback: any dataset that supports this difficulty
        if not candidates:
            for rel_path, meta in manifest.items():
                if difficulty not in meta.get("difficulty_range", []):
                    continue
                abs_path = str(seed_dir / rel_path)
                if pathlib.Path(abs_path).exists():
                    candidates.append((abs_path, meta))

        if not candidates:
            return None

        return random.choice(candidates)

    # ------------------------------------------------------------------
    # Solution verification
    # ------------------------------------------------------------------

    def _verify_solution(
        self,
        data_gen_code: str,
        solution_code: str,
        expected_key_values: Dict[str, float],
    ) -> bool:
        """
        Re-run solution code in the generation tmpdir and verify key_values match.
        Returns True if verification passes.
        """
        if not solution_code:
            return False

        try:
            # Run in tmpdir if available (has seed_data.csv + dataset.csv)
            _gen_tmpdir = getattr(self, "_gen_tmpdir", None)
            prev_cwd = os.getcwd()
            if _gen_tmpdir and _gen_tmpdir.exists():
                os.chdir(str(_gen_tmpdir))
            try:
                namespace: Dict[str, Any] = {}
                # Run data generation if we don't already have dataset.csv
                if data_gen_code and not pathlib.Path("dataset.csv").exists():
                    exec(compile(data_gen_code, "<verify_data>", "exec"), namespace)  # noqa: S102
                # Run solution
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    exec(compile(solution_code, "<verify_solution>", "exec"), namespace)  # noqa: S102
                output = buf.getvalue()
            finally:
                os.chdir(prev_cwd)

            # Check if expected key values appear in output
            matched = 0
            for key, expected in expected_key_values.items():
                # Look for "key = value" or "key: value" patterns
                pattern = rf"{re.escape(key)}\s*[=:]\s*(-?\d+\.?\d*)"
                match = re.search(pattern, output, re.IGNORECASE)
                if match:
                    actual = float(match.group(1))
                    rel_err = abs(actual - expected) / max(abs(expected), 1e-10)
                    if rel_err < 0.1:  # 10% tolerance for verification
                        matched += 1

            # Pass if at least half of key values match
            return matched >= max(1, len(expected_key_values) // 2)

        except Exception as exc:
            logger.warning("Verification failed: %s", exc)
            return False
