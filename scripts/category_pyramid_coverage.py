"""Category x pyramid coverage report for the validation scenario library (T-B-02).

Reports the **5 x 4 = 20-cell** coverage matrix over the fixed scenario
taxonomy and the validation pyramid:

- categories: ``happy_path``, ``edge_case``, ``failure``,
  ``agent_interaction``, ``performance``
- pyramid layers: ``unit``, ``component``, ``e2e``, ``red_team``

Each scenario YAML under ``src/autoinfo/mcp/scenarios/`` (recursively,
including ``regression/``) declares a REQUIRED top-level ``category`` and
``pyramid_layer``.  Both are enum-validated by the loader in
``autoinfo.mcp.validation``; this script is the coverage surface over that
schema.

Definitions
-----------
- A scenario is **classified** when its ``category`` is one of the 5 and its
  ``pyramid_layer`` is one of the 4.  The enums are imported from the loader
  so this report can never drift from the schema (no duplicated enum lists).
- A **populated cell** holds >= 1 scenario.
- An **empty cell** (0 scenarios) is a recorded coverage gap — valid at this
  stage (e.g. ``performance`` and the adversarial ``red_team`` layer are
  filled by later waves), never an error.
- An **unclassified scenario** — a missing or out-of-enum ``category`` /
  ``pyramid_layer`` — is an error: the script exits non-zero so coverage can
  never silently claim a cell it cannot place a scenario in.

NOTE: the scenario-authoring contract (``docs/dev/validation-scenario-contract.md``)
is owned by another work item, so this script is the authoritative description
of how ``category`` / ``pyramid_layer`` are consumed for coverage purposes.

Run from the project root::

    python3 scripts/category_pyramid_coverage.py [scenarios_dir]

Exit code 0 when every on-disk scenario is classified (empty cells allowed),
1 otherwise.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS_DIR = ROOT / "src" / "autoinfo" / "mcp" / "scenarios"

# Single source of truth: the loader's enums (sys.path first so the script
# runs from a source checkout without an editable install).
sys.path.insert(0, str(ROOT / "src"))
from autoinfo.mcp.validation import (  # noqa: E402
    PYRAMID_LAYERS,
    SCENARIO_CATEGORIES,
)

CATEGORY_ORDER: tuple[str, ...] = (
    "happy_path",
    "edge_case",
    "failure",
    "agent_interaction",
    "performance",
)
LAYER_ORDER: tuple[str, ...] = ("unit", "component", "e2e", "red_team")


def _ordered(values: frozenset[str], preferred: tuple[str, ...]) -> list[str]:
    """Preferred display order, then any extra enum members alphabetically."""
    known = [v for v in preferred if v in values]
    extra = sorted(values - set(preferred))
    return known + extra


def scan(scenarios_dir: Path) -> dict[str, Any]:
    """Classify every scenario YAML into the 20-cell matrix.

    Returns ``{"cells": {category: {layer: [names]}}, "unclassified":
    [(name, reason)], "total": int}``.  Parsing is static YAML — no server
    import, no execution.
    """
    cells: dict[str, dict[str, list[str]]] = {
        c: {layer: [] for layer in LAYER_ORDER} for c in CATEGORY_ORDER
    }
    unclassified: list[tuple[str, str]] = []
    total = 0
    for yf in sorted(scenarios_dir.rglob("*.yaml")):
        data = yaml.safe_load(yf.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            unclassified.append((yf.name, "not a YAML mapping"))
            continue
        total += 1
        name = str(data.get("name") or yf.stem)
        category = data.get("category")
        layer = data.get("pyramid_layer")
        reasons: list[str] = []
        if not isinstance(category, str) or category not in SCENARIO_CATEGORIES:
            reasons.append(f"invalid/missing category={category!r}")
        if not isinstance(layer, str) or layer not in PYRAMID_LAYERS:
            reasons.append(f"invalid/missing pyramid_layer={layer!r}")
        if reasons:
            unclassified.append((name, "; ".join(reasons)))
            continue
        if not isinstance(category, str) or not isinstance(layer, str):
            raise AssertionError("validated enum members must be strings")
        cells[category][layer].append(name)
    return {"cells": cells, "unclassified": unclassified, "total": total}


def main(argv: Sequence[str] | None = None) -> int:
    tokens = list(sys.argv) if argv is None else list(argv)
    scenarios_dir = Path(tokens[1]) if len(tokens) > 1 else SCENARIOS_DIR
    report = scan(scenarios_dir)
    cells = report["cells"]
    unclassified = report["unclassified"]

    categories = _ordered(SCENARIO_CATEGORIES, CATEGORY_ORDER)
    layers = _ordered(PYRAMID_LAYERS, LAYER_ORDER)

    print("Category x pyramid coverage (5 x 4 = 20 cells)")
    print("=" * 72)
    header = f"{'category':<20}" + "".join(f"{layer:>12}" for layer in layers)
    print(header + f"{'total':>10}")
    populated = 0
    empty = 0
    cat_totals: Counter[str] = Counter()
    layer_totals: Counter[str] = Counter()
    for cat in categories:
        row = cells.get(cat, {})
        counts = [len(row.get(layer, [])) for layer in layers]
        print(f"{cat:<20}" + "".join(f"{n:>12}" for n in counts) + f"{sum(counts):>10}")
        for layer, n in zip(layers, counts):
            if n:
                populated += 1
            else:
                empty += 1
            cat_totals[cat] += n
            layer_totals[layer] += n
    total_row = [layer_totals[layer] for layer in layers]
    print(f"{'TOTAL':<20}" + "".join(f"{n:>12}" for n in total_row) + f"{report['total']:>10}")
    print()
    print(f"Scenarios scanned  : {report['total']}")
    print(f"Cells populated    : {populated}/20")
    print(f"Cells empty (gap)  : {empty}/20")
    print(f"Unclassified       : {len(unclassified)}")

    if unclassified:
        print()
        print(f"UNCLASSIFIED scenarios ({len(unclassified)}):")
        for name, reason in unclassified:
            print(f"  - {name}: {reason}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
