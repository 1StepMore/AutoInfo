#!/usr/bin/env python3
"""Package AutoInfo validation artifacts into a delivery zip (fixes #123).

Runs after validation scenarios that declare collect_artifacts. Builds:

    validation-delivery-<timestamp>.zip
    ├── 01-RAW/          # real collected data (cached items, 01-Raw entries)
    ├── 02-PROCESSED/    # produced products (digest/report/tutorial...)
    ├── 03-KB/           # KB entries by tier (02-Draft, 03-Wiki)
    ├── 06-REJECTED/     # artifacts that failed delivery gates (E7)
    ├── validation-report.md  # scenario statuses + artifact manifest
    └── manifest.json    # per-file source/type/size + gates/quality/rejected

Usage:
    python3 scripts/validation_delivery.py [--scenarios-dir ...] [--out ...]
"""
from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# E7 (#131): reuse the production D1-D3 orchestration from autoinfo.quality
# UNMODIFIED; aliased because the wrapper below is also named run_delivery_gates.
from autoinfo.quality import run_delivery_gates as _quality_run_delivery_gates  # noqa: PLC0415


def _configured_domains() -> list[str]:
    from autoinfo.config import get_config_path, load_config
    try:
        cfg_path = get_config_path()
        if not cfg_path:
            return []
        cfg = load_config(cfg_path)
        return [d.name for d in cfg.domains]
    except Exception:
        return []


def _requires_llm_key(scenario_path: Path) -> bool:
    """True if the scenario declares an LLM API key in ``requires_env``."""
    import yaml

    try:
        data = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    envs = data.get("requires_env") or []
    return any(
        "LLM" in e or "OPENAI" in e or "OPENROUTER" in e for e in envs
    )


