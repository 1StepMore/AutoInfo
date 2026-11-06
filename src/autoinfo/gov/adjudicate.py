"""Authority-order adjudication (T02/G3): one winner, deterministically.

When two surfaces state the same fact, the contract's ``[authority].order``
picks the winner. ``gov adjudicate`` resolves candidate values against that
order so the rule is executable, not prose (DoD #4: same winner 3/3 runs).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from autoinfo.gov.contract import Contract


def authority_rank(source: str, order: tuple[str, ...]) -> int:
    """Rank of *source* under the authority order (lower wins).

    Matching rules: ``runtime:``-prefixed sources match the runtime entry;
    ``path/*`` entries match by prefix; ``README.md#status`` matches its base
    path; anything else is ``other_docs`` (assumed last; otherwise it ranks
    after every explicit entry).
    """
    fallback = len(order) - 1 if order else 0
    for rank, entry in enumerate(order):
        base = entry.split("#", 1)[0]
        if base == "runtime:src+derived_facts":
            if source.startswith(("runtime:", "derived:", "facts:")):
                return rank
        elif entry.endswith("/*") or entry.endswith("/**"):
            if source.startswith(entry.rsplit("*", 1)[0]):
                return rank
        elif source == base or source == entry:
            return rank
    return max(fallback, 0)


def parse_candidates(raw: str) -> list[dict[str, Any]]:
    """Parse 'README.md=151,CONTRIBUTING.md=999' → ranked candidate dicts.

    Raises ValueError on malformed input (callers map that to exit 2).
    """
    candidates: list[dict[str, Any]] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        source, sep, value = chunk.partition("=")
        if not sep or not source.strip() or not value.strip():
            raise ValueError(f"malformed candidate {chunk!r} (expected source=value)")
        candidates.append({"source": source.strip(), "value": int(value)})
    return candidates


def adjudicate(contract: Contract, fact: str, candidates_raw: str) -> dict[str, Any]:
    """Resolve the winning candidate for *fact* under the authority order."""
    candidates = parse_candidates(candidates_raw)
    if not candidates:
        raise ValueError("no candidates given")
    ranked: list[tuple[int, int, dict[str, Any]]] = []
    for index, cand in enumerate(candidates):
        rank = authority_rank(str(cand["source"]), contract.authority_order)
        entry = dict(cand)
        entry["rank"] = rank
        entry["authority"] = (
            contract.authority_order[rank] if rank < len(contract.authority_order) else "other_docs"
        )
        ranked.append((rank, index, entry))
    ranked.sort(key=lambda item: (item[0], item[1]))
    winner = ranked[0][2]
    return {
        "fact": fact,
        "winner": winner,
        "candidates": [entry for _, _, entry in ranked],
        "order": list(contract.authority_order),
        "distinct_values": len({int(c["value"]) for c in candidates}),
    }
