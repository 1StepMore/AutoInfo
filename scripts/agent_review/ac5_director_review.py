#!/usr/bin/env python3
"""AC5 director-review DRAFT generator (advisory input for a human).

This module produces a machine **DRAFT** of the AC5 (quality) director
sampling review described in ``docs/dev/acceptance-framework.md`` §5.2.  It
reads the PROCESSED product forms of a validation-delivery package, asks the
config-driven LLM channel to judge each against the four PROCESSED quality
concerns, and emits a draft verdict per form.

THE ONE PROPERTY THAT MATTERS — the RISK CEILING
------------------------------------------------
A correct model verdict of ``PASS`` is **coerced to ``RISK``** on the way out
(:func:`coerce_to_draft`), so a rubber stamp is structurally impossible.  An
unreachable model is ``ESCALATE``; unparseable / garbage / truncated output is
``ESCALATE``; never ``PASS``.  The draft is never a director verdict and never
an acceptance verdict — it is advisory input for a human.

Why RISK and not PASS is mandatory (director decision, 2026-08-08):
``acceptance-framework.md:56`` — the acceptance lens for deliverables is always
human-first; "human judgment remains the primary view".  ``:90`` (P5) — "The
agent grades; the human disposes."  ``:194`` (§3.3) — "Agent evidence alone is
never sufficient for a deliverable-type acceptance"; a missing human verdict is
RISK, and RISK blocks sign-off (``:332``).  RISK is therefore the
framework-sanctioned ceiling for a machine AC5 judgment, and ``ESCALATE`` is
the fail-loud floor.

Reuse, not duplication: all model-calling, structured-output capability
probing, markdown/JSON verdict parsing, truncation detection, and fail-loud
escalation are inherited from ``scripts/agent_review/battery.py``.  This module
adds only the AC5 worklist, the RISK-ceiling coercion, and draft persistence.

Vendor/model agnosticism: the channel is the repo's config-driven
``autoinfo.llm.call_with_fallback`` (provider/model/api_key/base_url + fallback
chain).  No vendor or model name appears in this file.

Runtime state only: the draft is written under ``validation-runs/ac5-draft/``
(gitignored), never under ``docs/``.

Usage (from repo root):

    python3 scripts/agent_review/ac5_director_review.py \\
        --delivery-dir validation-deliveries/<date>
      # deterministic preview: no model call, every row RISK
    python3 scripts/agent_review/ac5_director_review.py \\
        --delivery-dir validation-deliveries/<date> --semantic --json
      # full draft: model verdicts coerced to the RISK ceiling
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Sequence

# Reuse the battery's config-driven channel + fail-loud parsing machinery.
# scripts/agent_review/ is not a package, so the directory is on sys.path when
# this module is imported (tests/scripts and the CLI entry add it).
from battery import (
    _channel_json_capable,
    _family_of_file,
    _judge_with_llm,
    _normalize_verdict,
    _read_file_snippet,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

#: The four PROCESSED quality concerns from acceptance-framework.md §5.2
#: (:255-:259): the table's three rows, with the completeness/accuracy row's
#: PROCESSED lens (factual accuracy) and the presentation-quality lens of the
#: traceability/presentation row broken out explicitly.
_AC5_CONCERNS: tuple[tuple[str, str], ...] = (
    (
        "Completeness / accuracy",
        "every synthesized claim is supported; no errors, hallucination, or "
        "misattribution; no key items missing",
    ),
    (
        "Depth / freshness",
        "analysis depth is sufficient and the briefing is timely for its domain",
    ),
    (
        "Traceability",
        "source provenance is visible for the synthesized claims",
    ),
    (
        "Presentation quality",
        "renders cleanly and reads well for a human",
    ),
)


# ---------------------------------------------------------------------------
# Worklist
# ---------------------------------------------------------------------------


def build_ac5_worklist(delivery_dir: Path) -> list[dict[str, str]]:
    """Return one worklist item per PROCESSED product form.

    Primary source is the delivery ``manifest.json`` (``kind ==
    "PROCESSED"``), whose file entries are written by
    ``scripts/validation_delivery.py``.  When no readable manifest is present
    the directory's ``*.md`` products are scanned instead.

    Each item is ``{family, file, path}``: the blind-spot/product family, the
    display file name, and the resolvable path the reviewer reads.
    """
    base = Path(delivery_dir)
    manifest_path = base / "manifest.json"
    if manifest_path.is_file():
        data: Any = None
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = None
        if isinstance(data, dict):
            files = data.get("files")
            entries = files if isinstance(files, list) else []
            return [
                _item_from_manifest(base, entry)
                for entry in entries
                if isinstance(entry, dict) and entry.get("kind") == "PROCESSED"
            ]
    return _items_from_scan(base)


def _item_from_manifest(base: Path, entry: dict[str, Any]) -> dict[str, str]:
    rel = str(entry.get("file", ""))
    path = base / rel
    return {
        "family": _family_of_file(path),
        "file": Path(rel).name,
        "path": str(path),
    }


def _items_from_scan(base: Path) -> list[dict[str, str]]:
    return [
        {"family": _family_of_file(md), "file": md.name, "path": str(md)}
        for md in sorted(base.glob("*.md"))
    ]


# ---------------------------------------------------------------------------
# THE INVARIANT — the RISK ceiling
# ---------------------------------------------------------------------------

_RISK_TOKEN_RE = re.compile(r"\bRISK\b")


def coerce_to_draft(raw: str) -> str:
    """Coerce a raw verdict to the AC5 draft ceiling — never ``PASS``.

    ``PASS`` → ``RISK``; ``FLAG`` → ``RISK``; ``RISK`` → ``RISK``;
    ``ESCALATE`` → ``ESCALATE``; anything unrecognised → ``ESCALATE``.

    Pure and total: no input string maps to ``PASS``, so a machine draft can
    never rubber-stamp a product.  ``PASS``/``FLAG``/``RISK`` all collapse to
    the framework-sanctioned RISK ceiling (agent evidence alone is never
    sufficient for a deliverable-type acceptance — acceptance-framework.md
    :194).
    """
    token = _normalize_verdict(raw)
    if token == "ESCALATE":
        return "ESCALATE"
    if token in ("PASS", "FLAG"):
        return "RISK"
    # RISK is not in the battery's verdict token set; recognise it explicitly.
    if _RISK_TOKEN_RE.search(raw.upper()):
        return "RISK"
    return "ESCALATE"


# ---------------------------------------------------------------------------
# Per-item review
# ---------------------------------------------------------------------------


def _ac5_prompt(item: dict[str, str]) -> str:
    """Build the AC5 quality-review prompt for one product form.

    The product's real content is embedded (bounded snippet) so the stateless
    model judges actual text, not a path.  The output contract matches the
    battery's markdown verdict parser exactly.
    """
    concerns = "\n".join(f"- {name}: {desc}" for name, desc in _AC5_CONCERNS)
    snippet = _read_file_snippet(item["path"])
    return (
        "You are performing a director-sampling quality review of one "
        "PROCESSED product form (AC5, acceptance-framework.md §5.2).\n"
        f"Product family: {item['family']}\n"
        f"File: {item['file']}\n\n"
        "Judge the product against these four quality concerns:\n"
        f"{concerns}\n\n"
        "Product content:\n"
        f"{snippet}\n\n"
        "Rules:\n"
        "- Verdict PASS only when the product satisfies all four concerns; "
        "FLAG when it violates one; ESCALATE when you cannot judge or it is a "
        "product-intent/value call for a human.\n"
        "- Honest hedges ('not disclosed', 'not provided in the sources') are "
        "CORRECT behavior — never FLAG them.\n"
        "- Every verdict MUST cite evidence (file:line or source URL). A "
        "verdict without evidence is invalid.\n"
        "- If you cannot reach a judgment for any reason, output ESCALATE — "
        "never PASS on an unverified claim.\n\n"
        "OUTPUT SCHEMA — respond with EXACTLY ONE block starting with the "
        "header '## Verdict', followed by these four lines:\n"
        "- **blind_spot**: <id>\n"
        "- **verdict**: PASS | FLAG | ESCALATE\n"
        "- **evidence**: <file:line or source URL>\n"
        "- **note**: <1-3 sentences>\n"
        "Output NOTHING outside that block.\n"
    )


def review_product(item: dict[str, str], *, semantic: bool) -> dict[str, Any]:
    """Draft-review one product form; return ``{family, file, draft_verdict,
    llm_verdict, evidence, note}``.

    ``draft_verdict = coerce_to_draft(llm_verdict)`` always — the RISK ceiling
    is applied here, not optional.  With ``semantic=False`` no model call is
    made at all and the preview row is emitted with ``draft_verdict="RISK"``
    (no human/director verdict on record ⇒ the AC5 ceiling).

    Evidence is mandatory: a recognised verdict whose evidence is empty is
    inadmissible and escalates — fail loud, never a silent risk-free pass.
    """
    family = item.get("family", "")
    file = item.get("file", "")

    if not semantic:
        return {
            "family": family,
            "file": file,
            "draft_verdict": "RISK",
            "llm_verdict": "NOT_REVIEWED",
            "evidence": "",
            "note": (
                "semantic pass not requested (deterministic preview); no "
                "director verdict on record — AC5 ceiling is RISK"
            ),
        }

    want_json = _channel_json_capable()
    result = _judge_with_llm(_ac5_prompt(item), want_json=want_json)
    evidence = str(result.get("evidence", "")).strip()
    if evidence:
        llm_verdict = str(result.get("verdict", ""))
        note = str(result.get("note", ""))
    else:
        # No evidence ⇒ inadmissible judgment ⇒ fail loud.
        llm_verdict = "ESCALATE"
        note = "no evidence cited — mandatory AC5 evidence absent; escalated"

    return {
        "family": family,
        "file": file,
        "draft_verdict": coerce_to_draft(llm_verdict),
        "llm_verdict": llm_verdict,
        "evidence": evidence,
        "note": note,
    }


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


def run_ac5_review(delivery_dir: Path, *, semantic: bool = False) -> dict[str, Any]:
    """Run the AC5 draft review; return ``{worklist, verdicts, summary,
    honesty}``.

    ``summary.passed`` is always 0: no draft verdict can ever be PASS.
    """
    worklist = build_ac5_worklist(Path(delivery_dir))
    verdicts = [review_product(item, semantic=semantic) for item in worklist]

    total = len(worklist)
    risk = sum(1 for v in verdicts if v["draft_verdict"] == "RISK")
    escalate = sum(1 for v in verdicts if v["draft_verdict"] == "ESCALATE")
    passed = sum(1 for v in verdicts if v["draft_verdict"] == "PASS")

    if not semantic:
        channel = "deterministic preview (no --semantic)"
    else:
        channel = "config.llm json_mode" if _channel_json_capable() else "config.llm markdown"

    return {
        "worklist": worklist,
        "verdicts": verdicts,
        "summary": {
            "total": total,
            "risk": risk,
            "escalate": escalate,
            "passed": passed,
        },
        "honesty": {
            "channel": channel,
            "reviewed": [v["file"] for v in verdicts] if semantic else [],
            "not_reviewed": [] if semantic else [i["file"] for i in worklist],
        },
    }


def _persist(report: dict[str, Any], version: str, runs_dir: Path) -> Path:
    """Write the draft under ``<runs_dir>/ac5-draft/ac5-draft-<date>.json``.

    Runtime state (``validation-runs/`` is gitignored), never under ``docs/``.
    Returns the written path.
    """
    target_dir = Path(runs_dir) / "ac5-draft"
    target_dir.mkdir(parents=True, exist_ok=True)
    out = target_dir / f"ac5-draft-{date.today().isoformat()}.json"
    payload = {
        "version": version,
        "generated": datetime.now(timezone.utc).isoformat(),
        "report": report,
    }
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--delivery-dir",
        type=Path,
        required=True,
        help="validation-delivery package (manifest.json or *.md products)",
    )
    parser.add_argument(
        "--semantic",
        action="store_true",
        help="enable the model verdict pass (default: deterministic preview)",
    )
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    parser.add_argument(
        "--version",
        default="unreleased",
        help="version label recorded in the persisted draft",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="runs directory to persist under (default: <repo>/validation-runs)",
    )
    args = parser.parse_args(argv)

    if not args.delivery_dir.is_dir():
        print(f"ERROR: {args.delivery_dir} is not a directory", file=sys.stderr)
        return 2

    report = run_ac5_review(args.delivery_dir, semantic=args.semantic)
    runs_dir = args.out if args.out is not None else _REPO_ROOT / "validation-runs"
    _persist(report, args.version, runs_dir)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"AC5 director-review DRAFT — {args.delivery_dir}")
        print(f"Worklist: {report['summary']['total']} product form(s)")
        for v in report["verdicts"]:
            print(f"  [{v['draft_verdict']}] {v['file']}: {v['note'][:100]}")
        s = report["summary"]
        print(f"SUMMARY: risk={s['risk']} escalate={s['escalate']} passed={s['passed']}")

    return 1 if report["summary"]["escalate"] else 0


if __name__ == "__main__":
    sys.exit(main())
