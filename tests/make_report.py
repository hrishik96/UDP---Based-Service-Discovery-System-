import csv
import os
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

here = os.path.dirname(os.path.abspath(__file__))
results = os.path.join(here, "..", "results")

# ---- latency chart from latency.csv (repeated runs are averaged) ----
data = defaultdict(list)
with open(os.path.join(results, "latency.csv")) as f:
    for row in csv.DictReader(f):
        key = (row["controller"], int(row["clients"]))
        data[key].append((float(row["mean_ms"]), float(row["p95_ms"])))

clients = sorted({k[1] for k in data})
width = 0.35
fig, axes = plt.subplots(1, 2, figsize=(10, 4))
for ax, idx, title in ((axes[0], 0, "Mean discovery latency (ms)"),
                       (axes[1], 1, "p95 discovery latency (ms)")):
    for shift, label in ((-width / 2, "static"), (width / 2, "dynamic")):
        vals = []
        for c in clients:
            runs = data.get((label, c), [])
            vals.append(sum(r[idx] for r in runs) / len(runs) if runs else 0)
        ax.bar([i + shift for i in range(len(clients))], vals, width, label=label)
    ax.set_xticks(range(len(clients)))
    ax.set_xticklabels([str(c) for c in clients])
    ax.set_xlabel("Concurrent clients")
    ax.set_title(title)
    ax.legend()
plt.tight_layout()
plt.savefig(os.path.join(results, "latency_chart.png"), dpi=150)
plt.close()

# ---- failure comparison (values measured in the Mininet runs) ----
recovery = {"static": 5.18, "dynamic": 5.10}
stale = {"static": 52, "dynamic": 1}

with open(os.path.join(results, "failure_comparison.csv"), "w") as f:
    f.write("controller,recovery_time_s,packets_forwarded_to_dead_server\n")
    for name in ("static", "dynamic"):
        f.write("%s,%.2f,%d\n" % (name, recovery[name], stale[name]))

fig, axes = plt.subplots(1, 2, figsize=(9, 4))
axes[0].bar(list(recovery), list(recovery.values()), color=["#888888", "#2E75B6"])
axes[0].set_title("Client recovery time (s)")
axes[1].bar(list(stale), list(stale.values()), color=["#888888", "#2E75B6"])
axes[1].set_title("Packets forwarded to dead server (of 50 sent)")
plt.tight_layout()
plt.savefig(os.path.join(results, "failure_chart.png"), dpi=150)
plt.close()

print("Saved latency_chart.png, failure_chart.png, failure_comparison.csv in results/")
