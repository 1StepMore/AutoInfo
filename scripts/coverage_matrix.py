#!/usr/bin/env python3
"""Generate the end-user coverage matrix report (E8, issue #131).

Reads ``docs/dev/specs/end-user-matrix.yaml`` (sparse spec: 13 demo domains
x 8 products x 7 formats) plus real evidence — ``outputs/**`` persisted
artifacts (``outputs/<domain>/<product>-<format>-<stamp>.<ext>``, written by
the MCP ``persist`` path) and the ``manifest.json`` from
``scripts/validation_delivery.py`` (bare or inside its ``*.zip`` archive) —
and renders ``matrix-report.md`` marking every cell as one of::

    有produced              evidence found for this domain x product x format
    空gap                   required cell with no evidence (LLM available,
                            or product is not LLM-gated)
    不适用not-applicable    non-required cell with no evidence
    未配置unconfigured      required cell whose product is LLM-gated while
                            the LLM key is unavailable (Oracle R8: NOT a gap)

Usage::

    python3 scripts/coverage_matrix.py \\
        --spec docs/dev/specs/end-user-matrix.yaml --evidence outputs \\
        [--llm-available | --no-llm] [--output outputs/coverage-matrix/]

Exit codes: 0 on success (report is informational — gaps are fine);
2 when the spec file or the evidence directory is missing.

The classification logic lives in :func:`classify_cell` as a pure function so
``tests/test_coverage_matrix.py`` can exercise it without a CLI run.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any

import yaml

# --- Cell statuses ----------------------------------------------------------
PRODUCED = "有produced"
GAP = "空gap"
NOT_APPLICABLE = "不适用not-applicable"
UNCONFIGURED = "未配置unconfigured"

_ALL_STATUSES = (PRODUCED, GAP, NOT_APPLICABLE, UNCONFIGURED)

# format -> extension, mirrors _PERSIST_EXT_BY_FORMAT in src/autoinfo/mcp/server.py
FORMAT_EXT = {
    "markdown": ".md",
    "html": ".html",
    "json": ".json",
    "agent": ".json",
    "audio": ".mp3",
    "epub": ".epub",
    "audiobook": ".zip",
}

# Persisted artifact filename: <product>-<format>-<YYYYmmdd-HHMMSS>.<ext>.
# Product names may contain dashes (magazine-digest, premium-briefing, ...),
# so the format token is anchored to the known format set.
_PERSISTED_RE = re.compile(
    r"^(?P<product>.+?)-(?P<format>markdown|html|json|agent|audio|epub|audiobook)"
    r"-\d{8}-\d{6}(?P<ext>\.md|\.json|\.html|\.mp3|\.epub|\.zip)$"
)

Cell = tuple[str, str, str]  # (domain, product, format)


# ---------------------------------------------------------------------------
# Pure classification logic (tested by tests/test_coverage_matrix.py)
# ---------------------------------------------------------------------------


def required_cells_set(spec: dict[str, Any]) -> set[Cell]:
    """Return the required cells of *spec* as ``{(domain, product, format)}``."""
    out: set[Cell] = set()
    for c in spec.get("required_cells", []):
        out.add((c["domain"], c["product"], c["format"]))
    return out


def classify_cell(
    cell: dict[str, str] | Cell,
    produced: set[Cell],
    llm_available: bool,
    spec: dict[str, Any],
) -> str:
    """Classify one domain x product x format cell.

    Priority (Oracle R8 — required empty LLM-gated cells are
    ``未配置unconfigured``, NEVER ``空gap``):

    1. required AND produced                      -> 有produced
    2. required AND NOT produced:
       - product in llm_gated_products AND LLM unavailable -> 未配置unconfigured
       - otherwise                              -> 空gap
    3. non-required AND produced                 -> 有produced
    4. non-required AND no evidence              -> 不适用not-applicable
    """
    if isinstance(cell, dict):
        key = (cell["domain"], cell["product"], cell["format"])
    else:
        key = cell
    if key in produced:
        return PRODUCED
    if key in required_cells_set(spec):
        if key[1] in spec.get("llm_gated_products", []) and not llm_available:
            return UNCONFIGURED
        return GAP
    return NOT_APPLICABLE


# ---------------------------------------------------------------------------
# Evidence scanning
# ---------------------------------------------------------------------------


def parse_persisted_path(rel_path: str) -> Cell | None:
    """Parse ``outputs/<domain>/<product>-<format>-<stamp>.<ext>`` into a cell.

    Returns ``None`` when the path is not a persisted output artifact (e.g.
    KB files or manifests), so the caller can silently skip it.
    """
    rel = rel_path.replace("\\", "/")
    if "outputs/" not in rel:
        return None
    parts = [p for p in rel.split("/") if p]
    try:
        idx = parts.index("outputs")
    except ValueError:
        return None
    if idx + 2 > len(parts) - 1:
        return None  # need outputs/<domain>/<file>
    domain = parts[idx + 1]
    match = _PERSISTED_RE.match(parts[idx + 2])
    if not match:
        return None
    return (domain, match.group("product"), match.group("format"))


def _cells_from_manifest(data: dict[str, Any]) -> set[Cell]:
    """Extract produced cells from a validation_delivery manifest dict.

    Only entries that passed delivery gates (``quality != "FAIL"``) count;
    rejected entries are excluded exactly like the delivery itself excludes
    them from the manifest's ``files`` list (E7).
    """
    cells: set[Cell] = set()
    for entry in data.get("files", []):
        if entry.get("quality") == "FAIL":
            continue
        cell = parse_persisted_path(str(entry.get("source", "")))
        if cell is not None:
            cells.add(cell)
    return cells


def scan_evidence(evidence_dir: str | Path) -> set[Cell]:
    """Scan *evidence_dir* for produced artifacts.

    Two evidence sources are honoured:

    1. ``outputs/**`` — persisted artifacts written by the MCP ``persist``
       path (E2): ``outputs/<domain>/<product>-<format>-<stamp>.<ext>``.
    2. ``manifest.json`` from ``scripts/validation_delivery.py`` (E7) — bare
       files and ``manifest.json`` inside ``*.zip`` archives
       (``validation-deliveries/<date>/validation-delivery-<stamp>.zip``).
       Only entries with ``quality != "FAIL"`` count.

    Returns the set of produced ``(domain, product, format)`` cells.
    """
    root = Path(evidence_dir)
    if not root.is_dir():
        return set()

    produced: set[Cell] = set()

    outputs_dir = root / "outputs"
    if outputs_dir.is_dir():
        for f in outputs_dir.rglob("*"):
            if not f.is_file():
                continue
            cell = parse_persisted_path(f.as_posix())
            if cell is not None:
                produced.add(cell)

    for mf in root.rglob("manifest.json"):
        try:
            data = json.loads(mf.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        produced |= _cells_from_manifest(data)

    for zp in root.rglob("*.zip"):
        try:
            with zipfile.ZipFile(zp) as zf:
                if "manifest.json" not in zf.namelist():
                    continue
                data = json.loads(zf.read("manifest.json").decode("utf-8"))
        except (OSError, zipfile.BadZipFile, json.JSONDecodeError, KeyError):
            continue
        produced |= _cells_from_manifest(data)

    return produced


# ---------------------------------------------------------------------------
# LLM availability
# ---------------------------------------------------------------------------


def detect_llm_available(config_path: str | Path | None = None) -> bool:
    """Detect LLM availability from the project config.

    Reads ``.autoinfo/config.yaml`` (override with *config_path*) and returns
    True when ``llm.api_key`` is a non-empty string. A missing/unreadable
    config file is treated as "not available".
    """
    path = Path(config_path) if config_path else Path(".autoinfo/config.yaml")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return False
    llm = data.get("llm") or {}
    return bool(str(llm.get("api_key", "") or "").strip())


def classify_grid(
    spec: dict[str, Any],
    produced: set[Cell],
    llm_available: bool,
) -> dict[Cell, str]:
    """Classify every domain x product x format cell of *spec*."""
    cells: dict[Cell, str] = {}
    for product in spec.get("products", []):
        for domain in spec.get("domains", []):
            for fmt in spec.get("formats", []):
                cells[(domain, product, fmt)] = classify_cell(
                    (domain, product, fmt), produced, llm_available, spec
                )
    return cells


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


def render_report(
    spec: dict[str, Any],
    produced: set[Cell],
    llm_available: bool,
    *,
    spec_path: str = "",
    evidence_dir: str = "",
) -> str:
    """Render the markdown matrix report for *spec*.

    Returns the full ``matrix-report.md`` text (title, meta, legend, the
    products x domains table, and the ``COVERAGE_GAP`` summary listing every
    required cell classified ``空gap`` — never silent).
    """
    products: list[str] = list(spec.get("products", []))
    domains: list[str] = list(spec.get("domains", []))
    required = required_cells_set(spec)

    cells = classify_grid(spec, produced, llm_available)

    gaps = sorted(
        (c for c, s in cells.items() if s == GAP),
        key=lambda c: (c[0], c[1], c[2]),
    )
    produced_count = sum(1 for s in cells.values() if s == PRODUCED)
    gap_count = len(gaps)
    unconfigured_count = sum(1 for s in cells.values() if s == UNCONFIGURED)
    na_count = sum(1 for s in cells.values() if s == NOT_APPLICABLE)

    lines: list[str] = []
    lines.append("# End-User Coverage Matrix (E8, issue #131)")
    lines.append("")
    lines.append(f"- Spec: `{spec_path or 'docs/dev/specs/end-user-matrix.yaml'}`")
    lines.append(f"- Spec version: {spec.get('version', 1)}")
    lines.append(f"- Evidence dir: `{evidence_dir or '(none — no evidence scanned)'}`")
    llm_note = (
        "yes" if llm_available
        else "no (llm_gated products are 未配置unconfigured, not gaps)"
    )
    lines.append(f"- LLM available: {llm_note}")
    lines.append(f"- Generated: {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
    lines.append(
        f"- Cells: {len(cells)} (domains={len(domains)} x products={len(products)} "
        f"x formats={len(spec.get('formats', []))}), required={len(required)} — "
        f"produced={produced_count}, gap={gap_count}, "
        f"unconfigured={unconfigured_count}, not-applicable={na_count}"
    )
    lines.append("")

    lines.append("## Legend")
    lines.append("")
    lines.append("| Symbol | Status | Meaning |")
    lines.append("|--------|--------|---------|")
    lines.append(f"| 有 | {PRODUCED} | Evidence found for this domain x product x format |")
    lines.append(
        f"| 空 | {GAP} | Required cell with no evidence "
        "(LLM available or product not LLM-gated) |"
    )
    lines.append(
        f"| 不适用 | {NOT_APPLICABLE} | Non-required cell with no evidence |"
    )
    lines.append(
        f"| 未配置 | {UNCONFIGURED} | Required LLM-gated cell while the "
        "LLM key is unavailable (not a gap) |"
    )
    lines.append("")

    lines.append("## Matrix (rows = products, columns = domains)")
    lines.append("")
    lines.append("| Product | " + " | ".join(domains) + " |")
    lines.append("|---------|" + "|".join("---" for _ in domains) + "|")
    for product in products:
        row_cells: list[str] = []
        for domain in domains:
            # Report one cell per product x domain — the most-produced format
            # wins the cell label (first format in spec order with evidence).
            cell_status = NOT_APPLICABLE
            for fmt in spec.get("formats", []):
                status = cells[(domain, product, fmt)]
                if status == PRODUCED:
                    cell_status = PRODUCED
                    break
                if status in (GAP, UNCONFIGURED):
                    cell_status = status
            row_cells.append(cell_status)
        lines.append(f"| {product} | " + " | ".join(row_cells) + " |")
    lines.append("")

    lines.append("## COVERAGE_GAP")
    lines.append("")
    lines.append(
        "Required cells with NO produced evidence and NOT LLM-unconfigured "
        "(these block acceptance — issue #131):"
    )
    lines.append("")
    if gaps:
        lines.append("| Domain | Product | Format |")
        lines.append("|--------|---------|--------|")
        for domain, product, fmt in gaps:
            lines.append(f"| {domain} | {product} | {fmt} |")
    else:
        lines.append(
            "No required-empty gap cells — every required cell is "
            "有produced or 未配置unconfigured."
        )
    lines.append("")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Render the end-user coverage matrix report (E8, #131) from the "
            "spec plus real evidence (outputs/** and validation_delivery "
            "manifests)."
        )
    )
    parser.add_argument(
        "--spec",
        default="docs/dev/specs/end-user-matrix.yaml",
        help="Path to the end-user-matrix.yaml spec (default: docs/dev/specs/end-user-matrix.yaml)",
    )
    parser.add_argument(
        "--evidence",
        required=True,
        help="Directory to scan for produced artifacts (outputs/** + manifest.json)",
    )
    llm = parser.add_mutually_exclusive_group()
    llm.add_argument(
        "--llm-available",
        dest="llm_available",
        action="store_true",
        help="Treat the LLM as configured (llm_gated products become 空gap when empty)",
    )
    llm.add_argument(
        "--no-llm",
        dest="llm_available",
        action="store_false",
        help="Treat the LLM as unavailable (required llm_gated cells become 未配置unconfigured)",
    )
    parser.set_defaults(llm_available=None)
    parser.add_argument(
        "--config",
        default=".autoinfo/config.yaml",
        help="Project config to detect LLM availability from (default: .autoinfo/config.yaml)",
    )
    parser.add_argument(
        "--output",
        default="outputs/coverage-matrix/",
        help="Output directory for matrix-report.md (default: outputs/coverage-matrix/)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    spec_path = Path(args.spec)
    if not spec_path.is_file():
        print(f"ERROR: spec file not found: {args.spec}", file=sys.stderr)
        return 2

    evidence_dir = Path(args.evidence)
    if not evidence_dir.is_dir():
        print(f"ERROR: evidence directory not found: {args.evidence}", file=sys.stderr)
        return 2

    try:
        spec = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        print(f"ERROR: cannot parse spec {args.spec}: {exc}", file=sys.stderr)
        return 2

    produced = scan_evidence(evidence_dir)

    if args.llm_available is None:
        llm_available = detect_llm_available(args.config)
    else:
        llm_available = args.llm_available

    report = render_report(
        spec,
        produced,
        llm_available,
        spec_path=args.spec,
        evidence_dir=args.evidence,
    )

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "matrix-report.md"
    report_path.write_text(report, encoding="utf-8")

    counts = {status: 0 for status in _ALL_STATUSES}
    for status in classify_grid(spec, produced, llm_available).values():
        counts[status] += 1
    print(f"MATRIX: {report_path}")
    print(f"cells={sum(counts.values())} (domains x products x formats), "
          f"llm_available={llm_available}")
    for status in _ALL_STATUSES:
        print(f"  {status}: {counts[status]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
