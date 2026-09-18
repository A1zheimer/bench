from __future__ import annotations

import difflib
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from ..models.report import ProcessScore
from ..models.task import TaskInput
from ..models.trace import ActionType, AgentTrace, TraceStep
from .base import BaseEvaluator


class RecoveryPattern(str, Enum):
    BLIND_RETRY = "blind_retry"           # Same code retried
    DIAGNOSTIC = "diagnostic"             # Print variables / check data
    STRATEGY_SHIFT = "strategy_shift"     # Try a different approach
    GIVE_UP = "give_up"                   # No further attempts


class ProcessAuditor(BaseEvaluator):
    """
    Analyzes AgentTrace to score process quality:
      - planning_score: does agent decompose the problem?
      - tool_efficiency: useful tool calls / total
      - error_recovery_score: recovered errors / total errors
      - feedback_loop_score: agent uses observations to update plans
      - step_utilization: steps_used / max_steps
      - redundant_action_ratio: consecutive identical actions / total
    """

    @property
    def name(self) -> str:
        return "ProcessAuditor"

    def evaluate(
        self,
        task: TaskInput,
        trace: AgentTrace,
        final_output: Dict[str, Any],
        ground_truth: Optional[Dict[str, Any]],
    ) -> ProcessScore:
        steps = trace.steps
        max_steps = task.environment_config.max_steps

        if not steps:
            return ProcessScore(
                planning_score=0.0,
                tool_efficiency=0.0,
                error_recovery_score=1.0,
                feedback_loop_score=0.0,
                step_utilization=0.0,
                redundant_action_ratio=0.0,
                recovery_patterns={},
                diagnostic_ratio=0.0,
                tool_call_diversity=0.0,
                first_success_step=-1,
            )

        recovery_patterns = self._analyze_recovery_patterns(steps)
        total_attempts = recovery_patterns.get(RecoveryPattern.BLIND_RETRY.value, 0) + \
                         recovery_patterns.get(RecoveryPattern.DIAGNOSTIC.value, 0)
        diagnostic_ratio = recovery_patterns.get(RecoveryPattern.DIAGNOSTIC.value, 0) / max(1, total_attempts)

        return ProcessScore(
            planning_score=self._planning_score(steps),
            tool_efficiency=self._tool_efficiency(steps),
            error_recovery_score=self._error_recovery(steps),
            feedback_loop_score=self._feedback_loop(steps),
            step_utilization=len(steps) / max(max_steps, 1),
            redundant_action_ratio=self._redundant_ratio(steps),
            recovery_patterns=recovery_patterns,
            diagnostic_ratio=diagnostic_ratio,
            tool_call_diversity=self._tool_call_diversity(steps),
            first_success_step=self._first_success_step(steps),
        )

    def _planning_score(self, steps: List[TraceStep]) -> float:
        """Score based on distinct concepts in first 2 THINK steps."""
        think_steps = [s for s in steps[:3] if s.action_type == ActionType.THINK]
        if not think_steps:
            code_steps = [
                s for s in steps[:3]
                if s.action_type == ActionType.CODE_EXEC and s.tool_args and "code" in s.tool_args
            ]
            if not code_steps:
                return 0.0
            code = "\n".join(str(s.tool_args.get("code", "")) for s in code_steps)
            planning_markers = [
                "read_csv", "head", "describe", "isna", "dtypes", "groupby",
                "mean", "median", "std", "corr", "fit", "predict", "print",
            ]
            matched = sum(1 for marker in planning_markers if marker in code.lower())
            return min(0.6, max(0.3, matched / 8.0))
        combined_thought = " ".join(s.thought for s in think_steps)
        # Count distinct sentences as proxy for concept count
        sentences = [t.strip() for t in combined_thought.split(".") if len(t.strip()) > 10]
        distinct = len(set(sentences[:8]))
        return min(distinct / 4.0, 1.0)

    def _tool_efficiency(self, steps: List[TraceStep]) -> float:
        """useful_tool_calls / total_tool_calls. Useful = changes next action type."""
        tool_steps = [s for s in steps if s.tool_name is not None]
        if not tool_steps:
            return 1.0

        useful = 0
        for i, step in enumerate(steps):
            if step.tool_name is None:
                continue
            if step.observation and step.observation.strip() and "ERROR" not in step.observation:
                useful += 1
                continue
            if i + 1 < len(steps) and steps[i + 1].action_type != step.action_type:
                useful += 1

        return min(useful / len(tool_steps), 1.0)

    def _error_recovery(self, steps: List[TraceStep]) -> float:
        """recovered errors / total errors. No errors → 1.0."""
        error_steps = [i for i, s in enumerate(steps) if s.action_type == ActionType.ERROR
                       or (s.tool_result and "ERROR" in str(s.tool_result))]
        if not error_steps:
            return 1.0

        recovered = 0
        for err_idx in error_steps:
            # Recovery: next step exists and is not also an error
            if err_idx + 1 < len(steps):
                next_step = steps[err_idx + 1]
                if next_step.action_type != ActionType.ERROR:
                    recovered += 1

        return recovered / len(error_steps)

    def _feedback_loop(self, steps: List[TraceStep]) -> float:
        """THINK steps that reference content from previous observation."""
        think_steps = [(i, s) for i, s in enumerate(steps) if s.action_type == ActionType.THINK]
        if not think_steps:
            successful_tool_steps = [
                s for s in steps
                if s.tool_name and s.tool_result and "ERROR" not in str(s.tool_result)
            ]
            return 0.5 if successful_tool_steps else 0.0

        reused = 0
        for i, step in think_steps:
            if i == 0:
                continue
            prev_obs = steps[i - 1].observation
            thought = step.thought
            overlap = self._bigram_overlap(prev_obs, thought)
            if overlap > 0.15:
                reused += 1

        return reused / len(think_steps)

    def _redundant_ratio(self, steps: List[TraceStep]) -> float:
        """Consecutive identical (action_type, tool_name) pairs / total."""
        if len(steps) < 2:
            return 0.0
        redundant = 0
        for i in range(1, len(steps)):
            if (steps[i].action_type == steps[i - 1].action_type
                    and steps[i].tool_name == steps[i - 1].tool_name
                    and steps[i].action[:30] == steps[i - 1].action[:30]):
                redundant += 1
        return redundant / (len(steps) - 1)

    def _analyze_recovery_patterns(self, steps: List[TraceStep]) -> Dict[str, int]:
        """Classify how the agent reacts to an error in the next tool call."""
        patterns = {p.value: 0 for p in RecoveryPattern}
        
        for i, s in enumerate(steps):
            is_error = s.action_type == ActionType.ERROR or (s.tool_result and "ERROR" in str(s.tool_result))
            if is_error:
                # Find next tool call
                next_tool_step = None
                for j in range(i + 1, len(steps)):
                    if steps[j].tool_name == "python_repl":
                        next_tool_step = steps[j]
                        break
                        
                if not next_tool_step:
                    patterns[RecoveryPattern.GIVE_UP.value] += 1
                    continue
                    
                # Compare code
                curr_code = s.action if s.tool_name == "python_repl" else ""
                next_code = next_tool_step.action
                
                if not curr_code:
                    patterns[RecoveryPattern.STRATEGY_SHIFT.value] += 1
                    continue
                    
                similarity = difflib.SequenceMatcher(None, curr_code, next_code).ratio()
                
                if similarity > 0.9:
                    patterns[RecoveryPattern.BLIND_RETRY.value] += 1
                elif similarity > 0.3:
                    patterns[RecoveryPattern.DIAGNOSTIC.value] += 1
                else:
                    patterns[RecoveryPattern.STRATEGY_SHIFT.value] += 1
                    
        return patterns

    def _tool_call_diversity(self, steps: List[TraceStep]) -> float:
        tool_steps = [s for s in steps if s.tool_name is not None]
        if not tool_steps:
            return 0.0
        unique_pairs = set((s.action_type, s.tool_name) for s in tool_steps)
        return len(unique_pairs) / len(tool_steps)

    def _first_success_step(self, steps: List[TraceStep]) -> int:
        for i, s in enumerate(steps):
            if s.tool_name == "python_repl" and s.tool_result and "ERROR" not in str(s.tool_result):
                return i + 1
        return -1

    @staticmethod
    def _bigram_overlap(text_a: str, text_b: str) -> float:
        """Jaccard similarity of word bigrams between two texts."""
        def bigrams(text: str) -> Set[Tuple[str, str]]:
            words = text.lower().split()
            return set(zip(words, words[1:])) if len(words) >= 2 else set()

        a_bi = bigrams(text_a)
        b_bi = bigrams(text_b)
        if not a_bi and not b_bi:
            return 0.0
        intersection = a_bi & b_bi
        union = a_bi | b_bi
        return len(intersection) / len(union) if union else 0.0
