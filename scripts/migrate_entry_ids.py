#!/usr/bin/env python3
"""One-shot migration of legacy KB entry ids to the collision-free scheme.

Legacy ids were ``{domain}-{topic}-{slug}`` (issue #695): two items that
shared a title collapsed onto one id and one ``{date}-{slug}.md`` file, so
the second overwrote the first and its index row replaced the first.
This script rewrites every tier file's ``entry_id`` and file name to
``{domain}-{date}-{hash8}`` / ``{date}-{slug}-{hash8}.md``, rekeys the
dependent SQLite tables, then rebuilds the index from disk.

``03-Wiki`` is append-only: it is skipped unless ``--include-wiki`` is
passed, which is the director's explicit authorization for that exception.

Dry-run is the default; pass ``--apply`` to write.  Re-running after a
successful apply plans zero changes (idempotent).

Usage::

    python scripts/migrate_entry_ids.py                 # dry-run report
    python scripts/migrate_entry_ids.py --apply         # rewrite non-Wiki tiers
    python scripts/migrate_entry_ids.py --apply --include-wiki
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

TIERS = ("01-Raw", "02-Draft", "03-Wiki")
SKIP_PARTS = frozenset({"_archive", "_failed"})
_DATE_PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2})-")
_ENTRY_ID_LINE = re.compile(r"(?m)^entry_id:.*$")


@dataclass(frozen=True)
class Change:
    old_id: str
    new_id: str
    old_path: str
    new_path: str
    tier: str


def _slugify(text: str, max_len: int = 100) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug[:max_len].rstrip("-")


def _hash8(basis: str) -> str:
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:8]


def _relative_path(path: str | Path, kb_root: Path) -> str:
    """Return *path* relative to *kb_root* when possible."""
    candidate = Path(path)
    if not candidate.is_absolute():
        return candidate.as_posix()
    try:
        return candidate.resolve().relative_to(kb_root.resolve()).as_posix()
    except (ValueError, OSError):
        return str(candidate)


def _date_of(value: Any, path: Path) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str) and value.strip():
        candidate = value.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(candidate).date().isoformat()
        except ValueError:
            try:
                return date.fromisoformat(candidate).isoformat()
            except ValueError:
                pass
    match = _DATE_PREFIX.match(path.name)
    if match:
        return match.group(1)
    return datetime.fromtimestamp(path.stat().st_mtime).date().isoformat()


def _split_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    if not raw.startswith("---"):
        return {}, raw
    end = raw.find("---", 3)
    if end == -1:
        return {}, raw
    data = yaml.safe_load(raw[3:end])
    return (data if isinstance(data, dict) else {}), raw[end + 3 :].lstrip("\n")


def plan_migration(
    kb_root: Path, *, include_wiki: bool = False
) -> tuple[list[Change], list[dict[str, str]], list[dict[str, str]]]:
    """Return ``(changes, errors, skipped)`` without touching disk."""
    changes: list[Change] = []
    errors: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []

    if not kb_root.is_dir():
        return [], [{"file": str(kb_root), "error": "KB root not found"}], []

    for path in sorted(kb_root.rglob("*.md")):
        rel = path.relative_to(kb_root)
        if SKIP_PARTS.intersection(rel.parts):
            continue
        if len(rel.parts) < 3 or rel.parts[1] not in TIERS:
            continue
        tier = rel.parts[1]
        if tier == "03-Wiki" and not include_wiki:
            skipped.append({"file": str(path), "reason": "03-Wiki is append-only"})
            continue
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append({"file": str(path), "error": str(exc)})
            continue
        fm, body = _split_frontmatter(raw)
        old_id = str(fm.get("entry_id") or "").strip()
        if not old_id:
            errors.append({"file": str(path), "error": "frontmatter has no entry_id"})
            continue
        domain = str(fm.get("domain") or rel.parts[0]).strip() or rel.parts[0]
        day = _date_of(fm.get("collected_at"), path)
        basis = str(fm.get("source_url") or "").strip() or (f"{fm.get('title', '')}\x1f{body}")
        digest = _hash8(basis)
        new_id = f"{domain}-{day}-{digest}"
        slug = _slugify(str(fm.get("title") or "")) or "entry"
        new_path = path.with_name(f"{day}-{slug}-{digest}.md")
        if new_id == old_id and new_path == path:
            continue
        changes.append(
            Change(
                old_id=old_id,
                new_id=new_id,
                old_path=str(path),
                new_path=str(new_path),
                tier=tier,
            )
        )

    old_paths = {Path(change.old_path) for change in changes}
    by_new_id: dict[str, Change] = {}
    for change in changes:
        prior = by_new_id.get(change.new_id)
        if prior is not None:
            errors.append(
                {
                    "file": change.old_path,
                    "error": f"target id {change.new_id} also produced by {prior.old_path}",
                }
            )
            continue
        by_new_id[change.new_id] = change
        target = Path(change.new_path)
        if target.exists() and target not in old_paths:
            errors.append(
                {
                    "file": change.old_path,
                    "error": f"target path already exists: {target}",
                }
            )
    return changes, errors, skipped


def apply_changes(changes: list[Change]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for change in changes:
        old_path = Path(change.old_path)
        new_path = Path(change.new_path)
        try:
            raw = old_path.read_text(encoding="utf-8")
            rewritten, count = _ENTRY_ID_LINE.subn(f"entry_id: {change.new_id}", raw, count=1)
            if count != 1:
                errors.append({"file": str(old_path), "error": "entry_id line not rewritable"})
                continue
            new_path.write_text(rewritten, encoding="utf-8")
            if new_path.resolve() != old_path.resolve():
                old_path.unlink()
        except OSError as exc:
            errors.append({"file": str(old_path), "error": str(exc)})
    return errors


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone()
    return row is not None


def rekey_index(
    db_path: Path, changes: list[Change], kb_root: Path | None = None
) -> list[dict[str, str]]:
    """Rekey dependent rows before the caller rebuilds the index from disk."""
    if not db_path.is_file() or not changes:
        return []

    root = (kb_root or (db_path.parent / "knowledge")).resolve()
    errors: list[dict[str, str]] = []
    id_map = {change.old_id: change.new_id for change in changes}
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        with conn:
            tables = {
                name: _table_exists(conn, name)
                for name in ("entries", "entities", "entry_versions", "relations")
            }
            for change in changes:
                if tables["entries"]:
                    occupied = conn.execute(
                        "SELECT 1 FROM entries WHERE entry_id = ?", (change.new_id,)
                    ).fetchone()
                    if occupied:
                        errors.append(
                            {
                                "entry_id": change.new_id,
                                "error": "target entry_id already indexed",
                            }
                        )
                        continue
                    conn.execute(
                        "UPDATE entries SET entry_id = ?, file_path = ? WHERE entry_id = ?",
                        (change.new_id, _relative_path(change.new_path, root), change.old_id),
                    )
                if tables["entities"]:
                    conn.execute(
                        "UPDATE entities SET entry_id = ? WHERE entry_id = ?",
                        (change.new_id, change.old_id),
                    )
                if tables["entry_versions"]:
                    conn.execute(
                        "UPDATE entry_versions SET entry_id = ? WHERE entry_id = ?",
                        (change.new_id, change.old_id),
                    )
                if tables["relations"]:
                    conn.execute(
                        "UPDATE relations SET item_a_id = ? WHERE item_a_id = ?",
                        (change.new_id, change.old_id),
                    )
                    conn.execute(
                        "UPDATE relations SET item_b_id = ? WHERE item_b_id = ?",
                        (change.new_id, change.old_id),
                    )
            if _table_exists(conn, "kg_relations"):
                for rowid, payload in conn.execute(
                    "SELECT rowid, entries_shared FROM kg_relations"
                ):
                    if not payload:
                        continue
                    try:
                        ids = json.loads(payload)
                    except (TypeError, json.JSONDecodeError):
                        continue
                    if not isinstance(ids, list):
                        continue
                    remapped = [id_map.get(str(item), str(item)) for item in ids]
                    if remapped != ids:
                        conn.execute(
                            "UPDATE kg_relations SET entries_shared = ? WHERE rowid = ?",
                            (json.dumps(sorted(set(remapped))), rowid),
                        )
            if _table_exists(conn, "entry_embeddings"):
                for change in changes:
                    conn.execute(
                        "UPDATE entry_embeddings SET entry_id = ? WHERE entry_id = ?",
                        (change.new_id, change.old_id),
                    )
    finally:
        conn.close()
    return errors


def normalize_index_paths(db_path: Path, kb_root: Path, *, apply: bool = False) -> dict[str, int]:
    """Rewrite absolute ``file_path`` values to KB-relative POSIX paths."""
    counts = {"entries": 0, "versions": 0}
    if not db_path.is_file():
        return counts

    conn = sqlite3.connect(db_path)
    try:
        with conn:
            for table, key, count_key in (
                ("entries", "entry_id", "entries"),
                ("entry_versions", "version_id", "versions"),
            ):
                if not _table_exists(conn, table):
                    continue
                rows = conn.execute(f"SELECT {key}, file_path FROM {table}").fetchall()
                for row_key, stored in rows:
                    if not stored:
                        continue
                    relative = _relative_path(stored, kb_root)
                    if relative == stored:
                        continue
                    counts[count_key] += 1
                    if apply:
                        conn.execute(
                            f"UPDATE {table} SET file_path = ? WHERE {key} = ?",
                            (relative, row_key),
                        )
    finally:
        conn.close()
    return counts


def rebuild_index(kb_root: Path) -> dict[str, Any]:
    from autoinfo.kb import KBStore

    store = KBStore(base_path=kb_root)
    return store.reindex_knowledge_base()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="project root (default: .)")
    parser.add_argument("--kb", default="knowledge", help="KB directory relative to --root")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the migration (default: dry-run report only)",
    )
    parser.add_argument(
        "--include-wiki",
        action="store_true",
        help=(
            "also rewrite 03-Wiki (append-only exception; requires explicit director authorization)"
        ),
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = Path(args.root).resolve()
    kb_root = (root / args.kb).resolve()

    changes, errors, skipped = plan_migration(kb_root, include_wiki=args.include_wiki)
    applied_errors: list[dict[str, str]] = []
    reindexed: dict[str, Any] | None = None
    path_rewrites = normalize_index_paths(root / "autoinfo.db", kb_root, apply=False)

    if args.apply and not errors:
        applied_errors = apply_changes(changes)
        if not applied_errors:
            applied_errors = rekey_index(root / "autoinfo.db", changes, kb_root=kb_root)
        if not applied_errors:
            path_rewrites = normalize_index_paths(root / "autoinfo.db", kb_root, apply=True)
            reindexed = rebuild_index(kb_root)
            if reindexed.get("errors"):
                applied_errors = [dict(item) for item in reindexed["errors"]]
        errors = applied_errors

    report = {
        "mode": "apply" if args.apply else "dry-run",
        "kb_root": str(kb_root),
        "planned": len(changes),
        "changes": [asdict(change) for change in changes],
        "errors": errors,
        "skipped": skipped,
        "path_rewrites": path_rewrites,
        "reindexed": reindexed,
    }
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"kb root: {kb_root}")
        print(f"mode: {report['mode']}")
        print(f"planned changes: {len(changes)}")
        print(f"skipped (03-Wiki): {len(skipped)}")
        print(f"errors: {len(errors)}")
        for item in changes[:20]:
            print(f"  {item.tier}: {item.old_id} -> {item.new_id}")
        if len(changes) > 20:
            print(f"  ... {len(changes) - 20} more")
        for item in errors:
            print(f"  ERROR {item}")
        if reindexed is not None:
            print(
                "reindexed: "
                f"files={reindexed.get('files_found')} "
                f"fts5={reindexed.get('fts5_indexed')} "
                f"errors={len(reindexed.get('errors') or [])}"
            )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
