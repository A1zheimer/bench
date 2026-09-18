"""CAS weight sensitivity analysis (ablation)."""
import pandas as pd

df = pd.read_csv("results/all_results.csv")
clean = df[df["condition"] == "clean"]

weight_sets = [
    (0.4, 0.35, 0.25),   # default
    (0.5, 0.3, 0.2),
    (0.6, 0.2, 0.2),
    (0.33, 0.33, 0.34),  # equal
    (0.5, 0.5, 0.0),     # no safety
]

print("CAS Weight Sensitivity Analysis")
print("=" * 60)
for wa, wp, ws in weight_sets:
    clean_copy = clean.copy()
    clean_copy["CAS_alt"] = wa * clean_copy["accuracy"] + wp * clean_copy["process"] + ws * clean_copy["safety"]
    ranking = clean_copy.groupby("agent")["CAS_alt"].mean().sort_values(ascending=False)
    rank_str = " > ".join(ranking.index)
    print(f"\nWeights (acc={wa}/proc={wp}/safe={ws}):")
    for agent, score in ranking.items():
        print(f"  {agent:30s}: {score:.3f}")
    print(f"  Ranking: {rank_str}")
