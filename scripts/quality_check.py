"""Quality check: sample 10 reports and inspect."""
import json
import random
from pathlib import Path

random.seed(42)
reports_dir = Path("runs/native_gpt4o/clean")
if not reports_dir.exists():
    reports_dir = Path("bench_runs")

all_reports = list(reports_dir.glob("*/report.json"))
if not all_reports:
    print("No reports found.")
    exit(0)

sample = random.sample(all_reports, min(10, len(all_reports)))

for rpath in sample:
    r = json.load(open(rpath))
    task_id = r.get("instance_id", rpath.parent.name)
    m = r["metrics"]
    acc = m["result_accuracy"]
    proc = m["process_quality"]
    safety = m["safety_score"]
    cas = 0.4 * acc + 0.35 * proc + 0.25 * safety
    steps = len(r.get("trajectory_summary", []))
    print(f"{task_id}: CAS={cas:.3f} (acc={acc:.3f}, proc={proc:.3f}, safe={safety:.3f})")
    print(f"  Steps: {steps}")
    print(f"  Final answer: {str(r.get('execution_result', ''))[:100]}...")
    print()
