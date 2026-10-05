#!/usr/bin/env python3
"""#427 — a commit's ``Signed-off-by`` email must match its author email.

CODE_CONVENTIONS **E4 提交可追溯** (submission traceability): a DCO sign-off is
an authorship attestation, so it is only meaningful if the signer is the author.
When they differ, review cannot tell who is accountable for the change.

The check has run against real history and found exactly two populations:

* **GitHub squash/rebase merges** — the author field is rewritten to
  ``<id>+<login>@users.noreply.github.com`` while the human's real identity stays
  in the trailer. GitHub wrote that field, so comparing it to the sign-off is
  meaningless: 45 of the 50 historical mismatches are this, and flagging them
  would be pure noise.
* **Genuine mismatches** — a real author address paired with somebody else's
  sign-off (e.g. author ``renanzai@zohomail.com`` signed off as
  ``hermes-agent@nousresearch.com``). These are real violations and this script
  reports them.

So the rule is: a commit whose author address is a GitHub noreply address is
exempt from the comparison (but must still carry a sign-off); any other author
address must match one of the commit's ``Signed-off-by`` addresses exactly.

Scope: only the commits given on the command line are judged. History is not
re-litigated — the acceptance criterion for #427 is that *new* commits stop
producing mismatches.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass

NOREPLY_SUFFIX = "@users.noreply.github.com"

#: Bot authors are exempt: DCO binds human authors, and an automation token
#: cannot make a human attestation.
BOT_MARKERS = ("[bot]", "bot@", "-bot@")

#: One ``Name <email>`` entry of a ``Signed-off-by`` trailer block.
_SIGNOFF_ENTRY_RE = re.compile(r"^(?P<name>.*?)\s*<(?P<email>[^>]*)>\s*$")

#: Format that yields the author address plus the whole sign-off block, so the
#: two cannot drift between separate invocations.
_LOG_FORMAT = "%H%x1f%ae%x1f%P%x1f%(trailers:key=Signed-off-by,valueonly)"
_FIELD_SEP = "\x1f"


@dataclass(frozen=True)
class Commit:
    sha: str
    author_email: str
    signoff_emails: tuple[str, ...]
    parent_count: int = 1


def parse_signoff(block: str) -> tuple[str, ...]:
    """Return the emails in a ``Signed-off-by`` trailer block, in order."""
    emails: list[str] = []
    for raw in block.splitlines():
        line = raw.strip()
        if not line:
            continue
        match = _SIGNOFF_ENTRY_RE.match(line)
        if match:
            emails.append(match.group("email").strip().lower())
    return tuple(emails)


def violation(commit: Commit) -> str | None:
    """Return a violation string for *commit*, or ``None`` when it is clean.

    Pure so the policy is testable without a git repository.
    """
    if commit.parent_count > 1:
        # Merge commits carry no authorship to attest; GitHub's DCO app skips them.
        return None
    author = commit.author_email.strip().lower()
    if any(marker in author for marker in BOT_MARKERS):
        return None
    if not commit.signoff_emails:
        return f"{commit.sha}: missing Signed-off-by trailer (author {author or '<none>'})"
    if author.endswith(NOREPLY_SUFFIX):
        # GitHub wrote this field; there is nothing to compare against.
        return None
    if author and author in commit.signoff_emails:
        return None
    return (
        f"{commit.sha}: Signed-off-by {', '.join(commit.signoff_emails)} "
        f"does not match author email {author or '<none>'}"
    )


def read_commits(revision_range: str) -> list[Commit]:
    """Load commits for *revision_range* (e.g. ``base..HEAD``) from git."""
    proc = subprocess.run(
        ["git", "log", "--format=" + _LOG_FORMAT, revision_range],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git log failed")
    commits: list[Commit] = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split(_FIELD_SEP)
        if len(parts) != 4:
            continue
        commits.append(
            Commit(
                sha=parts[0],
                author_email=parts[1],
                signoff_emails=parse_signoff(parts[3]),
                parent_count=len([p for p in parts[2].split() if p]),
            )
        )
    return commits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "range",
        nargs="?",
        default="HEAD~1..HEAD",
        help="commit range to judge (default: HEAD~1..HEAD). History is not re-litigated.",
    )
    args = parser.parse_args(argv)

    try:
        commits = read_commits(args.range)
    except RuntimeError as exc:
        print(f"check_signoff_identity: {exc}", file=sys.stderr)
        return 2

    if not commits:
        print(f"check_signoff_identity: no commits in {args.range!r} — nothing to judge")
        return 0

    problems = [text for text in (violation(c) for c in commits) if text]
    signed = sum(1 for c in commits if c.signoff_emails)
    print(f"check_signoff_identity: {len(commits)} commit(s), {signed} with a sign-off")
    if not problems:
        print("  every signer is its author (GitHub-noreply authors exempt)")
        return 0
    print(f"  {len(problems)} identity mismatch(es):")
    for text in problems:
        print(f"  - {text}")
    print("  Fix: set git config user.email to the address you sign off with.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
