"""Coverage audit: which of the 141 MCP tools are exercised by scenarios.

Run from the project root: ``python3 scripts/coverage_audit.py``

Writes a timestamped report to ``validation-runs/coverage/coverage-<date>.json``
and prints the same summary to stdout (fixes #129 P1-5).
"""
import datetime
import json
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

stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
out_dir = ROOT / "validation-runs" / "coverage"
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / f"coverage-{stamp}.json"
payload = {
    "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
    "total_tools": len(tools),
    "covered_tools": len(covered),
    "missing_tools": missing,
    "scenario_count": len(scenario_names),
    "scenario_names": scenario_names,
}
out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Coverage report: {out_path}")
