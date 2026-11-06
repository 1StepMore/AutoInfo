"""Acceptance instrument bridge (T12/G6) — reuse, never rewrite.

The human-reserved semantics live in ``scripts/acceptance_report.py``
(``HUMAN_RESERVED`` + ``PENDING DIRECTOR SIGN-OFF`` + the machine-row
refusal). This module imports them — it MUST NOT restate them — and exposes
the guard the gov layer needs: a human-reserved dimension can never be
adjudicated by machine output.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from autoinfo.gov.contract import resolve_repo_root

ACCEPTANCE_SCRIPT = Path("scripts") / "acceptance_report.py"


def load_acceptance_module(root: Path | None = None) -> Any:
    """Import scripts/acceptance_report.py by path (scripts is not a package)."""
    if root is None:
        root = resolve_repo_root()
    path = root / ACCEPTANCE_SCRIPT
    if not path.is_file():
        raise FileNotFoundError(f"acceptance report script missing: {path}")
    spec = importlib.util.spec_from_file_location("gov_acceptance_report", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    # Register before exec: dataclass processing resolves cls.__module__ via
    # sys.modules — an unregistered module makes that lookup return None.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def assert_machine_allowed(dim_id: str) -> None:
    """Mirror the script's own refusal: human-reserved ids are not machine rows."""
    module = load_acceptance_module()
    if dim_id in module.HUMAN_RESERVED:
        fallback = module.RESERVED_TOKEN.get(dim_id, "PENDING HUMAN")
        raise ValueError(
            f"{dim_id} is human-reserved ({fallback}) — a machine "
            "verdict must never be produced for it; escalate instead (gov escalate)"
        )


def check() -> dict[str, Any]:
    """`gov acceptance` payload — the bridge is intact and refuses correctly."""
    module = load_acceptance_module()
    refused = False
    try:
        assert_machine_allowed("overall")
    except ValueError:
        refused = True
    return {
        "script": ACCEPTANCE_SCRIPT.as_posix(),
        "human_reserved": sorted(module.HUMAN_RESERVED),
        "reserved_token": dict(module.RESERVED_TOKEN),
        "machine_refusal_works": refused,
        "success": refused and bool(module.HUMAN_RESERVED),
    }
