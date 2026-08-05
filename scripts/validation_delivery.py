#!/usr/bin/env python3
"""Package AutoInfo validation artifacts into a delivery zip (fixes #123).

Runs after validation scenarios that declare collect_artifacts. Builds:

    validation-delivery-<timestamp>.zip
    ├── 01-RAW/          # real collected data (cached items, 01-Raw entries)
    ├── 02-PROCESSED/    # produced products (digest/report/tutorial...)
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


async def _run_all_scenarios(scenarios_dir: Path) -> tuple[list[dict], list[dict]]:
    """Run every scenario via the real engine; return (results, artifacts)."""
    from autoinfo.mcp.server import _handle_run_validation_scenario

    results = []
    artifacts = []
    for sc in sorted(scenarios_dir.glob("*.yaml")):
        name = sc.stem
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


def _package(artifacts: list[dict], results: list[dict], out: Path) -> Path:
    """Copy artifact files into a staged dir, write report, zip it."""
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    stage = out / f"validation-delivery-{stamp}"
    raw_dir = stage / "01-RAW"
    proc_dir = stage / "02-PROCESSED"
    raw_dir.mkdir(parents=True, exist_ok=True)
    proc_dir.mkdir(parents=True, exist_ok=True)

    manifest = []
    for a in artifacts:
        src = Path(a["path"])
        if not src.exists():
            continue
        rel = str(src)
        if "collections/" in rel or "01-Raw" in rel:
            dest = raw_dir / src.name
            kind = "RAW"
        else:
            dest = proc_dir / src.name
            kind = "PROCESSED"
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
    report = [
        "# AutoInfo Validation Delivery Report",
        "",
        f"- Date: {stamp}",
        f"- Scenarios: {len(results)} (passed={passed}, failed={failed}, unconfigured={unconf})",
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

    results, artifacts = await _run_all_scenarios(args.scenarios_dir)
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
