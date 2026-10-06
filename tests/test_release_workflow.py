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

3. #494: that dispatch used to hang off a bounded poll for the merge, which
   lost the race against this repo's own CI turnaround and left a silent
   half-release (manifest bumped, no tag, exit 0). The tag cut is therefore
   reconciled against the manifest on a timer, and an expired poll now fails
   loudly instead of passing.

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


# ---------------------------------------------------------------------------
# release-pr-auto-merge.yml -- tag reconciliation (#494)
# ---------------------------------------------------------------------------


def _reconcile_job() -> dict[str, Any]:
    data = _load(AUTO_MERGE)
    return cast(dict[str, Any], data["jobs"]["reconcile-release-tag"])


def test_reconcile_job_exists_and_is_reachable() -> None:
    """Without a non-`workflow_run` trigger the safety net can never fire.

    #494's tag was lost because every signal the fast path can watch arrives
    before the merge does. The reconciler only helps if something triggers it, so
    each trigger is pinned individually.
    """
    triggers = _load(AUTO_MERGE)["on"]
    assert "workflow_dispatch" in triggers, "no manual retry path for a lost tag"
    assert "schedule" in triggers, "covers the token-merge case, which fires no push"


def test_reconcile_also_runs_on_push_because_cron_is_unreliable() -> None:
    """`schedule` alone was measured dropping ~3 consecutive ticks.

    v1.17.9's release PR merged as a token-attributed merge, which fires no push
    event, so the untagged state survived until a manual dispatch ~33 min later.
    `push` to main fires reliably for human- and agent-authored pushes, which
    makes it the complement the timer cannot be. If this regresses to `schedule`
    only, the safety net silently depends on best-effort cron.
    """
    triggers = _load(AUTO_MERGE)["on"]
    assert "push" in triggers, "no reliable complement to best-effort cron"
    assert triggers["push"]["branches"] == ["main"], "push must be main-only"
    assert "push" in str(_reconcile_job()["if"]), "the push trigger must reach the reconciler"


def test_fast_path_never_runs_on_push() -> None:
    """A `push` event must not drag the fast path in with it.

    The fast path approves runs and enables auto-merge on a release PR. Its guard
    tests `workflow_run.conclusion`, which is null on `push`, so the job is
    skipped — that guard is now load-bearing for a second event type and must not
    be relaxed into a bare `success()` check.
    """
    job_if = str(_auto_merge_job()["if"])
    assert "workflow_run.conclusion == 'success'" in job_if
    assert "always" not in job_if


def test_reconcile_job_does_not_race_the_fast_path() -> None:
    """Two dispatchers on one merge would double-dispatch `Release`.

    The `workflow_run` path already tries to cut the tag immediately, so the
    reconciler must stay off it or the same merge gets two dispatches.
    """
    job_if = str(_reconcile_job()["if"])
    assert "schedule" in job_if
    assert "workflow_dispatch" in job_if
    assert "workflow_run" not in job_if


def test_reconcile_reads_the_manifest_from_the_default_branch() -> None:
    """The reconciler holds write scopes, so it must not read PR-supplied content.

    It reads `.release-please-manifest.json` over the contents API pinned to
    `ref=main`. Reading the manifest from the PR head instead would let a
    contributor choose the version this privileged job publishes.
    """
    body = str(_reconcile_job()["steps"][0]["run"])
    assert ".release-please-manifest.json?ref=main" in body


def test_reconcile_dispatches_release_when_the_pinned_version_is_unpublished() -> None:
    """The healing action itself: an unpublished pinned version triggers a dispatch.

    Idempotence comes from the guard just above it (already-published exits 0),
    so this pair is what makes the timer safe to run unconditionally.
    """
    body = str(_reconcile_job()["steps"][0]["run"])
    assert "gh release view" in body, "no existing-release check, so it would always dispatch"
    assert "gh workflow run release-please.yml" in body


def _step(job: dict[str, Any], name_fragment: str) -> dict[str, Any]:
    steps = cast(list[dict[str, Any]], job["steps"])
    for step in steps:
        if name_fragment in str(step["name"]):
            return step
    raise AssertionError(f"no step matching {name_fragment!r} in {[s['name'] for s in steps]}")


# ---------------------------------------------------------------------------
# release-pr-auto-merge.yml -- bot-approval visibility (#494 follow-up)
# ---------------------------------------------------------------------------


def test_approval_failure_cannot_skip_the_tag_cut() -> None:
    """`GITHUB_TOKEN` cannot always approve a bot PR's runs.

    Observed 2026-10-06: the approval silently failed for release PR #496 and its
    4 runs sat in `action_required` for ~12.6h, blocking the merge. A plain
    `exit 1` here would be worse than the status quo -- it would skip the
    auto-merge enable and the tag cut below. So the step is non-fatal and the
    outcome is asserted separately.
    """
    approve = _step(_auto_merge_job(), "Approve workflow runs")
    # `yaml.BaseLoader` (used by `_load`) yields every scalar as a string.
    assert approve["continue-on-error"] in (True, "true")


def test_unapproved_runs_fail_the_job_and_name_the_pr() -> None:
    """The failure must be loud and actionable, not a warning nobody reads.

    #494's lesson applied to approval: `::warning::` + exit 0 turned a blocked
    release into a green run. The assertion is `always()` so it still reports when
    the tag cut timed out, which is the usual shape of this failure.
    """
    step = _step(_auto_merge_job(), "Assert no release run is left waiting")
    assert "always()" in str(step["if"])
    body = str(step["run"])
    assert "::error::" in body
    assert "${PR_NUMBER}" in body, "the error must name the PR a human has to unblock"
    assert "exit 1" in body


def test_reconcile_surfaces_a_release_pr_stuck_awaiting_approval() -> None:
    """Nothing retries approval after the fast path fails, so the timer must.

    Without this, a release PR blocked in `action_required` is invisible: the
    reconciler only cared about the tag, and the fast path that would have
    noticed had already failed.
    """
    body = str(_reconcile_job()["steps"][0]["run"])
    assert "action_required" in body, "the reconciler must look for unapproved runs"
    assert "release-please--branches--" in body, "it must only consider release PRs"
    assert "::error::" in body


def test_expired_poll_fails_loudly_instead_of_passing() -> None:
    """The silent half-release: `::warning::` + `exit 0` shipped as #494.

    An expired poll used to warn and exit 0, so a release could merge with the
    manifest and `_version.py` bumped but no tag and no GitHub release — the
    version number then never appears in any changelog, and nothing reports it.
    The failure must be loud, because that silence is the actual defect.
    """
    body = str(_auto_merge_job()["steps"][-1]["run"])
    assert "::error::" in body, "an expired poll must raise an error annotation"
    assert "exit 1" in body, "an expired poll must fail the job, not exit 0"
    assert "::warning::PR" not in body, "the #494 silent-pass branch is back"
