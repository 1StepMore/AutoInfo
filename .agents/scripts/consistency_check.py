#!/usr/bin/env python3
"""Agent-governance consistency checks — C3/C4/C5/C7 (guideline 02 稿 §6.2, A13).

Deterministic, stdlib-only, non-LLM. Failure exits non-zero and names file + line +
check id, so a red CI job points straight at the fix (§6.3: 失败挡 CI).

Scope split (Owner decision 4 — no parallel instrument):
  C1/C2/C6 ride on existing instruments wired in guard.yml:
      scripts/doc_inventory.py  (README/AGENTS facts, living-doc counts, INVENTORY.md
                                 freshness = C6)
      scripts/surface_parity.py (REST surface parity)
      scripts/coverage_matrix.py (end-user matrix parity)
  This script adds the four checks those instruments do not cover:
      C3  root AGENTS.md ≤ 200 lines
      C4  .agents/roles/{coder,maintainer,tester,user}.md — five element headings
          (Done / 返回格式 / 工具与来源指引 / 任务边界 / Stop & Escalate) present, each
          ≤30 lines, every element heading followed by non-empty content
      C5  no {{placeholder}} residue in landed governance files (scoped to the files
          this remediation landed; Jinja *.j2 and prompt sources are out of scope —
          they legitimately contain braces)
      C7  .agents/expectations/INDEX.md ↔ scenarios/ one-to-one, no orphan scenarios

Usage:
    python .agents/scripts/consistency_check.py --check   # exit 0 = clean
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROLES = ROOT / ".agents" / "roles"
EXPECT = ROOT / ".agents" / "expectations"

ROLE_FILES = ("coder.md", "maintainer.md", "tester.md", "user.md")
ELEMENT_HEADINGS = (
    "## Done",
    "## 返回格式",
    "## 工具与来源指引",
    "## 任务边界与禁止触碰",
    "## Stop & Escalate",
)
ROLE_LINE_LIMIT = 30
AGENTS_LINE_LIMIT = 200

#: C5 scope — exactly the files this remediation landed (governance layer only).
#: Glob patterns are relative to ROOT; `**` matches any depth (pathlib ≥3.13).
C5_SCOPES = (
    "AGENTS.md",
    "src/autoinfo/AGENTS.md",
    "docs/AGENTS.md",
    "tests/AGENTS.md",
    ".agents/roles/*.md",
    ".agents/expectations/*.md",
    ".agents/audit/*.md",
    ".specify/memory/*.md",
    ".claude/agents/*.md",
    ".github/agents/*.md",
    "docs/dev/DEBT.md",
    "docs/user/*.md",
    "docs/user/**/*.md",
    "tests/e2e/features/*.md",
    "tests/e2e/features/**/*.md",
)

PLACEHOLDER = re.compile(r"\{\{[^{}]*\}\}")
SCENARIO_REF = re.compile(r"scenarios/([A-Za-z0-9_-]+)\.md")
#: Headings may carry a parenthetical qualifier (02 稿 templates: "## Done（全部满足）").
#: Normalize by dropping everything from the first full/half-width paren.
_HEADING_NOISE = re.compile(r"[（(].*$")


def _heading_of(line: str) -> str:
    return _HEADING_NOISE.sub("", line.strip())


def _failures() -> list[str]:
    failures: list[str] = []

    # --- C3: root AGENTS.md line ceiling -------------------------------------
    agents = ROOT / "AGENTS.md"
    if not agents.exists():
        failures.append("C3: AGENTS.md missing")
    else:
        n = len(agents.read_text(encoding="utf-8").splitlines())
        if n > AGENTS_LINE_LIMIT:
            failures.append(
                f"C3: AGENTS.md has {n} lines > {AGENTS_LINE_LIMIT} ceiling — compress or downshift"
            )
        else:
            print(f"  C3: AGENTS.md {n} lines ≤ {AGENTS_LINE_LIMIT} -> ok")

    # --- C4: role contracts, four elements, ≤30 lines, non-empty sections ----
    for name in ROLE_FILES:
        path = ROLES / name
        if not path.exists():
            failures.append(f"C4: .agents/roles/{name} missing")
            continue
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        if len(lines) > ROLE_LINE_LIMIT:
            failures.append(f"C4: .agents/roles/{name} has {len(lines)} lines > {ROLE_LINE_LIMIT}")
        body = text.split("\n")
        before = len(failures)
        for heading in ELEMENT_HEADINGS:
            idx = next((i for i, ln in enumerate(body) if _heading_of(ln) == heading), None)
            if idx is None:
                failures.append(f"C4: .agents/roles/{name} missing element heading '{heading}'")
                continue
            # content = lines after the heading until the next heading/EOF
            nxt = next(
                (j for j in range(idx + 1, len(body)) if body[j].startswith("#")),
                len(body),
            )
            if not any(ln.strip() for ln in body[idx + 1 : nxt]):
                failures.append(
                    f"C4: .agents/roles/{name} element '{heading}' has empty content "
                    f"(line {idx + 1})"
                )
        if len(failures) == before:
            print(f"  C4: .agents/roles/{name} ({len(lines)} lines) elements + content -> ok")

    # --- C5: no {{placeholder}} residue in landed governance files ------------
    scanned = 0
    for pattern in C5_SCOPES:
        for path in sorted(ROOT.glob(pattern)):
            if not path.is_file():
                continue
            scanned += 1
            for i, ln in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if PLACEHOLDER.search(ln):
                    failures.append(f"C5: {{}} placeholder residue in {path.relative_to(ROOT)}:{i}")
    print(
        f"  C5: scanned {scanned} governance file(s) for placeholder residue -> "
        f"{'ok' if not failures else 'see failures'}"
    )

    # --- C7: INDEX ↔ scenarios one-to-one, no orphans -------------------------
    index = EXPECT / "INDEX.md"
    scenarios_dir = EXPECT / "scenarios"
    if not index.exists():
        failures.append("C7: .agents/expectations/INDEX.md missing")
    else:
        refs = set(SCENARIO_REF.findall(index.read_text(encoding="utf-8")))
        have = {p.stem for p in scenarios_dir.glob("*.md")} if scenarios_dir.exists() else set()
        for missing in sorted(refs - have):
            failures.append(f"C7: INDEX references scenarios/{missing}.md which does not exist")
        for orphan in sorted(have - refs):
            failures.append(
                f"C7: orphan scenario file scenarios/{orphan}.md not indexed in INDEX.md"
            )
        if not (refs - have) and not (have - refs):
            print(f"  C7: INDEX ↔ scenarios consistent ({len(have)} scenario file(s)) -> ok")

    return failures


def main() -> int:
    print("consistency_check --check (C3/C4/C5/C7)")
    failures = _failures()
    print()
    if failures:
        print(f"check FAILED ({len(failures)} issue(s)):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(
        "check passed: C3/C4/C5/C7 clean "
        "(C1/C2/C6 ride on doc_inventory/surface_parity/coverage_matrix)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
