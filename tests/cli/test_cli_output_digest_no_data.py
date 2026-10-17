"""Tests for the no-data persist guard on ``output digest`` (issue #525).

Before #525 ``autoinfo output digest --persist`` wrote the rendered artifact
unconditionally, so an empty knowledge base produced an empty-state stub under
``outputs/<domain>/``.  The MCP report path already suppressed this via the
``_is_no_data_product`` judgement (#385); that judgement is now shared as
:func:`autoinfo.output.is_no_data_product` and applied on the CLI persist
branch.

Two directions are covered:

(a) no-data empty state + ``--persist`` -> no file is written, no
    ``outputs/<domain>/`` directory is created, ``persisted_path`` is null;
(b) real digest + ``--persist`` -> the file is written (no regression).

The ``generate_*`` functions are imported inside the command body, so patching
``autoinfo.output.generate_digest`` resolves at call time.  ``cwd`` is moved to
``tmp_path`` so the tests never touch the real ``outputs/`` tree.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from autoinfo.cli import app

EMPTY_DIGEST = (
    "# Gaming \u2014 Digest\n\n"
    "This edition has no curated items yet. Check back after the next collection run."
)
REAL_DIGEST = "# Gaming \u2014 Digest\n\n## Top Stories\n\nReal content."


@pytest.fixture
def cli_runner() -> Any:
    """Return a CliRunner instance."""
    from typer.testing import CliRunner

    return CliRunner()


class TestOutputDigestNoDataPersistGuard:
    """``output digest --persist`` must not persist a no-data empty shell."""

    @patch("autoinfo.output.generate_digest", return_value=EMPTY_DIGEST)
    def test_persist_no_data_writes_no_file(
        self,
        mock_gen: MagicMock,
        cli_runner: Any,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Empty state + ``--persist`` -> no artifact, ``persisted_path`` null."""
        monkeypatch.chdir(tmp_path)
        result = cli_runner.invoke(
            app,
            [
                "--json",
                "output", "digest",
                "--domain", "gaming",
                "--period", "weekly",
                "--persist",
            ],
        )
        assert result.exit_code == 0, result.output
        envelope = json.loads(result.output)
        assert envelope["data"]["persisted_path"] is None
        assert not (tmp_path / "outputs").exists(), (
            "no-data digest created an outputs/ directory"
        )

    @patch("autoinfo.output.generate_digest", return_value=REAL_DIGEST)
    def test_persist_real_digest_writes_file(
        self,
        mock_gen: MagicMock,
        cli_runner: Any,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Real digest + ``--persist`` -> the artifact is written (no regression)."""
        monkeypatch.chdir(tmp_path)
        result = cli_runner.invoke(
            app,
            [
                "--json",
                "output", "digest",
                "--domain", "gaming",
                "--period", "weekly",
                "--persist",
            ],
        )
        assert result.exit_code == 0, result.output
        envelope = json.loads(result.output)
        persisted = envelope["data"]["persisted_path"]
        assert persisted is not None
        path = Path(persisted)
        assert path.exists()
        assert path.read_text(encoding="utf-8") == REAL_DIGEST
