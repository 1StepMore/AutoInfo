"""Line-anchored frontmatter delimiters for KB parsing (issue #735).

A bare ``content.find("---", 3)`` treated the first three consecutive dashes
anywhere as the closing delimiter.  A title containing ``----`` (four hyphens)
was truncated mid-value, leaving ``entry_id`` / ``domain`` in the body, so
``KBEntry.from_dict`` raised ``TypeError`` and every collection round skipped
the entry.  The delimiter must match a whole line instead.
"""

from __future__ import annotations

from pathlib import Path

from autoinfo.dedup import DedupChecker

_TITLE_WITH_DASHES = (
    "程序员的副业 IP 探索之路----小白用AI做了个游戏，发出去第一天居然有300多个人玩！！！"
)


def _frontmatter(newline: str = "\n", body: str = "正文第一段。\n") -> str:
    fields = [
        "---",
        f"title: {_TITLE_WITH_DASHES}",
        "entry_id: tech-ai-developer-general-ip-ai-300",
        "domain: tech-ai-developer",
        "tier: 01-Raw",
        "source_url: https://example.com/ip-ai-300",
        "source_type: rss",
        "source_platform: rss",
        "---",
    ]
    return newline.join(fields) + newline + body


def test_frontmatter_title_with_quadruple_dash_and_body_rule_parse(tmp_path: Path) -> None:
    md = tmp_path / "entry.md"
    md.write_text(
        _frontmatter(body="正文第一段。\n\n---\n\n水平线之后的正文。\n"), encoding="utf-8"
    )

    entry = DedupChecker._parse_kb_file(md)

    assert entry is not None
    assert entry.entry_id == "tech-ai-developer-general-ip-ai-300"
    assert entry.domain == "tech-ai-developer"
    assert entry.title == _TITLE_WITH_DASHES
    assert entry.file_path == str(md)


def test_frontmatter_crlf_line_endings_parse(tmp_path: Path) -> None:
    md = tmp_path / "entry.md"
    md.write_bytes(_frontmatter(newline="\r\n").encode("utf-8"))

    entry = DedupChecker._parse_kb_file(md)

    assert entry is not None
    assert entry.entry_id == "tech-ai-developer-general-ip-ai-300"
    assert entry.domain == "tech-ai-developer"


def test_frontmatter_missing_closing_delimiter_returns_none(tmp_path: Path) -> None:
    md = tmp_path / "broken.md"
    md.write_text("---\ntitle: Broken\nentry_id: x\ndomain: d\n", encoding="utf-8")

    assert DedupChecker._parse_kb_file(md) is None
