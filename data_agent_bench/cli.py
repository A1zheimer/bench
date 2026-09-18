from __future__ import annotations

import argparse
import json
import logging
import pathlib
import sys
from typing import List

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from .database.report_db import ReportDatabase
from .engine.agents import build_agent
from .engine.executor import BenchmarkExecutor
from .evaluation.aggregator import ScoreAggregator
from .evaluation.answer_extractor import AnswerExtractor
from .evaluation.deterministic import DeterministicEvaluator
from .evaluation.process_auditor import ProcessAuditor
from .evaluation.risk_assessor import RiskAssessor
from .evaluation.scorer_audit import ScorerAudit
from .evaluation.trace_grounding import TraceGroundingVerifier
from .evaluation.trace_integrity import TraceIntegrityValidator
from .models.task import Difficulty, Domain, TaskInput
from .repository.provenance import filter_formal_reports, load_ground_truth, task_provenance
from .repository.task_repo import TaskRepository
from .reporting.json_reporter import JSONReporter
from .tracing import LangfuseExporter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rich / fallback display helpers
# ---------------------------------------------------------------------------

def _try_rich() -> bool:
    try:
        import rich  # noqa: F401
        return True
    except ImportError:
        return False


def _print_table(rows: List[dict], title: str = "") -> None:
    if _try_rich():
        from rich.console import Console
        from rich.table import Table

        console = Console()
        if not rows:
            console.print(f"[yellow]{title}: no data[/yellow]")
            return
        table = Table(title=title, show_header=True, header_style="bold cyan")
        for col in rows[0].keys():
            table.add_column(col, overflow="fold")
        for row in rows:
            table.add_row(*[str(v) for v in row.values()])
        console.print(table)
    else:
        if title:
            print(f"\n=== {title} ===")
        if not rows:
            print("(no data)")
            return
        headers = list(rows[0].keys())
        widths = {h: max(len(h), max(len(str(r[h])) for r in rows)) for h in headers}
        header_line = " | ".join(h.ljust(widths[h]) for h in headers)
        print(header_line)
        print("-" * len(header_line))
        for row in rows:
            print(" | ".join(str(row[h]).ljust(widths[h]) for h in headers))


def _print_json(data: dict) -> None:
    if _try_rich():
        from rich.console import Console
        from rich.syntax import Syntax
        console = Console()
        console.print(Syntax(json.dumps(data, indent=2, default=str), "json"))
    else:
        print(json.dumps(data, indent=2, default=str))


def _task_source_set(task: TaskInput) -> str:
    task_dir = pathlib.Path(task.task_dir or "")
    root_name = task_dir.parent.name if task_dir.parent.name else ""
    if root_name in {"tasks_legacy_unverified", "tasks_taskgen_candidates"}:
        return "legacy_unverified" if root_name == "tasks_legacy_unverified" else "taskgen_candidates"
    if root_name.startswith("tasks_verified"):
        return "verified"
    return ""


# ---------------------------------------------------------------------------
# Core benchmark runner
# ---------------------------------------------------------------------------

