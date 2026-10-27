#!/usr/bin/env python3
"""Classify the 78 required ``domain x source`` pairs from the end-user spec.

Pure filesystem — reads ``docs/dev/specs/end-user-matrix.yaml``,
``src/autoinfo/data/domains/<domain>/sources.yaml`` and ``collections/`` and
never makes a network call or mutates a source config.  Emits a CSV and a
markdown table::

    python3 scripts/source_diagnosis.py \\
        --output docs/dev/validation-reports/capability-27x3/

Buckets:

* ``satisfied``       items > 0 and the last recorded run succeeded
* ``degraded``        items > 0 but the last run did not succeed (failed or
                      there is no run log to verify it)
* ``failing``         attempted (collection dir exists), 0 items
* ``never-attempted`` enabled, no ``collections/<domain>/<source>/`` dir
* ``configured-off``  ``enabled: false``

Items live at ``collections/<domain>/<source>/<date>/*.json``; ``_runs.json``
is run metadata, not an item, and ``collections/<domain>/_failed/`` holds
G0-rejected dumps, so neither is counted.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]

COLUMNS = [
    "domain",
    "source",
    "configured",
    "enabled",
    "collections_items",
    "last_run_status",
    "last_run_at",
    "last_error",
    "bucket",
    "domain_stable_sources",
    "recommendation",
    "dir_matched",
]

BUCKETS = ("satisfied", "degraded", "failing", "never-attempted", "configured-off")
RECOMMENDATIONS = ("keep", "fix-collector", "run-collection", "deferred", "replace-blocked")

CSV_NAME = "source-diagnosis.csv"
MD_NAME = "source-diagnosis.md"


# ---------------------------------------------------------------------------
# Config / spec loading
# ---------------------------------------------------------------------------


def load_required_sources(spec_path: str | Path) -> list[dict[str, str]]:
    raw = yaml.safe_load(Path(spec_path).read_text(encoding="utf-8")) or {}
    required = raw.get("required_sources") or []
    return [{"domain": str(r["domain"]), "source": str(r["source"])} for r in required]


def load_domain_sources(config_root: str | Path, domain: str) -> list[dict[str, Any]]:
    path = Path(config_root) / domain / "sources.yaml"
    if not path.is_file():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [s for s in (raw.get("sources") or []) if isinstance(s, dict)]


def _slug(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")


def _source_identities(cfg: dict[str, Any]) -> list[tuple[str, str]]:
    """Return ``(kind, value)`` identity pairs: config ``name`` then ``id``."""
    out: list[tuple[str, str]] = []
    for key in ("name", "id"):
        value = cfg.get(key)
        if isinstance(value, str) and value.strip():
            out.append((key, value))
    return out


def resolve_source(sources: list[dict[str, Any]], token: str) -> tuple[dict[str, Any] | None, str]:
    """Match *token* against every source's ``name`` and ``id``.

    Exact match wins; case-insensitive then slug-normalised fallbacks resolve
    spec tokens that drift in case or punctuation.  Returns the config and the
    identity kind that matched (``""`` when unconfigured).
    """
    for kind in ("name", "id"):
        for cfg in sources:
            if cfg.get(kind) == token:
                return cfg, kind
    folded = token.strip().casefold()
    for kind in ("name", "id"):
        for cfg in sources:
            value = cfg.get(kind)
            if isinstance(value, str) and value.strip().casefold() == folded:
                return cfg, kind
    slug = _slug(token)
    for kind in ("name", "id"):
        for cfg in sources:
            value = cfg.get(kind)
            if isinstance(value, str) and _slug(value) == slug:
                return cfg, kind
    return None, ""


def find_collection_dir(
    collections_root: str | Path,
    domain: str,
    token: str,
    cfg: dict[str, Any] | None,
) -> tuple[Path | None, str]:
    """Find the collection dir by config display name, id, then spec token."""
    domain_dir = Path(collections_root) / domain
    candidates: list[tuple[str, str]] = []
    if cfg is not None:
        candidates.extend(_source_identities(cfg))
    candidates.append(("token", token))
    seen: set[str] = set()
    for kind, value in candidates:
        if value in seen:
            continue
        seen.add(value)
        path = domain_dir / value
        if path.is_dir():
            return path, f"{kind}:{value}"
    return None, ""


# ---------------------------------------------------------------------------
# Filesystem reads
# ---------------------------------------------------------------------------


def count_items(source_dir: Path | None) -> int:
    if source_dir is None:
        return 0
    return sum(
        1
        for path in source_dir.rglob("*.json")
        if path.name != "_runs.json" and "_failed" not in path.parts
    )


def read_last_run(source_dir: Path | None) -> dict[str, str]:
    """Return ``status`` / ``at`` / ``error`` from the newest ``_runs.json``."""
    empty = {"status": "", "at": "", "error": ""}
    if source_dir is None:
        return empty
    runs_path = source_dir / "_runs.json"
    if not runs_path.is_file():
        return empty
    try:
        runs = json.loads(runs_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {**empty, "error": "unreadable _runs.json"}
    if not isinstance(runs, list) or not runs:
        return empty
    run = max(
        (r for r in runs if isinstance(r, dict)),
        key=lambda r: str(r.get("timestamp", "")),
        default={},
    )
    errors = run.get("errors") or []
    error = ""
    if errors:
        first = errors[0]
        if isinstance(first, dict):
            error = str(first.get("reason") or first.get("message") or first)
        else:
            error = str(first)
    return {
        "status": str(run.get("status", "")),
        "at": str(run.get("timestamp", "")),
        "error": error,
    }


def _classify(
    configured: bool,
    enabled: bool,
    items: int,
    last_status: str,
    attempted: bool,
) -> str:
    if not enabled:
        return "configured-off"
    if items > 0 and last_status == "success":
        return "satisfied"
    if items > 0:
        return "degraded"
    if attempted:
        return "failing"
    if configured:
        return "never-attempted"
    return "configured-off"


def _recommend(bucket: str, stable: int) -> str:
    if bucket == "satisfied":
        return "keep"
    if bucket in ("degraded", "failing"):
        return "fix-collector"
    if bucket == "never-attempted":
        return "run-collection" if stable < 2 else "deferred"
    return "replace-blocked" if stable < 2 else "deferred"


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def diagnose(
    spec_path: str | Path,
    config_root: str | Path,
    collections_root: str | Path,
) -> list[dict[str, Any]]:
    required = load_required_sources(spec_path)
    sources_by_domain: dict[str, list[dict[str, Any]]] = {}
    rows: list[dict[str, Any]] = []

    for req in required:
        domain, token = req["domain"], req["source"]
        if domain not in sources_by_domain:
            sources_by_domain[domain] = load_domain_sources(config_root, domain)
        cfg, _ = resolve_source(sources_by_domain[domain], token)
        configured = cfg is not None
        enabled = bool(cfg.get("enabled", True)) if configured else False
        source_dir, dir_matched = find_collection_dir(collections_root, domain, token, cfg)
        items = count_items(source_dir)
        last = read_last_run(source_dir)
        bucket = _classify(
            configured=configured,
            enabled=enabled,
            items=items,
            last_status=last["status"],
            attempted=source_dir is not None,
        )
        rows.append(
            {
                "domain": domain,
                "source": token,
                "configured": configured,
                "enabled": enabled,
                "collections_items": items,
                "last_run_status": last["status"],
                "last_run_at": last["at"],
                "last_error": last["error"],
                "bucket": bucket,
                "domain_stable_sources": 0,
                "recommendation": "",
                "dir_matched": dir_matched,
            }
        )

    stable_by_domain = Counter(row["domain"] for row in rows if row["bucket"] == "satisfied")
    for row in rows:
        stable = stable_by_domain[row["domain"]]
        row["domain_stable_sources"] = stable
        row["recommendation"] = _recommend(row["bucket"], stable)
    return rows


def bucket_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(row["bucket"] for row in rows)
    return {bucket: counts.get(bucket, 0) for bucket in BUCKETS}


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _cell(value: Any) -> str:
    text = str(value)
    return " ".join(text.split()).replace("|", "\\|")


def write_csv(rows: list[dict[str, Any]], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in COLUMNS})


def render_markdown(rows: list[dict[str, Any]]) -> str:
    counts = bucket_counts(rows)
    lines = [
        "# Source diagnosis — 78 required `domain x source` pairs",
        "",
        "Pure-filesystem classification. Regenerate with:",
        "",
        "```bash",
        "python3 scripts/source_diagnosis.py",
        "```",
        "",
        "## Bucket counts",
        "",
        "| bucket | count |",
        "|---|---|",
    ]
    lines.extend(f"| {bucket} | {counts[bucket]} |" for bucket in BUCKETS)
    lines.extend(
        [
            f"| **total** | **{len(rows)}** |",
            "",
            "## Rows",
            "",
            "| " + " | ".join(COLUMNS) + " |",
            "|" + "|".join("---" for _ in COLUMNS) + "|",
        ]
    )
    for row in rows:
        lines.append("| " + " | ".join(_cell(row.get(key, "")) for key in COLUMNS) + " |")
    lines.append("")
    return "\n".join(lines)


def write_markdown(rows: list[dict[str, Any]], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(rows), encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Classify the required domain x source pairs from the end-user spec "
            "using only config files and collections/ on disk."
        )
    )
    parser.add_argument(
        "--spec",
        default=str(ROOT / "docs" / "dev" / "specs" / "end-user-matrix.yaml"),
        help="end-user matrix spec (required_sources source of truth)",
    )
    parser.add_argument(
        "--config-root",
        default=str(ROOT / "src" / "autoinfo" / "data" / "domains"),
        help="root of per-domain sources.yaml configs",
    )
    parser.add_argument(
        "--collections",
        default=str(ROOT / "collections"),
        help="collections/ root to inspect",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "docs" / "dev" / "validation-reports" / "capability-27x3"),
        help="directory for source-diagnosis.csv and source-diagnosis.md",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    spec_path = Path(args.spec)
    if not spec_path.is_file():
        print(f"error: spec not found: {spec_path}", file=sys.stderr)
        return 2
    rows = diagnose(spec_path, args.config_root, args.collections)
    out_dir = Path(args.output)
    write_csv(rows, out_dir / CSV_NAME)
    write_markdown(rows, out_dir / MD_NAME)
    counts = bucket_counts(rows)
    summary = "  ".join(f"{bucket}={counts[bucket]}" for bucket in BUCKETS)
    print(f"rows={len(rows)}  {summary}")
    print(f"wrote {out_dir / CSV_NAME}")
    print(f"wrote {out_dir / MD_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
