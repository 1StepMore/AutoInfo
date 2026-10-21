#!/usr/bin/env python3
"""Render the NIGHTLY.md live zone from the append-only nightly ledger.

`docs/dev/plans/nightly-ledger.jsonl` is the single source of truth for the
four live sections of `docs/dev/plans/NIGHTLY.md`. The frozen zone
(完成定义 / 验收命令) is never touched: the renderer only replaces text between
the `LEDGER:BEGIN <name>` / `LEDGER:END <name>` marker pairs.

Four event kinds:

    gap_snapshot       {"date", "kind", "text", "commit", ...}
    queue_item         {"date", "kind", "id", "text", "status", "owner", ...}
    friction           {"date", "kind", "id", "text", "cost", "disposition", ...}
    revision_request   {"date", "kind", "id", "text", "target", "status", ...}

State changes are new events carrying `supersedes`: old lines are never edited
(append-only, so two nightly branches never conflict on the ledger).

Rendering is deterministic: snapshots are newest-first (latest 10), queue /
friction / revision rows sort by id, and no timestamps are generated.

Usage:
    python scripts/nightly_ledger.py --check
    python scripts/nightly_ledger.py --write
    python scripts/nightly_ledger.py --append '<json event>'
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
NIGHTLY_PATH = REPO_ROOT / "docs" / "dev" / "plans" / "NIGHTLY.md"
LEDGER_PATH = REPO_ROOT / "docs" / "dev" / "plans" / "nightly-ledger.jsonl"

BLOCK_NAMES = ("gap_snapshot", "next_queue", "friction_log", "revision_requests")
EVENT_KINDS = ("gap_snapshot", "queue_item", "friction", "revision_request")
SNAPSHOT_LIMIT = 10

QUEUE_INTRO = (
    "> 取活策略（L1 §4）：**先纵后横** —— 先把**一个域**的四条件全链路打穿"
    "（采集 → 处理 → 产物 → 断言全过），再把这套办法复制到其余域。\n"
    "> agent 每晚完成后自己更新此队列，并把已完成项移入「已完成」小节。"
)
QUEUE_DONE_HEADING = "### 已完成（agent 追加）"

FRICTION_INTRO = (
    "> 规则（L1 §5）：**不挡住 DoD 的发现，当晚一律不修，只记账**。挡住 DoD 的允许插队。\n"
    "> 本阶段摩擦预算 = 0。"
)

REVISION_INTRO = "> 认为冻结区某条不合理 → 写这里（附证据）。**不得自行修改冻结区。**"


def load_events(path: Path) -> list[dict]:
    """Load the JSONL ledger, preserving file order in a private `_seq` field."""
    if not path.exists():
        return []
    events: list[dict] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{lineno}: invalid JSON: {exc}") from exc
        if not isinstance(event, dict):
            raise SystemExit(f"{path}:{lineno}: event must be a JSON object")
        kind = event.get("kind")
        if kind not in EVENT_KINDS:
            raise SystemExit(f"{path}:{lineno}: unknown kind {kind!r}")
        if kind != "gap_snapshot" and not event.get("id"):
            raise SystemExit(f"{path}:{lineno}: {kind} event requires an id")
        if not event.get("date"):
            raise SystemExit(f"{path}:{lineno}: event requires a date")
        event["_seq"] = len(events)
        events.append(event)
    return events


def _effective(events: list[dict], kind: str) -> dict[str, dict]:
    """Fold supersedes chains without mutating the ledger.

    A later event replaces the state of the id it `supersedes` (usually itself).
    """
    state: dict[str, dict] = {}
    for event in events:
        if event["kind"] != kind:
            continue
        event_id = event["id"]
        superseded = event.get("supersedes")
        if superseded:
            state.pop(superseded, None)
        state[event_id] = event
    return state


def render_gap_snapshot(events: list[dict]) -> str:
    snapshots = [e for e in events if e["kind"] == "gap_snapshot"]
    snapshots.sort(key=lambda e: (e["date"], e["_seq"]), reverse=True)
    snapshots = snapshots[:SNAPSHOT_LIMIT]

    parts: list[str] = []
    for event in snapshots:
        body = (event.get("text") or "").strip("\n")
        if event.get("heading", True):
            commit = event.get("commit") or "unknown"
            heading = f"### {event['date']} 夜间复跑（在最新 main `{commit}` 上）"
            parts.append(f"{heading}\n\n{body}" if body else heading)
        elif body:
            parts.append(body)
    return "\n\n".join(parts)


def render_next_queue(events: list[dict]) -> str:
    state = _effective(events, "queue_item")
    active = sorted(
        (e for e in state.values() if e.get("group", "active") == "active"),
        key=lambda e: e["id"],
    )
    done = sorted(
        (e for e in state.values() if e.get("group") == "done"),
        key=lambda e: e["id"],
    )

    lines = QUEUE_INTRO.split("\n") + [""]
    for number, event in enumerate(active, 1):
        lines.append(f"{number}. {(event.get('text') or '').strip()}")
    if done:
        lines += ["", QUEUE_DONE_HEADING, ""]
        lines.extend(f"- {(event.get('text') or '').strip()}" for event in done)
    return "\n".join(lines)


def _cell(value: object) -> str:
    """Render a markdown table cell from a raw ledger value."""
    return str(value or "").strip().replace("|", "\\|")


def render_friction_log(events: list[dict]) -> str:
    state = _effective(events, "friction")
    rows = sorted(state.values(), key=lambda e: e["id"])
    lines = FRICTION_INTRO.split("\n") + [
        "",
        "| 日期 | 发现 | 是否挡住 DoD | 处置 |",
        "|:---|:---|:---|:---|",
    ]
    for event in rows:
        lines.append(
            f"| {_cell(event.get('date'))} | {_cell(event.get('text'))} "
            f"| {_cell(event.get('cost'))} "
            f"| {_cell(event.get('disposition'))} |"
        )
    return "\n".join(lines)


def render_revision_requests(events: list[dict]) -> str:
    state = _effective(events, "revision_request")
    rows = sorted(state.values(), key=lambda e: e["id"])
    lines = [
        REVISION_INTRO,
        "",
        "| 日期 | 目标条款 | 理由 + 证据 | 裁定 |",
        "|:---|:---|:---|:---|",
    ]
    for event in rows:
        lines.append(
            f"| {_cell(event.get('date'))} | {_cell(event.get('target'))} "
            f"| {_cell(event.get('text'))} "
            f"| {_cell(event.get('status'))} |"
        )
    return "\n".join(lines)


def build_blocks(events: list[dict]) -> dict[str, str]:
    return {
        "gap_snapshot": render_gap_snapshot(events),
        "next_queue": render_next_queue(events),
        "friction_log": render_friction_log(events),
        "revision_requests": render_revision_requests(events),
    }


def _block_bounds(text: str, name: str) -> tuple[int, int]:
    """Return (content_start, end_marker_line_start) for one marker pair."""
    begin = f"<!-- LEDGER:BEGIN {name} -->"
    end = f"<!-- LEDGER:END {name} -->"

    begin_at = text.find(begin)
    if begin_at < 0:
        raise SystemExit(f"{NIGHTLY_PATH}: missing marker {begin!r}")
    begin_newline = text.find("\n", begin_at)
    if begin_newline < 0:
        raise SystemExit(f"{NIGHTLY_PATH}: begin marker {name!r} is not on its own line")

    end_at = text.find(end, begin_newline)
    if end_at < 0:
        raise SystemExit(f"{NIGHTLY_PATH}: missing marker {end!r}")
    end_line_start = text.rfind("\n", 0, end_at) + 1
    if text[end_line_start:end_at].strip():
        raise SystemExit(f"{NIGHTLY_PATH}: end marker {name!r} is not on its own line")

    if end_line_start < begin_newline:
        raise SystemExit(f"{NIGHTLY_PATH}: markers out of order for {name!r}")
    return begin_newline + 1, end_line_start


def _current_content(text: str, name: str) -> str:
    start, end = _block_bounds(text, name)
    content = text[start:end]
    if content.endswith("\n"):
        content = content[:-1]
    return content


def check(path: Path, blocks: dict[str, str]) -> bool:
    text = path.read_text(encoding="utf-8")
    ok = True
    for name in BLOCK_NAMES:
        current = _current_content(text, name)
        expected = blocks[name]
        if current == expected:
            continue
        ok = False
        print(f"DRIFT: {name} does not match the ledger", file=sys.stderr)
        diff = difflib.unified_diff(
            current.splitlines(),
            expected.splitlines(),
            fromfile=f"{path.name} [{name}]",
            tofile=f"{LEDGER_PATH.name} [{name}]",
            lineterm="",
        )
        print("\n".join(diff), file=sys.stderr)
    return ok


def write(path: Path, blocks: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8")
    for name in BLOCK_NAMES:
        start, end = _block_bounds(text, name)
        content = blocks[name]
        replacement = f"{content}\n" if content else ""
        text = text[:start] + replacement + text[end:]
    path.write_text(text, encoding="utf-8")


def append_event(path: Path, raw: str) -> dict:
    try:
        event = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--append: invalid JSON: {exc}") from exc
    if not isinstance(event, dict):
        raise SystemExit("--append: event must be a JSON object")
    kind = event.get("kind")
    if kind not in EVENT_KINDS:
        raise SystemExit(f"--append: unknown kind {kind!r}")
    if not event.get("date"):
        raise SystemExit("--append: event requires a date")
    if kind != "gap_snapshot" and not event.get("id"):
        raise SystemExit(f"--append: {kind} event requires an id")

    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    with path.open("a", encoding="utf-8") as handle:
        if existing and not existing.endswith("\n"):
            handle.write("\n")
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render or verify the NIGHTLY.md live zone from the JSONL ledger.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="verify without writing")
    mode.add_argument("--write", action="store_true", help="rewrite the live zone")
    mode.add_argument("--append", metavar="JSON", help="append an event, then rewrite")
    args = parser.parse_args(argv)

    if args.append is not None:
        append_event(LEDGER_PATH, args.append)

    events = load_events(LEDGER_PATH)
    blocks = build_blocks(events)

    if args.check:
        if check(NIGHTLY_PATH, blocks):
            print("nightly ledger: NIGHTLY.md live zone is in sync")
            return 0
        print("nightly ledger: NIGHTLY.md live zone is STALE — run --write", file=sys.stderr)
        return 1

    write(NIGHTLY_PATH, blocks)
    print(f"nightly ledger: wrote {len(BLOCK_NAMES)} live blocks to {NIGHTLY_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
