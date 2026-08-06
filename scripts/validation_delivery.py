#!/usr/bin/env python3
"""Package AutoInfo validation artifacts into a delivery zip (fixes #123).

Runs after validation scenarios that declare collect_artifacts. Builds:

    validation-delivery-<timestamp>.zip
    ├── 01-RAW/          # real collected data (cached items, 01-Raw entries)
    ├── 02-PROCESSED/    # produced products (digest/report/tutorial...)
    ├── 03-KB/           # KB entries by tier (02-Draft, 03-Wiki)
    ├── validation-report.md  # scenario statuses + artifact manifest
    └── manifest.json    # per-file source/type/size

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


def _package(artifacts: list[dict[str, Any]], results: list[dict[str, Any]], out: Path) -> Path:
    """Copy artifact files into a staged dir, write report, zip it."""
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    stage = out / f"validation-delivery-{stamp}"
    raw_dir = stage / "01-RAW"
    proc_dir = stage / "02-PROCESSED"
    kb_dir = stage / "03-KB"
    raw_dir.mkdir(parents=True, exist_ok=True)
    proc_dir.mkdir(parents=True, exist_ok=True)
    kb_dir.mkdir(parents=True, exist_ok=True)

    manifest = []
    for a in artifacts:
        src = Path(a["path"])
        if not src.exists():
            continue
        rel = src.as_posix()  # normalize separators so '/01-Raw/' checks hold
        if "/01-Raw/" in rel or "collections/" in rel:
            dest = raw_dir / _tier_subpath(src)
            kind = "RAW"
        elif "/02-Draft/" in rel or "/03-Wiki/" in rel:
            dest = kb_dir / _tier_subpath(src)
            kind = "KB"
        else:
            dest = proc_dir / _tier_subpath(src)
            kind = "PROCESSED"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        manifest.append({
            "file": str(dest.relative_to(stage)),
            "kind": kind,
            "source": rel,
            "size": src.stat().st_size,
        })

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
        f"- Artifacts: {len(manifest)}",
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
        report.append(f"- `{m['file']}` ({m['kind']}, {m['size']}B, from {m['source']})")
    report.append("")
    (stage / "validation-report.md").write_text("\n".join(report), encoding="utf-8")
    (stage / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
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
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    zip_path = _package(artifacts, results, out)
    print(f"DELIVERY: {zip_path}")
    print(f"scenarios={len(results)} artifacts={len(artifacts)}")


if __name__ == "__main__":
    asyncio.run(main())
