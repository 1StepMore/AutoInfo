"""Bootstrap the single governance entry point (T04) — zero business logic.

Runs ``python -m autoinfo.gov`` semantics from a checkout where ``autoinfo``
may not be installed: puts ``src/`` on sys.path, then hands off. Every verb,
flag and exit code lives in ``autoinfo.gov.__main__`` (single implementation,
plan R4).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_SRC = ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from autoinfo.gov.__main__ import main  # noqa: E402 — bootstrap path setup first

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
