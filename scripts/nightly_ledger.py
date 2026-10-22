#!/usr/bin/env python3
"""Render the NIGHTLY.md live zone from the append-only nightly ledger.

`docs/dev/plans/nightly-ledger.jsonl` is the single source of truth for the
four live sections of `docs/dev/plans/NIGHTLY.md`. The frozen zone
(完成定义 / 验收命令) is never touched: the renderer owns the whole live zone,
from the `## 【活区】当前差距矩阵` heading to EOF. The
`LEDGER:BEGIN <name>` / `LEDGER:END <name>` markers are human-readable anchors
only — `--check` compares the entire live segment byte-for-byte, so hand-edits
outside a marker pair are caught too.

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

LIVE_ZONE_HEADING = "## 【活区】当前差距矩阵"
LIVE_SECTIONS = (
    ("## 【活区】当前差距矩阵（2026-10-02 夜间循环）", "gap_snapshot"),
    ("## 【活区】下一步队列", "next_queue"),
    ("## 【活区】摩擦账本", "friction_log"),
    ("## 【活区】修订请求", "revision_requests"),
)
BLOCK_NAMES = tuple(name for _, name in LIVE_SECTIONS)
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


def render_live_zone(events: list[dict]) -> str:
    """Render the entire live zone, headings and separators included."""
    blocks = build_blocks(events)
    sections: list[str] = []
    for heading, name in LIVE_SECTIONS:
        lines = [heading, f"<!-- LEDGER:BEGIN {name} -->"]
        content = blocks[name]
        if content:
            lines.append(content)
        lines.append(f"<!-- LEDGER:END {name} -->")
        sections.append("\n".join(lines))
    return "\n\n---\n\n".join(sections) + "\n"


def live_zone_start(text: str) -> int:
    """Return the byte offset where the hand-editable live zone begins."""
    start = text.find(LIVE_ZONE_HEADING)
    if start < 0:
        raise SystemExit(f"{NIGHTLY_PATH}: missing live zone heading {LIVE_ZONE_HEADING!r}")
    return start


def check(path: Path, rendered: str) -> bool:
    text = path.read_text(encoding="utf-8")
    current = text[live_zone_start(text) :]
    if current == rendered:
        return True

    print("DRIFT: live zone does not match the ledger", file=sys.stderr)
    diff = difflib.unified_diff(
        current.splitlines(),
        rendered.splitlines(),
        fromfile=f"{path.name} [live zone]",
        tofile=f"{LEDGER_PATH.name} [live zone]",
        lineterm="",
    )
    print("\n".join(diff), file=sys.stderr)
    return False


def write(path: Path, rendered: str) -> None:
    text = path.read_text(encoding="utf-8")
    frozen = text[: live_zone_start(text)]
    path.write_text(frozen + rendered, encoding="utf-8")


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
    rendered = render_live_zone(events)

    if args.check:
        if check(NIGHTLY_PATH, rendered):
            print("nightly ledger: NIGHTLY.md live zone is in sync")
            return 0
        print("nightly ledger: NIGHTLY.md live zone is STALE — run --write", file=sys.stderr)
        return 1

    write(NIGHTLY_PATH, rendered)
    print(f"nightly ledger: wrote the live zone to {NIGHTLY_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
