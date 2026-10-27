#!/usr/bin/env python3
"""Scan and optionally remove legacy empty KB entries (issue #279).

Entries written before the 50-char minimum-content guard existed can be
empty shells.  This script scans ``knowledge/**/{01-Raw,02-Draft}/*.md``
for files whose body content is shorter than ``MIN_KB_CONTENT_CHARS`` and
reports (``--dry-run``, default) or removes (``--apply``) them.

03-Wiki is append-only and is NEVER scanned or removed — the script
hard-refuses any path containing ``03-Wiki``.

Usage::

    python scripts/cleanup_empty_kb_entries.py [--dry-run] [KNOWLEDGE_ROOT]
    python scripts/cleanup_empty_kb_entries.py --apply [KNOWLEDGE_ROOT]
    python scripts/cleanup_empty_kb_entries.py --prune-missing [--apply] [KNOWLEDGE_ROOT]

``--prune-missing`` removes ``entries`` rows whose ``file_path`` no longer
exists. A row whose file is gone is index metadata, not a KB file, so pruning
it is not a demotion — the 03-Wiki append-only guardrail protects files.
``--dry-run`` (the default) reports per-domain counts without deleting.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterator

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from autoinfo.kb import MIN_KB_CONTENT_CHARS, KBStore  # noqa: E402

_EMPTY_TIERS = ("01-Raw", "02-Draft")
_WIKI_MARKER = "03-Wiki"


def _iter_entries(knowledge_root: Path) -> Iterator[Path]:
    """Yield every markdown file under ``<root>/<domain>/{01-Raw,02-Draft}/``.

    Never descends into 03-Wiki: only the two writable tiers are globbed,
    and any path that nevertheless contains the 03-Wiki marker is refused.
    """
    root = Path(knowledge_root)
    for domain_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        for tier in _EMPTY_TIERS:
            tier_dir = domain_dir / tier
            if not tier_dir.is_dir():
                continue
            for md_file in tier_dir.rglob("*.md"):
                if _WIKI_MARKER in md_file.parts:
                    raise RuntimeError(
                        f"refusing to touch 03-Wiki path: {md_file}"
                    )
                yield md_file


def _body_length(md_file: Path) -> int:
    """Length of the markdown body, i.e. the file content minus YAML
    frontmatter — the same notion the KB pipeline's 50-char guard uses."""
    raw = md_file.read_text(encoding="utf-8")
    if raw.startswith("---"):
        end = raw.find("---", 3)
        if end != -1:
            raw = raw[end + 3 :]
    return len(raw.strip())


def scan_empty_entries(knowledge_root: Path) -> list[Path]:
    """Return entries in 01-Raw/02-Draft whose content is shorter than
    ``MIN_KB_CONTENT_CHARS``.  03-Wiki is never scanned."""
    empty: list[Path] = []
    for md_file in _iter_entries(knowledge_root):
        try:
            if _body_length(md_file) < MIN_KB_CONTENT_CHARS:
                empty.append(md_file)
        except OSError:
            continue
    return sorted(empty)


_KB_TIERS = frozenset({"01-Raw", "02-Draft", "03-Wiki"})


def _is_kb_file(file_path: str, knowledge_root: Path) -> bool:
    """True when *file_path* sits at ``<root>/<domain>/<tier>/...``."""
    try:
        rel = Path(file_path).resolve().relative_to(Path(knowledge_root).resolve())
    except ValueError:
        return False
    return len(rel.parts) >= 3 and rel.parts[1] in _KB_TIERS


def prune_missing_index_rows(
    knowledge_root: Path, *, apply: bool
) -> tuple[dict[str, list[int]], int]:
    """Delete ``entries`` rows that do not point at a live KB file.

    Two kinds qualify. A row whose file is gone is simply stale. A row whose
    file sits outside the four tiers (``_failed/`` quarantine, ``_archive/``)
    is miscounted as a KB entry: keeping it makes a blocked item look like a
    promotable Draft. That row loses its index entry only — the file stays.

    Returns ``({domain: [missing, outside_tier]}, total)``.
    """
    store = KBStore(base_path=Path(knowledge_root))
    with store.index._connect() as conn:
        rows = conn.execute("SELECT entry_id, domain, file_path FROM entries").fetchall()

    missing: list[tuple[str, str]] = []
    outside: list[tuple[str, str]] = []
    for row in rows:
        entry_id, domain, file_path = row["entry_id"], row["domain"] or "", row["file_path"] or ""
        if not (file_path and Path(file_path).is_file()):
            missing.append((entry_id, domain))
        elif not _is_kb_file(file_path, knowledge_root):
            outside.append((entry_id, domain))

    per_domain: dict[str, list[int]] = {}
    for _, domain in missing + outside:
        per_domain.setdefault(domain, [0, 0])
    for _, domain in missing:
        per_domain[domain][0] += 1
    for _, domain in outside:
        per_domain[domain][1] += 1

    if apply:
        for entry_id, _ in missing:
            store.delete_entry(entry_id)
        for entry_id, _ in outside:
            store.index.delete_index_row(entry_id)

    return per_domain, len(missing) + len(outside)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Scan KB entries shorter than MIN_KB_CONTENT_CHARS "
            f"({MIN_KB_CONTENT_CHARS} chars). Never touches 03-Wiki."
        )
    )
    parser.add_argument(
        "knowledge_root",
        nargs="?",
        default="knowledge",
        type=Path,
        help="KB root containing <domain>/{01-Raw,02-Draft,03-Wiki} (default: knowledge)",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="report flagged entries without deleting (default)",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="delete flagged entries",
    )
    parser.add_argument(
        "--prune-missing",
        action="store_true",
        help="prune index rows whose file no longer exists (dry-run unless --apply)",
    )
    args = parser.parse_args(argv)

    root = Path(args.knowledge_root)
    if args.prune_missing:
        per_domain, total = prune_missing_index_rows(root, apply=args.apply)
        for domain, (stale, untiered) in sorted(per_domain.items()):
            total = stale + untiered
            print(f"{domain or '(none)'}: {total} (stale {stale}, outside-tier {untiered})")
        verb = "pruned" if args.apply else "flagged"
        print(f"{total} dangling index rows {verb}")
        return 0
    scanned = sum(1 for _ in _iter_entries(root))
    empty = scan_empty_entries(root)

    if args.apply:
        for entry in empty:
            entry.unlink()
        verb = "removed"
    else:
        verb = "flagged"
        for entry in empty:
            print(entry)

    print(
        f"{len(empty)} empty {verb} / {scanned} scanned "
        f"(min content: {MIN_KB_CONTENT_CHARS} chars)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
