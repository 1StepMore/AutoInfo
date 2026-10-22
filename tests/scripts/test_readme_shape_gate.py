"""README structural budget gate (#584).

scripts/ is not a package — load it via sys.path like the other script tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

import doc_inventory as di  # noqa: E402  (sys.path insert above)


def _readme(features: str, known: str) -> str:
    return (
        "## Features\n\n"
        f"{features}\n\n"
        "## Status\n\n| x | y |\n\n"
        "## Known Limitations\n\n"
        f"{known}\n\n"
        "## License\n"
    )


def test_accepts_thematic_features_and_short_limitations() -> None:
    text = _readme("- **A** — a\n- **B** — b", "- one\n- two")
    assert di._readme_shape_failures(text) == []


def test_rejects_feature_bullet_explosion() -> None:
    features = "\n".join(f"- **F{i}** — x" for i in range(13))
    failures = di._readme_shape_failures(_readme(features, "- one"))
    assert any("Features has 13 bullets" in f for f in failures)


def test_rejects_long_known_limitations() -> None:
    known = "\n".join(f"line {i}" for i in range(31))
    failures = di._readme_shape_failures(_readme("- **A** — a", known))
    assert any("Known Limitations is 31 lines" in f for f in failures)
