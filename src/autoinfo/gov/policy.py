"""Capability boundary — profile-based decide() (T15/G4).

One contract, two runtime profiles (``[profiles]``). ``decide()`` is the ONLY
arbitration point: ``attempted: true`` is produced exclusively by a request
that really passed through here (and is written to the attempt log) — never
by table lookups or hardcoding. A probe never executes side effects: it only
asks the policy layer, so "not really pushed" can never mean attempted=false.

Denial codes: FORBIDDEN (denied by the profile's deny list or not covered by
its allow list), plus exit-mapping done by the caller.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ATTEMPT_LOG = "attempts.jsonl"


def _matches(action: str, pattern: str) -> bool:
    """Glob-style match for rules like 'run:gov-*'; exact otherwise."""
    if pattern == "*":
        return True
    if "*" in pattern:
        prefix, _, suffix = pattern.partition("*")
        return action.startswith(prefix) and action.endswith(suffix)
    return action == pattern


def decide(
    profiles: dict[str, dict[str, list[str]]],
    profile: str,
    action: str,
    log_dir: Path | None = None,
) -> dict[str, Any]:
    """Arbitrate *action* under *profile*. The only source of attempted=True."""
    cfg = profiles.get(profile)
    if cfg is None:
        return {
            "allowed": False,
            "code": "UNKNOWN_PROFILE",
            "reason": f"profile {profile!r} is not declared in the contract [profiles]",
            "attempted": False,  # the request never reached a real policy layer
            "profile": profile,
            "action": action,
        }
    denied_by = next((rule for rule in cfg.get("deny", []) if _matches(action, rule)), None)
    allowed_by = next((rule for rule in cfg.get("allow", []) if _matches(action, rule)), None)
    if denied_by is not None:
        result: dict[str, Any] = {
            "allowed": False,
            "code": "FORBIDDEN",
            "reason": f"denied by [profiles.{profile}] deny rule {denied_by!r}",
            "attempted": True,
            "profile": profile,
            "action": action,
            "matched_rule": denied_by,
        }
    elif allowed_by is not None:
        result = {
            "allowed": True,
            "code": "ALLOWED",
            "reason": f"allowed by [profiles.{profile}] allow rule {allowed_by!r}",
            "attempted": True,
            "profile": profile,
            "action": action,
            "matched_rule": allowed_by,
        }
    else:
        # Default-deny: an action neither allowed nor denied is not granted.
        result = {
            "allowed": False,
            "code": "FORBIDDEN",
            "reason": f"not covered by [profiles.{profile}] allow list (default-deny)",
            "attempted": True,
            "profile": profile,
            "action": action,
        }
    if log_dir is not None:
        _log_attempt(log_dir, result)
    return result


def _log_attempt(log_dir: Path, result: dict[str, Any]) -> None:
    """Append the attempt record — the E3 evidence that decide() really ran."""
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        record = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **result}
        with (log_dir / ATTEMPT_LOG).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
    except OSError:
        pass  # the attempt log is evidence, not a control — never fail on it


def diff_profiles(profiles: dict[str, dict[str, list[str]]]) -> list[str]:
    """Semantic differences between declared profiles beyond their intent.

    Profiles are ALLOWED to differ in their rules (that is their point); the
    diff asserted empty by DoD #8 is structural: same key sets, same rule
    shape, no unknown fields — two profiles of ONE contract, not two contracts.
    """
    if not profiles:
        return ["no profiles declared"]
    diffs: list[str] = []
    key_sets = {name: sorted(body) for name, body in profiles.items()}
    first = next(iter(key_sets))
    for name, keys in key_sets.items():
        if keys != key_sets[first]:
            diffs.append(
                f"profile {name!r} keys {keys} != profile {first!r} keys {key_sets[first]}"
            )
    for name, body in profiles.items():
        for field in ("allow", "deny"):
            rules = body.get(field, [])
            if any(not isinstance(rule, str) or not rule for rule in rules):
                diffs.append(f"profile {name!r}.{field} contains empty/non-string rules")
    return diffs
