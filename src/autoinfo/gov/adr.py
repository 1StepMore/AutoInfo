"""ADR guard + decision consumer sync (T10/G5).

Decisions live in ``docs/adr/NNNN-*.md`` — the single "why" carrier. This
module enforces four invariants (plan T10):

1. ``docs/adr/README.md`` index ↔ on-disk ``NNNN-*.md`` files agree both ways.
2. Every ADR carries Status/Date/Author, the Status is a legal value, and a
   ``Superseded by NNNN`` pointer resolves to an existing ADR.
3. Every decision registered in the contract's ``[decisions]`` finds its
   consumer anchors (substring ``expect`` or ``expect_regex``) — a missing or
   edited-away anchor is ``UNSYNCED`` (G5: a decision that stopped
   propagating must turn red, keyword-presence alone is not sync — QA §8.1).
4. Every ADR file is registered in ``[decisions]`` — a new ADR that nobody
   registered is ``UNSYNCED``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from autoinfo.gov.contract import Contract

ADR_DIR = Path("docs") / "adr"
ADR_FILE_RE = re.compile(r"^(\d{4})-.+\.md$")
INDEX_FILE = "README.md"

#: Status vocabulary from docs/adr/TEMPLATE.md.
LEGAL_STATUSES = frozenset({"Proposed", "Accepted", "Amended", "Superseded", "Deprecated"})
STATUS_LINE_RE = re.compile(r"^\s*-\s*\*\*Status\*\*:\s*(.+?)\s*$", re.M)
#: Some early ADRs use YYYY-MM; parenthetical annotations may follow.
DATE_LINE_RE = re.compile(r"^\s*-\s*\*\*Date\*\*:\s*(\d{4}-\d{2}(?:-\d{2})?)", re.M)
#: 0010 uses "Deciders" — accepted as the same field.
AUTHOR_LINE_RE = re.compile(r"^\s*-\s*\*\*(?:Author|Deciders)\*\*:\s*(.+?)\s*$", re.M)
SUPERSEDED_RE = re.compile(r"Superseded by\s+(\d{4})", re.IGNORECASE)


@dataclass(frozen=True)
class AdrRecord:
    number: str
    path: Path
    status: str
    date: str
    author: str
    superseded_by: str | None


def adr_files(root: Path) -> dict[str, Path]:
    """number → path for every on-disk numbered ADR (excludes README/TEMPLATE)."""
    out: dict[str, Path] = {}
    directory = root / ADR_DIR
    if not directory.is_dir():
        return out
    for path in sorted(directory.glob("*.md")):
        match = ADR_FILE_RE.match(path.name)
        if match:
            out[match.group(1)] = path
    return out


def index_numbers(root: Path) -> set[str]:
    """ADR numbers linked from the docs/adr/README.md index table."""
    index = root / ADR_DIR / INDEX_FILE
    if not index.is_file():
        return set()
    text = index.read_text(encoding="utf-8", errors="replace")
    return set(re.findall(r"\((\d{4})-.+?\.md\)", text))


def parse_adr(path: Path) -> AdrRecord | None:
    """Parse one ADR file; None if it lacks a number header entirely."""
    number = ADR_FILE_RE.match(path.name)
    if number is None:
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    status = STATUS_LINE_RE.search(text)
    date = DATE_LINE_RE.search(text)
    author = AUTHOR_LINE_RE.search(text)
    superseded = SUPERSEDED_RE.search(text)
    return AdrRecord(
        number=number.group(1),
        path=path,
        status=status.group(1).strip() if status else "",
        date=date.group(1) if date else "",
        author=author.group(1).strip() if author else "",
        superseded_by=superseded.group(1) if superseded else None,
    )


def _consumer_missing(root: Path, consumer: dict[str, str]) -> str | None:
    """None when the anchor is present; a reason string when UNSYNCED."""
    rel = consumer.get("file", "")
    path = root / rel
    if not path.is_file():
        return f"{rel}: consumer file missing"
    text = path.read_text(encoding="utf-8", errors="replace")
    regex = consumer.get("expect_regex")
    if regex:
        if re.search(regex, text) is None:
            return f"{rel}: expect_regex {regex!r} not found"
        return None
    expect = consumer.get("expect", "")
    if expect and expect not in text:
        return f"{rel}: expect {expect!r} not found"
    return None


def check(root: Path, contract: Contract) -> dict[str, Any]:
    """Run all four invariants; return {errors, unsynced} (plan T10 payload)."""
    errors: list[str] = []
    unsynced: list[str] = []
    files = adr_files(root)
    indexed = index_numbers(root)

    # ① index ↔ files, both directions
    for number in sorted(set(files) - indexed):
        errors.append(f"docs/adr/README.md: ADR {number} exists on disk but is not indexed")
    for number in sorted(indexed - set(files)):
        errors.append(f"docs/adr/README.md: index links ADR {number} but the file is missing")

    # ② per-file structure
    for number, path in files.items():
        record = parse_adr(path)
        if record is None:
            continue
        rel = path.relative_to(root).as_posix()
        if not record.status:
            errors.append(f"{rel}: missing Status line")
        else:
            # First word only: annotations like "Accepted (amended by 0013)"
            # are legal — the vocabulary constrains the state, not the note.
            first_word = re.split(r"[\s(]", record.status, 1)[0]
            if first_word not in LEGAL_STATUSES:
                errors.append(f"{rel}: illegal Status {record.status!r}")
        if not record.date:
            errors.append(f"{rel}: missing Date line")
        if not record.author:
            errors.append(f"{rel}: missing Author line")
        if record.superseded_by is not None and record.superseded_by not in files:
            errors.append(
                f"{rel}: Superseded by {record.superseded_by} but that ADR does not exist"
            )

    # ③ registered decisions must find their consumer anchors
    registered: set[str] = set()
    for name, decision in contract.decisions.items():
        registered.add(decision.adr)
        if decision.adr not in files:
            unsynced.append(f"[decisions.{name}] ADR {decision.adr} does not exist on disk")
            continue
        for consumer in decision.consumers:
            reason = _consumer_missing(root, consumer)
            if reason:
                unsynced.append(f"[decisions.{name}] {reason}")

    # ④ every ADR file must be registered
    for number in sorted(set(files) - registered):
        unsynced.append(
            f"ADR {number} is not registered in the contract [decisions] — "
            "a decision without registered consumers cannot be checked for sync"
        )

    return {"errors": errors, "unsynced": unsynced, "adr_count": len(files)}
