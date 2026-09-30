"""Tests for the dependency version policy (issue #428).

`pyproject.toml` carries 38 concrete direct-dependency specifiers. Both
real-world breakages this repo suffered were *direct-dependency major jumps*
that were only caught after the fact and then bounded post-hoc: mcp 2.x broke
collection of 34 modules (#245), and pytest 9.1.1 removed
`EncodedFile.getvalue`, crashing caplog (#211). These tests lock the
incident-driven policy: the nine high-risk direct dependencies must carry an
upper bound, and their existing floors must not drift when a bound is bumped.

The tests parse `pyproject.toml` with the stdlib `tomllib` (Python >= 3.11, the
project floor) and touch nothing else — no network, no installs, no imports of
the package under test.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

_PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"

# High-risk direct dependencies: each has either shipped a breaking change to
# this repo, is a 0.x project (where a minor bump may remove APIs), or is a
# framework/SDK whose next major would change call sites we cannot audit ahead
# of time. The upper bounds are deliberately selective — not a policy of
# bounding everything.
HIGH_RISK = (
    "httpx",  # 0.x minors remove APIs; sync+async client surface is wide
    "fastapi",  # 1.0 is a breaking REST-framework release
    "uvicorn",  # rides FastAPI's 1.0 boundary; [standard] extra
    "litellm",  # major jumps change the completion call shape (#245 class)
    "trafilatura",  # 2.0 was a breaking extraction-pipeline jump
    "lxml",  # C-extension parser; majors break trafilatura's API use
    "beautifulsoup4",  # parser API is anchored at the 5.0 boundary
    "sqlite-vec",  # 0.x; index format is not a stable compatibility promise
    "stripe",  # SDK major jumps rename/move client APIs
)

# The floors as of the policy commit. A bound bump must never silently raise a
# floor: widening `<15` to `<16` is fine, but `>=9.0` -> `>=10.0` is a
# user-facing requirement change that needs its own decision.
FLOORS = {
    "httpx": "0.27",
    "fastapi": "0.115",
    "uvicorn": "0.32",
    "litellm": "1.40",
    "trafilatura": "1.8",
    "lxml": "5.0",
    "beautifulsoup4": "4.12",
    "sqlite-vec": "0.1",
    "stripe": "9.0",
}

_REQUIREMENT = re.compile(r"^(?P<name>[A-Za-z0-9._-]+)(?:\[(?P<extras>[^\]]*)\])?(?P<spec>.*)$")
_FLOOR = re.compile(r">=(?P<version>[0-9][^,<]*)")


def _specifier(raw: str) -> str:
    """Return the version-specifier tail of a requirement string."""
    match = _REQUIREMENT.match(raw.strip())
    assert match is not None, raw
    return match.group("spec")


def _direct_deps() -> dict[str, str]:
    with _PYPROJECT.open("rb") as handle:
        data = tomllib.load(handle)
    deps: dict[str, str] = {}
    for raw in data["project"]["dependencies"]:
        name = _REQUIREMENT.match(raw.strip())
        assert name is not None, raw
        deps[name.group("name")] = raw
    return deps


def test_high_risk_direct_deps_have_upper_bounds() -> None:
    deps = _direct_deps()

    for name in HIGH_RISK:
        assert name in deps, f"{name} is missing from [project].dependencies"
        specifier = _specifier(deps[name])
        assert "<" in specifier, f"{deps[name]!r} has no upper bound"


def test_floors_unchanged() -> None:
    deps = _direct_deps()

    for name, floor in FLOORS.items():
        match = _FLOOR.search(_specifier(deps[name]))
        assert match is not None, f"{deps[name]!r} has no lower bound"
        assert match.group("version") == floor, (
            f"{name} floor moved: expected >={floor}, got >={match.group('version')}"
        )
