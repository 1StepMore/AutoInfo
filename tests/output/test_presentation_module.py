"""Direct coverage for the extracted presentation module (#582 phase 2).

``generate_presentation`` tests patch the LLM seam at the hub, so the moved
``_call_llm_for_presentation`` body and the mkslides subprocess fallbacks are
not exercised there.  These tests drive those paths directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from autoinfo.output.presentation import (
    _call_llm_for_presentation,
    _render_presentation_mkslides,
)


def _config() -> MagicMock:
    cfg = MagicMock()
    cfg.llm.resolve_model.return_value = "test/model"
    cfg.llm.json_mode = False
    cfg.llm.reasoning_model = False
    cfg.llm.api_key = ""
    cfg.llm.base_url = ""
    return cfg


def _response(content: str) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    return response


class TestCallLlmForPresentation:
    def test_success_returns_parsed_json(self) -> None:
        with (
            patch("autoinfo.output.get_config_path", return_value=None),
            patch("autoinfo.output.Config", return_value=_config()),
            patch(
                "autoinfo.output.call_with_fallback",
                return_value=_response('{"slides": [{"title": "T"}]}'),
            ) as llm,
            patch("autoinfo.output.get_prompt", return_value="system"),
            patch(
                "autoinfo.output._parse_json_response",
                return_value={"slides": [{"title": "T"}]},
            ),
        ):
            result = _call_llm_for_presentation("prompt", 3)

        assert result == {"slides": [{"title": "T"}]}
        assert llm.call_args.kwargs["model"] == "test/model"

    def test_loads_config_when_file_exists(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text("llm: {}\n")
        with (
            patch("autoinfo.output.get_config_path", return_value=config_file),
            patch("autoinfo.output.load_config", return_value=_config()) as load,
            patch(
                "autoinfo.output.call_with_fallback",
                return_value=_response('{"slides": []}'),
            ),
            patch("autoinfo.output.get_prompt", return_value="system"),
            patch("autoinfo.output._parse_json_response", return_value={"slides": []}),
        ):
            assert _call_llm_for_presentation("prompt", 3) == {"slides": []}
        load.assert_called_once_with(config_file)

    def test_llm_failure_returns_empty_mapping(self) -> None:
        with (
            patch("autoinfo.output.get_config_path", return_value=None),
            patch("autoinfo.output.Config", return_value=_config()),
            patch("autoinfo.output.call_with_fallback", side_effect=RuntimeError("down")),
            patch("autoinfo.output.get_prompt", return_value="system"),
        ):
            assert _call_llm_for_presentation("prompt", 3) == {}


class TestMkslidesFallbacks:
    @pytest.fixture(autouse=True)
    def _html_fallback(self) -> Any:
        with patch(
            "autoinfo.output._render_presentation_html", return_value="<html>fallback</html>"
        ) as fallback:
            yield fallback

    def _context(self) -> dict[str, Any]:
        return {
            "title": "T",
            "domain": "d",
            "theme": "black",
            "slides": [{"title": "S", "content": "C", "bullets": ["b"], "notes": "n"}],
        }

    def test_missing_binary_falls_back(self, _html_fallback: Any) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = _render_presentation_mkslides(self._context())
        assert result == "<html>fallback</html>"
        _html_fallback.assert_called_once()

    def test_timeout_falls_back(self, _html_fallback: Any) -> None:
        import subprocess

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("mkslides", 30)):
            result = _render_presentation_mkslides(self._context())
        assert result == "<html>fallback</html>"

    def test_nonzero_exit_falls_back(self, _html_fallback: Any) -> None:
        with patch("subprocess.run", return_value=MagicMock(returncode=1, stderr="boom")):
            result = _render_presentation_mkslides(self._context())
        assert result == "<html>fallback</html>"

    def test_success_returns_built_html(self, _html_fallback: Any) -> None:
        def fake_run(*args: Any, **kwargs: Any) -> MagicMock:
            cwd = Path(kwargs["cwd"])
            out = cwd / "public"
            out.mkdir()
            (out / "index.html").write_text("<html>built</html>", encoding="utf-8")
            return MagicMock(returncode=0, stderr="")

        with patch("subprocess.run", side_effect=fake_run):
            result = _render_presentation_mkslides(self._context())
        assert result == "<html>built</html>"
        _html_fallback.assert_not_called()

    def test_no_html_output_falls_back(self, _html_fallback: Any) -> None:
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stderr="")):
            result = _render_presentation_mkslides(self._context())
        assert result == "<html>fallback</html>"

    def test_unexpected_exception_falls_back(self, _html_fallback: Any) -> None:
        with patch("subprocess.run", side_effect=OSError("disk")):
            result = _render_presentation_mkslides(self._context())
        assert result == "<html>fallback</html>"
