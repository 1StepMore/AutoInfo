"""Issue #364: a missing config file raises ``ConfigNotFoundError``.

``ConfigNotFoundError`` subclasses ``FileNotFoundError`` so existing
``except FileNotFoundError`` callers keep working, while MCP error
classification can surface the semantic ``ConfigNotFound`` code.
"""

from __future__ import annotations

import pytest

from autoinfo.config import ConfigNotFoundError, load_config


def test_missing_path_raises_config_not_found(tmp_path) -> None:
    missing = tmp_path / "nonexistent" / "x.yaml"

    with pytest.raises(ConfigNotFoundError):
        load_config(missing)


def test_config_not_found_is_file_not_found(tmp_path) -> None:
    missing = tmp_path / "nonexistent" / "x.yaml"

    with pytest.raises(ConfigNotFoundError) as excinfo:
        load_config(missing)

    assert isinstance(excinfo.value, FileNotFoundError)


def test_config_not_found_message_carries_path(tmp_path) -> None:
    missing = tmp_path / "nonexistent" / "x.yaml"

    with pytest.raises(ConfigNotFoundError) as excinfo:
        load_config(missing)

    assert str(missing) in str(excinfo.value)


def test_absolute_nonexistent_path_raises() -> None:
    with pytest.raises(ConfigNotFoundError):
        load_config("/nonexistent/x.yaml")
