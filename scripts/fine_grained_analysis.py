"""Fine-grained analysis by domain and difficulty."""
import json
import pandas as pd

df = pd.read_csv("results/all_results.csv")

task_meta = {}
core_tasks = json.load(open("core_80_tasks.json"))
for task_id in core_tasks:
    try:
        meta = json.load(open(f"tasks/{task_id}/task.json"))["task_metadata"]
        task_meta[task_id] = {"domain": meta["domain"], "difficulty": meta["difficulty"]}
    except Exception:
        pass

df["domain"] = df["task_id"].map(lambda x: task_meta.get(x, {}).get("domain", "?"))
df["difficulty"] = df["task_id"].map(lambda x: task_meta.get(x, {}).get("difficulty", "?"))

print("=== CAS by Domain (Clean) ===")
pivot = df[df["condition"] == "clean"].groupby(["agent", "domain"])["CAS"].mean().unstack()
print(pivot.round(3).to_string())

print("\n=== CAS by Difficulty (Clean) ===")
pivot = df[df["condition"] == "clean"].groupby(["agent", "difficulty"])["CAS"].mean().unstack()
print(pivot.round(3).to_string())

print("\n=== ΔCAS(L3) by Domain ===")
for domain in sorted(df["domain"].unique()):
    if domain == "?":
        continue
    print(f"\n--- {domain} ---")
    for agent in df["agent"].unique():
        c = df[(df["agent"] == agent) & (df["condition"] == "clean") & (df["domain"] == domain)]["CAS"].mean()
        l3 = df[(df["agent"] == agent) & (df["condition"] == "L3") & (df["domain"] == domain)]["CAS"].mean()
        if pd.notna(c) and pd.notna(l3):
            print(f"  {agent:30s}: ΔCAS = {c - l3:.4f}")
