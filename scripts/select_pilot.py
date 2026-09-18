"""Select 20 pilot tasks from the 80 core tasks."""
import json
import random

random.seed(123)

core = json.load(open("core_80_tasks.json"))
pilot = random.sample(core, 20)

with open("pilot_20_tasks.json", "w") as f:
    json.dump(pilot, f, indent=2)

print(f"Pilot tasks ({len(pilot)}):")
for t in sorted(pilot):
    print(f"  {t}")
