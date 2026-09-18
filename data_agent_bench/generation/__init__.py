"""
Generation: LLM-backed agents for dynamically generating benchmark tasks.

The generation pipeline:
  1. TaskGeneratorAgent plans a task, generates data, solves it, and packages output
  2. ReviewerAgent independently validates generated tasks
  3. GenerationPipeline orchestrates batch generation with retries and validation
"""
from .task_generator_agent import TaskGeneratorAgent, GeneratedTask
from .reviewer_agent import ReviewerAgent, ReviewResult
from .pipeline import GenerationPipeline, GenerationSpec, GenerationReport

__all__ = [
    "TaskGeneratorAgent",
    "GeneratedTask",
    "ReviewerAgent",
    "ReviewResult",
    "GenerationPipeline",
    "GenerationSpec",
    "GenerationReport",
]
