import copy
import json
import logging
import pathlib
import pandas as pd
from typing import List, Dict, Any
from ..repository.task_repo import TaskRepository
from ..engine.executor import BenchmarkExecutor
from ..engine.agents import build_agent
from ..database.report_db import ReportDatabase
from ..evaluation.deterministic import DeterministicEvaluator
from ..evaluation.process_auditor import ProcessAuditor
from ..evaluation.risk_assessor import RiskAssessor
from ..evaluation.aggregator import ScoreAggregator
from ..reporting.json_reporter import JSONReporter
from ..models.trace import ActionType

logger = logging.getLogger(__name__)

class AcademicSuite:
    def __init__(self, tasks_dir: str, db_path: str, output_dir: str):
        self.repo = TaskRepository(tasks_dir)
        self.db = ReportDatabase(db_path)
        self.output_dir = pathlib.Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.reporter = JSONReporter()
        self.evaluators = (
            DeterministicEvaluator(),
            ProcessAuditor(),
            RiskAssessor(),
            ScoreAggregator(),
        )

    def run_oracle(self, agent_spec: str = "native:openai/gpt-4o", max_steps: int = 40):
        """Runs the expert model to find the average steps (N) for each task."""
        print(f"Starting Oracle Run with {agent_spec} (max_steps={max_steps})...")
        agent = build_agent(agent_spec, temperature=0.0)
        executor = BenchmarkExecutor(
            agent=agent,
            output_dir=str(self.output_dir / "oracle"),
            task_root=self.repo.tasks_dir,
            model_id=agent_spec,
        )
        
        results = []
        for task in self.repo.iter_all():
            try:
                print(f" Profiling {task.instance_id}...")
                task_copy = copy.deepcopy(task)
                task_copy.max_steps = max_steps
                trace, final_output = executor.run(task_copy)
                
                actual_steps = len([s for s in trace.steps if s.action_type in [ActionType.CODE_EXEC, ActionType.FINAL_ANSWER]])
                
                results.append({
                    "instance_id": task.instance_id,
                    "difficulty": task.task_metadata.difficulty.value,
                    "oracle_steps": actual_steps,
                    "success": trace.termination and trace.termination.reason in ("final_answer_called", "completed")
                })
            except Exception as e:
                logger.error(f"Task {task.instance_id} failed in oracle run: {e}")
                continue
            
        oracle_path = self.output_dir / "oracle_results.json"
        oracle_path.write_text(json.dumps(results, indent=2), "utf-8")
        print(f"Oracle results saved to {oracle_path}")
        return results

    def run_sensitivity_analysis(self, agent_spec: str, steps_range: List[int]):
        """Runs sensitivity analysis by varying max_steps."""
        print(f"Starting Sensitivity Analysis for {agent_spec}...")
        agent = build_agent(agent_spec, temperature=0.0)
        
        all_results = []
        for max_s in steps_range:
            print(f" Testing with max_steps = {max_s}")
            executor = BenchmarkExecutor(
                agent=agent,
                output_dir=str(self.output_dir / f"sensitivity_step_{max_s}"),
                task_root=self.repo.tasks_dir,
                model_id=f"{agent_spec}_s{max_s}",
            )
            
            success_count = 0
            total_tasks = 0
            
            for task in self.repo.iter_all():
                try:
                    task_copy = copy.deepcopy(task)
                    task_copy.max_steps = max_s
                    trace, final_output = executor.run(task_copy)
                    
                    is_success = trace.termination and trace.termination.reason in ("final_answer_called", "completed")
                    if is_success:
                        success_count += 1
                    total_tasks += 1
                except Exception as e:
                    logger.error(f"Task {task.instance_id} failed in sensitivity analysis (max_steps={max_s}): {e}")
                    continue
                
            sr = success_count / total_tasks if total_tasks > 0 else 0
            all_results.append({"max_steps": max_s, "success_rate": sr})
            
        sensitivity_path = self.output_dir / f"sensitivity_{agent_spec.replace('/', '_')}.json"
        sensitivity_path.write_text(json.dumps(all_results, indent=2), "utf-8")
        return all_results

    @staticmethod
    def plot_saturation_curve(data_file: str, output_plot: str):
        """Plots the success rate vs max steps curve."""
        import matplotlib.pyplot as plt
        with open(data_file, "r") as f:
            data = json.load(f)
        
        df = pd.DataFrame(data)
        plt.figure(figsize=(10, 6))
        plt.plot(df["max_steps"], df["success_rate"], marker='o', linestyle='-', color='b')
        plt.title("Success Rate Saturation Curve")
        plt.xlabel("Max Steps")
        plt.ylabel("Success Rate (Completion)")
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.ylim(0, 1.1)
        plt.savefig(output_plot)
        plt.close()
        print(f"Plot saved to {output_plot}")