def _run_single(
    task: TaskInput,
    executor: BenchmarkExecutor,
    evaluators_tuple: tuple,
    reporter: JSONReporter,
    db: ReportDatabase,
    output_dir: str,
    model_id: str = "simulated",
    run_index: int = 0,
    temperature: float = 0.0,
    judge_panel=None,
    langfuse_exporter: LangfuseExporter | None = None,
) -> dict:
    answer_extractor, det_eval, proc_eval, risk_eval, trace_grounding_eval, trace_integrity_eval, scorer_audit_eval, aggregator = evaluators_tuple

    # Execute
    trace, final_output = executor.run(task, run_index=run_index)

    # Load ground truth
    ground_truth = None
    provenance = None
    if task.ground_truth_path:
        try:
            ground_truth = load_ground_truth(task.ground_truth_path)
            provenance = task_provenance(ground_truth, source_set=_task_source_set(task))
        except Exception as exc:
            logger.warning("Could not load ground truth: %s", exc)
    final_output["benchmark_extracted_answer"] = answer_extractor.extract(
        task, trace, final_output, ground_truth
    )

    # Deterministic evaluation (always runs)
    det_score = det_eval.evaluate(task, trace, final_output, ground_truth)
    proc_score = proc_eval.evaluate(task, trace, final_output, ground_truth)
    risk_score = risk_eval.evaluate(task, trace, final_output, ground_truth)
    trace_grounding_score = trace_grounding_eval.evaluate(task, trace, final_output, ground_truth)
    trace_integrity_score = trace_integrity_eval.evaluate(task, trace, final_output, ground_truth)
    scorer_audit_score = scorer_audit_eval.evaluate(
        task, trace, final_output, ground_truth, deterministic_score=det_score
    )
    metrics, failure = aggregator.aggregate(
        task, trace, det_score, proc_score, risk_score, scorer_audit=scorer_audit_score
    )

    # Agent-as-Judge evaluation (optional, runs in parallel with deterministic)
    panel_verdict = None
    if judge_panel is not None:
        try:
            panel_verdict = judge_panel.judge(
                instance_id=task.instance_id,
                domain=task.task_metadata.domain.value,
                difficulty=task.task_metadata.difficulty.value,
                problem_statement=task.context.problem_statement,
                expert_knowledge=task.context.expert_knowledge,
                trajectory=[s.to_dict() for s in trace.steps],
                final_output=final_output,
                ground_truth=ground_truth,
            )
            # Blend judge score into metrics (overwrites llm_judge_score field)
            metrics.llm_judge_score = panel_verdict.llm_judge_score
            if panel_verdict.needs_human_review:
                logger.warning(
                    "Task %s flagged for human review (disagreement=%s, iaa=%.3f)",
                    task.instance_id,
                    panel_verdict.disagreement_flag,
                    panel_verdict.iaa_alpha,
                )
        except Exception as exc:
            logger.warning("Judge panel failed for %s: %s", task.instance_id, exc)

    # Report
    report = reporter.build(
        task, trace, final_output, det_score, proc_score, risk_score, metrics, failure,
        trace_grounding_score=trace_grounding_score,
        trace_integrity_score=trace_integrity_score,
        scorer_audit_score=scorer_audit_score,
    )

    # Attach panel verdict to report JSON if available
    if panel_verdict is not None:
        report.metadata = getattr(report, "metadata", {}) or {}
        report.metadata["judge_panel"] = panel_verdict.to_dict()
    if provenance is not None:
        report.metadata = getattr(report, "metadata", {}) or {}
        report.metadata["task_provenance"] = provenance

    out_path = pathlib.Path(output_dir) / task.instance_id
    report_path = reporter.write(report, out_path)
    db.save_with_meta(
        report,
        task.task_metadata.domain.value,
        task.task_metadata.difficulty.value,
        model_id=model_id,
        run_index=run_index,
        temperature=temperature,
    )
    if langfuse_exporter is not None:
        langfuse_exporter.export_run(
            task=task,
            trace=trace,
            final_output=final_output,
            deterministic=det_score,
            process=proc_score,
            risk=risk_score,
            trace_grounding=trace_grounding_score,
            trace_integrity=trace_integrity_score,
            scorer_audit=scorer_audit_score,
            metrics=metrics,
            failure=failure,
            report=report,
            report_path=report_path,
            model_id=model_id,
            run_index=run_index,
            temperature=temperature,
        )

    summary = reporter.summary_table(report)
    summary["report_path"] = str(report_path)
    if panel_verdict is not None:
        summary["judge_score"] = f"{panel_verdict.llm_judge_score:.3f}"
        summary["iaa_alpha"] = f"{panel_verdict.iaa_alpha:.3f}"
        summary["review"] = "⚠" if panel_verdict.needs_human_review else "ok"
    return summary


# ---------------------------------------------------------------------------
# CLI subcommands
# ---------------------------------------------------------------------------

