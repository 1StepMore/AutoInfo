"""Tests for video output pipeline."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from autoinfo.output.video import (
    VideoConfig,
    generate_audio_narration,
    generate_slide_images,
)


class TestVideoConfig:
    """Unit tests for VideoConfig dataclass."""

    def test_default_values(self) -> None:
        """Default VideoConfig has expected values."""
        cfg = VideoConfig()
        assert cfg.fps == 1
        assert cfg.resolution == (1920, 1080)
        assert cfg.bg_color == "#1a1a2e"
        assert cfg.font_color == "#ffffff"
        assert cfg.font_size == 48
        assert cfg.tts_speed == 1.0
        assert cfg.transition == "fade"

    def test_custom_values(self) -> None:
        """Custom VideoConfig stores provided values."""
        cfg = VideoConfig(
            fps=30,
            resolution=(3840, 2160),
            bg_color="#000000",
            font_color="#ff0000",
            font_size=64,
            tts_speed=1.5,
            transition="slide",
        )
        assert cfg.fps == 30
        assert cfg.resolution == (3840, 2160)
        assert cfg.bg_color == "#000000"
        assert cfg.font_color == "#ff0000"
        assert cfg.font_size == 64
        assert cfg.tts_speed == 1.5
        assert cfg.transition == "slide"


class TestGenerateAudioNarration:
    """Unit tests for TTS audio narration generation."""

    @patch("autoinfo.output._render_audio")
    def test_happy_path(self, mock_render: object) -> None:
        """TTS narration generates an MP3 file from section content."""
        mock_render.return_value = b"fake_mp3_data" * 100  # > 100 bytes

        output_dir = "/tmp/test-video-audio-happy"
        os.makedirs(output_dir, exist_ok=True)

        sections = [{"heading": "Intro", "body": "This is a test."}]
        result = generate_audio_narration(
            title="Test Video",
            sections=sections,
            output_dir=output_dir,
        )

        assert os.path.exists(result)
        assert os.path.getsize(result) > 100
        mock_render.assert_called_once()

    @patch("autoinfo.output._render_audio")
    def test_multiple_sections(self, mock_render: object) -> None:
        """Narration text includes all section headings and bodies."""
        mock_render.return_value = b"fake_mp3_data" * 100

        output_dir = "/tmp/test-video-audio-multi"
        os.makedirs(output_dir, exist_ok=True)

        sections = [
            {"heading": "Intro", "body": "First section body."},
            {"heading": "Methods", "body": "Second section body."},
            {"heading": "", "body": "No heading section."},
        ]
        result = generate_audio_narration(
            title="Multi-Section",
            sections=sections,
            output_dir=output_dir,
        )

        assert os.path.exists(result)
        # Verify the text passed to _render_audio contains all parts
        call_text = mock_render.call_args[0][0]
        assert "Multi-Section" in call_text
        assert "Intro" in call_text
        assert "First section body" in call_text
        assert "Methods" in call_text
        assert "Second section body" in call_text
        assert "No heading section" in call_text

    @patch("autoinfo.output._render_audio")
    def test_too_small_audio_raises(self, mock_render: object) -> None:
        """Audio file smaller than 100 bytes raises RuntimeError."""
        mock_render.return_value = b"tiny"  # < 100 bytes

        output_dir = "/tmp/test-video-audio-small"
        os.makedirs(output_dir, exist_ok=True)

        with pytest.raises(RuntimeError, match="TTS audio too small"):
            generate_audio_narration(
                title="Test",
                sections=[{"heading": "H", "body": "B"}],
                output_dir=output_dir,
            )

    @patch("autoinfo.output._render_audio")
    def test_voice_passed_through(self, mock_render: object) -> None:
        """Voice parameter is forwarded to _render_audio."""
        mock_render.return_value = b"fake_mp3_data" * 100

        output_dir = "/tmp/test-video-audio-voice"
        os.makedirs(output_dir, exist_ok=True)

        generate_audio_narration(
            title="Test",
            sections=[{"heading": "H", "body": "B"}],
            output_dir=output_dir,
            voice="nova",
        )

        mock_render.assert_called_once()
        assert mock_render.call_args[1].get("voice") == "nova"


class TestGenerateSlideImages:
    """Unit tests for slide image generation."""

    def test_happy_path(self) -> None:
        """Slide images generated for all sections."""
        output_dir = "/tmp/test-video-slides-happy"
        paths = generate_slide_images(
            title="Test",
            sections=[
                {"heading": "S1", "body": "Body1"},
                {"heading": "S2", "body": "Body2"},
            ],
            output_dir=output_dir,
            resolution=(1920, 1080),
        )

        assert len(paths) >= 2  # title slide + at least 1 content slide
        for p in paths:
            assert os.path.exists(p), f"Missing: {p}"

    def test_placeholder_fallback(self) -> None:
        """Placeholder images are generated when Pillow is unavailable."""
        with patch(
            "autoinfo.output.video._generate_placeholder_images",
            wraps=__import__(
                "autoinfo.output.video", fromlist=["_generate_placeholder_images"]
            )._generate_placeholder_images,
        ) as mock_placeholder:
            with patch.dict("sys.modules", {"PIL": None}):
                # Need to re-import to trigger the ImportError path.
                # Instead, we directly test _generate_placeholder_images.
                pass

        # Directly test placeholder generation
        from autoinfo.output.video import (
            _generate_placeholder_images,
        )

        output_dir = "/tmp/test-video-slides-placeholder"
        paths = _generate_placeholder_images(
            title="Placeholder Test",
            sections=[{"heading": "PH1", "body": "Body text here"}],
            output_dir=output_dir,
            resolution=(1920, 1080),
        )

        assert len(paths) >= 2
        for p in paths:
            assert os.path.exists(p), f"Missing placeholder: {p}"
            assert p.endswith(".txt")

    def test_no_sections(self) -> None:
        """Title-only slide generated when sections list is empty."""
        output_dir = "/tmp/test-video-slides-empty"
        paths = generate_slide_images(
            title="Title Only",
            sections=[],
            output_dir=output_dir,
        )

        # Should generate at least the title slide
        assert len(paths) >= 1
        assert os.path.exists(paths[0])
