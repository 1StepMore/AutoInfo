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

THE WORKLIST FILTER — only reviewable TEXT products reach the judge
------------------------------------------------------------------
A delivery manifest's ``kind == "PROCESSED"`` is **much** coarser than "a
product form a human director can read".  Measured on a real 3383-entry
delivery package: 474 PROCESSED entries, of which only 298 are ``.md`` — the
other 176 are 128 ``.err``, 33 ``.log``, 13 ``.mp4``, 1 ``.zip``, 1 ``.json``
(``validation_delivery.py`` copies pipeline logs and failed-step logs into
``02-PROCESSED/`` beside the products).  Feeding those to the judge aborts the
whole run on the first ``UnicodeDecodeError`` from a ``.mp4``/``.zip``.

The filter is therefore an **allowlist of reviewable text suffixes**
(:data:`_REVIEWABLE_TEXT_SUFFIXES`), not a blocklist of known binaries:

* fail-closed — a format nobody anticipated (``.epub``, ``.mobi``, ``.mp3``,
  ``.pdf``, ``.sqlite``, a future ``.avif``) is excluded by default instead of
  crashing the run; a blocklist would have to enumerate every one of them;
* ``.log``/``.err`` are excluded because they are *pipeline execution
  transcripts*, not product forms: they carry no synthesized claim, no
  presentation, and no source provenance to judge, and 161 of them would
  dilute an AC5 *sampling* review of products.  They are not "unreviewable" —
  they are out of scope, and :func:`run_ac5_review` reports every excluded
  artifact with its reason so the omission is visible, never silent;
* ``.json``/``.pdf`` are excluded for the same out-of-scope reason (machine
  metadata / a non-text rendering) — this reviewer judges *text*, it does not
  OCR, transcribe, or parse containers.

Two independent fail-loud guards follow from this:

* a worklist file that passes the suffix filter but cannot be decoded as
  UTF-8 (or cannot be read at all) is surfaced as an **ESCALATE** row via
  :func:`review_product` — never a model call on garbage bytes, never a silent
  drop, never a pass (:func:`_read_product_snippet`);
* an **empty or fully-excluded** worklist is a *blocked* run, not a clean run:
  :func:`run_ac5_review` marks it and :func:`main` exits ``2`` (see below).  A
  0-item worklist used to print ``SUMMARY: risk=0 escalate=0 passed=0`` — a
  false "all clean" on the acceptance path, which is worse than a crash.

