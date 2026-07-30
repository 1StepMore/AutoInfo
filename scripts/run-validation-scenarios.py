#!/usr/bin/env python3
"""
run-validation-scenarios.py — YAML-based validation scenario runner for AutoInfo.

Reads all YAML scenario files from the scenarios directory, executes each step,
validates expected outcomes (exit code, stdout patterns, artifacts), and reports
pass/fail per scenario.

Usage:
    python3 scripts/run-validation-scenarios.py [--dry-run] [--verbose]
    python3 scripts/run-validation-scenarios.py --scenario init-project
    python3 scripts/run-validation-scenarios.py --list
    python3 scripts/run-validation-scenarios.py --help
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from string import Template
from typing import Any, Optional

# ---------------------------------------------------------------------------
# YAML support (try pyyaml first, fall back to built-in warning)
# ---------------------------------------------------------------------------
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


# ---------------------------------------------------------------------------
# ANSI colour helpers
# ---------------------------------------------------------------------------
class Colour:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    DIM = "\033[2m"


def _green(s: str) -> str:  return f"{Colour.GREEN}{s}{Colour.RESET}"
def _red(s: str) -> str:    return f"{Colour.RED}{s}{Colour.RESET}"
def _yellow(s: str) -> str: return f"{Colour.YELLOW}{s}{Colour.RESET}"
def _bold(s: str) -> str:   return f"{Colour.BOLD}{s}{Colour.RESET}"
def _cyan(s: str) -> str:   return f"{Colour.CYAN}{s}{Colour.RESET}"
def _dim(s: str) -> str:    return f"{Colour.DIM}{s}{Colour.RESET}"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class StepResult:
    """Single step execution result."""
    name: str
    passed: bool
    exit_code: int
    expected_exit_code: int
    checks: list[tuple[str, bool, str]] = field(default_factory=list)
    # (description, passed, detail)
    stdout: str = ""
    stderr: str = ""


@dataclass
class ScenarioResult:
    """Overall scenario execution result."""
    name: str
    file: str
    passed: bool
    steps_total: int
    steps_passed: int
    step_results: list[StepResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Variable substitution
# ---------------------------------------------------------------------------
def _substitute_vars(text: str, variables: dict[str, str]) -> str:
    """Substitute ${VAR} patterns using Template-safe substitution."""
    if not variables or "${" not in text:
        return text
    # Use safe_substitute to leave unknown vars untouched
    return Template(text).safe_substitute(variables)


def _expand_env(s: str) -> str:
    """Expand environment variables and tildes in a string."""
    s = os.path.expanduser(s)
    # Simple ${ENV} and $ENV expansion
    s = re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), m.group(0)), s)
    s = re.sub(r"\$(\w+)", lambda m: os.environ.get(m.group(1), m.group(0)), s)
    return s


# ---------------------------------------------------------------------------
# Step execution
# ---------------------------------------------------------------------------
def _execute_step(
    step: dict,
    variables: dict[str, str],
    scenario_dir: Path,
    dry_run: bool,
    verbose: bool,
) -> StepResult:
    """Execute a single scenario step and return the result."""
    name = step.get("name", "unnamed step")
    command_raw = step.get("command", "").strip()
    setup_raw = step.get("setup", "").strip()
    expected = step.get("expected", {})
    post_checks = step.get("post_checks", [])
    artifacts = expected.get("artifacts", [])

    expected_exit_code = expected.get("exit_code", 0)
    stdout_contains = expected.get("stdout_contains", [])
    stdout_not_contains = expected.get("stdout_not_contains", [])

    result = StepResult(
        name=name,
        passed=False,
        exit_code=-1,
        expected_exit_code=expected_exit_code,
    )

    # Substitute variables
    command = _substitute_vars(command_raw, variables)
    setup_cmd = _substitute_vars(setup_raw, variables)
    stdout_contains = [_substitute_vars(s, variables) for s in stdout_contains]
    stdout_not_contains = [_substitute_vars(s, variables) for s in stdout_not_contains]
    artifacts = [_expand_env(_substitute_vars(a, variables)) for a in artifacts]

    if dry_run:
        print(f"  {_cyan('[DRY-RUN]')} {_bold(name)}")
        if setup_cmd:
            print(f"    {_dim('setup')}: {setup_cmd[:120]}")
        print(f"    {_dim('command')}: {command[:200]}")
        return result

    # Execute setup
    if setup_cmd:
        if verbose:
            print(f"    {_dim('setup')}: {setup_cmd[:120]}")
        subprocess.run(
            setup_cmd, shell=True, executable="/bin/bash",
            capture_output=True,
            timeout=120,
        )

    # Execute command
    if verbose:
        print(f"    {_dim('run')}: {command[:200]}")

    proc = subprocess.run(
        command,
        shell=True,
        executable="/bin/bash",
        capture_output=True,
        text=True,
        timeout=300,
        cwd=scenario_dir,
    )

    combined_output = proc.stdout + proc.stderr
    result.exit_code = proc.returncode
    result.stdout = proc.stdout[:8000]
    result.stderr = proc.stderr[:8000]

    checks_passed = 0
    checks_total = 0

    # Check exit code
    checks_total += 1
    if proc.returncode == expected_exit_code:
        result.checks.append((f"exit_code {expected_exit_code}", True, f"got {proc.returncode}"))
        checks_passed += 1
    else:
        result.checks.append((f"exit_code {expected_exit_code}", False,
                              f"expected {expected_exit_code}, got {proc.returncode}"))

    # Check stdout_contains
    for pattern in stdout_contains:
        checks_total += 1
        if pattern in combined_output:
            result.checks.append((f"stdout contains '{pattern}'", True, ""))
            checks_passed += 1
        else:
            result.checks.append((f"stdout contains '{pattern}'", False, "not found"))
            if verbose:
                print(f"      {_yellow('[MISSING]')} '{pattern}'")

    # Check stdout_not_contains
    for pattern in stdout_not_contains:
        checks_total += 1
        if pattern in combined_output:
            result.checks.append((f"stdout NOT contains '{pattern}'", False, "found"))
        else:
            result.checks.append((f"stdout NOT contains '{pattern}'", True, ""))
            checks_passed += 1

    # Check artifacts
    for artifact in artifacts:
        checks_total += 1
        path = Path(artifact) if Path(artifact).is_absolute() else Path.home() / artifact if artifact.startswith("~") else Path(artifact)
        if path.exists():
            result.checks.append((f"artifact '{artifact}' exists", True, ""))
            checks_passed += 1
        else:
            result.checks.append((f"artifact '{artifact}' exists", False, "missing"))

    # Execute post_checks
    for i, check in enumerate(post_checks):
        check_desc = check.get("description", f"post-check-{i + 1}")
        check_cmd = _substitute_vars(check.get("command", ""), variables)
        expected_stdout = check.get("expected_stdout", [])
        checks_total += 1

        if check_cmd:
            pc = subprocess.run(
                check_cmd, shell=True, executable="/bin/bash",
                capture_output=True, text=True, timeout=60,
                cwd=scenario_dir,
            )
            pc_out = pc.stdout + pc.stderr
            if expected_stdout:
                all_found = all(exp in pc_out for exp in expected_stdout)
                if all_found:
                    result.checks.append((check_desc, True, ""))
                    checks_passed += 1
                else:
                    result.checks.append((check_desc, False, f"expected patterns not found; got: {pc_out[:200]}"))
            else:
                result.checks.append((check_desc, pc.returncode == 0, ""))
                if pc.returncode == 0:
                    checks_passed += 1
        else:
            result.checks.append((check_desc, True, "no-op"))

    result.passed = (checks_passed == checks_total and checks_total > 0)
    return result


# ---------------------------------------------------------------------------
# Scenario loading
# ---------------------------------------------------------------------------
def _load_yaml(path: Path) -> Optional[dict]:
    """Load a YAML file, returning the parsed dict or None on failure."""
    if HAS_YAML:
        with open(path, "r") as f:
            return yaml.safe_load(f)
    else:
        print(f"{_red('ERROR')}: PyYAML not installed. Run: pip install pyyaml")
        return None


def _load_scenarios(scenario_dir: Path, scenario_filter: Optional[str] = None) -> list[tuple[Path, dict]]:
    """Load all YAML scenario files from the directory."""
    yaml_files = sorted(glob.glob(str(scenario_dir / "*.yaml")))
    yaml_files += sorted(glob.glob(str(scenario_dir / "*.yml")))

    scenarios: list[tuple[Path, dict]] = []
    for fpath in yaml_files:
        if scenario_filter and scenario_filter not in os.path.basename(fpath):
            continue
        data = _load_yaml(Path(fpath))
        if data:
            scenarios.append((Path(fpath), data))
    return scenarios


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------
def run_scenarios(
    scenario_dir: Path,
    dry_run: bool = False,
    verbose: bool = False,
    scenario_filter: Optional[str] = None,
) -> list[ScenarioResult]:
    """Run all scenarios and return results."""
    scenarios = _load_scenarios(scenario_dir, scenario_filter)

    if not scenarios:
        print(f"{_yellow('WARNING')}: No scenario YAML files found in {scenario_dir}")
        return []

    results: list[ScenarioResult] = []

    for fpath, data in scenarios:
        name = data.get("name", fpath.stem)
        description = data.get("description", "").strip()
        variables = data.get("variables", {})
        steps_data = data.get("steps", [])
        tags = data.get("tags", [])

        print()
        print(f"━━━ {_bold(name)} ━━━ {_dim(fpath.name)}")
        if description:
            for line in textwrap.wrap(description, width=78):
                print(f"  {_dim(line)}")
        if tags:
            print(f"  Tags: {', '.join(tags)}")
        print(f"  Steps: {len(steps_data)}")

        scenario_result = ScenarioResult(
            name=name,
            file=str(fpath),
            passed=True,
            steps_total=len(steps_data),
            steps_passed=0,
        )

        for step in steps_data:
            step_result = _execute_step(
                step, variables, scenario_dir.parent.parent, dry_run, verbose
            )

            if dry_run:
                continue

            scenario_result.step_results.append(step_result)

            if step_result.passed:
                scenario_result.steps_passed += 1
                print(f"  {_green('✅ PASS')} {step_result.name}")
            else:
                scenario_result.passed = False
                print(f"  {_red('❌ FAIL')} {step_result.name}")
                for desc, ok, detail in step_result.checks:
                    if ok:
                        print(f"      {_green('✓')} {desc}")
                    else:
                        print(f"      {_red('✗')} {desc}  {_dim(f'({detail})')}")

        if not dry_run:
            if scenario_result.passed:
                print(f"  {_green(f'✅ ALL {scenario_result.steps_total}/{scenario_result.steps_total} STEPS PASSED')}")
            else:
                print(f"  {_red(f'❌ {scenario_result.steps_passed}/{scenario_result.steps_total} STEPS PASSED')}")

        results.append(scenario_result)

    return results


# ---------------------------------------------------------------------------
# Summary report
# ---------------------------------------------------------------------------
def print_summary(results: list[ScenarioResult]) -> int:
    """Print summary and return exit code (0 = all pass, 1 = any fail)."""
    all_pass = all(r.passed for r in results)

    print()
    print("=" * 60)
    print(f"  {_bold('VALIDATION SUMMARY')}")
    print("=" * 60)

    for r in results:
        icon = _green("✅") if r.passed else _red("❌")
        print(f"  {icon} {r.name}  ({r.steps_passed}/{r.steps_total} passed)  [{Path(r.file).name}]")

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    print()
    print(f"  Total scenarios:  {total}")
    print(f"  Passed:           {_green(str(passed))}")
    if failed:
        print(f"  Failed:           {_red(str(failed))}")

    if all_pass:
        print(f"\n  {_green(_bold('✅ ALL SCENARIOS PASSED'))}")
    else:
        print(f"\n  {_red(_bold(f'❌ {failed} SCENARIO(S) FAILED'))}")

    return 0 if all_pass else 1


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="AutoInfo YAML Validation Scenario Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              %(prog)s                           # Run all scenarios
              %(prog)s --dry-run                 # Preview only
              %(prog)s --scenario init-project   # Run one scenario
              %(prog)s --verbose                 # Verbose output
              %(prog)s --list                    # List available scenarios
              %(prog)s --dir my-scenarios/       # Custom scenario directory
        """),
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview steps without executing",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show detailed execution output",
    )
    parser.add_argument(
        "--scenario", "-s", type=str, default=None,
        help="Run only scenarios matching this name (substring match on filename)",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List available scenario files and exit",
    )
    parser.add_argument(
        "--dir", type=str, default=None,
        help="Path to the scenarios directory (default: docs/autoinfo-validation-master-plan/scenarios/)",
    )

    args = parser.parse_args()

    # Determine scenario directory
    if args.dir:
        scenario_dir = Path(args.dir).resolve()
    else:
        # Default: relative to repo root (parent of scripts/)
        script_dir = Path(__file__).resolve().parent
        repo_root = script_dir.parent
        scenario_dir = repo_root / "docs" / "autoinfo-validation-master-plan" / "scenarios"

    if not scenario_dir.is_dir():
        print(f"{_red('ERROR')}: Scenario directory not found: {scenario_dir}")
        print(f"  Create it with: mkdir -p {scenario_dir}")
        sys.exit(1)

    if args.list:
        scenarios = _load_scenarios(scenario_dir)
        print(f"{_bold('Available Scenarios')} ({len(scenarios)}):")
        for fpath, data in scenarios:
            name = data.get("name", fpath.stem)
            steps = len(data.get("steps", []))
            tags = ", ".join(data.get("tags", []))
            print(f"  {fpath.name:40s}  {_bold(name):30s}  steps={steps}  tags=[{tags}]")
        sys.exit(0)

    print(f"{_bold('Scenario Directory')}: {scenario_dir}")
    if args.dry_run:
        print(f"{_cyan('[DRY-RUN MODE]')} — no commands will be executed")
    print()

    results = run_scenarios(
        scenario_dir=scenario_dir,
        dry_run=args.dry_run,
        verbose=args.verbose,
        scenario_filter=args.scenario,
    )

    if args.dry_run:
        print(f"\n{_cyan('[DRY-RUN COMPLETE]')} — no commands were executed")
        sys.exit(0)

    exit_code = print_summary(results)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
