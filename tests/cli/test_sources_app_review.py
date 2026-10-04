"""CLI regression for the app-review gate (#450).

Covers ``autoinfo sources add``:

- ``--requires-app-review --app-review-ack`` land on the new source and
  survive a save/load round trip (still True, not leaked into settings).
- Omitting both flags defaults to ``False`` and the source is not blocked
  by the fail-closed gate.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from autoinfo.cli.sources import app as _sources_app
from autoinfo.collect import _app_review_block_reason
from autoinfo.config import load_config

_MINIMAL_CONFIG = {
    "project": {"name": "Test", "created_at": ""},
    "llm": {"provider": "openai", "model": "gpt-4o-mini", "api_key": ""},
    "domains": [
        {
            "name": "test-domain",
            "active": True,
            "sources": [],
            "topics": [],
        }
    ],
}


@pytest.fixture
def empty_domain_config(tmp_path: Path) -> Path:
    config_dir = tmp_path / ".autoinfo"
    config_dir.mkdir(parents=True, exist_ok=True)
    with open(config_dir / "config.yaml", "w", encoding="utf-8") as fh:
        yaml.dump(_MINIMAL_CONFIG, fh, default_flow_style=False)

    cwd = Path.cwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(cwd)


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


def _get_source(name: str):
    config = load_config(Path.cwd() / ".autoinfo" / "config.yaml")
    domain = [d for d in config.domains if d.name == "test-domain"][0]
    return [s for s in domain.sources if s.name == name][0]


def test_add_with_app_review_flags_persists_and_round_trips(
    cli_runner: CliRunner, empty_domain_config: Path
) -> None:
    result = cli_runner.invoke(
        _sources_app,
        [
            "add",
            "--name",
            "reviewed-feed",
            "--url",
            "https://reviewed.example.com/rss",
            "--type",
            "rss",
            "--domain",
            "test-domain",
            "--requires-app-review",
            "--app-review-ack",
        ],
    )
    assert result.exit_code == 0, result.output

    src = _get_source("reviewed-feed")
    assert src.requires_app_review is True
    assert src.app_review_ack is True
    assert src.settings == {}

    # 存盘往返后仍在（load_config 重新解析同一文件）
    src2 = _get_source("reviewed-feed")
    assert src2.requires_app_review is True
    assert src2.app_review_ack is True
    assert not [k for k in src2.settings if "app_review" in k]


def test_add_without_flags_defaults_false_and_not_blocked(
    cli_runner: CliRunner, empty_domain_config: Path
) -> None:
    result = cli_runner.invoke(
        _sources_app,
        [
            "add",
            "--name",
            "plain-feed",
            "--url",
            "https://plain.example.com/rss",
            "--type",
            "rss",
            "--domain",
            "test-domain",
        ],
    )
    assert result.exit_code == 0, result.output

    src = _get_source("plain-feed")
    assert src.requires_app_review is False
    assert src.app_review_ack is False

    class _Plain:
        def requires_app_review(self) -> bool:
            return False

    assert _app_review_block_reason(src, _Plain()) is None
