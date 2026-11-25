"""Tests for the Azure Speech TTS engine (issue #647).

All tests mock ``httpx.post``; no real network call is made.
"""

from __future__ import annotations

import re
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


class TestAzureOutputFormatTier:
    """Guard: all Azure audio ships at the 48 kHz / 192 kbps tier (#926 step 1).

    The format-structure gate only asserts ``bitrate > 0``, so it cannot
    tell 48 kbps from 192 kbps — these tests are the only automated
    protection against silently reintroducing the old 24 kHz / 48 kbps tier.
    """

    _FORMAT_PATTERN = re.compile(
        r"^audio-(?P<sample_rate_khz>\d+)khz-(?P<bitrate_kbps>\d+)kbitrate-mono-mp3$"
    )

    def test_constant_is_the_high_tier(self) -> None:
        assert AZURE_TTS_OUTPUT_FORMAT == "audio-48khz-192kbitrate-mono-mp3"

    def test_format_string_parses_to_48khz_192kbps(self) -> None:
        match = self._FORMAT_PATTERN.match(AZURE_TTS_OUTPUT_FORMAT)
        assert match is not None, f"unparseable format: {AZURE_TTS_OUTPUT_FORMAT!r}"
        assert int(match.group("sample_rate_khz")) * 1000 == 48000
        assert int(match.group("bitrate_kbps")) * 1000 == 192000

    def test_request_payload_uses_module_constant(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The real request path must carry ``AZURE_TTS_OUTPUT_FORMAT`` verbatim,
        so a hard-coded low tier cannot sneak back into ``_render_audio_azure``."""
        monkeypatch.setenv("AZURE_SPEECH_KEY", "azure-test-key")
        monkeypatch.setenv("AZURE_SPEECH_REGION", "eastasia")
        monkeypatch.setattr("autoinfo.output.get_config_path", lambda: None)

        with patch("autoinfo.output.audio.httpx.post") as mock_post:
            mock_post.return_value = _ok_response()
            _render_audio_azure("Hello")

        headers = mock_post.call_args.kwargs["headers"]
        assert headers["X-Microsoft-OutputFormat"] == AZURE_TTS_OUTPUT_FORMAT
        assert headers["X-Microsoft-OutputFormat"] == "audio-48khz-192kbitrate-mono-mp3"


class TestAudioProbeRecordedInAudit:
    """#926 第 2 步（owner 2026-11-25 裁定）：阈值不动，改为把实测码率记进 sidecar。"""

    def test_probe_reports_real_mp3_properties(self, tmp_path) -> None:
        import shutil
        import subprocess

        if shutil.which("ffmpeg") is None:
            pytest.skip("ffmpeg not installed")
        mp3 = tmp_path / "sample.mp3"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "quiet",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=0.3",
                "-b:a",
                "192k",
                "-ar",
                "48000",
                "-ac",
                "1",
                str(mp3),
            ],
            check=True,
        )
        probe = audio_module.probe_audio_bytes(mp3.read_bytes())
        assert probe["probe"] == "ok", probe
        assert probe["codec_name"] == "mp3"
        assert int(probe["sample_rate"]) == 48000
        assert int(probe["bit_rate"]) >= 128000
        assert probe["bytes"] == mp3.stat().st_size

    def test_probe_degrades_without_raising(self, monkeypatch) -> None:
        monkeypatch.setattr(audio_module.shutil, "which", lambda name: None)
        probe = audio_module.probe_audio_bytes(b"not really mp3")
        assert probe == {"probe": "unavailable", "reason": "ffprobe not on PATH"}

    def test_empty_payload_is_reported_not_raised(self) -> None:
        assert audio_module.probe_audio_bytes(b"")["probe"] == "empty"

    def test_render_audio_writes_probe_into_audit(self, monkeypatch, tmp_path) -> None:
        # 用真实 mp3 字节，确保 probe 走通；引擎本身被替身，不碰网络。
        import shutil
        import subprocess

        if shutil.which("ffmpeg") is None:
            pytest.skip("ffmpeg not installed")
        path = str(tmp_path / "probe-src.mp3")
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "quiet",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=0.2",
                "-b:a",
                "192k",
                path,
            ],
            check=True,
        )
        payload = open(path, "rb").read()
        monkeypatch.setattr(audio_module, "_render_audio_openai", lambda *a, **k: payload)
        audit: dict = {}
        out = _render_audio("hello world", engine="openai", audit_out=audit)
        assert out == payload
        assert audit["audio_probe"]["probe"] == "ok"
        assert int(audit["audio_probe"]["bit_rate"]) >= 128000
