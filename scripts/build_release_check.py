#!/usr/bin/env python3
"""Build/release surface validation (T-S-11) — the methodology's acid test.

Run from the project root::

    python3 scripts/build_release_check.py            # validate current install
    python3 scripts/build_release_check.py --install  # run ``pip install -e .`` first

The acid test the development methodology names is: *build and test from the
README/AGENTS instructions*.  This check turns that into a machine assertion
over the **build/release surface**:

* ``pip install -e .`` is importable — ``import autoinfo`` resolves to a file
  inside this repo (an editable/source install, not a stale wheel);
* the installed distribution version equals ``autoinfo._version.__version__``
  (no release-please/manifest drift);
* the ``autoinfo`` console-script entry point is registered and points at
  ``autoinfo.cli:app``;
* ``pyproject.toml`` is structurally sound (name, requires-python, scripts,
  dynamic version source, src-layout package discovery);
* the release-please manifest version matches the source version and the
  release config + CHANGELOG are present.

Counts are always derived from the live files — never hard-coded.  Exit 0 only
when every check passes.  ``--install`` performs a real editable reinstall
(the flag the task names) before asserting.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata as metadata
import json
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
MANIFEST = ROOT / ".release-please-manifest.json"
RELEASE_CONFIG = ROOT / "release-please-config.json"
CHANGELOG = ROOT / "CHANGELOG.md"


class Check:
    """One named build/release assertion."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.ok = True
        self.detail = ""

    def pass_(self, detail: str = "") -> "Check":
        self.ok = True
        self.detail = detail
        return self

    def fail(self, detail: str) -> "Check":
        self.ok = False
        self.detail = detail
        return self


def _import_check() -> tuple[Check, str | None, Path | None]:
    check = Check("import autoinfo (editable source install)")
    try:
        import autoinfo
    except Exception as exc:  # pragma: no cover - environment failure path
        return check.fail(f"import raised {type(exc).__name__}: {exc}"), None, None
    file = Path(autoinfo.__file__).resolve()
    if ROOT.resolve() not in file.parents:
        return (
            check.fail(
                f"resolved to {file}, outside the repo root {ROOT} — not an "
                "editable source install (run: pip install -e .)"
            ),
            None,
            file,
        )
    return check.pass_(f"{file}"), autoinfo.__version__, file


def _metadata_checks(source_version: str | None, imported_file: Path | None) -> list[Check]:
    checks: list[Check] = []
    dist_check = Check("installed distribution metadata present")
    try:
        dist = metadata.distribution("autoinfo")
    except metadata.PackageNotFoundError:
        checks.append(dist_check.fail("autoinfo distribution is not installed"))
        return checks
    checks.append(dist_check.pass_(f"version {dist.version}"))

    version_check = Check("installed version == autoinfo._version.__version__")
    if source_version is None:
        checks.append(version_check.fail("source version unavailable (import failed)"))
    elif dist.version != source_version:
        checks.append(
            version_check.fail(
                f"installed {dist.version} != source {source_version} — run "
                "'pip install -e .' to refresh the editable install"
            )
        )
    else:
        checks.append(version_check.pass_(dist.version))

    edit_check = Check("editable/source install (repo-resolved import)")
    raw = dist.read_text("direct_url.json")
    if raw:
        try:
            info = json.loads(raw)
        except json.JSONDecodeError:
            info = {}
        if info.get("dir_info", {}).get("editable") is True:
            checks.append(edit_check.pass_(info.get("url", "")))
        else:
            checks.append(edit_check.fail(f"direct_url.json is not editable: {raw}"))
    elif imported_file is not None and ROOT.resolve() in imported_file.parents:
        checks.append(
            edit_check.pass_(
                "source-resolved import from the repo (no direct_url.json in the "
                "discovered distribution)"
            )
        )
    else:
        checks.append(
            edit_check.fail("distribution is not an editable install (no direct_url.json)")
        )

    entry_check = Check("console script autoinfo -> autoinfo.cli:app")
    eps = [ep for ep in metadata.entry_points(group="console_scripts") if ep.name == "autoinfo"]
    if not eps:
        checks.append(entry_check.fail("no 'autoinfo' console-script entry point"))
    elif any(ep.value == "autoinfo.cli:app" for ep in eps):
        checks.append(entry_check.pass_(eps[0].value))
    else:
        checks.append(
            entry_check.fail(f"entry point points at {eps[0].value!r}, expected 'autoinfo.cli:app'")
        )
    return checks


