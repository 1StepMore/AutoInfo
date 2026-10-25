"""Regression tests for #600 — gitignored KB paths skip git versioning.

``knowledge/`` is gitignored, so every entry version used to spawn
``git add``/``git commit`` and fail with a WARNING.  The versioning helper now
probes ``git check-ignore`` once per directory and skips ignored paths.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

import pytest

from autoinfo.kb import SQLiteIndex

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _commands(calls: list[list[str]], verb: str) -> list[list[str]]:
    return [c for c in calls if len(c) >= 2 and c[0] == "git" and c[1] == verb]


@pytest.fixture
def git_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "AutoInfo Test")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "commit.gpgsign", "false")
    monkeypatch.chdir(repo)
    return repo


@pytest.fixture
def recorded_git_calls(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    calls: list[list[str]] = []
    real_run = subprocess.run

    def recorder(args, *pargs, **kwargs):
        calls.append([str(a) for a in args])
        return real_run(args, *pargs, **kwargs)

    monkeypatch.setattr("autoinfo.kb.subprocess.run", recorder)
    return calls


def test_ignored_path_skips_add_and_commit(git_repo: Path, recorded_git_calls, caplog) -> None:
    (git_repo / ".gitignore").write_text("knowledge/\n", encoding="utf-8")
    fp = git_repo / "knowledge" / "demo" / "01-Raw" / "topic" / "entry.md"
    fp.parent.mkdir(parents=True)
    fp.write_text("# entry\n", encoding="utf-8")

    with caplog.at_level(logging.DEBUG):
        sha = SQLiteIndex._git_commit_and_get_sha(str(fp), "entry-ignored", 1)

    assert sha == ""
    assert _commands(recorded_git_calls, "add") == []
    assert _commands(recorded_git_calls, "commit") == []
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    # One probe of the ignored ancestor (``knowledge``), no per-entry probes.
    check_ignore = _commands(recorded_git_calls, "check-ignore")
    assert len(check_ignore) == 1
    assert check_ignore[0][-1] == "knowledge"


def test_ignored_verdict_cached_across_entries(git_repo: Path, recorded_git_calls) -> None:
    (git_repo / ".gitignore").write_text("knowledge/\n", encoding="utf-8")
    for i in range(3):
        fp = git_repo / "knowledge" / "demo" / "01-Raw" / f"topic-{i}" / "entry.md"
        fp.parent.mkdir(parents=True)
        fp.write_text(f"# entry {i}\n", encoding="utf-8")
        assert SQLiteIndex._git_commit_and_get_sha(str(fp), f"entry-{i}", 1) == ""

    assert len(_commands(recorded_git_calls, "check-ignore")) == 1
    assert _commands(recorded_git_calls, "add") == []
    assert _commands(recorded_git_calls, "commit") == []


def test_tracked_path_still_adds_and_commits(git_repo: Path, recorded_git_calls) -> None:
    fp = git_repo / "tracked" / "entry.md"
    fp.parent.mkdir()
    fp.write_text("# entry\n", encoding="utf-8")

    sha = SQLiteIndex._git_commit_and_get_sha(str(fp), "entry-tracked", 1)

    assert len(sha) == 40
    assert len(_commands(recorded_git_calls, "add")) == 1
    assert len(_commands(recorded_git_calls, "commit")) == 1
    head = _git(git_repo, "rev-parse", "HEAD")
    assert head.stdout.strip() == sha