def cmd_run(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    repo = TaskRepository(
        args.tasks_dir,
        require_verified=not getattr(args, "include_unverified", False),
    )
    if repo.count() == 0:
        suffix = ""
        if repo.skipped_unverified:
            suffix = (
                f" ({len(repo.skipped_unverified)} unverified task(s) skipped; "
                "pass --include-unverified for debugging)"
            )
        print(f"ERROR: No verified tasks found in {args.tasks_dir}{suffix}", file=sys.stderr)
        return 1

    # Select tasks
    tasks: List[TaskInput] = []
    if args.task:
        try:
            tasks = [repo.get(args.task)]
        except KeyError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
    elif getattr(args, "tasks_file", None):
        task_ids = json.load(open(args.tasks_file))
        for tid in task_ids:
            try:
                tasks.append(repo.get(tid))
            except KeyError:
                print(f"WARNING: task {tid} not found, skipping", file=sys.stderr)
    elif getattr(args, "all", False):
        tasks = list(repo.iter_all())
    elif args.domain or args.difficulty:
        if args.domain:
            tasks = list(repo.iter_by_domain(Domain(args.domain)))
        if args.difficulty:
            tasks = [t for t in (tasks or list(repo.iter_all()))
                     if t.task_metadata.difficulty == Difficulty(args.difficulty)]
    else:
        tasks = list(repo.iter_all())

    if not tasks:
        print("No matching tasks found.", file=sys.stderr)
        return 1

    # Set up components
    agent_spec = getattr(args, "agent", "simulated") or "simulated"
    temperature = float(getattr(args, "temperature", 0.0) or 0.0)
    n_runs = max(1, int(getattr(args, "runs", 1) or 1))

    # Determine model_id for DB tracking
    model_id = agent_spec if agent_spec != "simulated" else "simulated"

    try:
        agent = build_agent(agent_spec, temperature=temperature)
    except Exception as exc:
        print(f"ERROR: Failed to build agent '{agent_spec}': {exc}", file=sys.stderr)
        return 1

    executor = BenchmarkExecutor(
        agent=agent,
        output_dir=args.output_dir,
        task_root=args.tasks_dir,
        model_id=model_id,
        temperature=temperature,
        env_type=getattr(args, "env", "local"),
    )
    evaluators = (
        AnswerExtractor(),
        DeterministicEvaluator(),
        ProcessAuditor(),
        RiskAssessor(),
        TraceGroundingVerifier(),
        TraceIntegrityValidator(),
        ScorerAudit(),
        ScoreAggregator(),
    )
    reporter = JSONReporter()
    db = ReportDatabase(args.db)
    langfuse_exporter = LangfuseExporter(
        enabled=bool(getattr(args, "langfuse", False)),
        experiment_name=getattr(args, "langfuse_experiment", "data-agent-bench"),
    )

    # Build judge panel (optional)
    judge_panel = None
    judge_specs = getattr(args, "judge", None)
    if judge_specs:
        from .evaluation.multi_judge_panel import MultiJudgePanel
        try:
            judge_panel = MultiJudgePanel.from_specs(judge_specs)
            print(f"Judge panel: {[j.judge_id for j in judge_panel._judges]}")
        except Exception as exc:
            print(f"WARNING: Could not build judge panel: {exc}", file=sys.stderr)

    summaries = []
    all_passed = True
    for task in tasks:
        print(f"\nRunning: {task.instance_id} [{task.task_metadata.domain.value} / {task.task_metadata.difficulty.value}] x{n_runs} run(s)")
        for run_idx in range(n_runs):
            try:
                summary = _run_single(
                    task, executor, evaluators, reporter, db, args.output_dir,
                    model_id=model_id, run_index=run_idx, temperature=temperature,
                    judge_panel=judge_panel,
                    langfuse_exporter=langfuse_exporter,
                )
                summaries.append(summary)
                if summary.get("completion") != "100%":
                    all_passed = False
            except Exception as exc:
                logger.exception("Task %s run %d failed", task.instance_id, run_idx)
                print(f"  ERROR: {exc}", file=sys.stderr)
                all_passed = False

    if summaries:
        _print_table(summaries, title="Benchmark Results")

    # Print aggregate
    stats = db.aggregate_stats()
    print(f"\nAggregate stats over {stats.get('count', 0)} report(s):")
    print(f"  Completion: {stats.get('avg_completion_rate', 0):.1%} | "
          f"Accuracy: {stats.get('avg_result_accuracy', 0):.3f} | "
          f"Process: {stats.get('avg_process_quality', 0):.3f} | "
          f"Safety: {stats.get('avg_safety_score', 0):.3f}")
    if stats.get("failure_distribution"):
        fd = stats["failure_distribution"]
        print(f"  Failures: {fd}")

    langfuse_exporter.flush()
    return 0 if all_passed else 1


def cmd_list(args: argparse.Namespace) -> int:
    repo = TaskRepository(
        args.tasks_dir,
        require_verified=not getattr(args, "include_unverified", False),
    )
    rows = []
    for task in repo.iter_all():
        verified = "no"
        if task.ground_truth_path:
            try:
                verified = "yes" if task_provenance(load_ground_truth(task.ground_truth_path))["verified"] else "no"
            except Exception:
                verified = "no"
        rows.append({
            "instance_id": task.instance_id,
            "domain": task.task_metadata.domain.value,
            "difficulty": task.task_metadata.difficulty.value,
            "tags": ", ".join(task.task_metadata.tags),
            "has_gt": "yes" if task.ground_truth_path else "no",
            "verified": verified,
        })
    _print_table(rows, title=f"Tasks in {args.tasks_dir}")
    print(f"\nTotal: {repo.count()} task(s)")
    if repo.skipped_unverified:
        print(f"Skipped unverified: {len(repo.skipped_unverified)}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    db = ReportDatabase(args.db)
    if args.report_id:
        data = db.get(args.report_id)
        if not data:
            print(f"Report {args.report_id} not found.", file=sys.stderr)
            return 1
        _print_json(data)
    else:
        lines = db.list_all()
        if not lines:
            print("No reports in database.")
        for line in lines:
            print(line)
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    db = ReportDatabase(args.db)
    stats = db.aggregate_stats(
        domain=args.domain or None,
        difficulty=args.difficulty or None,
    )
    _print_json(stats)
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    db = ReportDatabase(args.db)
    count = db.export_jsonl(args.output)
    print(f"Exported {count} report(s) to {args.output}")
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    """Generate benchmark tasks using an LLM agent."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    from .generation.task_generator_agent import TaskGeneratorAgent
    from .generation.reviewer_agent import ReviewerAgent
    from .generation.data_critic_agent import DataCriticAgent
    from .generation.red_team_agent import RedTeamAgent
    from .generation.pipeline import GenerationPipeline, GenerationSpec

    # Parse agent spec
    parts = args.agent.split(":")
    if len(parts) != 2:
        print(
            f"ERROR: --agent must be 'provider:model' (e.g. 'anthropic:claude-sonnet-4-6'), "
            f"got '{args.agent}'",
            file=sys.stderr,
        )
        return 1
    provider, model_id = parts

    generator = TaskGeneratorAgent(
        provider=provider,
        model_id=model_id,
        temperature=args.temperature,
        output_root=args.output_dir,
    )

    reviewer = None
    if args.with_review:
        rev_spec = args.reviewer_agent or args.agent
        rev_parts = rev_spec.split(":")
        reviewer = ReviewerAgent(
            provider=rev_parts[0],
            model_id=rev_parts[1] if len(rev_parts) > 1 else model_id,
            temperature=0.0,  # deterministic for review
        )

    critic = None
    if args.with_critic:
        critic_spec = args.critic_agent or args.agent
        critic_parts = critic_spec.split(":")
        critic = DataCriticAgent(
            provider=critic_parts[0],
            model_id=critic_parts[1] if len(critic_parts) > 1 else model_id,
            temperature=0.0,
        )
        
    red_team = None
    if args.with_redteam:
        red_spec = args.redteam_agent or args.agent
        red_parts = red_spec.split(":")
        red_team = RedTeamAgent(
            provider=red_parts[0],
            model_id=red_parts[1] if len(red_parts) > 1 else model_id,
            temperature=0.3,
        )

    pipeline = GenerationPipeline(
        generator=generator,
        reviewer=reviewer,
        critic=critic,
        red_team=red_team,
        max_retries_per_task=3,
        enforce_quality_gate=not args.allow_unverified,
    )

    # Build specs
    if args.spec:
        # Load from JSON file
        spec_data = json.loads(pathlib.Path(args.spec).read_text("utf-8"))
        specs = [GenerationSpec(**s) for s in spec_data]
    else:
        if not args.domain:
            print("ERROR: --domain is required (or use --spec for batch)", file=sys.stderr)
            return 1
        tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
        specs = [GenerationSpec(
            domain=args.domain,
            difficulty=args.difficulty or "Medium",
            count=args.count,
            tags=tags,
        )]

    print(f"Generating tasks: {sum(s.count for s in specs)} total")
    for s in specs:
        print(f"  {s.domain}/{s.difficulty} x{s.count}")

    report = pipeline.run(specs)

    print(f"\n{report.summary()}")

    # Validate generated tasks by loading through TaskRepository
    if report.task_ids:
        try:
            repo = TaskRepository(args.output_dir)
            loaded = repo.count()
            print(f"\nTaskRepository loaded {loaded} task(s) from {args.output_dir}")
        except Exception as exc:
            print(f"\nWARNING: TaskRepository validation failed: {exc}", file=sys.stderr)

    return 0 if report.total_generated > 0 else 1


def cmd_analyze(args: argparse.Namespace) -> int:
    from .analysis import LeaderboardGenerator

    db = ReportDatabase(args.db)
    reports = db.query()
    if not getattr(args, "include_unverified", False):
        reports = filter_formal_reports(reports)
    if not reports:
        print("No formal verified reports in database.", file=sys.stderr)
        return 1

    lb = LeaderboardGenerator.build(
        reports,
        include_unverified=getattr(args, "include_unverified", False),
    )

    if args.format == "latex":
        print(LeaderboardGenerator.generate_latex_table(lb))
        return 0

    result: dict = {
        "leaderboard": lb,
        "radar_chart": LeaderboardGenerator.radar_chart_data(lb),
        "reasoning_outcome_decoupling": LeaderboardGenerator.reasoning_outcome_analysis(reports),
    }

    if args.output:
        import pathlib
        pathlib.Path(args.output).write_text(
            __import__("json").dumps(result, indent=2, default=str), encoding="utf-8"
        )
        print(f"Analysis written to {args.output}")
    else:
        _print_json(result)

    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="data_agent_bench",
        description="Data Agent Benchmark Framework",
    )
    sub = parser.add_subparsers(dest="command")

    # run
    run_p = sub.add_parser("run", help="Run benchmark on one or more tasks")
    run_p.add_argument("--task", help="Single instance_id to run")
    run_p.add_argument("--tasks-file", help="JSON file containing a list of task IDs to run")
    run_p.add_argument("--all", action="store_true", help="Run all tasks")
    run_p.add_argument("--domain", choices=[d.value for d in Domain], help="Filter by domain")
    run_p.add_argument("--difficulty", choices=[d.value for d in Difficulty], help="Filter by difficulty")
    run_p.add_argument("--tasks-dir", default="./tasks", help="Path to tasks directory")
    run_p.add_argument(
        "--include-unverified",
        action="store_true",
        help="Debug only: include tasks without verified GT provenance.",
    )
    run_p.add_argument("--tasks-root", action="store_true",
                       help="Use tasks-dir as root for resolving data paths")
    run_p.add_argument("--db", default="bench.db", help="SQLite database path")
    run_p.add_argument("--output-dir", default="./bench_runs", help="Output directory for run artifacts")
    run_p.add_argument("--agent", default="simulated",
                       help="Agent spec: 'simulated', 'anthropic:<model>', 'openai:<model>'")
    run_p.add_argument("--env", choices=["local", "docker"], default="local",
                       help="Execution environment for python_repl tool")
    run_p.add_argument("--runs", type=int, default=1, help="Number of runs per task (for pass@k stats)")
    run_p.add_argument("--temperature", type=float, default=0.0, help="LLM temperature")
    run_p.add_argument(
        "--langfuse",
        action="store_true",
        help=(
            "Export agent trajectory and benchmark judging spans to Langfuse. "
            "Requires langfuse package and LANGFUSE_* environment variables."
        ),
    )
    run_p.add_argument(
        "--langfuse-experiment",
        default="data-agent-bench",
        help="Experiment/session label stored in Langfuse trace metadata.",
    )
    run_p.add_argument(
        "--judge", nargs="+", metavar="SPEC", default=None,
        help=(
            "Judge agent spec(s). Each: 'provider:model' or 'provider:model:role'. "
            "Example: --judge anthropic:claude-sonnet-4-6 openai:gpt-4o "
            "anthropic:claude-sonnet-4-6:adversarial"
        ),
    )

    # list
    list_p = sub.add_parser("list", help="List available tasks")
    list_p.add_argument("--tasks-dir", default="./tasks")
    list_p.add_argument(
        "--include-unverified",
        action="store_true",
        help="Debug only: include tasks without verified GT provenance.",
    )

    # archive
    archive_p = sub.add_parser("archive", help="Archive executed tasks into a JSONL file to save space")
    archive_p.add_argument("--tasks-dir", default="./tasks", help="Path to tasks directory")
    archive_p.add_argument("--runs-dir", default="./bench_runs", help="Path to execution runs directory")
    archive_p.add_argument("--archive-file", default="./archives/archived_tasks.jsonl", help="Path to the JSONL archive file")

    # restore
    restore_p = sub.add_parser("restore", help="Restore a specific task from archive")
    restore_p.add_argument("task_id", help="The instance_id of the task to restore (e.g. DS_TASK_051)")
    restore_p.add_argument("--tasks-dir", default="./tasks", help="Path to extract the task to")
    restore_p.add_argument("--archive-file", default="./archives/archived_tasks.jsonl", help="Path to the JSONL archive file")

    # experiment
    exp_p = sub.add_parser("experiment", help="Run contrastive experiments on tasks")
    exp_p.add_argument("--tasks-dir", default="./tasks", help="Path to tasks directory")
    exp_p.add_argument("--tasks-file", help="JSON file containing a list of task IDs to test")
    exp_p.add_argument("--output-dir", default="./bench_runs/experiments", help="Output directory")
    exp_p.add_argument("--db", default="./bench.db", help="Database path")
    exp_p.add_argument("--agent", nargs="+", required=True, help="Agent specs to test")
    exp_p.add_argument("--judge", nargs="*", help="Judge specs")
    exp_p.add_argument("--levels", type=int, nargs="+", default=[0, 1, 2, 3], help="Perturbation levels to run (0=Clean)")
    exp_p.add_argument("--temperature", type=float, default=0.0, help="LLM temperature")

    # report
    rpt_p = sub.add_parser("report", help="Show stored report(s)")
    rpt_p.add_argument("--db", default="bench.db")
    rpt_p.add_argument("--report-id", help="Specific report ID")

    # stats
    stats_p = sub.add_parser("stats", help="Aggregate statistics from database")
    stats_p.add_argument("--db", default="bench.db")
    stats_p.add_argument("--domain", choices=[d.value for d in Domain])
    stats_p.add_argument("--difficulty", choices=[d.value for d in Difficulty])

    # export
    exp_p = sub.add_parser("export", help="Export all reports as JSONL")
    exp_p.add_argument("--db", default="bench.db")
    exp_p.add_argument("--output", default="results.jsonl")

    # generate
    gen_p = sub.add_parser("generate", help="Generate benchmark tasks using LLM agent")
    gen_p.add_argument("--domain", choices=[d.value for d in Domain],
                       help="Target domain for generated tasks")
    gen_p.add_argument("--difficulty", choices=[d.value for d in Difficulty],
                       default="Medium", help="Target difficulty level")
    gen_p.add_argument("--count", type=int, default=5, help="Number of tasks to generate")
    gen_p.add_argument("--tags", default="", help="Comma-separated tags (e.g. 'anova,missing-values')")
    gen_p.add_argument("--agent", required=True,
                       help="Generator agent spec: 'provider:model' (e.g. 'anthropic:claude-sonnet-4-6')")
    gen_p.add_argument(
        "--output-dir",
        default="./tasks_taskgen_candidates",
        help="TaskGen candidate output directory. Use verifier-backed packager for formal tasks.",
    )
    gen_p.add_argument("--spec", help="JSON file with batch generation specs")
    gen_p.add_argument("--with-review", action="store_true",
                       help="Enable ReviewerAgent validation")
    gen_p.add_argument("--reviewer-agent", default=None,
                       help="Reviewer agent spec (defaults to same as --agent)")
    gen_p.add_argument("--with-critic", action="store_true",
                       help="Enable DataCriticAgent validation for realistic datasets")
    gen_p.add_argument("--critic-agent", default=None,
                       help="DataCritic agent spec (defaults to same as --agent)")
    gen_p.add_argument("--with-redteam", action="store_true",
                       help="Enable RedTeamAgent for adversarial perturbation")
    gen_p.add_argument("--redteam-agent", default=None,
                       help="RedTeam agent spec (defaults to same as --agent)")
    gen_p.add_argument("--temperature", type=float, default=0.35,
                       help="LLM temperature for generation (higher = more diverse)")
    gen_p.add_argument(
        "--allow-unverified",
        action="store_true",
        help=(
            "Package generated tasks even if the generation quality gate rejects them. "
            "Use only for debugging; formal benchmark generation rejects unverified tasks by default."
        ),
    )

    # analyze
    ana_p = sub.add_parser("analyze", help="Statistical leaderboard and decoupling analysis")
    ana_p.add_argument("--db", default="bench.db")
    ana_p.add_argument("--output", default="", help="Write JSON result to this file instead of stdout")
    ana_p.add_argument("--format", choices=["json", "latex"], default="json",
                       help="Output format (json or latex table)")
    ana_p.add_argument(
        "--include-unverified",
        action="store_true",
        help="Debug only: include reports without verified task provenance.",
    )

    # academic (oracle profiler & sensitivity analysis)
    aca_p = sub.add_parser("academic", help="Academic validation: oracle run & sensitivity analysis")
    aca_sub = aca_p.add_subparsers(dest="sub")
    
    # oracle
    ora_p = aca_sub.add_parser("oracle", help="Run oracle run to find N")
    ora_p.add_argument("--agent", default="native:openai/gpt-4o", help="Expert agent spec")
    ora_p.add_argument("--max-steps", type=int, default=40, help="Max steps for oracle run")
    ora_p.add_argument("--tasks-dir", default="./tasks")
    ora_p.add_argument("--output-dir", default="./academic/oracle")
    ora_p.add_argument("--db", default="bench.db")
    
    # sensitivity
    sen_p = aca_sub.add_parser("sensitivity", help="Run sensitivity analysis")
    sen_p.add_argument("--agent", required=True, help="Agent spec to test")
    sen_p.add_argument("--range", type=int, nargs="+", default=[5, 10, 15, 20, 25, 30], help="Steps range to test")
    sen_p.add_argument("--tasks-dir", default="./tasks")
    sen_p.add_argument("--output-dir", default="./academic/sensitivity")
    sen_p.add_argument("--db", default="bench.db")
    
    # plot
    plt_p = aca_sub.add_parser("plot", help="Plot saturation curve")
    plt_p.add_argument("--data", required=True, help="Path to sensitivity JSON data")
    plt_p.add_argument("--output", default="./academic/saturation_curve.png", help="Output plot path")

    # export-sft (SFT training data export for fine-tuning)
    sft_p = sub.add_parser("export-sft", help="Export SFT training data from tasks or run traces")
    sft_p.add_argument("--source", choices=["tasks", "runs"], default="tasks",
                       help="Source of training data: 'tasks' (solution_code) or 'runs' (trajectories)")
    sft_p.add_argument("--tasks-dir", default="./tasks", help="Tasks directory (for --source=tasks)")
    sft_p.add_argument("--runs-dir", default="./bench_runs", help="Runs directory (for --source=runs)")
    sft_p.add_argument("--output", default="./sft_data/train.jsonl", help="Output JSONL file")
    sft_p.add_argument("--format", choices=["openai", "sharegpt", "alpaca"], default="openai",
                       help="SFT data format")
    sft_p.add_argument("--min-cas", type=float, default=0.7,
                       help="Min CAS threshold for run-based export (default: 0.7)")
    sft_p.add_argument("--no-verify-filter", action="store_true",
                       help="Include unverified tasks in task-based export")

    # train (standalone training from exported SFT jsonl)
    trn_p = sub.add_parser("train", help="Run standalone training from SFT JSONL")
    trn_p.add_argument("--data", required=True, help="Path to SFT JSONL data")
    trn_p.add_argument("--model-ref", required=True, help="Target model reference")
    trn_p.add_argument("--batch-size", type=int, default=32, help="Training micro-batch size")

    return parser


def cmd_export_sft(args: argparse.Namespace) -> int:
    """Export SFT training data for fine-tuning a data science agent."""
    from .training.sft_data_exporter import SFTDataExporter

    exporter = SFTDataExporter()
    fmt = args.format

    if args.source == "tasks":
        count = exporter.export_from_tasks(
            tasks_dir=args.tasks_dir,
            output_path=args.output,
            fmt=fmt,
            min_verified=not args.no_verify_filter,
        )
    else:
        count = exporter.export_from_runs(
            runs_dir=args.runs_dir,
            output_path=args.output,
            fmt=fmt,
            min_cas=args.min_cas,
        )

    print(f"Exported {count} SFT examples ({fmt} format) → {args.output}")
    return 0 if count > 0 else 1


def cmd_train(args: argparse.Namespace) -> int:
    """Run standalone model training from exported SFT JSONL."""
    from .training.adapters.hf_sft import HFSFTTrainingAdapter
    from .training.runner import TrainingRunner

    adapter = HFSFTTrainingAdapter(model_ref=args.model_ref)
    runner = TrainingRunner(adapter=adapter, batch_size=args.batch_size)
    summary = runner.train_from_jsonl(data_path=args.data, model_ref=args.model_ref)

    print("Training summary")
    print(f"  model_ref:        {summary.model_ref}")
    print(f"  data_path:        {summary.data_path}")
    print(f"  total_examples:   {summary.total_examples}")
    print(f"  consumed_examples:{summary.consumed_examples}")
    print(f"  total_batches:    {summary.total_batches}")
    print(f"  wall_time:        {summary.wall_time_seconds:.2f}s")
    print(f"  status:           {summary.status}")

    return 0 if summary.consumed_examples > 0 else 1


def archive_main(args: argparse.Namespace) -> None:
    from .repository.task_archiver import TaskArchiver
    archiver = TaskArchiver(tasks_dir=args.tasks_dir, runs_dir=args.runs_dir, archive_file=args.archive_file)
    count = archiver.archive_executed_tasks()
    print(f"Successfully archived {count} tasks.")

def restore_main(args: argparse.Namespace) -> None:
    from .repository.task_archiver import TaskArchiver
    archiver = TaskArchiver(tasks_dir=args.tasks_dir, archive_file=args.archive_file)
    success = archiver.restore_task(args.task_id)
    if success:
        print(f"Successfully restored {args.task_id} to {args.tasks_dir}.")
    else:
        print(f"Failed to restore {args.task_id}. Check logs.")

def experiment_main(args: argparse.Namespace) -> int:
    """Run contrastive experiments: clean vs perturbed paired evaluation."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    from .experiments.contrastive import ContrastiveExperiment
    from .analysis.contrastive_analyzer import ContrastiveAnalyzer
    import dataclasses

    agent_specs = args.agent if isinstance(args.agent, list) else [args.agent]
    judge_specs = (
        args.judge if isinstance(args.judge, list)
        else [args.judge] if args.judge
        else []
    )

    # Load task IDs from file if specified
    task_ids = None
    if getattr(args, "tasks_file", None):
        task_ids = json.load(open(args.tasks_file))

    temperature = float(getattr(args, "temperature", 0.0) or 0.0)

    experiment = ContrastiveExperiment(
        agent_specs=agent_specs,
        judge_specs=judge_specs,
        tasks_dir=args.tasks_dir,
        output_dir=args.output_dir,
        db_path=args.db,
        task_ids=task_ids,
        temperature=temperature,
    )

    results = experiment.run_batch(levels=args.levels)

    # Analyze
    analyzer = ContrastiveAnalyzer()
    analysis_report = analyzer.analyze(results)

    # Save
    out_path = pathlib.Path(args.output_dir) / "contrastive_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "raw_pairs": [dataclasses.asdict(r) for r in results],
                "analysis": analysis_report,
            },
            f, indent=2, default=str,
        )

    print(f"\nExperiment completed: {len(results)} paired result(s)")
    if "degradation_matrix" in analysis_report:
        print("Degradation matrix (mean ΔCAS):")
        for model, row in analysis_report["degradation_matrix"].items():
            cols = " | ".join(f"{k}: {v:+.4f}" for k, v in row.items())
            print(f"  {model}: {cols}")
    if "statistical_tests" in analysis_report:
        for model, t in analysis_report["statistical_tests"].items():
            sig = "YES" if t.get("ttest_significant") else "no"
            d = t.get("cohens_d", "?")
            print(f"  {model}: p={t.get('ttest_p', '?')}, Cohen's d={d}, significant={sig}")

    print(f"Full results saved to {out_path}")
    return 0

def cmd_academic(args: argparse.Namespace) -> int:
    from .analysis.academic_suite import AcademicSuite
    
    suite = AcademicSuite(args.tasks_dir, args.db, args.output_dir if hasattr(args, 'output_dir') else "./academic")
    
    if args.sub == "oracle":
        suite.run_oracle(agent_spec=args.agent, max_steps=args.max_steps)
    elif args.sub == "sensitivity":
        suite.run_sensitivity_analysis(agent_spec=args.agent, steps_range=args.range)
    elif args.sub == "plot":
        suite.plot_saturation_curve(args.data, args.output)
    else:
        print("ERROR: Invalid academic subcommand.")
        return 1
    return 0

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    dispatch = {
        "run": cmd_run,
        "list": cmd_list,
        "report": cmd_report,
        "stats": cmd_stats,
        "export": cmd_export,
        "analyze": cmd_analyze,
        "generate": cmd_generate,
        "archive": archive_main,
        "restore": restore_main,
        "experiment": experiment_main,
        "export-sft": cmd_export_sft,
        "train": cmd_train,
        "academic": cmd_academic,
    }
    sys.exit(dispatch[args.command](args))


if __name__ == "__main__":
    main()
