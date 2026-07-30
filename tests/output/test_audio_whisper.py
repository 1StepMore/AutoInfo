"""Tests for Whisper TTS engine: _render_audio with engine="whisper".

Verifies that the whisper engine dispatches correctly, falls back gracefully,
and integrates with the existing engine resolution system.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from autoinfo.output import (
    _render_audio,
    _render_audio_openai,
    _render_audio_whisper,
)


class TestRenderAudioWhisper:
    """Tests for _render_audio with engine="whisper"."""

    @pytest.fixture(autouse=True)
    def mock_env_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTOINFO_LLM_API_KEY", "sk-whisper-test")

    def test_whisper_engine_dispatches_with_whisper_model(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Whisper engine sends model="whisper-1" to the OpenAI TTS API."""
        monkeypatch.setenv("AUTOINFO_LLM_API_KEY", "sk-whisper")

        mock_response = MagicMock()
        mock_response.content = b"whisper-mp3-bytes"
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.post") as mock_post:
            mock_post.return_value = mock_response
            result = _render_audio("Hello world", engine="whisper")

        assert isinstance(result, bytes)
        assert result == b"whisper-mp3-bytes"
        # Verify model parameter was "whisper-1"
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["model"] == "whisper-1"
        assert call_kwargs["json"]["voice"] == "alloy"

    def test_whisper_engine_custom_voice(self) -> None:
        """Whisper engine respects custom voice parameter."""
        mock_response = MagicMock()
        mock_response.content = b"nova-whisper"
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.post") as mock_post:
            mock_post.return_value = mock_response
            _render_audio("Hello", engine="whisper", voice="nova")

        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["model"] == "whisper-1"
        assert call_kwargs["json"]["voice"] == "nova"

    def test_whisper_falls_back_to_openai_on_api_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When whisper API call fails, engine falls back to openai (tts-1)."""
        monkeypatch.setenv("AUTOINFO_LLM_API_KEY", "sk-fallback")

        import httpx

        # First call (whisper) fails
        fail_response = MagicMock()
        fail_response.status_code = 404
        fail_response.text = "Not Found"
        fail_response.json.return_value = {"error": "model not found"}
        fail_request = MagicMock()
        http_error = httpx.HTTPStatusError(
            "Not Found", request=fail_request, response=fail_response
        )

        # Second call (openai fallback) succeeds
        success_response = MagicMock()
        success_response.content = b"fallback-openai-mp3"
        success_response.raise_for_status = MagicMock()

        with patch("httpx.post") as mock_post:
            mock_post.side_effect = [http_error, success_response]
            result = _render_audio("test", engine="whisper")

        assert result == b"fallback-openai-mp3"
        # Verify two API calls were made
        assert mock_post.call_count == 2
        # First call should have been whisper model
        assert mock_post.call_args_list[0][1]["json"]["model"] == "whisper-1"
        # Second call should have been tts-1 (fallback)
        assert mock_post.call_args_list[1][1]["json"]["model"] == "tts-1"

    def test_whisper_falls_back_on_network_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When whisper network request fails, falls back to openai."""
        monkeypatch.setenv("AUTOINFO_LLM_API_KEY", "sk-network")

        import httpx

        network_error = httpx.RequestError("Connection refused")

        success_response = MagicMock()
        success_response.content = b"network-fallback"
        success_response.raise_for_status = MagicMock()

        with patch("httpx.post") as mock_post:
            mock_post.side_effect = [network_error, success_response]
            result = _render_audio("test", engine="whisper")

        assert result == b"network-fallback"
        assert mock_post.call_count == 2

    def test_whisper_engine_empty_text_raises(self) -> None:
        """Empty text raises ValueError for whisper engine."""
        with pytest.raises(ValueError, match="Cannot render empty text"):
            _render_audio("", engine="whisper")

    def test_whisper_engine_text_truncated(self) -> None:
        """Text exceeding 4096 chars is truncated for whisper engine."""
        long_text = "x" * 5000
        mock_response = MagicMock()
        mock_response.content = b"truncated-whisper"
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.post") as mock_post:
            mock_post.return_value = mock_response
            _render_audio(long_text, engine="whisper")

        sent_input = mock_post.call_args[1]["json"]["input"]
        assert len(sent_input) < 4100
        assert "[truncated]" in sent_input