async def _run_all_scenarios(scenarios_dir: Path, skip_llm: bool = False) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Run every scenario via the real engine; return (results, artifacts)."""
    from autoinfo.mcp.server import _handle_run_validation_scenario

    results = []
    artifacts = []
    for sc in sorted(scenarios_dir.glob("*.yaml")):
        name = sc.stem
        if skip_llm and _requires_llm_key(sc):
            results.append({"name": name, "status": "skipped", "summary": {}})
            continue
        try:
            res = await _handle_run_validation_scenario(scenario=name)
        except Exception as e:  # noqa: BLE001
            results.append({"name": name, "status": "error", "detail": str(e)[:200]})
            continue
        data = res.get("data", res)
        results.append({
            "name": name,
            "status": data.get("status"),
            "summary": data.get("summary", {}),
        })
        for a in data.get("artifacts", []):
            artifacts.append(a)
    return results, artifacts


def _tier_subpath(src: Path) -> Path:
    """Path below '<root>/<domain>/' so nested structure survives the copy.

    E.g. ``knowledge/medical-research/01-Raw/crispr/2026-08-05-x.md`` maps to
    ``01-Raw/crispr/2026-08-05-x.md``; shallow paths fall back to the bare name.
    """
    parts = src.parts
    return Path(*parts[2:]) if len(parts) >= 3 else Path(src.name)


def _bucket(path: Path) -> str:
    """Classify an artifact path into ``RAW`` / ``KB`` / ``PROCESSED``.

    ``/01-Raw/`` or ``collections/`` -> RAW; ``/02-Draft/`` or ``/03-Wiki/``
    -> KB; everything else -> PROCESSED.
    """
    rel = path.as_posix()  # normalize separators so '/01-Raw/' checks hold
    if "/01-Raw/" in rel or "collections/" in rel:
        return "RAW"
    if "/02-Draft/" in rel or "/03-Wiki/" in rel:
        return "KB"
    return "PROCESSED"


# ---------------------------------------------------------------------------
# E7 (#131): per-artifact authenticity pre-check + D1-D3 delivery gates
# ---------------------------------------------------------------------------

# Text formats whose content can be structurally inspected as a product.
_INSPECTABLE_FORMATS: dict[str, str] = {
    ".md": "markdown",
    ".html": "html",
    ".htm": "html",
    ".json": "json",
    ".jsonl": "json",
}

# Keys that mark a JSON dict as a structured source entry.
_ENTRY_KEYS = frozenset(
    {"source_url", "source_type", "source_platform", "title", "entry_id", "uuid"}
)

# Canonical D1 sections -> markdown heading aliases.
_SECTION_HEADING_ALIASES: dict[str, tuple[str, ...]] = {
    "key_findings": ("key findings", "key_findings", "key-findings", "key points"),
    "summary": ("summary", "executive summary", "overview"),
    "recommendations": ("recommendations", "conclusion", "next steps"),
}

# Canonical D1 sections -> JSON top-level / llm_synthesis key aliases.
_SECTION_SOURCE_KEYS: dict[str, tuple[str, ...]] = {
    "key_findings": ("key_findings", "key-findings", "findings"),
    "summary": ("summary", "executive_summary", "executive-summary"),
    "recommendations": ("recommendations", "next_steps", "conclusion"),
}


def _parse_json_payload(file_path: Path) -> Any:
    """Load JSON / JSONL content; returns ``None`` when unparseable."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001 — binary or unreadable file
        return None
    if file_path.suffix.lower() == ".jsonl":
        objs: list[Any] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                objs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return objs or None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _parse_frontmatter(file_path: Path) -> dict[str, Any]:
    """Extract YAML frontmatter (``---``-delimited) from a markdown file."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return {}
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    try:
        import yaml

        data = yaml.safe_load(text[3:end])
    except Exception:  # noqa: BLE001
        return {}
    return data if isinstance(data, dict) else {}


def _json_entries(parsed: Any) -> list[dict[str, Any]]:
    """Extract structured source-entry dicts from a parsed JSON payload."""
    if isinstance(parsed, list):
        return [e for e in parsed if isinstance(e, dict) and (_ENTRY_KEYS & e.keys())]
    if not isinstance(parsed, dict):
        return []
    for key in ("entries", "items", "results", "articles", "payload"):
        val = parsed.get(key)
        if isinstance(val, list):
            hit = [e for e in val if isinstance(e, dict) and (_ENTRY_KEYS & e.keys())]
            if hit:
                return hit
    if _ENTRY_KEYS & parsed.keys():
        return [parsed]
    return []


def _sections_from_headings(text: str) -> dict[str, str]:
    """Map canonical D1 sections to non-empty heading content (md/html)."""
    import re

    found: dict[str, str] = {}
    heading_re = re.compile(r"<h([1-6])[^>]*>(.*?)</h\1>", re.IGNORECASE | re.DOTALL)
    if heading_re.search(text):
        # HTML: split on headings like markdown for a uniform pass below
        lines: list[str] = []
        for m in heading_re.finditer(text):
            lines.append(
                "\n" + "#" * int(m.group(1)) + " "
                + re.sub(r"<[^>]+>", "", m.group(2)).strip()
            )
        text = "\n".join(lines)
    blocks: list[tuple[str, list[str]]] = []
    cur_heading: str | None = None
    cur_lines: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^#{1,6}\s+(.+?)\s*$", line.strip())
        if m:
            if cur_heading:
                blocks.append((cur_heading, cur_lines))
            cur_heading = m.group(1).lower().replace("*", "").replace("`", "").strip()
            cur_lines = []
        elif cur_heading:
            cur_lines.append(line.strip())
    if cur_heading:
        blocks.append((cur_heading, cur_lines))
    for canonical, aliases in _SECTION_HEADING_ALIASES.items():
        for heading, lines in blocks:
            if heading in aliases and canonical not in found:
                content = " ".join(line for line in lines if line)
                found[canonical] = content or "present"
    return found


def _section_value(parsed: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    """First non-empty value for *aliases* at top level or in llm_synthesis."""
    llm_synthesis = parsed.get("llm_synthesis")
    llm_synthesis = llm_synthesis if isinstance(llm_synthesis, dict) else {}
    for scope in (parsed, llm_synthesis):
        for key in aliases:
            val = scope.get(key)
            if val not in (None, "", [], {}):
                return val
    return None


def _build_product_output(file_path: Path, bucket: str) -> dict[str, Any]:
    """Adapt an artifact file into the ``product_output`` dict quality.py expects.

    RAW/KB content and non-inspectable binary formats run with
    ``product_type="RAW"`` so the D gates trivially skip (that content was
    already gated at pipeline time). PROCESSED text products (md/html/json)
    get the real D1-D3 treatment with sections derived from headings/keys.
    """
    suffix = file_path.suffix.lower()
    fmt = _INSPECTABLE_FORMATS.get(suffix)
    product_type = "RAW" if (bucket in ("RAW", "KB") or fmt is None) else "PROCESSED"
    entries: list[dict[str, Any]] = []
    sections: dict[str, Any] = {}
    body: Any = ""
    if fmt in ("markdown", "html"):
        try:
            body = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            body = ""
        sections = _sections_from_headings(str(body))
    elif fmt == "json":
        try:
            body = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            body = ""
        parsed = _parse_json_payload(file_path)
        entries = _json_entries(parsed)
        if isinstance(parsed, dict):
            sections = {
                "key_findings": _section_value(parsed, _SECTION_SOURCE_KEYS["key_findings"]),
                "summary": _section_value(parsed, _SECTION_SOURCE_KEYS["summary"]),
                "recommendations": _section_value(parsed, _SECTION_SOURCE_KEYS["recommendations"]),
            }
    key_findings = sections.get("key_findings")
    summary = sections.get("summary")
    recommendations = sections.get("recommendations")
    return {
        "product_type": product_type,
        "format": fmt or "markdown",
        "body": body,
        "key_findings": key_findings if key_findings not in (None, "") else [],
        "summary": summary if summary not in (None, []) else "",
        "recommendations": recommendations if recommendations not in (None, "") else [],
        "entries": entries,
    }


def check_authenticity(file_path: Path) -> dict[str, Any]:
    """Per-artifact authenticity pre-check (field presence only — Oracle R3).

    md/html content files are text products, not structured source entries:
    they pass as N/A (informational frontmatter fields are reported when
    present but never fail). JSON/JSONL payloads are checked for complete
    source provenance — every embedded entry must carry non-empty
    ``source_url`` (not an ``example.com`` placeholder), ``source_type`` and
    ``source_platform``. Payloads without structured entries have nothing to
    verify and pass.

    Returns ``{"authenticity": "pass"|"fail", "reason": str}``.
    """
    suffix = file_path.suffix.lower()
    if suffix in (".md", ".html", ".htm"):
        fm = _parse_frontmatter(file_path)
        reason = "N/A: text content file — not a structured source entry"
        if fm:
            reason += f" (frontmatter fields: {', '.join(sorted(fm)[:6])})"
        return {"authenticity": "pass", "reason": reason}
    entries = _json_entries(_parse_json_payload(file_path))
    if not entries:
        return {
            "authenticity": "pass",
            "reason": "no structured source entries found in payload — nothing to verify",
        }
    problems: list[str] = []
    for i, entry in enumerate(entries):
        url = entry.get("source_url", "")
        if not isinstance(url, str) or not url.strip():
            problems.append(f"entry[{i}] missing source_url")
        elif "example.com" in url:
            problems.append(f"entry[{i}] placeholder source_url: {url}")
        for field in ("source_type", "source_platform"):
            val = entry.get(field, "")
            if not isinstance(val, str) or not val.strip():
                problems.append(f"entry[{i}] missing {field}")
    if problems:
        shown = "; ".join(problems[:6])
        if len(problems) > 6:
            shown += " ..."
        return {"authenticity": "fail", "reason": shown}
    n = len(entries)
    return {
        "authenticity": "pass",
        "reason": f"{n} structured entr{'y' if n == 1 else 'ies'} with complete source fields",
    }


def _serialize_gate_result(result: Any) -> dict[str, Any]:
    """Turn a quality.QualityResult into a JSON-serializable dict."""
    if result is None:
        return {
            "gate": "unknown",
            "passed": True,
            "score": 0.0,
            "flagged": False,
            "details": {"skipped": True, "reason": "gate did not run"},
        }
    return {
        "gate": getattr(result, "gate_name", ""),
        "passed": bool(getattr(result, "passed", True)),
        "score": float(getattr(result, "score", 0.0) or 0.0),
        "flagged": bool(getattr(result, "flagged", False)),
        "details": dict(getattr(result, "details", {}) or {}),
    }


def run_delivery_gates(file_path: Path, bucket: str) -> dict[str, Any]:
    """Run D1-D3 delivery gates + authenticity pre-check for one artifact.

    Reuses :func:`autoinfo.quality.run_delivery_gates` unmodified — the file
    is adapted into the ``product_output`` dict it expects. Returns
    ``{"gates": {"D1": ..., "D2": ..., "D3": ..., "authenticity": ...},
    "quality": "PASS"|"FAIL"}``; ``quality`` is PASS only when every gate
    passes.
    """
    authenticity = check_authenticity(file_path)
    product_output = _build_product_output(file_path, bucket)
    quality_results = _quality_run_delivery_gates(product_output, {})
    gates = {
        "D1": _serialize_gate_result(quality_results.get("D1-ProductCompleteness")),
        "D2": _serialize_gate_result(quality_results.get("D2-FormatIntegrity")),
        "D3": _serialize_gate_result(quality_results.get("D3-Freshness")),
        "authenticity": authenticity,
    }
    all_pass = (
        gates["D1"]["passed"]
        and gates["D2"]["passed"]
        and gates["D3"]["passed"]
        and gates["authenticity"]["authenticity"] == "pass"
    )
    return {"gates": gates, "quality": "PASS" if all_pass else "FAIL"}


def _failure_reason(gates: dict[str, Any]) -> str:
    """Human-readable summary of why an artifact failed the gates."""
    reasons: list[str] = []
    for name in ("D1", "D2", "D3"):
        g = gates.get(name) or {}
        if not g.get("passed", True):
            details = g.get("details") or {}
            why = details.get("error") or details.get("reason") or f"gate {name} failed"
            reasons.append(f"{name}: {why}")
    auth = gates.get("authenticity") or {}
    if auth.get("authenticity") != "pass":
        reasons.append(f"authenticity: {auth.get('reason', 'failed')}")
    return "; ".join(reasons) or "quality gate failure"


def _package(artifacts: list[dict[str, Any]], results: list[dict[str, Any]], out: Path) -> Path:
    """Copy artifact files into a staged dir, write report, zip it.

    E7 (#131): every artifact is checked with :func:`run_delivery_gates`
    (D1-D3 + authenticity). Failed artifacts are moved to ``06-REJECTED/``
    and listed (with reasons) in the manifest's ``rejected`` summary instead
    of being delivered.
    """
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    stage = out / f"validation-delivery-{stamp}"
    raw_dir = stage / "01-RAW"
    proc_dir = stage / "02-PROCESSED"
    kb_dir = stage / "03-KB"
    rej_dir = stage / "06-REJECTED"
    for d in (raw_dir, proc_dir, kb_dir, rej_dir):
        d.mkdir(parents=True, exist_ok=True)

    bucket_dirs = {"RAW": raw_dir, "KB": kb_dir, "PROCESSED": proc_dir}
    manifest = []
    rejected = []
    for a in artifacts:
        src = Path(a["path"])
        if not src.exists():
            continue
        rel = src.as_posix()
        bucket = _bucket(src)
        dest = bucket_dirs[bucket] / _tier_subpath(src)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        try:
            gate_eval = run_delivery_gates(src, bucket)
        except Exception as exc:  # noqa: BLE001 — one bad file must never break delivery
            gate_eval = {
                "gates": {
                    "D1": {"passed": False, "details": {"error": f"gate evaluation error: {exc}"}},
                    "D2": {"passed": True, "details": {}},
                    "D3": {"passed": True, "details": {}},
                    "authenticity": {"authenticity": "fail", "reason": f"check error: {exc}"},
                },
                "quality": "FAIL",
            }
        gates = gate_eval.get("gates", {})
        quality = gate_eval.get("quality", "FAIL")
        entry = {
            "file": str(dest.relative_to(stage)),
            "kind": bucket,
            "source": rel,
            "size": src.stat().st_size,
            "gates": gates,
            "quality": quality,
        }
        if quality == "FAIL":
            rej_dest = rej_dir / _tier_subpath(src)
            rej_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(dest, rej_dest)
            rejected.append({
                "file": str(rej_dest.relative_to(stage)),
                "source": rel,
                "reason": _failure_reason(gates),
            })
        else:
            manifest.append(entry)

    # validation report
    passed = sum(1 for r in results if r["status"] == "passed")
    failed = sum(1 for r in results if r["status"] == "failed")
    unconf = sum(1 for r in results if r["status"] == "unconfigured")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    report = [
        "# AutoInfo Validation Delivery Report",
        "",
        f"- Date: {stamp}",
        f"- Scenarios: {len(results)} (passed={passed}, failed={failed}, unconfigured={unconf}, skipped={skipped})",
        f"- Artifacts: {len(manifest)} delivered, {len(rejected)} rejected",
        f"- Domains: {', '.join(_configured_domains()) or '(none)'}",
        "",
        "## Scenario Status",
        "",
        "| Scenario | Status | Summary |",
        "|----------|--------|---------|",
    ]
    for r in sorted(results, key=lambda x: x["name"]):
        report.append(f"| {r['name']} | {r['status']} | {r.get('summary', {})} |")
    report.append("")
    report.append("## Artifacts")
    report.append("")
    for m in manifest:
        report.append(
            f"- `{m['file']}` ({m['kind']}, {m['size']}B, "
            f"{m['quality']}, from {m['source']})"
        )
    if rejected:
        report.append("")
        report.append("## Rejected Artifacts (failed delivery gates)")
        report.append("")
        for rj in rejected:
            report.append(f"- `{rj['file']}` — {rj['reason']} (from {rj['source']})")
    report.append("")
    (stage / "validation-report.md").write_text("\n".join(report), encoding="utf-8")
    (stage / "manifest.json").write_text(
        json.dumps(
            {"files": manifest, "rejected": rejected},
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    # zip it (python zipfile — user prefers zip, no tar)
    zip_path = out / f"{stage.name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in stage.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(stage))
    shutil.rmtree(stage)
    return zip_path


async def main() -> None:
    parser = argparse.ArgumentParser(description="Package validation artifacts")
    parser.add_argument("--scenarios-dir", type=Path,
                        default=Path("src/autoinfo/mcp/scenarios"))
    parser.add_argument("--out", type=Path, default=Path("validation-deliveries"))
    parser.add_argument("--skip-llm-scenarios", action="store_true",
                        help="Skip scenarios that require an LLM key (faster smoke run)")
    args = parser.parse_args()

    # Load LLM key from Hermes env (mirrors other validation scripts) so the
    # delivery run can execute LLM-gated scenarios without shell exports.
    import os
    key = ""
    env_path = Path(os.path.expanduser("~/.hermes/.env"))
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("OPENCODE_GO_API_KEY"):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    if key:
        os.environ["OPENAI_API_KEY"] = key
        os.environ["AUTOINFO_LLM_API_KEY"] = key

    results, artifacts = await _run_all_scenarios(
        args.scenarios_dir, skip_llm=args.skip_llm_scenarios
    )
    if not artifacts:
        print("No artifacts collected (scenarios produced no data files).", file=sys.stderr)
        # still write a report-only zip so the user sees what ran

    # #129 P0-3: persist results for cross-run regression; best-effort,
    # never blocks delivery even if persistence fails.
    try:
        from autoinfo.mcp.validation import save_scenario_results
        save_scenario_results(results)
    except Exception as e:  # noqa: BLE001
        print(f"WARN: could not persist scenario results: {e}", file=sys.stderr)

    # #129 P1-4: fixed archive location validation-deliveries/<date>/.
    out = args.out
    dated_out = out / datetime.datetime.now().strftime("%Y-%m-%d")
    dated_out.mkdir(parents=True, exist_ok=True)
    zip_path = _package(artifacts, results, dated_out)
    print(f"DELIVERY: {zip_path}")
    print(f"scenarios={len(results)} artifacts={len(artifacts)}")


if __name__ == "__main__":
    asyncio.run(main())
