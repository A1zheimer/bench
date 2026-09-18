from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from data_agent_bench.repository.task_repo import TaskRepository

from .dataset_builders import DatasetBuilderRegistry
from .manifest import TaskManifest
from .manifest_sampler import ManifestSampler
from .packager import PackagedTask, TaskPackager
from .redteam_builder import RedteamBuilder


def cmd_build_core(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    _prepare_output_dir(output_dir, overwrite=args.overwrite)
    cache_dir = output_dir.parent / f".{output_dir.name}_build_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    sampler = ManifestSampler(seed=args.seed)
    batch = sampler.sample_core(
        count_per_template=args.count_per_template,
        task_id_start=args.task_id_start,
    )
    dataset_builder = DatasetBuilderRegistry()
    packager = TaskPackager(output_dir)
    packaged: List[PackagedTask] = []
    rows: List[Dict[str, Any]] = []

    for manifest in batch.manifests:
        built = dataset_builder.build(manifest, cache_dir, seed=args.seed)
        task = packager.package(
            manifest,
            built.dataset_path,
            dataset_profile_path=built.profile_path,
        )
        replayed = packager.replay_verify(task.task_dir)
        packaged.append(task)
        rows.append({
            "task_id": task.task_id,
            "template_id": manifest.template_id,
            "domain": manifest.domain,
            "difficulty": manifest.difficulty,
            "key_count": len(task.expected_output.get("key_values", {})),
            "dataset_sha256": replayed["dataset_sha256"],
            "replay": "PASS",
        })

    tasks_file = Path(args.tasks_file) if args.tasks_file else output_dir.parent / f"{output_dir.name}_tasks.json"
    tasks_file.write_text(json.dumps([task.task_id for task in packaged], indent=2), "utf-8")

    repo = TaskRepository(str(output_dir), require_verified=True)
    report_path = Path(args.report) if args.report else Path("reports/verified_core_v1_smoke.md")
    _write_core_report(report_path, output_dir, rows, repo_count=repo.count(), tasks_file=tasks_file)

    print(f"Generated {len(packaged)} verified clean task(s) in {output_dir}")
    print(f"Bench repository loaded {repo.count()} verified task(s)")
    print(f"Task IDs: {tasks_file}")
    print(f"Report: {report_path}")
    return 0 if len(packaged) == repo.count() else 1


def cmd_build_redteam(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    _prepare_output_dir(output_dir, overwrite=args.overwrite)
    builder = RedteamBuilder(
        args.clean_tasks_dir,
        output_dir,
        seed=args.seed,
    )
    result = builder.build(max_base_tasks=args.max_base_tasks)

    tasks_file = Path(args.tasks_file) if args.tasks_file else output_dir.parent / f"{output_dir.name}_tasks.json"
    tasks_file.write_text(
        json.dumps([task.task_id for task in result.packaged_tasks], indent=2),
        "utf-8",
    )

    repo = TaskRepository(str(output_dir), require_verified=True)
    report_path = Path(args.report) if args.report else Path("reports/verified_redteam_v1_smoke.md")
    _write_redteam_report(report_path, output_dir, result.report_rows, repo_count=repo.count(), tasks_file=tasks_file)

    print(f"Generated {len(result.packaged_tasks)} verified redteam task(s) in {output_dir}")
    print(f"Bench repository loaded {repo.count()} verified task(s)")
    print(f"Task IDs: {tasks_file}")
    print(f"Report: {report_path}")
    return 0 if len(result.packaged_tasks) == repo.count() else 1


def cmd_replay(args: argparse.Namespace) -> int:
    root = Path(args.tasks_dir)
    packager = TaskPackager(root)
    rows: List[Dict[str, Any]] = []
    ok = True
    for task_dir in sorted(p for p in root.iterdir() if p.is_dir() and (p / "task_manifest.json").exists()):
        try:
            manifest = TaskManifest.from_path(task_dir / "task_manifest.json")
            replayed = packager.replay_verify(task_dir)
            rows.append({
                "task_id": manifest.task_id,
                "template_id": manifest.template_id,
                "dataset_sha256": replayed["dataset_sha256"],
                "replay": "PASS",
            })
        except Exception as exc:
            ok = False
            rows.append({
                "task_id": task_dir.name,
                "template_id": "?",
                "dataset_sha256": "?",
                "replay": f"FAIL: {exc}",
            })
    report_path = Path(args.report) if args.report else Path("reports/verified_replay.md")
    _write_replay_report(report_path, root, rows)
    print(f"Replay checked {len(rows)} task(s); report: {report_path}")
    return 0 if ok else 1


def _prepare_output_dir(output_dir: Path, *, overwrite: bool) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        if not overwrite:
            raise SystemExit(
                f"Output directory is not empty: {output_dir}. "
                "Use --overwrite to rebuild this generated verified set."
            )
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def _write_core_report(
    path: Path,
    output_dir: Path,
    rows: List[Dict[str, Any]],
    *,
    repo_count: int,
    tasks_file: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    template_dist = Counter(row["template_id"] for row in rows)
    domain_dist = Counter(row["domain"] for row in rows)
    difficulty_dist = Counter(row["difficulty"] for row in rows)
    lines = [
        "# Verified Core V1 Smoke Report",
        "",
        f"- generated_at: `{datetime.now(timezone.utc).isoformat()}`",
        f"- output_dir: `{output_dir}`",
        f"- tasks_file: `{tasks_file}`",
        f"- total_tasks: `{len(rows)}`",
        f"- bench_repo_verified_load_count: `{repo_count}`",
        f"- gt_replay: `{'PASS' if all(r['replay'] == 'PASS' for r in rows) else 'FAIL'}`",
        "",
        "Formal note: legacy pilot20/121 and taskgen candidate tasks are excluded from formal model conclusions.",
        "",
        "## Template Distribution",
        "",
        _counter_table(template_dist),
        "",
        "## Domain Distribution",
        "",
        _counter_table(domain_dist),
        "",
        "## Difficulty Distribution",
        "",
        _counter_table(difficulty_dist),
        "",
        "## Tasks",
        "",
        "| Task | Template | Domain | Difficulty | Keys | Replay | Dataset SHA256 |",
        "|---|---|---|---|---:|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['task_id']} | {row['template_id']} | {row['domain']} | "
            f"{row['difficulty']} | {row['key_count']} | {row['replay']} | "
            f"`{row['dataset_sha256'][:12]}...` |"
        )
    path.write_text("\n".join(lines) + "\n", "utf-8")


def _write_redteam_report(
    path: Path,
    output_dir: Path,
    rows: List[Dict[str, Any]],
    *,
    repo_count: int,
    tasks_file: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    attack_dist = Counter(row["attack_type"] for row in rows)
    policy_dist = Counter(row["gt_policy"] for row in rows)
    lines = [
        "# Verified Redteam V1 Smoke Report",
        "",
        f"- generated_at: `{datetime.now(timezone.utc).isoformat()}`",
        f"- output_dir: `{output_dir}`",
        f"- tasks_file: `{tasks_file}`",
        f"- total_tasks: `{len(rows)}`",
        f"- bench_repo_verified_load_count: `{repo_count}`",
        f"- invariant/recomputed_checks: `{'PASS' if all(r['replay'] == 'PASS' for r in rows) else 'FAIL'}`",
        "",
        "## Attack Distribution",
        "",
        _counter_table(attack_dist),
        "",
        "## GT Policy Distribution",
        "",
        _counter_table(policy_dist),
        "",
        "## Tasks",
        "",
        "| Task | Base Task | Template | Attack | GT Policy | Keys | Replay |",
        "|---|---|---|---|---|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['task_id']} | {row['base_task_id']} | {row['template_id']} | "
            f"{row['attack_type']} | {row['gt_policy']} | {row['key_count']} | {row['replay']} |"
        )
    path.write_text("\n".join(lines) + "\n", "utf-8")


def _write_replay_report(path: Path, root: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Verified Task Replay Report",
        "",
        f"- generated_at: `{datetime.now(timezone.utc).isoformat()}`",
        f"- tasks_dir: `{root}`",
        f"- total_tasks: `{len(rows)}`",
        "",
        "| Task | Template | Replay | Dataset SHA256 |",
        "|---|---|---|---|",
    ]
    for row in rows:
        digest = row["dataset_sha256"]
        digest_display = f"`{digest[:12]}...`" if digest != "?" else "?"
        lines.append(f"| {row['task_id']} | {row['template_id']} | {row['replay']} | {digest_display} |")
    path.write_text("\n".join(lines) + "\n", "utf-8")


def _counter_table(counter: Counter[str]) -> str:
    lines = ["| Value | Count |", "|---|---:|"]
    for key, value in sorted(counter.items()):
        lines.append(f"| {key} | {value} |")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="data_agent_taskgen",
        description="Verifier-backed task generation utilities for DataAgentBench.",
    )
    sub = parser.add_subparsers(dest="command")

    core = sub.add_parser("build-core", help="Build verifier-backed clean benchmark tasks")
    core.add_argument("--output-dir", default="tasks_verified_core_v1")
    core.add_argument("--count-per-template", type=int, default=2)
    core.add_argument("--seed", type=int, default=20260521)
    core.add_argument("--task-id-start", type=int, default=1)
    core.add_argument("--tasks-file", default="")
    core.add_argument("--report", default="reports/verified_core_v1_smoke.md")
    core.add_argument("--overwrite", action="store_true")

    red = sub.add_parser("build-redteam", help="Build paired redteam tasks from verified clean tasks")
    red.add_argument("--clean-tasks-dir", default="tasks_verified_core_v1")
    red.add_argument("--output-dir", default="tasks_verified_redteam_v1")
    red.add_argument("--max-base-tasks", type=int, default=5)
    red.add_argument("--seed", type=int, default=20260521)
    red.add_argument("--tasks-file", default="")
    red.add_argument("--report", default="reports/verified_redteam_v1_smoke.md")
    red.add_argument("--overwrite", action="store_true")

    replay = sub.add_parser("replay", help="Replay verifier for a verified task directory")
    replay.add_argument("--tasks-dir", required=True)
    replay.add_argument("--report", default="reports/verified_replay.md")

    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1
    dispatch = {
        "build-core": cmd_build_core,
        "build-redteam": cmd_build_redteam,
        "replay": cmd_replay,
    }
    return dispatch[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
