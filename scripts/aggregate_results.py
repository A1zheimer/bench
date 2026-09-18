"""Aggregate all experiment results into a single CSV."""
import json
import os
import pandas as pd
from pathlib import Path

core_tasks = json.load(open("core_80_tasks.json"))
agents = [
    ("native_gpt4o", "NativeAgent/GPT-4o"),
    ("native_claude", "NativeAgent/Claude-Sonnet"),
    ("native_4omini", "NativeAgent/GPT-4o-mini"),
    ("native_deepseek", "NativeAgent/DeepSeek-V3"),
    ("native_qwen7b", "NativeAgent/Qwen-7B"),
    ("data_interpreter", "MetaGPT/DataInterpreter"),
    ("open_interpreter", "OpenInterpreter"),
]
conditions = ["clean", "L1", "L2", "L3"]

rows = []
for agent_dir, agent_name in agents:
    for task_id in core_tasks:
        for cond in conditions:
            rpath = Path(f"runs/{agent_dir}/{cond}/{task_id}/report.json")
            if not rpath.exists():
                continue
            r = json.load(open(rpath))
            m = r["metrics"]
            cas = 0.4 * m["result_accuracy"] + 0.35 * m["process_quality"] + 0.25 * m["safety_score"]
            rows.append({
                "agent": agent_name,
                "task_id": task_id,
                "condition": cond,
                "CAS": cas,
                "accuracy": m["result_accuracy"],
                "process": m["process_quality"],
                "safety": m["safety_score"],
                "tokens": m.get("total_tokens", 0),
                "cost": m.get("total_cost_usd", 0),
                "wall_time": m.get("wall_time_seconds", 0),
            })

os.makedirs("results", exist_ok=True)
df = pd.DataFrame(rows)
df.to_csv("results/all_results.csv", index=False)
print(f"Total records: {len(df)}")
if len(df) > 0:
    print(df.groupby(["agent", "condition"])["CAS"].agg(["mean", "std", "count"]))
