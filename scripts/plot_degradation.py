"""Figure 3: CAS degradation curves under perturbation levels."""
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("results/all_results.csv")

fig, ax = plt.subplots(figsize=(8, 5))
levels = ["clean", "L1", "L2", "L3"]
colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]

for i, agent in enumerate(df["agent"].unique()):
    means = []
    for cond in levels:
        m = df[(df["agent"] == agent) & (df["condition"] == cond)]["CAS"].mean()
        means.append(m)
    ax.plot(levels, means, marker="o", label=agent, color=colors[i % len(colors)], linewidth=2)

ax.set_xlabel("Perturbation Level", fontsize=12)
ax.set_ylabel("CAS Score", fontsize=12)
ax.set_title("Semantic Robustness: CAS Degradation Under Perturbation", fontsize=13)
ax.legend(fontsize=9, loc="lower left")
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("results/fig3_degradation.pdf", dpi=300)
plt.savefig("results/fig3_degradation.png", dpi=300)
print("Saved fig3_degradation.pdf/.png")
