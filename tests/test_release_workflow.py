"""Regression tests for the release-please + auto-merge workflow pair (#275, #410).

Two independent mechanisms are guarded here.

1. `release-please.yml` opens the release PR with the default `GITHUB_TOKEN`.
   Because GitHub does not create new workflow runs for events caused by that
   token, a `pull_request_target` trigger CANNOT be used to auto-merge the
   release PR -- it never fires for the only PRs it targets.

2. `.github/workflows/release-pr-auto-merge.yml` therefore triggers on
   `workflow_run` for the `Release` workflow, which GitHub always schedules
   (the run was created by a human merge or a dispatch, not by a token).
   It approves the blocked runs, enables native auto-merge, and then
   dispatches `Release` explicitly so the git tag is actually cut.

The security property that makes this safe: the auto-merge workflow holds
`actions: write` + `contents: write` while reacting to pull-request events,
so it must NEVER execute PR-supplied code. These tests pin that: no
`actions/checkout`, no `uses:` at all, and the three eligibility gates stay
intact.

NOTE: the workflows use the YAML 1.1 `on:` key, which PyYAML's safe_load
misparses as the boolean `True`. We parse with `yaml.BaseLoader` (a
YAML-1.1-safe approach) so the document loads with the real `on` key.
"""

from pathlib import Path
from typing import Any, cast

import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"
RELEASE_PLEASE = WORKFLOWS / "release-please.yml"
AUTO_MERGE = WORKFLOWS / "release-pr-auto-merge.yml"


def _load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], yaml.load(path.read_text(), Loader=yaml.BaseLoader))


def _release_please_steps() -> list[dict[str, Any]]:
    data = _load(RELEASE_PLEASE)
    return cast(list[dict[str, Any]], data["jobs"]["release-please"]["steps"])


def _auto_merge_job() -> dict[str, Any]:
    data = _load(AUTO_MERGE)
    return cast(dict[str, Any], data["jobs"]["auto-merge"])


# ---------------------------------------------------------------------------
# release-please.yml
# ---------------------------------------------------------------------------


def test_release_please_needs_no_pat_to_run() -> None:
    """No credential may be REQUIRED, even though a PAT fallback still exists.

    The historical fix for the blocked-release problem was "authenticate as a
    human with a fine-grained PAT". #405 stopped *instructing* maintainers to
    mint one, but the `token:` input legitimately survives as
    `secrets.RELEASE_PLEASE_PAT || github.token`. The invariant that matters is
    therefore: with no secret configured the workflow still runs on the default
    token. If the `|| github.token` fallback is ever dropped, release-please
    would need a credential again and the "no PAT" property would be lost.
    """
    steps = _release_please_steps()
    token = str(steps[0]["with"]["token"])
    assert "github.token" in token, f"no credential-free fallback in {token!r}"


def test_no_release_type_or_package_name_inputs() -> None:
    steps = _release_please_steps()
    with_inputs = steps[0]["with"]
    assert "release-type" not in with_inputs
    assert "package-name" not in with_inputs


# ---------------------------------------------------------------------------
# release-pr-auto-merge.yml -- the trigger (#410)
# ---------------------------------------------------------------------------


def test_auto_merge_triggers_on_workflow_run_not_pull_request_target() -> None:
    """The whole fix: a GITHUB_TOKEN-created PR fires no workflow run.

    If this regresses to `pull_request_target` the bot silently never runs and
    every release stalls again -- which is exactly the bug that shipped once.
    """
    triggers = _load(AUTO_MERGE)["on"]
    assert "pull_request_target" not in triggers
    assert "pull_request" not in triggers
    assert "workflow_run" in triggers


def test_auto_merge_waits_for_the_release_workflow_to_succeed() -> None:
    """Approving/merging on a FAILED Release run would merge a broken release."""
    triggers = _load(AUTO_MERGE)["on"]
    assert triggers["workflow_run"]["types"] == ["completed"]
    assert triggers["workflow_run"]["branches"] == ["main"]
    job_if = str(_auto_merge_job()["if"])
    assert "workflow_run.conclusion == 'success'" in job_if


def test_auto_merge_filter_matches_the_release_workflow_name() -> None:
    """`workflows:` is matched by NAME, so a rename silently disables the bot."""
    release_name = str(_load(RELEASE_PLEASE)["name"])
    triggers = _load(AUTO_MERGE)["on"]
    assert triggers["workflow_run"]["workflows"] == [release_name]


# ---------------------------------------------------------------------------
# release-pr-auto-merge.yml -- the security boundary
# ---------------------------------------------------------------------------


def _strip_comments(text: str) -> str:
    """Drop whole-line YAML comments.

    The workflow's own header explains at length that it contains no `uses:`
    and no `run:` of PR code -- so a naive substring scan matches the very
    comment that documents the invariant. Only executable lines may be scanned.
    """
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def test_auto_merge_never_checks_out_or_runs_pr_code() -> None:
    """A privileged token must never execute PR-supplied code.

    The workflow reacts to pull-request state while holding `actions: write`
    and `contents: write`. Any checkout of the head ref, or any third-party
    `uses:`, would hand an attacker that privilege. Everything must go
    through `gh` / `gh api` in the default-branch copy of the file.
    """
    executable = _strip_comments(AUTO_MERGE.read_text())
    assert "actions/checkout" not in executable
    assert "pull_request_target" not in executable
    assert "uses:" not in executable


def test_auto_merge_retains_the_permissions_it_needs() -> None:
    """Approving a blocked run needs `actions: write`; merging needs `contents: write`."""
    perms = _load(AUTO_MERGE)["permissions"]
    assert perms["actions"] == "write"
    assert perms["contents"] == "write"
    assert perms["pull-requests"] == "write"


def test_auto_merge_keeps_the_three_eligibility_gates() -> None:
    """Bot author + release-please branch prefix + release title are the gate.

    Weakening these would let a non-release PR be force-merged by a workflow
    holding write scopes, so they are pinned individually.
    """
    text = AUTO_MERGE.read_text()
    assert "github-actions[bot]" in text
    assert "release-please--branches--" in text
    assert "chore(main): release " in text
    # The skip path must stay a clean no-op, never a fall-through.
    assert "::notice::" in text


def test_auto_merge_squashes_because_main_protection_allows_only_squash() -> None:
    """The main-protection ruleset permits `squash` alone (verified)."""
    text = AUTO_MERGE.read_text()
    assert "--squash" in text


def test_auto_merge_dispatches_release_so_the_tag_is_cut() -> None:
    """A token-attributed merge suppresses the `push` that would cut the tag.

    `workflow_dispatch` always creates a run even for token-caused events, so
    the workflow must dispatch `release-please.yml` after the merge lands.
    """
    text = AUTO_MERGE.read_text()
    assert "gh workflow run release-please.yml" in text
    assert "MERGED" in text
