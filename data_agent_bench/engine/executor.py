from __future__ import annotations

import logging
import pathlib
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Tuple, Type

from ..collector.trace_collector import TraceCollector
from ..models.task import TaskInput
from ..models.trace import ActionType, AgentTrace, TerminationInfo, TraceStep
from .agent_interface import AgentInterface, AgentAction
from .environment import SimulatedEnvironment, DockerSandboxEnvironment, ToolResult
from .monitors import SystemMonitor

logger = logging.getLogger(__name__)


class BenchmarkExecutor:
    """
    Orchestrates one full benchmark run for a single TaskInput.

    Data flow:
        run(task)
          → SimulatedEnvironment (context manager)
          → TraceCollector (streaming JSONL)
          → SystemMonitor (daemon thread)
          → _execution_loop (step-by-step agent interaction)
          → trace.finalize()
          → returns (AgentTrace, output_dict)
    """

    def __init__(
        self,
        agent: AgentInterface,
        output_dir: str = "./bench_runs",
        monitor_class: Type[SystemMonitor] = SystemMonitor,
        task_root: Optional[str] = None,
        model_id: str = "simulated",
        temperature: float = 0.0,
        env_type: str = "local",
    ) -> None:
        self._agent = agent
        self._output_dir = pathlib.Path(output_dir)
        self._monitor_class = monitor_class
        self._task_root = task_root
        self._model_id = model_id
        self._temperature = temperature
        self._env_type = env_type

    def run(self, task: TaskInput, run_index: int = 0) -> Tuple[AgentTrace, Dict[str, Any]]:
        run_id = str(uuid.uuid4())[:8]
        run_dir = self._output_dir / task.instance_id / run_id
        stop_event = threading.Event()

        trace = AgentTrace(
            instance_id=task.instance_id,
            start_time=datetime.utcnow(),
            end_time=None,
            steps=[],
            termination=None,
            metadata={
                "model_id": self._model_id,
                "temperature": self._temperature,
                "run_index": run_index,
                "run_id": run_id,
            },
        )

        collector = TraceCollector(trace, run_dir)
        collector.open()

        self._agent.reset(task)

        # Use per-task directory if available, fall back to global task_root
        task_root = task.task_dir or self._task_root
        env_class = DockerSandboxEnvironment if self._env_type == "docker" else SimulatedEnvironment
        with env_class(task.environment_config, task, task_root) as env:
            monitor = self._monitor_class(task.environment_config, trace, stop_event)
            monitor.start()
            try:
                final_output = self._execution_loop(task, env, trace, collector, monitor, stop_event)
            finally:
                monitor.stop()
                trace.finalize()
                if not trace.termination:
                    mon_info = monitor.get_termination_info()
                    trace.termination = mon_info or TerminationInfo(
                        reason="completed", forced=False
                    )
                collector.close()

        logger.info(
            "Task %s finished: %s | steps=%d | tokens=%d | cost=$%.4f | time=%.1fs",
            task.instance_id,
            trace.termination.reason if trace.termination else "?",
            len(trace.steps),
            trace.total_tokens,
            trace.total_cost_usd,
            trace.wall_time_seconds,
        )
        return trace, final_output

    def _execution_loop(
        self,
        task: TaskInput,
        env: SimulatedEnvironment,
        trace: AgentTrace,
        collector: TraceCollector,
        monitor: SystemMonitor,
        stop_event: threading.Event,
    ) -> Dict[str, Any]:
        # Build absolute data path so agent can use it directly in python_repl
        task_dir = task.task_dir or self._task_root
        if isinstance(task_dir, str):
            task_dir = pathlib.Path(task_dir)

        if task_dir and task.context.dataset_preview:
            abs_data_path = str(task_dir / task.context.dataset_preview)
        else:
            abs_data_path = task.context.dataset_preview
        
        observation = (
            f"Task: {task.context.problem_statement}\n"
            f"Data file: {abs_data_path}\n"
            f"In python_repl, use: pd.read_csv(DATA_PATH)  "
            f"# DATA_PATH is pre-set to the absolute path\n"
            f"Hints: {task.context.expert_knowledge}"
        )
        final_code_parts = []
        final_result = ""
        raw_agent_output = ""

        for step_num in range(1, task.environment_config.max_steps + 1):
            if stop_event.is_set():
                break

            t0 = time.perf_counter()
            action: AgentAction = self._agent.act(step_num, observation, trace.steps)
            think_latency = (time.perf_counter() - t0) * 1000
            if action.thought:
                raw_agent_output = action.thought

            # Execute tool if needed
            tool_result_obj: Optional[ToolResult] = None
            new_observation = ""

            if action.tool_name and action.tool_args is not None:
                tool_result_obj = env.execute_tool(action.tool_name, action.tool_args)
                new_observation = tool_result_obj.output
            elif action.action_type == ActionType.THINK:
                new_observation = f"Thought recorded: {action.thought[:100]}..."
            elif action.action_type == ActionType.FINAL_ANSWER:
                new_observation = "Task marked as complete."
            else:
                new_observation = "(no tool output)"

            # Accumulate code
            if action.action_type in (ActionType.CODE_EXEC, ActionType.TOOL_CALL):
                if action.tool_args and "code" in action.tool_args:
                    final_code_parts.append(action.tool_args["code"])
            if action.action_type == ActionType.FINAL_ANSWER:
                final_result = action.thought or new_observation
            
            step = TraceStep(
                step=step_num,
                timestamp=datetime.utcnow(),
                action_type=action.action_type,
                action=action.action,
                observation=new_observation,
                thought=action.thought,
                tool_name=action.tool_name,
                tool_args=action.tool_args,
                tool_result=tool_result_obj.output if tool_result_obj else None,
                tokens_in=action.tokens_in,
                tokens_out=action.tokens_out,
                latency_ms=think_latency + (tool_result_obj.latency_ms if tool_result_obj else 0),
                cost_usd=tool_result_obj.cost_usd if tool_result_obj else 0.0,
            )
            collector.record(step)
            monitor.observe(step)

            # Update running totals for monitor budget check
            trace.total_cost_usd = sum(s.cost_usd for s in trace.steps)
            trace.total_tokens = sum(s.tokens_in + s.tokens_out for s in trace.steps)

            observation = new_observation

            if self._agent.is_done():
                trace.termination = TerminationInfo(reason="completed", forced=False)
                break

        if not trace.termination:
            trace.termination = TerminationInfo(
                reason="max_steps",
                forced=True,
                details=f"Reached max_steps={task.environment_config.max_steps}",
            )

        # Build output dict matching Output Protocol
        trajectory_summary = [
            {"step": s.step, "action": s.action, "observation": s.observation[:200]}
            for s in trace.steps
        ]

        # Collect all successful code outputs for evaluation
        # Concatenate all non-error outputs so the evaluator can find values
        # from any step, not just the last one.
        code_steps = [s for s in trace.steps if s.tool_result]
        if code_steps:
            successful_outputs = [
                s.tool_result for s in code_steps
                if s.tool_result and not s.tool_result.startswith("ERROR:")
            ]
            if successful_outputs:
                # Join all non-error outputs; evaluator searches across the full text
                final_result = "\n---\n".join(successful_outputs)
            else:
                final_result = code_steps[-1].tool_result or ""

        return {
            "final_code": "\n\n".join(final_code_parts),
            "execution_result": final_result,
            "raw_agent_output": raw_agent_output,
            "trajectory": trajectory_summary,
            "metrics": {
                "completion_rate": 1.0 if (trace.termination and trace.termination.reason == "completed") else 0.0,
                "total_tokens": trace.total_tokens,
                "wall_time": f"{trace.wall_time_seconds:.1f}s",
            },
        }
