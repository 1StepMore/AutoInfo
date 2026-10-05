"""Tests for scripts/check_signoff_identity.py (#427).

The policy is exercised as a pure function so no git repository is needed:
`violation()` decides from a `Commit` value alone. That matters because the
real-world population is mixed — the same repo contains human commits, GitHub
noreply squash merges, bot commits, and merge commits — and each class has a
different correct verdict.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

import check_signoff_identity as csi  # noqa: E402  (sys.path insert above)


def test_parse_signoff_reads_every_entry_in_order() -> None:
    block = "Renan Zhai <renanzai@example.com>\nSomeone Else <other@example.com>\n"
    assert csi.parse_signoff(block) == ("renanzai@example.com", "other@example.com")


def test_parse_signoff_lowercases_and_tolerates_blank_lines() -> None:
    block = "\nRenan Zhai <Renan.Zhai@Example.COM>\n\n"
    assert csi.parse_signoff(block) == ("renan.zhai@example.com",)


def test_parse_signoff_is_empty_for_no_trailer() -> None:
    assert csi.parse_signoff("") == ()
    assert csi.parse_signoff("not a trailer line") == ()


def test_matching_author_and_signer_is_clean() -> None:
    commit = csi.Commit(
        sha="a1",
        author_email="renanzai@example.com",
        signoff_emails=("renanzai@example.com",),
    )
    assert csi.violation(commit) is None


def test_comparison_is_case_insensitive() -> None:
    commit = csi.Commit(
        sha="a2",
        author_email="Renan.Zhai@Example.com",
        signoff_emails=("renan.zhai@example.com",),
    )
    assert csi.violation(commit) is None


def test_real_mismatch_is_reported() -> None:
    """The genuine violation class from #427: a real address, someone else's sign-off."""
    commit = csi.Commit(
        sha="a3",
        author_email="renanzai@zohomail.com",
        signoff_emails=("hermes-agent@nousresearch.com",),
    )
    text = csi.violation(commit)
    assert text is not None
    assert "does not match author email" in text
    assert "hermes-agent@nousresearch.com" in text


def test_noreply_author_is_exempt_from_comparison() -> None:
    """GitHub wrote the author field, so there is nothing to compare against.

    45 of the 50 historical mismatches were this shape; flagging them would be
    pure noise.
    """
    commit = csi.Commit(
        sha="a4",
        author_email="140780063+1StepMore@users.noreply.github.com",
        signoff_emails=("renanzai@eva-01.localdomain",),
    )
    assert csi.violation(commit) is None


def test_bot_author_needs_no_signoff() -> None:
    commit = csi.Commit(
        sha="a5",
        author_email="41898282+github-actions[bot]@users.noreply.github.com",
        signoff_emails=(),
    )
    assert csi.violation(commit) is None


def test_merge_commit_is_exempt() -> None:
    """DCO binds authorship; a merge commit has none to attest."""
    commit = csi.Commit(
        sha="a6",
        author_email="renanzai@example.com",
        signoff_emails=(),
        parent_count=2,
    )
    assert csi.violation(commit) is None


def test_missing_signoff_on_a_human_commit_is_reported() -> None:
    commit = csi.Commit(
        sha="a7",
        author_email="renanzai@example.com",
        signoff_emails=(),
    )
    text = csi.violation(commit)
    assert text is not None
    assert "missing Signed-off-by" in text


def test_mismatch_against_any_of_several_signers_is_clean() -> None:
    commit = csi.Commit(
        sha="a8",
        author_email="renanzai@example.com",
        signoff_emails=("coauthor@example.com", "renanzai@example.com"),
    )
    assert csi.violation(commit) is None
