"""
SFTDataExporter: Converts benchmark tasks + solution traces into SFT training data.

Exports to:
  - Alpaca format (instruction/input/output)
  - ShareGPT format (conversations)
  - OpenAI fine-tuning JSONL (messages)

Usage:
    exporter = SFTDataExporter()
    exporter.export_from_tasks("./tasks", "./sft_data/train.jsonl", fmt="openai")
    exporter.export_from_runs("./bench_runs", "./sft_data/train.jsonl", fmt="sharegpt")
"""
from __future__ import annotations

import json
import logging
import pathlib
from typing import Any, Dict, List, Optional

from .schemas import TrainRecord

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an expert data scientist. You are given a data analysis problem and access to
a Python REPL tool. Solve the problem step by step by writing and executing Python code.
Always read the dataset first, then perform the required analysis, and clearly state
your numerical results at the end.
"""


class SFTDataExporter:
    """
    Converts benchmark task specifications and agent trajectories into
    supervised fine-tuning data for training a data science agent.
    """

    # ----------------------------------------------------------------
    # Export from task directory (uses solution_code from generation_meta)
    # ----------------------------------------------------------------

    def export_from_tasks(
        self,
        tasks_dir: str,
        output_path: str,
        fmt: str = "openai",
        min_verified: bool = True,
    ) -> int:
        """
        Export SFT data from generated tasks (solution_code in generation_meta.json).

        Args:
            tasks_dir: Path containing task directories.
            output_path: Output JSONL file path.
            fmt: "openai" | "sharegpt" | "alpaca"
            min_verified: Only export verified tasks (verified=True in generation_meta).

        Returns:
            Number of examples exported.
        """
        tasks_root = pathlib.Path(tasks_dir)
        examples = []

        for task_dir in sorted(tasks_root.iterdir()):
            if not task_dir.is_dir():
                continue
            task_file = task_dir / "task.json"
            meta_file = task_dir / "generation_meta.json"
            gt_file = task_dir / "ground_truth" / "expected_output.json"

            if not task_file.exists():
                continue

            task = json.loads(task_file.read_text("utf-8"))

            # Get solution code
            solution_code = None
            if meta_file.exists():
                meta = json.loads(meta_file.read_text("utf-8"))
                if min_verified and not meta.get("verified", False):
                    logger.debug("Skipping unverified: %s", task_dir.name)
                    continue
                solution_code = meta.get("solution_code")

            if not solution_code:
                continue

            # Get problem context
            ctx = task.get("context", {})
            problem = ctx.get("problem_statement", "")
            expert_knowledge = ctx.get("expert_knowledge", "")
            dataset_preview = ctx.get("dataset_preview", "")
            gt = json.loads(gt_file.read_text("utf-8")) if gt_file.exists() else {}

            # Build instruction
            instruction = self._build_instruction(
                problem, expert_knowledge, dataset_preview
            )
            response = self._build_response(solution_code, gt)

            example = self._format_example(instruction, response, fmt)
            if example:
                examples.append(example)

        output_path = pathlib.Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for ex in examples:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")

        logger.info("Exported %d SFT examples to %s", len(examples), output_path)
        return len(examples)

    # ----------------------------------------------------------------
    # Export from benchmark run traces (actual successful agent runs)
    # ----------------------------------------------------------------

    def export_from_runs(
        self,
        runs_dir: str,
        output_path: str,
        fmt: str = "sharegpt",
        min_cas: float = 0.7,
    ) -> int:
        """
        Export SFT data from successful agent run trajectories.

        Only exports runs where CAS >= min_cas (high-quality trajectories).
        These are real multi-turn tool-use conversations.

        Args:
            runs_dir: Path to bench_runs directory.
            output_path: Output JSONL file path.
            fmt: "openai" | "sharegpt"
            min_cas: Minimum CAS threshold for quality filtering.

        Returns:
            Number of examples exported.
        """
        runs_root = pathlib.Path(runs_dir)
        examples = []

        for report_dir in sorted(runs_root.rglob("report.json")):
            try:
                report = json.loads(report_dir.read_text("utf-8"))
            except Exception:
                continue

            # Quality filter
            metrics = report.get("metrics", {})
            acc = float(metrics.get("result_accuracy", 0))
            proc = float(metrics.get("process_quality", 0))
            saf = float(metrics.get("safety_score", 0))
            cas = 0.4 * acc + 0.35 * proc + 0.25 * saf
            if cas < min_cas:
                continue

            # Skip perturbed conditions — train only on clean data
            if report.get("experiment_condition") == "perturbed":
                continue

            trajectory = report.get("trajectory_summary", [])
            if not trajectory:
                continue

            conversation = self._trajectory_to_conversation(trajectory)
            if not conversation:
                continue

            example = self._format_conversation(conversation, fmt)
            if example:
                examples.append(example)

        output_path = pathlib.Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for ex in examples:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")

        logger.info(
            "Exported %d run-based SFT examples to %s", len(examples), output_path
        )
        return len(examples)

    # ----------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------

    @staticmethod
    def _build_instruction(
        problem: str,
        expert_knowledge: str,
        dataset_preview: str,
    ) -> str:
        parts = [f"## Problem\n{problem}"]
        if expert_knowledge:
            parts.append(f"## Domain Knowledge\n{expert_knowledge}")
        if dataset_preview:
            parts.append(
                f"## Dataset\nThe dataset is available at `{dataset_preview}`. "
                f"Load it with pandas before starting your analysis."
            )
        return "\n\n".join(parts)

    @staticmethod
    def _build_response(solution_code: str, gt: Dict[str, Any]) -> str:
        key_values = gt.get("key_values", {})
        response_parts = [f"```python\n{solution_code.strip()}\n```"]
        if key_values:
            kv_str = "\n".join(f"- **{k}**: {v}" for k, v in key_values.items())
            response_parts.append(f"\n**Results:**\n{kv_str}")
        return "\n".join(response_parts)

    @staticmethod
    def _trajectory_to_conversation(
        trajectory: List[Dict[str, Any]],
    ) -> Optional[List[Dict[str, str]]]:
        """Convert agent trajectory steps to a multi-turn conversation."""
        messages = []
        for step in trajectory:
            action_type = step.get("action_type", "")
            thought = step.get("thought", "")
            action = step.get("action", "")
            observation = step.get("observation", "")

            if action_type in ("THINK", "PLAN") and thought:
                messages.append({
                    "role": "assistant",
                    "content": f"<thinking>{thought}</thinking>",
                })
            elif action_type == "TOOL_CALL" and action:
                tool = step.get("tool_name", "python_repl")
                messages.append({
                    "role": "assistant",
                    "content": f"<tool_call>{tool}</tool_call>\n```python\n{action}\n```",
                })
                if observation:
                    messages.append({
                        "role": "tool",
                        "content": observation[:2000],  # Truncate long outputs
                    })
            elif action_type == "FINAL_ANSWER" and action:
                messages.append({
                    "role": "assistant",
                    "content": action,
                })

        return messages if len(messages) >= 3 else None

    def _format_example(
        self, instruction: str, response: str, fmt: str
    ) -> Optional[Dict[str, Any]]:
        """Format a single instruction-response pair."""
        if fmt == "openai":
            return {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": instruction},
                    {"role": "assistant", "content": response},
                ]
            }
        elif fmt == "alpaca":
            return {
                "instruction": instruction,
                "input": "",
                "output": response,
                "system": SYSTEM_PROMPT,
            }
        elif fmt == "sharegpt":
            return {
                "conversations": [
                    {"from": "system", "value": SYSTEM_PROMPT},
                    {"from": "human", "value": instruction},
                    {"from": "gpt", "value": response},
                ]
            }
        return None

    def _format_conversation(
        self, conversation: List[Dict[str, str]], fmt: str
    ) -> Optional[Dict[str, Any]]:
        """Format a multi-turn conversation from a trajectory."""
        if fmt == "openai":
            msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
            for msg in conversation:
                role = msg["role"]
                if role == "tool":
                    role = "tool"
                msgs.append({"role": role, "content": msg["content"]})
            return {"messages": msgs}
        elif fmt == "sharegpt":
            convs = [{"from": "system", "value": SYSTEM_PROMPT}]
            for msg in conversation:
                from_role = "human" if msg["role"] == "user" else "gpt"
                convs.append({"from": from_role, "value": msg["content"]})
            return {"conversations": convs}
        return None

    def append_record(
        self,
        record: TrainRecord,
        output_path: str,
        fmt: str = "openai",
    ) -> int:
        """Append one TrainRecord as a formatted JSONL line."""
        example = self._format_example(record.instruction, record.response, fmt)
        if not example:
            return 0
        output = pathlib.Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "a", encoding="utf-8") as f:
            f.write(json.dumps(example, ensure_ascii=False) + "\n")
        return 1

    def append_records(
        self,
        records: List[TrainRecord],
        output_path: str,
        fmt: str = "openai",
    ) -> int:
        """Append multiple TrainRecord entries in one flush."""
        output = pathlib.Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        with open(output, "a", encoding="utf-8") as f:
            for record in records:
                example = self._format_example(record.instruction, record.response, fmt)
                if not example:
                    continue
                f.write(json.dumps(example, ensure_ascii=False) + "\n")
                written += 1
        return written