def _pyproject_checks() -> tuple[list[Check], dict[str, Any] | None]:
    checks: list[Check] = []
    if not PYPROJECT.is_file():
        return [Check("pyproject.toml present").fail("file missing")], None
    checks.append(Check("pyproject.toml present").pass_(str(PYPROJECT)))
    try:
        data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        checks.append(Check("pyproject.toml parses").fail(str(exc)))
        return checks, None
    checks.append(Check("pyproject.toml parses").pass_())

    project = data.get("project", {})
    name_check = Check("project.name == 'autoinfo'")
    if project.get("name") == "autoinfo":
        checks.append(name_check.pass_())
    else:
        checks.append(name_check.fail(f"got {project.get('name')!r}"))

    py_check = Check("requires-python declared")
    if isinstance(project.get("requires-python"), str) and project["requires-python"]:
        checks.append(py_check.pass_(project["requires-python"]))
    else:
        checks.append(py_check.fail("missing requires-python"))

    scripts = project.get("scripts", {})
    script_check = Check("project.scripts.autoinfo -> autoinfo.cli:app")
    if scripts.get("autoinfo") == "autoinfo.cli:app":
        checks.append(script_check.pass_())
    else:
        checks.append(script_check.fail(f"got {scripts.get('autoinfo')!r}"))

    dynamic_check = Check("dynamic version <- autoinfo._version.__version__")
    dynamic = project.get("dynamic", [])
    version_attr = data.get("tool", {}).get("setuptools", {}).get("dynamic", {}).get("version", {})
    expected_attr = "autoinfo._version.__version__"
    if "version" in dynamic and version_attr.get("attr") == expected_attr:
        checks.append(dynamic_check.pass_(expected_attr))
    else:
        checks.append(
            dynamic_check.fail(
                f"dynamic={dynamic!r} version_attr={version_attr!r}, "
                f"expected attr {expected_attr!r}"
            )
        )

    layout_check = Check("src-layout package discovery")
    where = (
        data.get("tool", {})
        .get("setuptools", {})
        .get("packages", {})
        .get("find", {})
        .get("where", [])
    )
    if where == ["src"]:
        checks.append(layout_check.pass_("where=['src']"))
    else:
        checks.append(layout_check.fail(f"packages.find.where={where!r}, expected ['src']"))

    build_check = Check("build-system requires setuptools")
    build_reqs = data.get("build-system", {}).get("requires", [])
    if any("setuptools" in req for req in build_reqs):
        checks.append(build_check.pass_(", ".join(build_reqs)))
    else:
        checks.append(build_check.fail(f"build requires={build_reqs!r}"))
    return checks, data


