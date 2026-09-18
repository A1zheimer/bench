"""Select 80 core tasks via stratified sampling (domain × difficulty)."""
import json
import os
import random

random.seed(42)

TASKS_DIR = "./tasks"
all_task_dirs = sorted(
    d for d in os.listdir(TASKS_DIR)
    if os.path.isdir(os.path.join(TASKS_DIR, d)) and d.startswith("DS_TASK_")
)

# Load metadata for each task
tasks_by_group = {}
for t in all_task_dirs:
    task_json_path = os.path.join(TASKS_DIR, t, "task.json")
    if not os.path.exists(task_json_path):
        continue
    with open(task_json_path) as f:
        meta = json.load(f).get("task_metadata", {})
    domain = meta.get("domain", "Generic")
    diff = meta.get("difficulty", "Medium")
    key = (domain, diff)
    tasks_by_group.setdefault(key, []).append(t)

# Stratified sampling: ~5-6 per group (5 domains × 3 difficulties = 15 groups)
selected = []
for key in sorted(tasks_by_group.keys()):
    candidates = tasks_by_group[key]
    n = min(6, len(candidates))
    selected.extend(random.sample(candidates, n))

selected = selected[:80]

with open("core_80_tasks.json", "w") as f:
    json.dump(selected, f, indent=2)

print(f"Selected {len(selected)} tasks from {len(tasks_by_group)} groups")
for key in sorted(tasks_by_group.keys()):
    count = len([t for t in selected if t in tasks_by_group[key]])
    print(f"  {key[0]:12s} / {key[1]:8s}: {count}")