THE FALLBACK SCAN IS RECURSIVE
------------------------------
When no readable manifest exists, the scan is ``rglob``-based, not
``glob("*.md")``: the real product tree is ``outputs/<domain>/*.md`` (222
products across 13 domain subdirs, 0 at the top level), so a non-recursive
scan returned 0 items and the run reported "all clean" without reading a
single product.  The scan shares the one suffix rule and is sorted and
de-duplicated by resolved path, so the same tree always yields the same
deterministic worklist.

INCREMENTAL OUTPUT
------------------
Verdicts are emitted as they are judged (header with the worklist size, one
line per form, then SUMMARY) through the ``emit`` sink, so an operator running
``python3 -u`` can tell a progressing run from a hung one.  The previous
all-at-once printing left a 278-byte log for the whole 66-minute run, which
made "hung" indistinguishable from "working".

Exit codes: ``0`` draft produced with no ESCALATE · ``1`` at least one
ESCALATE · ``2`` the run could not produce a reviewable worklist (bad input
directory, or an empty/all-excluded worklist) — **not** a clean run.

Runtime state only: the draft is written under ``validation-runs/ac5-draft/``
(gitignored), never under ``docs/``.

Usage (from repo root):

    python3 -u scripts/agent_review/ac5_director_review.py \\
        --delivery-dir validation-deliveries/<date>
      # deterministic preview: no model call, every row RISK
    python3 -u scripts/agent_review/ac5_director_review.py \\
        --delivery-dir validation-deliveries/<date> --semantic
      # full draft: model verdicts coerced to the RISK ceiling
    python3 -u scripts/agent_review/ac5_director_review.py \\
        --delivery-dir validation-deliveries/<date> --semantic --json
      # progress lines go to stderr, the JSON report stays alone on stdout
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Sequence

# Reuse the battery's config-driven channel + fail-loud parsing machinery.
# scripts/agent_review/ is not a package, so the directory is on sys.path when
# this module is imported (tests/scripts and the CLI entry add it).
from battery import (
    _TRUNCATION_MARKER,
    _VERDICT_SCHEMA_BLOCK,
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

#: Suffixes this reviewer can judge as a product form: UTF-8 text a human reads
#: as the deliverable itself.  Allowlist, not blocklist — see the module
#: docstring ("THE WORKLIST FILTER") for the measured 474/298 split and why
#: ``.log``/``.err``/``.mp4``/``.zip``/``.json`` are out of scope rather than
#: merely unreadable.
_REVIEWABLE_TEXT_SUFFIXES: frozenset[str] = frozenset({".md", ".markdown", ".html", ".htm", ".txt"})

#: Exit code class shared with a bad ``--delivery-dir``: the run produced no
#: reviewable worklist at all, so it is NOT a clean review.
_EXIT_NO_WORKLIST = 2

#: Exit code for "a draft was produced but something needs a human".
_EXIT_ESCALATED = 1


def is_reviewable_product(path: Path) -> bool:
    """Return True when *path* is a text product form this reviewer can judge."""
    return path.suffix.lower() in _REVIEWABLE_TEXT_SUFFIXES


def _ac5_candidates(delivery_dir: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Partition a delivery into ``(reviewable worklist, excluded artifacts)``.

    Primary source is the delivery ``manifest.json`` (``kind ==
    "PROCESSED"``), whose file entries are written by
    ``scripts/validation_delivery.py``.  When no readable manifest is present
    the tree is scanned recursively instead.

    Each reviewable item is ``{family, file, path}``: the blind-spot/product
    family, the display file name, and the resolvable path the reviewer reads.
    Each excluded entry is ``{file, suffix, reason}`` so every dropped artifact
    is attributable in the report — an exclusion is never a silent pass.
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
            worklist: list[dict[str, str]] = []
            excluded: list[dict[str, str]] = []
            for entry in entries:
                if not isinstance(entry, dict) or entry.get("kind") != "PROCESSED":
                    continue
                path = base / str(entry.get("file", ""))
                if is_reviewable_product(path):
                    worklist.append(_item(path))
                else:
                    excluded.append(_excluded(path, "not a reviewable text product"))
            return worklist, excluded
    return _items_from_scan(base)


def build_ac5_worklist(delivery_dir: Path) -> list[dict[str, str]]:
    """Return one worklist item per reviewable PROCESSED product form.

    Non-text PROCESSED artifacts (video, zip, logs, metadata) are filtered out
    by :func:`is_reviewable_product`; use :func:`_ac5_candidates` when the
    excluded set is needed too.
    """
    worklist, _excluded = _ac5_candidates(Path(delivery_dir))
    return worklist


def _item(path: Path) -> dict[str, str]:
    return {
        "family": _family_of_file(path),
        "file": path.name,
        "path": str(path),
    }


def _excluded(path: Path, reason: str) -> dict[str, str]:
    return {"file": path.name, "suffix": path.suffix.lower(), "reason": reason}


def _items_from_scan(base: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Recursively scan *base* for reviewable product forms.

    Recursive (``rglob``) because the real product tree is
    ``outputs/<domain>/*.md`` — 222 products across 13 domain subdirs and 0 at
    the top level, so a non-recursive ``glob("*.md")`` found nothing and
    reported a false "all clean".

    Sorted and de-duplicated by resolved path, so the same tree always yields
    the same worklist regardless of filesystem iteration order.
    """
    resolved: dict[Path, Path] = {}
    for candidate in base.rglob("*"):
        if candidate.is_file() and is_reviewable_product(candidate):
            resolved.setdefault(candidate.resolve(), candidate)
    worklist = [_item(resolved[key]) for key in sorted(resolved, key=str)]
    return worklist, []


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

#: Sentinel battery's snippet reader returns for an unreadable file (it catches
#: ``OSError`` itself).  Judging a placeholder string would be a review of
#: nothing, so ac5 treats it as an unreadable skip.
_UNREADABLE_SENTINEL = "<unreadable file:"


@dataclass(frozen=True, slots=True)
class ProductSnippet:
    """Text of a product form, or the recorded reason it is unreviewable."""

    text: str
    reason: str = ""
    truncated: bool = False


def _read_product_snippet(path: str) -> ProductSnippet:
    """Read a product's text for judging, converting a read failure into a skip.

    The trust boundary: product bytes cross into a prompt here.  Three specific
    conditions are handled instead of propagating:

    * ``UnicodeDecodeError`` — a file that passed the suffix filter but is not
      UTF-8 text.  On the real 474-entry delivery this was fatal: the first
      ``.mp4`` or ``.zip`` aborted the entire review run;
    * battery's ``<unreadable file: ...>`` sentinel — a manifest entry whose
      file is missing or unreadable, which is an equally unreviewable product;
    * a file longer than battery's snippet limit — flagged via ``truncated`` so
      the caller ESCALATEs rather than judging a fraction of the document.

    That third case is not hypothetical.  Against ``outputs/`` at battery's
    former 8 000-char limit, all 5 ESCALATE rows were false: the files were
    18 962-70 617 chars and complete, but the reviewer saw only the first
    8 012 and the model correctly reported that *what it could see* stopped
    mid-section.  The finding was about the reviewer's own window, not the
    product.  So an over-limit file is reported as an unreadable window, never
    as a product defect.

    Both failure results become a recorded :class:`ProductSnippet`, so the
    caller can ESCALATE the row.  No other exception is caught: an unexpected
    error is a defect and must stay loud.
    """
    try:
        text = _read_file_snippet(path)
    except UnicodeDecodeError as exc:
        return ProductSnippet(text="", reason=f"not UTF-8 decodable: {exc}")
    if text.startswith(_UNREADABLE_SENTINEL):
        return ProductSnippet(text="", reason=text.strip())
    if text.endswith(_TRUNCATION_MARKER):
        size = len(text) - len(_TRUNCATION_MARKER)
        return ProductSnippet(
            text="",
            reason=(
                f"file exceeds the reviewer's read window ({size} chars read, "
                "cap is larger): the reviewer cannot judge this product"
            ),
            truncated=True,
        )
    return ProductSnippet(text=text)


def _ac5_prompt(item: dict[str, str], snippet: str) -> str:
    """Build the AC5 quality-review prompt for one product form.

    The product's real content is embedded (bounded snippet) so the stateless
    model judges actual text, not a path.  The output contract matches the
    battery's markdown verdict parser exactly.
    """
    concerns = "\n".join(f"- {name}: {desc}" for name, desc in _AC5_CONCERNS)
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
        "never PASS on an unverified claim.\n\n" + _VERDICT_SCHEMA_BLOCK
    )


def _escalated_row(family: str, file: str, llm_verdict: str, note: str) -> dict[str, Any]:
    return {
        "family": family,
        "file": file,
        "draft_verdict": coerce_to_draft(llm_verdict),
        "llm_verdict": llm_verdict,
        "evidence": "",
        "note": note,
    }


def review_product(item: dict[str, str], *, semantic: bool) -> dict[str, Any]:
    """Draft-review one product form; return ``{family, file, draft_verdict,
    llm_verdict, evidence, note}``.

    ``draft_verdict = coerce_to_draft(llm_verdict)`` always — the RISK ceiling
    is applied here, not optional.  With ``semantic=False`` no model call is
    made at all and the preview row is emitted with ``draft_verdict="RISK"``
    (no human/director verdict on record ⇒ the AC5 ceiling).

    Evidence is mandatory: a recognised verdict whose evidence is empty is
    inadmissible and escalates — fail loud, never a silent risk-free pass.

    A product whose bytes cannot be read (binary despite its suffix, missing,
    or undecodable) is ESCALATEd without a model call: a skip is a visible row
    carrying its reason, never a dropped item and never a pass.
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

    snippet = _read_product_snippet(item.get("path", ""))
    if snippet.reason:
        return _escalated_row(
            family,
            file,
            "ESCALATE",
            f"product content unreadable — not reviewed: {snippet.reason}",
        )

    want_json = _channel_json_capable()
    result = _judge_with_llm(_ac5_prompt(item, snippet.text), want_json=want_json)
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


def _display_path(path: str, base: Path) -> str:
    """Render *path* relative to *base* so a streamed line identifies the form."""
    try:
        return str(Path(path).relative_to(base))
    except ValueError:
        return path


def _suffix_breakdown(excluded: list[dict[str, str]]) -> str:
    counts: dict[str, int] = {}
    for entry in excluded:
        suffix = entry["suffix"] or "(none)"
        counts[suffix] = counts.get(suffix, 0) + 1
    return ", ".join(f"{suffix}={n}" for suffix, n in sorted(counts.items()))


def run_ac5_review(
    delivery_dir: Path,
    *,
    semantic: bool = False,
    emit: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Run the AC5 draft review; return ``{worklist, excluded, verdicts,
    summary, honesty}``.

    ``summary.passed`` is always 0: no draft verdict can ever be PASS.

    ``emit`` receives the human-readable progress narration in run order — the
    header (carrying the worklist size), one line per form as it is judged,
    then SUMMARY — so a caller watching a pipe sees the run grow.  ``None``
    (the default) narrates nothing, keeping this function usable as a library
    call.  The narration is deliberately owned here rather than in ``main``:
    only this function knows the worklist, the per-form order, and the totals.

    ``summary.blocked`` is set when no reviewable product form was found at
    all.  That is the shape of the bug this report used to hide: a 0-item
    worklist printed ``risk=0 escalate=0 passed=0`` and exited 0, i.e. "all
    clean" after reviewing nothing.  A blocked run is not a clean run.
    """
    base = Path(delivery_dir)
    worklist, excluded = _ac5_candidates(base)
    total = len(worklist)
    blocked = "" if total else "no reviewable product form found"

    def say(line: str) -> None:
        if emit is not None:
            emit(line)

    say(f"AC5 director-review DRAFT — {base}")
    say(f"Worklist: {total} product form(s)")
    if excluded:
        say(
            f"EXCLUDED: {len(excluded)} non-reviewable artifact(s) "
            f"[{_suffix_breakdown(excluded)}] — never counted as reviewed"
        )

    verdicts: list[dict[str, Any]] = []
    for index, item in enumerate(worklist, start=1):
        verdict = review_product(item, semantic=semantic)
        verdicts.append(verdict)
        label = _display_path(item["path"], base)
        say(f"  [{verdict['draft_verdict']}] {index}/{total} {label}: {str(verdict['note'])[:100]}")

    risk = sum(1 for v in verdicts if v["draft_verdict"] == "RISK")
    escalate = sum(1 for v in verdicts if v["draft_verdict"] == "ESCALATE")
    passed = sum(1 for v in verdicts if v["draft_verdict"] == "PASS")

    if not semantic:
        channel = "deterministic preview (no --semantic)"
    else:
        channel = "config.llm json_mode" if _channel_json_capable() else "config.llm markdown"

    summary = {
        "total": total,
        "risk": risk,
        "escalate": escalate,
        "passed": passed,
        "excluded": len(excluded),
        "blocked": blocked,
    }
    say(
        f"SUMMARY: risk={risk} escalate={escalate} passed={passed}"
        + (f" BLOCKED={blocked}" if blocked else "")
    )

    return {
        "worklist": worklist,
        "excluded": excluded,
        "verdicts": verdicts,
        "summary": summary,
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
        return _EXIT_NO_WORKLIST

    def _emit(line: str) -> None:
        # --json keeps stdout machine-parseable, so progress goes to stderr;
        # either way flush so `python3 -u` shows the run growing live.
        print(line, file=sys.stderr if args.json else sys.stdout, flush=True)

    report = run_ac5_review(args.delivery_dir, semantic=args.semantic, emit=_emit)
    runs_dir = args.out if args.out is not None else _REPO_ROOT / "validation-runs"
    _persist(report, args.version, runs_dir)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))

    s = report["summary"]
    if s["blocked"]:
        print(
            f"ERROR: BLOCKED — {s['blocked']} under {args.delivery_dir} "
            f"(manifest PROCESSED entries excluded as non-reviewable: "
            f"{s['excluded']}). NOTHING was reviewed; this is NOT a clean run.",
            file=sys.stderr,
        )
        return _EXIT_NO_WORKLIST

    return _EXIT_ESCALATED if s["escalate"] else 0


if __name__ == "__main__":
    sys.exit(main())
