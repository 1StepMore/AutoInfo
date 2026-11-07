"""Human escalation routing (T12/G6) — receiver, deadline, OVERDUE, no folding.

A machine cannot settle a subjective call: it escalates to a human receiver
(role != executor.profile — the executor must never receive its own
escalation), with a deadline. Past the deadline the escalation is OVERDUE and
the escalations gate is FAIL. The aggregation never folds an open escalation
into PASS.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from autoinfo.gov.contract import Contract

STORE_REL = Path(".autoinfo") / "gov" / "escalations.json"
DEFAULT_ROLE = "human.director"
DEFAULT_CHANNEL = "github-issue"
DEFAULT_DAYS = 7
FORBIDDEN_ROLE = "executor.profile"


class EscalationError(Exception):
    """Malformed escalation request — exit-2 class."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load_store(root: Path) -> dict[str, Any]:
    path = root / STORE_REL
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"escalations": []}
    if not isinstance(data, dict) or not isinstance(data.get("escalations"), list):
        return {"escalations": []}
    return data


def _save_store(root: Path, store: dict[str, Any]) -> None:
    path = root / STORE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(store, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _compute_state(deadline: str) -> str:
    try:
        dl = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
    except ValueError:
        return "OVERDUE"  # an unreadable deadline can never protect the human
    return "PENDING" if dl >= _now() else "OVERDUE"


def escalate(
    contract: Contract,
    item: str,
    role: str = DEFAULT_ROLE,
    channel: str = DEFAULT_CHANNEL,
    deadline: str | None = None,
) -> dict[str, Any]:
    """Get-or-create the escalation for *item*; recompute its state."""
    if role == FORBIDDEN_ROLE:
        # The executor must never receive its own escalation (plan T12, exit 2).
        raise EscalationError(
            f"receiver.role must not be {FORBIDDEN_ROLE!r} — an executor cannot "
            "adjudicate its own work; route to a human role"
        )
    store = _load_store(contract.root)
    entries = store["escalations"]
    record = next((e for e in entries if e.get("item") == item), None)
    if record is None:
        created = _now()
        record = {
            "item": item,
            "receiver": {"role": role, "channel": channel},
            "deadline": deadline
            or (created + timedelta(days=DEFAULT_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "created": created.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        entries.append(record)
    elif deadline is not None:
        # Re-routing/chasing an escalation updates the deadline in place —
        # this is how a PENDING item is driven to OVERDUE (DoD #9).
        record["deadline"] = deadline
    _save_store(contract.root, store)
    record["escalation"] = {"state": _compute_state(str(record["deadline"]))}
    return record


def pending(root: Path) -> list[dict[str, Any]]:
    """All open escalations (PENDING or OVERDUE) for the nightly report."""
    store = _load_store(root)
    out: list[dict[str, Any]] = []
    for record in store["escalations"]:
        state = _compute_state(str(record.get("deadline", "")))
        out.append({**record, "escalation": {"state": state}})
    return out