class TestRenderAudioWhisperDirect:
    """Tests for _render_audio_whisper() helper directly."""

    @pytest.fixture(autouse=True)
    def mock_env_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTOINFO_LLM_API_KEY", "sk-direct")

    def test_whisper_helper_returns_bytes(self) -> None:
        """_render_audio_whisper() directly returns MP3 bytes."""
        mock_response = MagicMock()
        mock_response.content = b"direct-whisper"
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.post") as mock_post:
            mock_post.return_value = mock_response
            result = _render_audio_whisper("test")

        assert result == b"direct-whisper"
        assert mock_post.call_args[1]["json"]["model"] == "whisper-1"

    def test_whisper_helper_falls_back_on_failure(self) -> None:
        """_render_audio_whisper() falls back to tts-1 model on failure."""
        import httpx

        fail_response = MagicMock()
        fail_response.status_code = 500
        fail_response.text = "Internal Error"
        fail_response.json.return_value = {"error": "server error"}
        fail_request = MagicMock()
        http_error = httpx.HTTPStatusError(
            "Server Error", request=fail_request, response=fail_response
        )

        success_response = MagicMock()
        success_response.content = b"fallback-from-whisper-helper"
        success_response.raise_for_status = MagicMock()

        with patch("httpx.post") as mock_post:
            mock_post.side_effect = [http_error, success_response]
            result = _render_audio_whisper("test")

        assert result == b"fallback-from-whisper-helper"
        assert mock_post.call_count == 2
        assert mock_post.call_args_list[1][1]["json"]["model"] == "tts-1"

    def test_whisper_helper_respects_voice(self) -> None:
        """_render_audio_whisper() passes voice through to API."""
        mock_response = MagicMock()
        mock_response.content = b"shimmer-whisper"
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.post") as mock_post:
            mock_post.return_value = mock_response
            _render_audio_whisper("Hello", voice="shimmer")

        assert mock_post.call_args[1]["json"]["voice"] == "shimmer"
        assert mock_post.call_args[1]["json"]["model"] == "whisper-1"


class TestEngineResolution:
    """Tests for engine validation with whisper in _render_audio()."""

    @pytest.fixture(autouse=True)
    def mock_env_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTOINFO_LLM_API_KEY", "sk-resolution")

    def test_whisper_is_valid_engine(self) -> None:
        """Engine "whisper" is accepted and dispatches correctly."""
        mock_response = MagicMock()
        mock_response.content = b"valid-whisper"
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_response):
            result = _render_audio("test", engine="whisper")

        assert result == b"valid-whisper"

    def test_unknown_engine_still_falls_back(self) -> None:
        """Invalid engine still falls back to openai (regression test)."""
        mock_response = MagicMock()
        mock_response.content = b"unknown-fallback"
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.post") as mock_post:
            mock_post.return_value = mock_response
            result = _render_audio("test", engine="invalid-engine")

        assert result == b"unknown-fallback"
        assert mock_post.call_args[1]["json"]["model"] == "tts-1"

    def test_openai_engine_uses_tts1_model(self) -> None:
        """Engine "openai" uses model="tts-1" (no regression)."""
        mock_response = MagicMock()
        mock_response.content = b"tts1-output"
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.post") as mock_post:
            mock_post.return_value = mock_response
            _render_audio("test", engine="openai")

        assert mock_post.call_args[1]["json"]["model"] == "tts-1"

    def test_whisper_engine_from_config(self, tmp_path: Path) -> None:
        """Config file with tts.engine=whisper triggers whisper dispatcher."""
        import yaml

        config_dir = tmp_path / ".autoinfo"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text(
            yaml.dump({"tts": {"engine": "whisper"}}),
            encoding="utf-8",
        )

        mock_response = MagicMock()
        mock_response.content = b"config-whisper"
        mock_response.raise_for_status = MagicMock()

        with patch(
            "autoinfo.output.get_config_path", return_value=config_file
        ):
            with patch("httpx.post") as mock_post:
                mock_post.return_value = mock_response
                result = _render_audio("test", engine=None)

        assert result == b"config-whisper"
        assert mock_post.call_args[1]["json"]["model"] == "whisper-1"


class TestOpenaiModelParam:
    """Tests that _render_audio_openai model parameter works and is backward-compatible."""

    @pytest.fixture(autouse=True)
    def mock_env_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTOINFO_LLM_API_KEY", "sk-model-test")

    def test_openai_defaults_to_tts1(self) -> None:
        """_render_audio_openai() defaults to model="tts-1"."""
        mock_response = MagicMock()
        mock_response.content = b"default-tts1"
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.post") as mock_post:
            mock_post.return_value = mock_response
            result = _render_audio_openai("test")

        assert result == b"default-tts1"
        assert mock_post.call_args[1]["json"]["model"] == "tts-1"

    def test_openai_custom_model(self) -> None:
        """_render_audio_openai() accepts custom model parameter."""
        mock_response = MagicMock()
        mock_response.content = b"custom-model"
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.post") as mock_post:
            mock_post.return_value = mock_response
            result = _render_audio_openai("test", model="custom-model-id")

        assert result == b"custom-model"
        assert mock_post.call_args[1]["json"]["model"] == "custom-model-id"
