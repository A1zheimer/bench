"""Figure 4: Radar chart comparing agents across 5 dimensions."""
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

df = pd.read_csv("results/all_results.csv")
clean = df[df["condition"] == "clean"]

categories = ["Accuracy", "Process", "Safety", "Efficiency", "Robustness"]
N = len(categories)
angles = [n / float(N) * 2 * np.pi for n in range(N)] + [0]

fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))

for agent in clean["agent"].unique():
    agent_data = clean[clean["agent"] == agent]
    acc = agent_data["accuracy"].mean()
    proc = agent_data["process"].mean()
    safe = agent_data["safety"].mean()
    max_tokens = clean["tokens"].max()
    efficiency = 1 - (agent_data["tokens"].mean() / max_tokens) if max_tokens > 0 else 0.5

    l3 = df[(df["agent"] == agent) & (df["condition"] == "L3")]
    if len(l3) > 0:
        delta = agent_data["CAS"].mean() - l3["CAS"].mean()
        robustness = max(0, 1 - delta * 2)
    else:
        robustness = 0.5

    values = [acc, proc, safe, efficiency, robustness] + [acc]
    ax.plot(angles, values, linewidth=2, label=agent)
    ax.fill(angles, values, alpha=0.1)

ax.set_xticks(angles[:-1])
ax.set_xticklabels(categories)
ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=8)
plt.tight_layout()
plt.savefig("results/fig4_radar.pdf", dpi=300)
plt.savefig("results/fig4_radar.png", dpi=300)
print("Saved fig4_radar.pdf/.png")
