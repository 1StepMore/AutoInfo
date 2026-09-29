"""Tests for the release-scope gate (scripts/check_release_scope.py, issue #406).

release-please keys off the conventional-commit TYPE alone, so a `fix(ci):`
internal-only PR cuts a public release with no user-facing content. The gate
fails that mismatch (and its mirror: a hidden type over user-visible paths),
with two escape-hatch labels for the genuine exceptions.

The decision logic is the pure `assess_release_scope`; these tests call it
directly and additionally lock the CLI contract (exit 0/1/2, stdin support).
No new dependencies, no network, no filesystem beyond `tmp_path`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

# scripts/ is not a package — load it via sys.path like the script itself does.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

import check_release_scope as gate  # noqa: E402  (sys.path insert above)

_SCRIPT = _SCRIPTS_DIR / "check_release_scope.py"

ALL_INTERNAL = [".github/workflows/ci.yml", "tests/cli/test_x.py", "scripts/foo.py"]
USER_VISIBLE = "src/autoinfo/x.py"


# ---------------------------------------------------------------------------
# Row 1: all-internal paths + visible type -> fail (unless the label says so)
# ---------------------------------------------------------------------------


def test_all_internal_with_visible_type_fails_and_names_paths() -> None:
    result = gate.assess_release_scope(ALL_INTERNAL, "fix", [])

    assert result.passed is False
    for path in ALL_INTERNAL:
        assert path in result.reason
    assert "chore" in result.remediation
    assert gate.USER_VISIBLE_LABEL in result.remediation


def test_all_internal_with_visible_type_and_label_passes() -> None:
    result = gate.assess_release_scope(ALL_INTERNAL, "fix", [gate.USER_VISIBLE_LABEL])

    assert result.passed is True


@pytest.mark.parametrize("hidden", sorted(gate.HIDDEN_TYPES))
def test_all_internal_with_hidden_type_passes(hidden: str) -> None:
    result = gate.assess_release_scope(ALL_INTERNAL, hidden, [])

    assert result.passed is True


# ---------------------------------------------------------------------------
# Row 2: user-visible paths + hidden type -> fail (unless the label says so)
# ---------------------------------------------------------------------------


def test_user_visible_with_hidden_type_fails_and_names_path() -> None:
    result = gate.assess_release_scope([USER_VISIBLE], "chore", [])

    assert result.passed is False
    assert USER_VISIBLE in result.reason
    assert gate.SKIP_LABEL in result.remediation


def test_user_visible_with_hidden_type_and_skip_label_passes() -> None:
    result = gate.assess_release_scope([USER_VISIBLE], "chore", [gate.SKIP_LABEL])

    assert result.passed is True


@pytest.mark.parametrize("visible", ["feat", "fix", "docs"])
def test_user_visible_with_visible_type_passes(visible: str) -> None:
    result = gate.assess_release_scope([USER_VISIBLE], visible, [])

    assert result.passed is True


# ---------------------------------------------------------------------------
# Row 3: mixed paths — the user-visible path decides
# ---------------------------------------------------------------------------


def test_mixed_paths_with_hidden_type_fails() -> None:
    result = gate.assess_release_scope([".github/workflows/ci.yml", USER_VISIBLE], "chore", [])

    assert result.passed is False
    assert USER_VISIBLE in result.reason


def test_mixed_paths_with_visible_type_passes() -> None:
    result = gate.assess_release_scope([".github/workflows/ci.yml", USER_VISIBLE], "fix", [])

    assert result.passed is True


# ---------------------------------------------------------------------------
# Row 4: exempt / non-conventional titles are not judged here
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "title",
    [
        "Update the docs",
        "Release v1.9.0",
        "dependabot[bot]: bump x from 1 to 2",
        "Merge branch 'main'",
    ],
)
def test_exempt_titles_pass_without_judging(title: str) -> None:
    result = gate.assess_release_scope(ALL_INTERNAL, gate.parse_title_type(title), [])

    assert result.passed is True


def test_empty_path_list_passes() -> None:
    result = gate.assess_release_scope([], "fix", [])

    assert result.passed is True


# ---------------------------------------------------------------------------
# Release-please's OWN release PR is exempt (#412)
# ---------------------------------------------------------------------------

# A release-please release PR is the OUTPUT of this gate's classification: it
# aggregates already-classified commits and rewrites the changelog. Applying
# "hidden type must not touch user-visible paths" to it is a category error --
# the release PR *is* the changelog, so it necessarily edits CHANGELOG.md,
# the version marker and the manifest. Left un-exempted it fails its own
# required check, which blocks every release indefinitely (#411, v1.13.7).

RELEASE_PR_PATHS = [
    "CHANGELOG.md",
    ".release-please-manifest.json",
    "src/autoinfo/_version.py",
]


def test_release_please_release_pr_passes_despite_user_visible_paths() -> None:
    result = gate.assess_release_scope(
        RELEASE_PR_PATHS,
        "chore",
        [],
        title="chore(main): release 1.13.7",
    )

    assert result.passed is True, result.reason
    assert "release pr" in result.reason.lower()


def test_release_please_release_pr_passes_even_mixed_with_other_paths() -> None:
    result = gate.assess_release_scope(
        [*RELEASE_PR_PATHS, ".github/workflows/release-please.yml"],
        "chore",
        [],
        title="chore(main): release 1.13.7",
    )

    assert result.passed is True, result.reason


def test_a_normal_chore_pr_touching_changelog_is_still_judged() -> None:
    """The exemption keys on the release PR's title, not on touching CHANGELOG.

    Otherwise any hidden-type PR that happens to edit the changelog would
    silently escape the gate.
    """
    result = gate.assess_release_scope(
        RELEASE_PR_PATHS,
        "chore",
        [],
        title="chore(docs): tidy the changelog",
    )

    assert result.passed is False, result.reason


def test_exemption_needs_no_label() -> None:
    result = gate.assess_release_scope(
        RELEASE_PR_PATHS,
        "chore",
        ["autorelease: pending"],
        title="chore(main): release 1.13.7",
    )

    assert result.passed is True, result.reason


def test_release_pr_exemption_also_holds_for_a_visible_typed_title() -> None:
    result = gate.assess_release_scope(
        RELEASE_PR_PATHS,
        "fix",
        [],
        title="chore(main): release 1.13.7",
    )

    assert result.passed is True, result.reason


# ---------------------------------------------------------------------------
# Fail-safe direction: unknown paths are user-visible
# ---------------------------------------------------------------------------


def test_unknown_path_is_treated_as_user_visible() -> None:
    # Fail-safe: an unrecognized path must demand a release rather than
    # silently suppress one, so a hidden type over it must FAIL.
    result = gate.assess_release_scope(["NEWFILE.xyz"], "chore", [])

    assert result.passed is False
    assert "NEWFILE.xyz" in result.reason


# ---------------------------------------------------------------------------
# is_internal_path classification
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "internal"),
    [
        (".github/workflows/ci.yml", True),
        ("tests/cli/test_x.py", True),
        ("scripts/foo.py", True),
        ("docs/dev/loop.md", True),
        ("docs/glossary.md", False),
        ("release-please-config.json", True),
        ("README.md", False),
        ("src/autoinfo/cli.py", False),
    ],
)
def test_is_internal_path(path: str, internal: bool) -> None:
    assert gate.is_internal_path(path) is internal


# ---------------------------------------------------------------------------
# CLI contract
# ---------------------------------------------------------------------------


def _run(args: list[str], stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_exit_zero_on_pass(tmp_path: Path) -> None:
    files = tmp_path / "files.txt"
    files.write_text(".github/workflows/ci.yml\n", encoding="utf-8")

    proc = _run(["--files", str(files), "--title", "ci: tweak", "--labels", ""])

    assert proc.returncode == 0


def test_cli_exit_one_on_fail(tmp_path: Path) -> None:
    files = tmp_path / "files.txt"
    files.write_text(".github/workflows/ci.yml\n", encoding="utf-8")

    proc = _run(["--files", str(files), "--title", "fix: tweak", "--labels", ""])

    assert proc.returncode == 1
    assert "Fix:" in proc.stderr


def test_cli_exit_two_when_no_file_source() -> None:
    proc = _run(["--title", "fix: tweak"])

    assert proc.returncode == 2


def test_cli_reads_files_from_stdin() -> None:
    proc = _run(["--files", "-", "--title", "fix: tweak", "--labels", ""], stdin=".github/ci.yml\n")

    assert proc.returncode == 1
