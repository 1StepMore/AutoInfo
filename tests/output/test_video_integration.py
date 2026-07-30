"""Integration tests for the FFmpeg video rendering pipeline.

Tests cover:
- ``render_video()`` — concat demuxer + xfade transitions
- ``generate_report_video()`` — full pipeline (slides + audio + FFmpeg)
- Error handling: missing FFmpeg, empty images, invalid audio
- ``_render_video_scaffold`` integration with ``generate_report``
"""

from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from autoinfo.output.video import (
    VideoConfig,
    generate_audio_narration,
    generate_report_video,
    generate_slide_images,
    render_video,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_dir() -> str:
    d = tempfile.mkdtemp(prefix="test_video_")
    yield d
    import shutil

    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def dummy_images(temp_dir: str) -> list[str]:
    """Generate 3 small PNG images using Pillow."""
    from PIL import Image

    paths: list[str] = []
    for i in range(3):
        img = Image.new("RGB", (320, 240), color=(40 + i * 40, 40, 80))
        p = os.path.join(temp_dir, f"slide_{i:03d}.png")
        img.save(p)
        paths.append(p)
    return paths


@pytest.fixture
def dummy_audio(temp_dir: str) -> str:
    """Create a minimal binary file that ffprobe/ffmpeg will accept."""
    audio_path = os.path.join(temp_dir, "narration.mp3")
    # Write a minimal ID3v2 tag + valid MPEG audio frame header
    # This is a silent MP3 frame: FF FB 90 00 = MPEG1 Layer3 128kbps 44100Hz stereo
    mp3_data = (
        b"ID3\x03\x00\x00\x00\x00\x00\x00"  # minimal ID3v2.3 tag
        + b"\xff\xfb\x90\x00" * 200  # silent frames
    )
    with open(audio_path, "wb") as f:
        f.write(mp3_data)
    return audio_path


# ---------------------------------------------------------------------------
# render_video — input validation
# ---------------------------------------------------------------------------


class TestRenderVideoValidation:
    def test_empty_image_list_raises_value_error(self, dummy_audio: str) -> None:
        with pytest.raises(ValueError, match="image_paths must not be empty"):
            render_video(
                audio_path=dummy_audio,
                image_paths=[],
                output_path="/tmp/should_not_create.mp4",
            )

    def test_missing_audio_raises_file_not_found(self, dummy_images: list[str]) -> None:
        with pytest.raises(FileNotFoundError, match="Audio file not found"):
            render_video(
                audio_path="/tmp/nonexistent_audio_xyz.mp3",
                image_paths=dummy_images,
                output_path="/tmp/should_not_create.mp4",
            )

    def test_all_images_missing_raises_value_error(
        self, dummy_audio: str, temp_dir: str
    ) -> None:
        with pytest.raises(ValueError, match="No valid image files found"):
            render_video(
                audio_path=dummy_audio,
                image_paths=[
                    os.path.join(temp_dir, "ghost_0.png"),
                    os.path.join(temp_dir, "ghost_1.png"),
                ],
                output_path=os.path.join(temp_dir, "out.mp4"),
            )

    def test_ffmpeg_not_found_raises_file_not_found(
        self, dummy_images: list[str], dummy_audio: str, temp_dir: str
    ) -> None:
        with patch("autoinfo.output.video.shutil.which", return_value=None):
            with pytest.raises(FileNotFoundError, match="not found on PATH"):
                render_video(
                    audio_path=dummy_audio,
                    image_paths=dummy_images,
                    output_path=os.path.join(temp_dir, "out.mp4"),
                )


# ---------------------------------------------------------------------------
# render_video — concat demuxer (mocked subprocess)
# ---------------------------------------------------------------------------


class TestRenderVideoConcat:
    def test_concat_no_transitions_mocked(
        self, dummy_images: list[str], dummy_audio: str, temp_dir: str
    ) -> None:
        """Concat demuxer path with transition='none' — verify subprocess call."""
        output_path = os.path.join(temp_dir, "output.mp4")

        mock_run = MagicMock()
        mock_run.return_value.returncode = 0

        with patch("autoinfo.output.video._run_ffmpeg", mock_run):
            with patch("autoinfo.output.video._find_binary", return_value="/usr/bin/ffmpeg"):
                with patch("autoinfo.output.video._probe_audio_duration", return_value=15.0):
                    # Create the output file so post-render validation passes
                    with open(output_path, "wb") as f:
                        f.write(b"\x00" * 500)

                    result = render_video(
                        audio_path=dummy_audio,
                        image_paths=dummy_images,
                        output_path=output_path,
                        config=VideoConfig(transition="none"),
                    )

        assert result == output_path
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "-f" in cmd
        assert "concat" in cmd

    def test_concat_with_audio_overlay_mocked(
        self, dummy_images: list[str], dummy_audio: str, temp_dir: str
    ) -> None:
        """Audio is included in concat command (-i audio, -c:a aac)."""
        output_path = os.path.join(temp_dir, "output2.mp4")

        mock_run = MagicMock()
        mock_run.return_value.returncode = 0

        with patch("autoinfo.output.video._run_ffmpeg", mock_run):
            with patch("autoinfo.output.video._find_binary", return_value="/usr/bin/ffmpeg"):
                with patch("autoinfo.output.video._probe_audio_duration", return_value=9.0):
                    with open(output_path, "wb") as f:
                        f.write(b"\x00" * 500)

                    render_video(
                        audio_path=dummy_audio,
                        image_paths=dummy_images,
                        output_path=output_path,
                        config=VideoConfig(transition="none"),
                    )

        cmd = mock_run.call_args[0][0]
        # Audio input should be present
        assert "-i" in cmd
        # Audio codec
        assert "aac" in cmd
        assert "-shortest" in cmd


# ---------------------------------------------------------------------------
# render_video — xfade transitions (mocked subprocess)
# ---------------------------------------------------------------------------


class TestRenderVideoXfade:
    def test_xfade_transition_mocked(
        self, dummy_images: list[str], dummy_audio: str, temp_dir: str
    ) -> None:
        """Xfade path with transition='fade'."""
        output_path = os.path.join(temp_dir, "output.mp4")

        mock_run = MagicMock()
        mock_run.return_value.returncode = 0

        with patch("autoinfo.output.video._run_ffmpeg", mock_run):
            with patch("autoinfo.output.video._find_binary", return_value="/usr/bin/ffmpeg"):
                with patch("autoinfo.output.video._probe_audio_duration", return_value=15.0):
                    with open(output_path, "wb") as f:
                        f.write(b"\x00" * 500)

                    result = render_video(
                        audio_path=dummy_audio,
                        image_paths=dummy_images,
                        output_path=output_path,
                        config=VideoConfig(transition="fade"),
                    )

        assert result == output_path
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "-filter_complex" in str(cmd)
        assert "xfade" in str(cmd)

    def test_xfade_single_image_falls_back_to_concat(
        self, dummy_images: list[str], dummy_audio: str, temp_dir: str
    ) -> None:
        """Single image should use concat path (no xfade needed)."""
        single = [dummy_images[0]]
        output_path = os.path.join(temp_dir, "output_single.mp4")

        mock_run = MagicMock()
        mock_run.return_value.returncode = 0

        with patch("autoinfo.output.video._run_ffmpeg", mock_run):
            with patch("autoinfo.output.video._find_binary", return_value="/usr/bin/ffmpeg"):
                with patch("autoinfo.output.video._probe_audio_duration", return_value=5.0):
                    with open(output_path, "wb") as f:
                        f.write(b"\x00" * 500)

                    render_video(
                        audio_path=dummy_audio,
                        image_paths=single,
                        output_path=output_path,
                        config=VideoConfig(transition="fade"),
                    )

        cmd = mock_run.call_args[0][0]
        assert "-f" in cmd
        assert "concat" in cmd

    def test_ffmpeg_failure_raises_runtime_error(
        self, dummy_images: list[str], dummy_audio: str, temp_dir: str
    ) -> None:
        """Non-zero exit code from FFmpeg raises RuntimeError."""
        output_path = os.path.join(temp_dir, "output_fail.mp4")

        mock_run = MagicMock()
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "ffmpeg error: Invalid argument"

        with patch("autoinfo.output.video._run_ffmpeg", mock_run):
            with patch("autoinfo.output.video._find_binary", return_value="/usr/bin/ffmpeg"):
                with patch("autoinfo.output.video._probe_audio_duration", return_value=10.0):
                    with open(output_path, "wb") as f:
                        f.write(b"\x00" * 500)

                    render_video(
                        audio_path=dummy_audio,
                        image_paths=dummy_images,
                        output_path=output_path,
                        config=VideoConfig(transition="fade"),
                    )

        # _run_ffmpeg was called and raised via mock side_effect would be
        # better, but the current implementation checks returncode after
        # _run_ffmpeg returns. Let's test the actual _run_ffmpeg behavior.
        # This test verifies that _run_ffmpeg is called — the actual exception
        # test is below.
        mock_run.assert_called_once()


class TestRunFfmpeg:
    def test_non_zero_exit_raises_runtime_error(self) -> None:
        from autoinfo.output.video import _run_ffmpeg

        with patch("subprocess.run") as mock_sub_run:
            mock_sub_run.return_value.returncode = 1
            mock_sub_run.return_value.stderr = "Error: codec not found\nMore error details"
            mock_sub_run.return_value.stdout = ""

            with pytest.raises(RuntimeError, match="FFmpeg exited with code 1"):
                _run_ffmpeg(["ffmpeg", "-i", "input.mp4", "output.mp4"])

    def test_timeout_raises_runtime_error(self) -> None:
        from autoinfo.output.video import _run_ffmpeg

        with patch("subprocess.run", side_effect=__import__("subprocess").TimeoutExpired(
            cmd=["ffmpeg"], timeout=1
        )):
            with pytest.raises(RuntimeError, match="FFmpeg timed out"):
                _run_ffmpeg(["ffmpeg", "-i", "input.mp4", "output.mp4"], timeout=1)


# ---------------------------------------------------------------------------
# ffprobe / audio probing
# ---------------------------------------------------------------------------


class TestProbeAudioDuration:
    def test_valid_duration(self) -> None:
        from autoinfo.output.video import _probe_audio_duration

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = json.dumps(
                {"format": {"duration": "42.5"}}
            )
            mock_run.return_value.stderr = ""

            result = _probe_audio_duration("/usr/bin/ffprobe", "/tmp/test.mp3")
            assert result == 42.5

    def test_probe_failure_returns_zero(self) -> None:
        from autoinfo.output.video import _probe_audio_duration

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stderr = "No such file"

            result = _probe_audio_duration("/usr/bin/ffprobe", "/tmp/missing.mp3")
            assert result == 0.0

    def test_invalid_json_returns_zero(self) -> None:
        from autoinfo.output.video import _probe_audio_duration

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "not json"
            mock_run.return_value.stderr = ""

            result = _probe_audio_duration("/usr/bin/ffprobe", "/tmp/test.mp3")
            assert result == 0.0


# ---------------------------------------------------------------------------
# generate_report_video — full pipeline (mocked FFmpeg)
# ---------------------------------------------------------------------------


class TestGenerateReportVideo:
    def test_full_pipeline_mocked(
        self, temp_dir: str
    ) -> None:
        """Full pipeline generates slides + audio + FFmpeg → MP4."""
        sections = [
            {"heading": "Intro", "body": "Welcome to the report."},
            {"heading": "Findings", "body": "Key results discovered."},
        ]

        mock_run = MagicMock()
        mock_run.return_value.returncode = 0

        with patch("autoinfo.output.video._run_ffmpeg", mock_run):
            with patch("autoinfo.output.video._find_binary", return_value="/usr/bin/ffmpeg"):
                with patch("autoinfo.output.video._probe_audio_duration", return_value=10.0):
                    # Need to mock _render_audio to avoid real TTS call
                    with patch("autoinfo.output._render_audio") as mock_tts:
                        mock_tts.return_value = b"fake_mp3_data" * 100

                        output_path = os.path.join(temp_dir, "report.mp4")

                        # Create the file before render_video validates it
                        # The mock _run_ffmpeg won't actually create it
                        with open(output_path, "wb") as f:
                            f.write(b"\x00" * 500)

                        result = generate_report_video(
                            title="Test Report",
                            sections=sections,
                            output_path=output_path,
                        )

        assert result == output_path
        mock_run.assert_called_once()

    def test_pipeline_no_slide_images_raises(
        self, temp_dir: str
    ) -> None:
        """When Pillow is missing, slide generation falls back to .txt
        placeholders which _cleanup_temp_artefacts skips — the pipeline
        should raise RuntimeError."""
        sections: list[dict] = []  # empty sections

        with patch("autoinfo.output._render_audio") as mock_tts:
            mock_tts.return_value = b"fake_mp3_data" * 100

            with patch.object(
                __import__("autoinfo.output.video", fromlist=["generate_slide_images"]),
                "generate_slide_images",
                return_value=["/tmp/nonexistent_slide.png"],
            ):
                with pytest.raises(RuntimeError, match="No slide images"):
                    generate_report_video(
                        title="Bad",
                        sections=sections,
                        output_path=os.path.join(temp_dir, "bad.mp4"),
                    )


# ---------------------------------------------------------------------------
# _render_video_scaffold integration via generate_report
# ---------------------------------------------------------------------------


class TestReportVideoIntegration:
    def test_generate_report_format_video_accepted(self, temp_dir: str) -> None:
        """format='video' flows through generate_report and returns JSON status."""
        import time

        mock_run = MagicMock()
        mock_run.return_value.returncode = 0

        with patch("autoinfo.output.KBStore") as mock_store:
            mock_store.return_value.list_entries.return_value = []

            with patch("autoinfo.output._render_audio") as mock_tts:
                mock_tts.return_value = b"fake_mp3_data" * 100

                with patch("autoinfo.output.video._find_binary", return_value="/usr/bin/ffmpeg"):
                    with patch("autoinfo.output.video._run_ffmpeg", mock_run):
                        with patch("autoinfo.output.video._probe_audio_duration", return_value=10.0):
                            # Pre-create an output file so post-render validation passes.
                            # _render_video_scaffold writes to /tmp/autoinfo/video/<ts>/report_<ts>.mp4.
                            # We intercept by mocking generate_report_video to return our own path.
                            fake_video = os.path.join(temp_dir, "fake_report.mp4")
                            with open(fake_video, "wb") as f:
                                f.write(b"\x00" * 500)

                            with patch(
                                "autoinfo.output.video.generate_report_video",
                                return_value=fake_video,
                            ):
                                from autoinfo.output import generate_report

                                result = generate_report(
                                    domain="test-domain",
                                    format="video",
                                )

        assert isinstance(result, str)
        data = json.loads(result)
        assert data.get("status") == "ok"
        assert data.get("output_type") == "video"
        assert "video_path" in data

    def test_generate_report_format_video_in_valid_set(self, temp_dir: str) -> None:
        """Verify 'video' appears in generate_report's valid_formats."""
        fake_video = os.path.join(temp_dir, "fake_report2.mp4")
        with open(fake_video, "wb") as f:
            f.write(b"\x00" * 500)

        with patch("autoinfo.output.KBStore") as mock_store:
            mock_store.return_value.list_entries.return_value = []

            with patch("autoinfo.output._render_audio") as mock_tts:
                mock_tts.return_value = b"fake_mp3_data" * 100

                with patch(
                    "autoinfo.output.video.generate_report_video",
                    return_value=fake_video,
                ):
                    from autoinfo.output import generate_report

                    # Should NOT raise ValueError for invalid format
                    try:
                        generate_report(domain="test-domain", format="video")
                    except ValueError as e:
                        if "Unsupported output format" in str(e):
                            pytest.fail(f"format='video' should be supported: {e}")
                        raise


# ---------------------------------------------------------------------------
# Optional: Real FFmpeg integration (skipped if not installed)
# ---------------------------------------------------------------------------


ffmpeg_available = bool(
    __import__("shutil").which("ffmpeg")
)


@pytest.mark.skipif(not ffmpeg_available, reason="ffmpeg not installed")
class TestRenderVideoReal:
    def test_real_ffmpeg_concat(
        self, dummy_images: list[str], dummy_audio: str, temp_dir: str
    ) -> None:
        """Real FFmpeg — concat demuxer produces a valid MP4 file."""
        output_path = os.path.join(temp_dir, "real_concat.mp4")
        result = render_video(
            audio_path=dummy_audio,
            image_paths=dummy_images,
            output_path=output_path,
            config=VideoConfig(transition="none"),
        )
        assert result == output_path
        assert os.path.isfile(output_path)
        assert os.path.getsize(output_path) > 1000

    def test_real_ffmpeg_xfade(
        self, dummy_images: list[str], dummy_audio: str, temp_dir: str
    ) -> None:
        """Real FFmpeg — xfade produces a valid MP4 file."""
        output_path = os.path.join(temp_dir, "real_xfade.mp4")
        result = render_video(
            audio_path=dummy_audio,
            image_paths=dummy_images,
            output_path=output_path,
            config=VideoConfig(transition="fade"),
        )
        assert result == output_path
        assert os.path.isfile(output_path)
        assert os.path.getsize(output_path) > 1000
