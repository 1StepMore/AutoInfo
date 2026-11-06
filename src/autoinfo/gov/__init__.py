"""autoinfo.gov — the governance substrate (plan 2026-11-06).

Single contract (``.github/governance-contract.toml``), one entry point
(``python -m autoinfo.gov``), derived facts, a default-ON whole-repo drift
scan, the 8-state gate model, and the negative-control harness. Every module
here is stdlib-only at import time; the derive functions import autoinfo
subsystems lazily so ``scripts/gov.py`` can bootstrap an uninstalled checkout.

Verbs (all support ``--json``): status | derive | check | adjudicate | escalate
| run | doctor | acceptance | negative-control | confidence | contract | adr |
scripts.
"""

from __future__ import annotations

__all__ = ["contract", "facts", "scan", "artifacts", "adjudicate", "doctor", "platform"]
