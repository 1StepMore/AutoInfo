"""Tests for the Azure Speech TTS engine (issue #647).

All tests mock ``httpx.post``; no real network call is made.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from autoinfo.output import _render_audio
from autoinfo.output import audio as audio_module
from autoinfo.output.audio import (
    AZURE_TTS_OUTPUT_FORMAT,
    AZURE_TTS_SSML_NS,
    AZURE_TTS_USER_AGENT,
    DEFAULT_AZURE_TTS_VOICE,
    _render_audio_azure,
)


def _ok_response(content: bytes = b"azure-mp3-bytes") -> MagicMock:
    response = MagicMock()
    response.status_code = 200
    response.content = content
    response.text = ""
    return response


class TestRenderAudioAzureDirect:
    """Tests for ``_render_audio_azure`` with mocked HTTP."""

    @pytest.fixture(autouse=True)
    def _credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AZURE_SPEECH_KEY", "azure-test-key")
        monkeypatch.setenv("AZURE_SPEECH_REGION", "eastasia")
        monkeypatch.setattr("autoinfo.output.get_config_path", lambda: None)

    def test_returns_mp3_bytes_and_posts_expected_request(self) -> None:
        with patch("autoinfo.output.audio.httpx.post") as mock_post:
            mock_post.return_value = _ok_response()
            result = _render_audio_azure("Hello Azure")

        assert result == b"azure-mp3-bytes"
        call = mock_post.call_args
        assert call.args[0] == "https://eastasia.tts.speech.microsoft.com/cognitiveservices/v1"
        headers = call.kwargs["headers"]
        assert headers["Ocp-Apim-Subscription-Key"] == "azure-test-key"
        assert headers["Content-Type"] == "application/ssml+xml"
        assert headers["X-Microsoft-OutputFormat"] == AZURE_TTS_OUTPUT_FORMAT
        assert headers["User-Agent"] == AZURE_TTS_USER_AGENT
        assert len(headers["User-Agent"]) < 255
        assert call.kwargs["timeout"] == 120.0

        ssml = call.kwargs["content"].decode("utf-8")
        assert ssml.startswith(
            f"<speak version='1.0' xmlns='{AZURE_TTS_SSML_NS}' xml:lang='zh-CN'>"
        )
        assert f"<voice name='{DEFAULT_AZURE_TTS_VOICE}'>Hello Azure</voice>" in ssml
        assert ssml.endswith("</speak>")

    def test_xml_escapes_text(self) -> None:
        with patch("autoinfo.output.audio.httpx.post") as mock_post:
            mock_post.return_value = _ok_response()
            _render_audio_azure("A & B <tag> C")

        ssml = mock_post.call_args.kwargs["content"].decode("utf-8")
        assert "A &amp; B &lt;tag&gt; C" in ssml
        assert "<tag>" not in ssml

    def test_infers_language_from_voice(self) -> None:
        with patch("autoinfo.output.audio.httpx.post") as mock_post:
            mock_post.return_value = _ok_response()
            _render_audio_azure("Hello", voice="en-US-JennyNeural")

        ssml = mock_post.call_args.kwargs["content"].decode("utf-8")
        assert "xml:lang='en-US'" in ssml
        assert "name='en-US-JennyNeural'" in ssml

    def test_missing_key_raises_actionable_runtimeerror(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
        with pytest.raises(RuntimeError, match="AZURE_SPEECH_KEY is not set"):
            _render_audio_azure("Hello")

    def test_missing_region_raises_actionable_runtimeerror(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
        with patch("autoinfo.output.get_config_path", return_value=None):
            with pytest.raises(RuntimeError, match="AZURE_SPEECH_REGION is not set"):
                _render_audio_azure("Hello")

    def test_http_error_includes_status_and_body(self) -> None:
        response = MagicMock()
        response.status_code = 401
        response.text = "Unauthorized: invalid subscription key"

        with patch("autoinfo.output.audio.httpx.post", return_value=response):
            with pytest.raises(RuntimeError, match="HTTP 401") as excinfo:
                _render_audio_azure("Hello")

        assert "Unauthorized: invalid subscription key" in str(excinfo.value)

    def test_http_error_body_is_truncated_to_200_chars(self) -> None:
        response = MagicMock()
        response.status_code = 400
        response.text = "x" * 500

        with patch("autoinfo.output.audio.httpx.post", return_value=response):
            with pytest.raises(RuntimeError) as excinfo:
                _render_audio_azure("Hello")

        message = str(excinfo.value)
        assert "HTTP 400" in message
        assert message.count("x") == 200

    def test_empty_audio_raises(self) -> None:
        with (
            patch(
                "autoinfo.output.audio.httpx.post",
                return_value=_ok_response(b""),
            ),
            pytest.raises(RuntimeError, match="empty audio data"),
        ):
            _render_audio_azure("Hello")

    def test_network_error_raises_runtimeerror(self) -> None:
        with (
            patch(
                "autoinfo.output.audio.httpx.post",
                side_effect=httpx.RequestError("connection refused"),
            ),
            pytest.raises(RuntimeError, match="Azure TTS network error"),
        ):
            _render_audio_azure("Hello")

    def test_timeout_is_forwarded(self) -> None:
        with patch("autoinfo.output.audio.httpx.post") as mock_post:
            mock_post.return_value = _ok_response()
            _render_audio_azure("Hello", timeout=7.5)

        assert mock_post.call_args.kwargs["timeout"] == 7.5


class TestRenderAudioAzureDispatch:
    """Tests for ``_render_audio(engine="azure")`` and the public alias."""

    @pytest.fixture(autouse=True)
    def _credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AZURE_SPEECH_KEY", "azure-test-key")
        monkeypatch.setenv("AZURE_SPEECH_REGION", "eastasia")
        monkeypatch.setattr("autoinfo.output.get_config_path", lambda: None)

    def test_engine_azure_dispatches(self) -> None:
        with patch("autoinfo.output.audio.httpx.post") as mock_post:
            mock_post.return_value = _ok_response()
            result = _render_audio("Hello", engine="azure")

        assert result == b"azure-mp3-bytes"
        assert "eastasia.tts.speech.microsoft.com" in mock_post.call_args.args[0]

    def test_engine_azure_strips_markdown(self) -> None:
        with patch("autoinfo.output.audio.httpx.post") as mock_post:
            mock_post.return_value = _ok_response()
            _render_audio("**bold** and *italic*", engine="azure")

        ssml = mock_post.call_args.kwargs["content"].decode("utf-8")
        assert "**" not in ssml
        assert "*" not in ssml
        assert "bold and italic" in ssml

    def test_engine_azure_truncates_long_text(self) -> None:
        with patch("autoinfo.output.audio.httpx.post") as mock_post:
            mock_post.return_value = _ok_response()
            _render_audio("x" * 5000, engine="azure")

        ssml = mock_post.call_args.kwargs["content"].decode("utf-8")
        assert "[truncated]" in ssml
        assert len(ssml) < 4300

    def test_public_render_audio_alias_uses_azure(self) -> None:
        with patch("autoinfo.output.audio.httpx.post") as mock_post:
            mock_post.return_value = _ok_response()
            result = audio_module.render_audio("Hello", engine="azure")

        assert result == b"azure-mp3-bytes"

    def test_unknown_engine_still_falls_back_to_openai(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("AUTOINFO_LLM_API_KEY", "sk-test")
        response = _ok_response(b"openai-fallback")

        with patch("autoinfo.output.audio.httpx.post", return_value=response):
            result = _render_audio("Hello", engine="not-a-real-engine")

        assert result == b"openai-fallback"


class TestAzureConfig:
    """Tests for the Azure fields on ``TTSConfig``."""

    def test_defaults(self) -> None:
        from autoinfo.config import TTSConfig

        tts = TTSConfig()
        assert tts.azure_voice == "zh-CN-XiaoxiaoNeural"
        assert tts.engine == "local"

    def test_region_defaults_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from autoinfo.config import TTSConfig

        monkeypatch.setenv("AZURE_SPEECH_REGION", "westeurope")
        assert TTSConfig().azure_region == "westeurope"

    def test_explicit_values(self) -> None:
        from autoinfo.config import TTSConfig

        tts = TTSConfig(engine="azure", azure_voice="en-US-JennyNeural", azure_region="westus")
        assert tts.engine == "azure"
        assert tts.azure_voice == "en-US-JennyNeural"
        assert tts.azure_region == "westus"
