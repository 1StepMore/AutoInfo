#!/usr/bin/env python3
"""Archive stale product outputs by the date embedded in each filename (#754).

The real-product assertion set keeps evolving.  Products generated *before* a
new assertion was introduced fail it simply because they predate the rule, not
because the current code is broken.  This script implements owner decision A
(archive-and-isolate): move artifacts whose filename date is on or before a
cutoff out of the live ``outputs/`` tree, keeping them scannable under an
archive root.

Guarantees:

* move-only — never delete, truncate, or overwrite an existing file;
* dry-run by default — with no ``--apply`` nothing on disk is touched;
* every apply writes a manifest (src, dst, sha256, size) that ``--rollback``
  replays to restore the original bytes and layout;
* no assertion logic lives here (``scripts/real_product_assertions.py`` is
  untouched) — the archive is just a moved directory.

Date parsing reads the filename only, supports ``YYYYMMDD`` and
``YYYY-MM-DD``, and keeps the *last* valid match (filenames often carry batch
numbers / domain fragments earlier in the name).

Usage (from repo root):

    python3 scripts/archive_stale_outputs.py --roots outputs --dry-run
    python3 scripts/archive_stale_outputs.py --roots outputs --apply
    python3 scripts/archive_stale_outputs.py --rollback outputs-archive/manifest-*.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Sequence

DEFAULT_CUTOFF = date(2026, 9, 30)
DEFAULT_ROOTS = ("outputs",)
DEFAULT_ARCHIVE_DIR = "outputs-archive"
UNDATED_BUCKET = "undated"
SAMPLE_SIZE = 10

_DATE_RE = re.compile(r"(?<!\d)(\d{4}-\d{2}-\d{2}|\d{8})(?!\d)")


@dataclass
class Candidate:
    """One file considered by the planner."""

    root: str
    src: Path
    rel: str
    parsed: date | None = None
    bucket: str | None = None
    dst: Path | None = None


@dataclass
class Plan:
    """Planner output for a dry-run or apply pass."""

    cutoff: date
    roots: list[str]
    total: int = 0
    to_archive: list[Candidate] = field(default_factory=list)
    kept: list[Candidate] = field(default_factory=list)
    undated: list[Candidate] = field(default_factory=list)
    conflicts: list[Candidate] = field(default_factory=list)


def parse_date(filename: str) -> date | None:
    """Return the last valid date in *filename*, or ``None`` if there is none."""

    found: date | None = None
    for match in _DATE_RE.finditer(filename):
        raw = match.group(1)
        try:
            if "-" in raw:
                found = date.fromisoformat(raw)
            else:
                found = datetime.strptime(raw, "%Y%m%d").date()
        except ValueError:
            continue
    return found


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base)
    except ValueError:
        return False
    return True


def _bucket(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def build_plan(
    roots: Sequence[str],
    archive_dir: Path,
    cutoff: date,
    include_undated: bool = False,
) -> Plan:
    """Walk *roots* and classify every file without touching the filesystem."""

    plan = Plan(cutoff=cutoff, roots=list(roots))
    archive_root = archive_dir.resolve()
    seen: set[str] = set()

    for root in roots:
        root_path = Path(root)
        if not root_path.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root_path, followlinks=False):
            current = Path(dirpath)
            dirnames[:] = sorted(
                name
                for name in dirnames
                if not _is_relative_to(current / name, archive_root)
            )
            for name in sorted(filenames):
                src = current / name
                if not src.is_file() or _is_relative_to(src, archive_root):
                    continue
                key = str(src.resolve())
                if key in seen:
                    continue
                seen.add(key)

                rel = str(src.relative_to(root_path))
                parsed = parse_date(name)
                plan.total += 1

                if parsed is None:
                    bucket = UNDATED_BUCKET if include_undated else None
                    dst = archive_dir / bucket / rel if bucket else None
                    candidate = Candidate(
                        root=root, src=src, rel=rel, parsed=None, bucket=bucket, dst=dst
                    )
                    plan.undated.append(candidate)
                    if include_undated:
                        plan.to_archive.append(candidate)
                    continue

                bucket = _bucket(parsed)
                dst = archive_dir / bucket / rel
                candidate = Candidate(
                    root=root, src=src, rel=rel, parsed=parsed, bucket=bucket, dst=dst
                )
                if parsed <= cutoff:
                    plan.to_archive.append(candidate)
                else:
                    plan.kept.append(candidate)

    plan.conflicts = [c for c in plan.to_archive if c.dst is not None and c.dst.exists()]
    return plan


def _by_month(candidates: Sequence[Candidate]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for candidate in candidates:
        key = candidate.bucket or UNDATED_BUCKET
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _plan_payload(plan: Plan, archive_dir: Path, include_undated: bool) -> dict[str, Any]:
    return {
        "mode": "dry-run",
        "cutoff": plan.cutoff.isoformat(),
        "roots": plan.roots,
        "archive_dir": str(archive_dir),
        "include_undated": include_undated,
        "total": plan.total,
        "would_archive": len(plan.to_archive),
        "by_month": _by_month(plan.to_archive),
        "kept": len(plan.kept),
        "undated": len(plan.undated),
        "conflicts": [str(c.dst) for c in plan.conflicts],
        "sample": [
            {"src": str(c.src), "dst": str(c.dst)} for c in plan.to_archive[:SAMPLE_SIZE]
        ],
    }


def render_plan(plan: Plan, archive_dir: Path, include_undated: bool) -> None:
    print(f"Roots: {', '.join(plan.roots)}")
    print(f"Cutoff: {plan.cutoff.isoformat()} (inclusive)")
    print(f"Archive dir: {archive_dir}")
    print(f"Total files: {plan.total}")
    print(f"Would archive: {len(plan.to_archive)}")
    for month, count in _by_month(plan.to_archive).items():
        print(f"  {month}: {count}")
    print(f"Kept (after cutoff): {len(plan.kept)}")
    print(f"Undated (not archived): {len(plan.undated)}")
    if plan.undated and not include_undated:
        print("  hint: use --include-undated to archive files without a filename date")
    print(f"Conflicts (destination exists, would skip): {len(plan.conflicts)}")
    for candidate in plan.conflicts[:SAMPLE_SIZE]:
        print(f"  conflict: {candidate.dst}")
    if plan.to_archive:
        print(f"First {min(len(plan.to_archive), SAMPLE_SIZE)} planned move(s):")
        for candidate in plan.to_archive[:SAMPLE_SIZE]:
            print(f"  {candidate.src} -> {candidate.dst}")
    print("Dry-run: no files were moved.")


def _manifest_path(archive_dir: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = archive_dir / f"manifest-{stamp}.json"
    counter = 1
    while path.exists():
        path = archive_dir / f"manifest-{stamp}-{counter}.json"
        counter += 1
    return path


def apply_plan(plan: Plan, archive_dir: Path, as_json: bool = False) -> int:
    archive_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    skipped: list[Candidate] = []

    for candidate in plan.to_archive:
        assert candidate.dst is not None
        if candidate.dst.exists():
            skipped.append(candidate)
            continue
        candidate.dst.parent.mkdir(parents=True, exist_ok=True)
        digest = sha256_file(candidate.src)
        size = candidate.src.stat().st_size
        shutil.move(str(candidate.src), str(candidate.dst))
        entries.append(
            {
                "rel": candidate.rel,
                "src": str(candidate.src),
                "dst": str(candidate.dst),
                "sha256": digest,
                "size": size,
            }
        )

    verify_failed: list[dict[str, Any]] = []
    for entry in entries:
        if sha256_file(Path(entry["dst"])) != entry["sha256"]:
            verify_failed.append(entry)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cutoff": plan.cutoff.isoformat(),
        "roots": plan.roots,
        "entries": entries,
        "summary": {
            "total": plan.total,
            "archived": len(entries),
            "kept": len(plan.kept),
            "undated": len(plan.undated),
            "skipped_conflict": len(skipped),
            "verify_failed": len(verify_failed),
            "by_month": _by_month(plan.to_archive),
        },
    }
    manifest_path = _manifest_path(archive_dir)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    payload = {
        "mode": "apply",
        "manifest": str(manifest_path),
        "total": plan.total,
        "archived": len(entries),
        "kept": len(plan.kept),
        "undated": len(plan.undated),
        "skipped_conflict": [str(c.src) for c in skipped],
        "verify_failed": [entry["dst"] for entry in verify_failed],
    }
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Archived: {len(entries)} file(s) into {archive_dir}")
        print(f"Skipped (destination exists): {len(skipped)}")
        print(f"Kept (after cutoff): {len(plan.kept)}")
        print(f"Undated: {len(plan.undated)}")
        print(f"Manifest: {manifest_path}")
        if verify_failed:
            print(f"VERIFY FAILED: {len(verify_failed)} file(s)", file=sys.stderr)

    return 1 if verify_failed else 0


def rollback_manifest(manifest_path: Path, as_json: bool = False) -> int:
    if not manifest_path.is_file():
        print(f"error: manifest not found: {manifest_path}", file=sys.stderr)
        return 2
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = data.get("entries", [])

    restored: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    verify_failed: list[dict[str, Any]] = []

    for entry in entries:
        src = Path(entry["src"])
        dst = Path(entry["dst"])
        if not dst.exists():
            missing.append(entry)
            continue
        if src.exists():
            skipped.append(entry)
            continue
        src.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(dst), str(src))
        expected = entry.get("sha256")
        if expected and sha256_file(src) != expected:
            verify_failed.append(entry)
        else:
            restored.append(entry)

    payload = {
        "mode": "rollback",
        "manifest": str(manifest_path),
        "restored": len(restored),
        "skipped": [entry["src"] for entry in skipped],
        "missing": [entry["dst"] for entry in missing],
        "verify_failed": [entry["src"] for entry in verify_failed],
    }
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Restored: {len(restored)} file(s)")
        print(f"Skipped (source already exists): {len(skipped)}")
        for entry in skipped:
            print(f"  skipped: {entry['src']}")
        print(f"Missing (destination not found): {len(missing)}")
        for entry in missing:
            print(f"  missing: {entry['dst']}")
        if verify_failed:
            print(f"VERIFY FAILED: {len(verify_failed)} file(s)", file=sys.stderr)

    return 1 if verify_failed else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Move filename-dated product outputs at or before a cutoff into an archive."
    )
    parser.add_argument(
        "--roots",
        action="append",
        default=None,
        metavar="PATH",
        help="product root to scan (repeatable; default: outputs)",
    )
    parser.add_argument(
        "--archive-dir",
        default=DEFAULT_ARCHIVE_DIR,
        help=f"archive root (default: {DEFAULT_ARCHIVE_DIR})",
    )
    parser.add_argument(
        "--cutoff",
        default=DEFAULT_CUTOFF.isoformat(),
        help=f"archive files dated on or before this day (default: {DEFAULT_CUTOFF})",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="print the plan only (default)")
    mode.add_argument("--apply", action="store_true", help="move files and write a manifest")
    parser.add_argument(
        "--include-undated",
        action="store_true",
        help="also archive files whose filename carries no date",
    )
    parser.add_argument(
        "--rollback",
        metavar="MANIFEST",
        help="restore files recorded in a previous apply manifest",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        cutoff = date.fromisoformat(args.cutoff)
    except ValueError:
        parser.error(f"invalid --cutoff date: {args.cutoff}")

    if args.rollback:
        if args.apply:
            parser.error("--rollback cannot be combined with --apply")
        return rollback_manifest(Path(args.rollback), as_json=args.json)

    roots = args.roots or list(DEFAULT_ROOTS)
    archive_dir = Path(args.archive_dir)
    plan = build_plan(roots, archive_dir, cutoff, include_undated=args.include_undated)

    if args.apply:
        return apply_plan(plan, archive_dir, as_json=args.json)

    if args.json:
        print(
            json.dumps(
                _plan_payload(plan, archive_dir, args.include_undated),
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        render_plan(plan, archive_dir, args.include_undated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
