"""Coverage-audit tests (E3, issue #134).

Covers three things:

1. ``kb-promote.yaml`` — valid YAML with the required scenario keys.
2. ``kb-promote.yaml`` — exactly 4 main steps exercising the full
   Raw -> Draft -> Wiki pipeline (create_kb_entry, create_kb_draft,
   promote_kb_draft, cli wiki verification) plus a cleanup step that
   purges BOTH the 03-Wiki and 01-Raw entries.
3. ``scripts/coverage_audit.py`` — the counting logic must be
   ``covered = declared ∩ scenario_used`` so that phantom scenario tools
   (e.g. ``definitely_not_a_real_tool`` in error-boundary.yaml) can never
   inflate the covered count and mask genuinely-missing declared tools.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import yaml

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS_DIR = ROOT / "src" / "autoinfo" / "mcp" / "scenarios"
KB_PROMOTE_YAML = SCENARIOS_DIR / "kb-promote.yaml"

SERVER_SRC = ROOT / "src" / "autoinfo" / "mcp" / "server.py"
AUDIT_SCRIPT = ROOT / "scripts" / "coverage_audit.py"


# ---------------------------------------------------------------------------
# Import the real coverage_audit.py so the tests exercise the script's own
# logic rather than a reimplementation.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def coverage_audit():
    spec = importlib.util.spec_from_file_location("coverage_audit", AUDIT_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# kb-promote.yaml: validity + structure
# ---------------------------------------------------------------------------


def test_kb_promote_yaml_exists_and_parses():
    assert KB_PROMOTE_YAML.is_file(), "kb-promote.yaml must exist"
    data = yaml.safe_load(KB_PROMOTE_YAML.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    # Required top-level keys enforced by validation.load_scenarios
    for key in ("name", "description", "steps"):
        assert key in data, f"missing required key: {key}"
    assert data["name"] == "kb-promote"
    assert data["category"] == "kb"
    assert data["requires_env"] == []
    assert data["requires_domain"] == ["medical-research"]
    assert data["collect_artifacts"] == [
        "knowledge/medical-research/01-Raw/**/*.md",
        "knowledge/medical-research/02-Draft/**/*.md",
    ]


def test_kb_promote_steps_and_cleanup():
    data = yaml.safe_load(KB_PROMOTE_YAML.read_text(encoding="utf-8"))
    steps = data["steps"]
    # Exactly 4 steps: create_kb_entry -> create_kb_draft -> promote_kb_draft
    # -> cli wiki verification.
    assert len(steps) == 4
    tools = [s.get("tool") for s in steps]
    assert tools[:3] == ["create_kb_entry", "create_kb_draft", "promote_kb_draft"]
    # Step 4 verifies the promoted wiki entry via a CLI python check.
    assert steps[3].get("kind") == "cli"
    assert "03-Wiki" in steps[3]["expect"]["stdout_has"]

    cleanup = data.get("cleanup_steps")
    assert isinstance(cleanup, list) and len(cleanup) >= 1
    cleanup_cmd = cleanup[0]["command"]
    # Cleanup must purge the promoted 03-Wiki entry AND the original 01-Raw
    # entry (promotion keeps the draft's entry_id in 03-Wiki).
    assert "medical-research-general-kb-promote-scenario-test-entry" in cleanup_cmd
    assert "medical-research-draft-kb-promote-scenario-draft" in cleanup_cmd
    assert "03-Wiki" in cleanup_cmd
    assert cleanup[0]["expect"].get("success") is True
    assert "CLEANED" in cleanup[0]["expect"]["stdout_has"]


def test_kb_promote_passes_load_scenarios_validation():
    """kb-promote.yaml must be accepted by the real scenario loader."""
    sys.path.insert(0, str(ROOT / "src"))
    try:
        from autoinfo.mcp.validation import load_scenarios
    finally:
        sys.path.remove(str(ROOT / "src"))
    names = {s["name"] for s in load_scenarios()}
    assert "kb-promote" in names


# ---------------------------------------------------------------------------
# coverage_audit.py counting logic (issue #134)
# ---------------------------------------------------------------------------

SERVER_SNIPPET = (
    'Tool(\n'
    '    name="alpha_tool",\n'
    '    description="...",\n'
    ')\n'
    'Tool(name="beta_tool")\n'
    'Tool(\n'
    '    name="gamma_tool",\n'
    ')\n'
)


def _write_scenario(dirpath: Path, name: str, tools: list[str]) -> Path:
    p = dirpath / f"{name}.yaml"
    steps = []
    for t in tools:
        steps.append({"name": f"call {t}", "tool": t, "expect": {"success": True}})
    p.write_text(
        yaml.safe_dump({"name": name, "description": name, "steps": steps}),
        encoding="utf-8",
    )
    return p


def test_covered_is_declared_intersection_with_phantom(coverage_audit, tmp_path):
    """A phantom scenario tool must NOT count as covering a declared tool."""
    _write_scenario(tmp_path, "good", ["alpha_tool", "beta_tool"])
    # error-boundary style: references a tool that server.py never declares
    _write_scenario(tmp_path, "phantom", ["alpha_tool", "definitely_not_a_real_tool"])

    cov = coverage_audit.compute_coverage(SERVER_SNIPPET, tmp_path)

    assert cov["declared"] == ["alpha_tool", "beta_tool", "gamma_tool"]
    assert cov["scenario_used"] == ["alpha_tool", "beta_tool", "definitely_not_a_real_tool"]
    # covered = declared ∩ scenario_used — the phantom contributes nothing
    assert cov["covered"] == ["alpha_tool", "beta_tool"]
    assert len(cov["covered"]) == 2
    # gamma_tool is genuinely uncovered
    assert cov["missing"] == ["gamma_tool"]
    # phantom is separated out, informational only
    assert cov["phantom"] == ["definitely_not_a_real_tool"]


def test_missing_is_declared_minus_covered(coverage_audit, tmp_path):
    """missing = declared - (declared ∩ scenario_used) = declared - scenario_used."""
    _write_scenario(tmp_path, "partial", ["alpha_tool"])
    cov = coverage_audit.compute_coverage(SERVER_SNIPPET, tmp_path)
    assert cov["covered"] == ["alpha_tool"]
    assert cov["missing"] == ["beta_tool", "gamma_tool"]
    assert set(cov["missing"]) == set(cov["declared"]) - set(cov["covered"])


def test_full_coverage_when_all_declared_used(coverage_audit, tmp_path):
    _write_scenario(
        tmp_path,
        "full",
        ["alpha_tool", "beta_tool", "gamma_tool", "definitely_not_a_real_tool"],
    )
    cov = coverage_audit.compute_coverage(SERVER_SNIPPET, tmp_path)
    assert len(cov["covered"]) == len(cov["declared"]) == 3
    assert cov["missing"] == []
    assert cov["phantom"] == ["definitely_not_a_real_tool"]


def test_non_mcp_steps_do_not_count(coverage_audit, tmp_path):
    """kind: cli steps reference no tool and must not enter scenario_used."""
    p = tmp_path / "mixed.yaml"
    p.write_text(
        yaml.safe_dump(
            {
                "name": "mixed",
                "description": "mixed kinds",
                "steps": [
                    {"name": "mcp step", "tool": "alpha_tool", "expect": {"success": True}},
                    {
                        "name": "cli step",
                        "kind": "cli",
                        "command": "python3 -c 'print(1)'",
                        "expect": {"success": True},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    cov = coverage_audit.compute_coverage(SERVER_SNIPPET, tmp_path)
    assert cov["scenario_used"] == ["alpha_tool"]
    assert cov["covered"] == ["alpha_tool"]


def test_live_audit_prints_full_coverage():
    """End-to-end: the real script against the real repo must report 142/142
    with an empty MISSING list (kb-promote.yaml covers promote_kb_draft, the
    phantom from error-boundary.yaml is not counted as a real tool)."""
    result = subprocess.run(
        [sys.executable, str(AUDIT_SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "Covered by scenarios: 142/142" in result.stdout
    assert "MISSING tools (0):" in result.stdout
    # phantom must be reported separately, never as missing
    assert "definitely_not_a_real_tool" in result.stdout
    assert result.stdout.index("MISSING tools (0):") < result.stdout.index(
        "definitely_not_a_real_tool"
    )


def test_live_audit_prints_regression_scenarios():
    """The real coverage_audit.py must print 'Regression scenarios: N (issues: ...)'."""
    result = subprocess.run(
        [sys.executable, str(AUDIT_SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "Regression scenarios:" in result.stdout
    lines = [l for l in result.stdout.splitlines() if l.startswith("Regression scenarios:")]
    assert len(lines) == 1
    line = lines[0]
    assert "#104" in line
    assert "#119" in line
    assert "#121" in line
    assert "#126" in line
    assert "#135" in line


def test_compute_coverage_includes_regression_subdir(coverage_audit, tmp_path):
    """compute_coverage with rglob scans regression/ subdirectory for tool coverage."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    _write_scenario(tmp_path, "top-level", ["alpha_tool"])
    reg_dir = tmp_path / "regression"
    reg_dir.mkdir()
    _write_scenario(reg_dir, "reg-sub", ["beta_tool"])
    cov = coverage_audit.compute_coverage(SERVER_SNIPPET, tmp_path)
    assert cov["covered"] == ["alpha_tool", "beta_tool"]
    assert "reg-sub" in cov["scenario_names"]