def _release_checks(source_version: str | None) -> list[Check]:
    checks: list[Check] = []

    manifest_check = Check("release-please manifest present")
    if not MANIFEST.is_file():
        checks.append(manifest_check.fail(f"{MANIFEST.name} missing"))
    else:
        checks.append(manifest_check.pass_(MANIFEST.name))
        try:
            manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            checks.append(Check("manifest parses").fail(str(exc)))
        else:
            manifest_version = manifest.get(".")
            sync_check = Check("manifest version == source version")
            if source_version is not None and manifest_version == source_version:
                checks.append(sync_check.pass_(str(manifest_version)))
            else:
                checks.append(
                    sync_check.fail(f"manifest {manifest_version!r} != source {source_version!r}")
                )

    config_check = Check("release-please config present + valid")
    if not RELEASE_CONFIG.is_file():
        checks.append(config_check.fail(f"{RELEASE_CONFIG.name} missing"))
    else:
        try:
            config = json.loads(RELEASE_CONFIG.read_text(encoding="utf-8"))
            packages = config.get("packages", {})
            if "." in packages:
                checks.append(config_check.pass_(f"packages={sorted(packages)}"))
            else:
                checks.append(config_check.fail("packages['.'] entry missing"))
        except json.JSONDecodeError as exc:
            checks.append(config_check.fail(str(exc)))

    changelog_check = Check("CHANGELOG.md present")
    if CHANGELOG.is_file() and CHANGELOG.stat().st_size > 0:
        checks.append(changelog_check.pass_(f"{CHANGELOG.stat().st_size} bytes"))
    else:
        checks.append(changelog_check.fail("CHANGELOG.md missing or empty"))
    return checks


def _cli_checks() -> list[Check]:
    check = Check("autoinfo.cli imports and registers command groups")
    try:
        cli = importlib.import_module("autoinfo.cli")
        app = getattr(cli, "app")
        groups = getattr(app, "registered_groups", [])
        if groups:
            return [check.pass_(f"{len(groups)} registered groups")]
        return [check.fail("no registered command groups")]
    except Exception as exc:  # pragma: no cover - environment failure path
        return [check.fail(f"{type(exc).__name__}: {exc}")]


def _run_editable_install() -> Check:
    """Actually run ``pip install -e .`` (the named acid test).

    Tries the standard invocation first (the CI path), then escalates through
    PEP 668 (externally-managed) and offline build-isolation fallbacks so the
    check is runnable on a developer box as well as in CI.  The first
    successful attempt wins; all-fail surfaces the last real error.
    """
    check = Check("pip install -e .")
    base = [sys.executable, "-m", "pip", "install", "-e", ".", "--no-deps"]
    attempts = (
        [],
        ["--break-system-packages"],
        ["--break-system-packages", "--no-build-isolation"],
        ["--no-build-isolation"],
    )
    last_error = "no attempt ran"
    for extra in attempts:
        proc = subprocess.run(base + extra, cwd=ROOT, capture_output=True, text=True, timeout=600)
        if proc.returncode == 0:
            return check.pass_(" ".join(base + extra))
        combined = (proc.stderr or proc.stdout).strip()
        last_error = combined.splitlines()[-1] if combined else f"exit {proc.returncode}"
    return check.fail(f"pip install -e . failed: {last_error}")


def run_checks(install: bool = False) -> list[Check]:
    checks: list[Check] = []
    if install:
        checks.append(_run_editable_install())

    import_check, source_version, _file = _import_check()
    checks.append(import_check)
    checks.extend(_metadata_checks(source_version, _file))
    py_checks, _data = _pyproject_checks()
    checks.extend(py_checks)
    checks.extend(_release_checks(source_version))
    checks.extend(_cli_checks())
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build/release surface check (T-S-11).")
    parser.add_argument(
        "--install",
        action="store_true",
        help="Run 'pip install -e .' before asserting (the methodology acid test).",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON results.")
    args = parser.parse_args(argv)

    checks = run_checks(install=args.install)
    failed = [c for c in checks if not c.ok]

    if args.json:
        print(
            json.dumps(
                {
                    "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail} for c in checks],
                    "passed": len(checks) - len(failed),
                    "total": len(checks),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for check in checks:
            mark = "ok" if check.ok else "FAIL"
            print(f"  [{mark}] {check.name}" + (f" — {check.detail}" if check.detail else ""))
        print(f"build/release checks passed: {len(checks) - len(failed)}/{len(checks)}")

    if failed:
        print("BUILD_RELEASE_FAIL")
        return 1
    print("BUILD_RELEASE_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
