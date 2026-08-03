"""Coverage audit: which of the 141 MCP tools are exercised by scenarios.

Run from the project root: ``python3 scripts/coverage_audit.py``
"""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src/autoinfo/mcp/server.py"
SCN = ROOT / "src/autoinfo/mcp/scenarios"

src = SRC.read_text()
tools = sorted(set(re.findall(r'Tool\(\s*name="(\w+)"', src)))
print(f"Total MCP tools declared: {len(tools)}")

covered = set()
scenario_names = []
for yf in sorted(SCN.glob("*.yaml")):
    data = yaml.safe_load(yf.read_text())
    scenario_names.append(data.get("name"))
    for step in data.get("steps", []):
        if step.get("kind", "mcp") == "mcp":
            covered.add(step.get("tool"))

missing = sorted(set(tools) - covered)
print(f"Covered by scenarios: {len(covered)}/{len(tools)}")
print(f"Scenarios: {len(scenario_names)}")
print(f"MISSING tools ({len(missing)}):")
for t in missing:
    print(f"  - {t}")
