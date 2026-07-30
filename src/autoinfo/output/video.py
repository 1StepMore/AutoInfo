"""Video output pipeline — TTS narration + slideshow assembly.

Generates video content from structured report data using:
1. TTS audio narration (via existing _render_audio from output.py)
2. Slide images (via PIL/Pillow)
3. FFmpeg assembly — concat demuxer + xfade transitions + audio overlay
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import os
import shutil
import subprocess
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class VideoConfig:
    """Configuration for video generation."""

    fps: int = 1
    resolution: tuple[int, int] = (1920, 1080)
    bg_color: str = "#1a1a2e"
    font_color: str = "#ffffff"
    font_size: int = 48
    tts_speed: float = 1.0
    transition: str = "fade"


def generate_audio_narration(
    title: str,
    sections: list[dict],
    output_dir: str,
    voice: str = "default",
) -> str:
    """Generate TTS audio narration for content.

    Args:
        title: Report title
        sections: List of dicts with 'heading' and 'body' keys
        output_dir: Directory to write audio file
        voice: TTS voice name

    Returns:
        Path to audio file

    Raises:
        RuntimeError: If TTS generation fails entirely
    """
    # Build narration text from sections
    text_parts = [f"Title: {title}"]
    for section in sections:
        heading = section.get("heading", "")
        body = section.get("body", "")
        if heading:
            text_parts.append(heading)
        if body:
            text_parts.append(body)

    narration_text = ". ".join(text_parts)

    # Use existing TTS engine from output.py
    from autoinfo.output import _render_audio

    audio_bytes = _render_audio(narration_text, voice=voice)

    os.makedirs(output_dir, exist_ok=True)
    audio_path = os.path.join(output_dir, "narration.mp3")
    with open(audio_path, "wb") as f:
        f.write(audio_bytes)

    if not os.path.getsize(audio_path) > 100:
        raise RuntimeError(f"TTS audio too small: {audio_path}")

    logger.info(
        "TTS audio generated: %s (%d bytes)",
        audio_path,
        os.path.getsize(audio_path),
    )
    return audio_path


def generate_slide_images(
    title: str,
    sections: list[dict],
    output_dir: str,
    resolution: tuple[int, int] = (1920, 1080),
) -> list[str]:
    """Generate slide images from content sections using PIL.

    Args:
        title: Report title
        sections: List of dicts with 'heading' and 'body' keys
        output_dir: Directory to write image files
        resolution: (width, height) tuple

    Returns:
        List of paths to generated image files
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.warning("Pillow not installed — using placeholder images instead")
        return _generate_placeholder_images(title, sections, output_dir, resolution)

    os.makedirs(output_dir, exist_ok=True)
    paths: list[str] = []
    width, height = resolution

    # --- Resolve fonts ---
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48
        )
        small_font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32
        )
    except (OSError, IOError):
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # --- Title slide ---
    img = Image.new("RGB", (width, height), color="#1a1a2e")
    draw = ImageDraw.Draw(img)
    draw.text((100, height // 2 - 50), title, fill="white", font=font)
    draw.text(
        (100, height // 2 + 20),
        "AutoInfo Video Summary",
        fill="#888888",
        font=small_font,
    )

    title_path = os.path.join(output_dir, "slide_000.png")
    img.save(title_path)
    paths.append(title_path)

    # --- Content slides ---
    for i, section in enumerate(sections, start=1):
        img = Image.new("RGB", (width, height), color="#16213e")
        draw = ImageDraw.Draw(img)
        heading = section.get("heading", f"Section {i}")
        body = section.get("body", "")

        draw.text((100, 100), heading, fill="#e94560", font=font)

        # Word-wrap body text
        y = 200
        words = body.split()
        line = ""
        for word in words:
            test_line = f"{line} {word}".strip()
            # Rough char-based wrapping (~55 chars per line)
            if len(test_line) > 55:
                draw.text((100, y), line, fill="white", font=small_font)
                y += 45
                line = word
            else:
                line = test_line
        if line:
            draw.text((100, y), line, fill="white", font=small_font)

        slide_path = os.path.join(output_dir, f"slide_{i:03d}.png")
        img.save(slide_path)
        paths.append(slide_path)

    logger.info("Generated %d slide images in %s", len(paths), output_dir)
    return paths


def _generate_placeholder_images(
    title: str,
    sections: list[dict],
    output_dir: str,
    resolution: tuple[int, int],
) -> list[str]:
    """Generate simple text-based placeholder images when Pillow is unavailable."""
    os.makedirs(output_dir, exist_ok=True)
    paths: list[str] = []
    width, height = resolution

    # Create minimal SVG-like text files as placeholders
    placeholder_path = os.path.join(output_dir, "slide_000.txt")
    with open(placeholder_path, "w") as f:
        f.write(f"SLIDE 0: {title}\n")
        for s in sections:
            f.write(f"  - {s.get('heading', '')}: {s.get('body', '')[:80]}\n")
    paths.append(placeholder_path)

    for i, section in enumerate(sections, start=1):
        spath = os.path.join(output_dir, f"slide_{i:03d}.txt")
        with open(spath, "w") as f:
            f.write(f"SLIDE {i}: {section.get('heading', f'Section {i}')}\n")
            f.write(f"{section.get('body', '')}\n")
        paths.append(spath)

    return paths


# ---------------------------------------------------------------------------
# FFmpeg video rendering engine
# ---------------------------------------------------------------------------


def render_video(
    audio_path: str,
    image_paths: list[str],
    output_path: str,
    config: VideoConfig | None = None,
) -> str:
    """Render a video from images and audio narration using FFmpeg.

    Supports two rendering modes:

    - **Concat demuxer** (``transition="none"``): Images played sequentially
      with per-slide duration derived from audio length. Simple, fast,
      no transitions.
    - **Xfade** (``transition="fade"``): Crossfade transitions between each
      adjacent slide pair using FFmpeg ``xfade`` filter.

    Audio is overlaid with ``-c:a aac`` and the video is truncated to
    match audio duration (``-shortest``).

    Parameters
    ----------
    audio_path : str
        Path to the audio narration file (MP3 format recommended).
    image_paths : list[str]
        Ordered list of image file paths (PNG recommended).  Non-existent
        files are silently filtered out.
    output_path : str
        Path where the output MP4 file will be written.
    config : VideoConfig, optional
        Configuration for resolution, FPS, background colour, and
        transition type.  Uses defaults when ``None``.

    Returns
    -------
    str
        Absolute path to the rendered video file.

    Raises
    ------
    FileNotFoundError
        If ``ffmpeg`` is not installed, or if *audio_path* does not exist.
    ValueError
        If *image_paths* is empty or contains no valid image files.
    RuntimeError
        If the FFmpeg subprocess exits with a non-zero code, or if the
        output file is missing or smaller than 100 bytes.
    """
    if config is None:
        config = VideoConfig()

    # --- Validate inputs --------------------------------------------------
    if not image_paths:
        raise ValueError("image_paths must not be empty")

    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Resolve valid image file paths (filter out non-existent ones)
    valid_images: list[str] = [
        str(p) for p in image_paths if os.path.isfile(str(p))
    ]
    if not valid_images:
        raise ValueError(
            f"No valid image files found among {len(image_paths)} paths"
        )

    # --- Locate FFmpeg / ffprobe ------------------------------------------
    ffmpeg_path = _find_binary("ffmpeg")
    ffprobe_path = _find_binary("ffprobe")

    # --- Determine per-slide duration from audio length -------------------
    audio_duration = _probe_audio_duration(ffprobe_path, audio_path)
    if audio_duration <= 0:
        # Fallback: 5 seconds per slide
        audio_duration = float(len(valid_images) * 5)

    per_slide_duration = audio_duration / len(valid_images)
    if per_slide_duration < 0.5:
        per_slide_duration = 5.0  # minimum 5s per slide

    # --- Ensure output directory exists -----------------------------------
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    width, height = config.resolution

    # --- Route to concat or xfade renderer --------------------------------
    if config.transition == "none" or len(valid_images) == 1:
        _render_concat_video(
            ffmpeg_path=ffmpeg_path,
            image_paths=valid_images,
            audio_path=audio_path,
            output_path=output_path,
            width=width,
            height=height,
            fps=config.fps,
            per_slide_duration=per_slide_duration,
        )
    else:
        _render_xfade_video(
            ffmpeg_path=ffmpeg_path,
            image_paths=valid_images,
            audio_path=audio_path,
            output_path=output_path,
            width=width,
            height=height,
            fps=config.fps,
            per_slide_duration=per_slide_duration,
            transition_type=config.transition,
        )

    # --- Post-render validation -------------------------------------------
    if not os.path.isfile(output_path) or os.path.getsize(output_path) < 100:
        raise RuntimeError(
            f"Video output is missing or too small: {output_path}"
        )

    logger.info(
        "Video rendered: %s (%d slides, %.1fs audio, transition=%s)",
        output_path,
        len(valid_images),
        audio_duration,
        config.transition,
    )
    return output_path


# ---------------------------------------------------------------------------
# FFmpeg binary discovery
# ---------------------------------------------------------------------------


def _find_binary(name: str) -> str:
    """Locate an executable on PATH.

    Parameters
    ----------
    name : str
        Binary name (e.g. ``"ffmpeg"``, ``"ffprobe"``).

    Returns
    -------
    str
        Absolute path to the binary.

    Raises
    ------
    FileNotFoundError
        If the binary cannot be found on ``$PATH``.
    """
    path = shutil.which(name)
    if path is None:
        raise FileNotFoundError(
            f"'{name}' not found on PATH. "
            f"Install FFmpeg to generate videos: https://ffmpeg.org/download.html"
        )
    return path


# ---------------------------------------------------------------------------
# Audio duration probing (ffprobe)
# ---------------------------------------------------------------------------


def _probe_audio_duration(ffprobe_path: str, audio_path: str) -> float:
    """Probe the duration of an audio file using ffprobe.

    Parameters
    ----------
    ffprobe_path : str
        Path to the ``ffprobe`` binary.
    audio_path : str
        Path to the audio file.

    Returns
    -------
    float
        Duration in seconds.  Returns ``0.0`` if probing fails.
    """
    try:
        result = subprocess.run(
            [
                ffprobe_path,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                audio_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.warning(
                "ffprobe exited with code %d: %s",
                result.returncode,
                result.stderr,
            )
            return 0.0

        data = json.loads(result.stdout)
        duration_str = data.get("format", {}).get("duration", "0")
        return float(duration_str)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, ValueError, OSError) as exc:
        logger.warning("Failed to probe audio duration: %s", exc)
        return 0.0


# ---------------------------------------------------------------------------
# Concat demuxer renderer (no transitions)
# ---------------------------------------------------------------------------


def _render_concat_video(
    ffmpeg_path: str,
    image_paths: list[str],
    audio_path: str,
    output_path: str,
    width: int,
    height: int,
    fps: int,
    per_slide_duration: float,
) -> None:
    """Render video using FFmpeg concat demuxer (no transitions).

    Creates a temporary ``filelist.txt`` with each image and its duration,
    then pipes it to ``ffmpeg -f concat``.  Audio is overlaid and the
    output is truncated to the shorter of video/audio (``-shortest``).

    The temp file is cleaned up on both success and failure.
    """
    concat_file: str | None = None
    try:
        # Write concat file list
        fd, concat_file = tempfile.mkstemp(
            suffix=".txt", prefix="autoinfo_concat_"
        )
        with os.fdopen(fd, "w") as f:
            for img in image_paths:
                f.write(f"file '{img}'\n")
                f.write(f"duration {per_slide_duration}\n")
            # Final image needs to be listed again for concat demuxer
            # to hold on the last frame
            if image_paths:
                f.write(f"file '{image_paths[-1]}'\n")

        cmd = [
            ffmpeg_path,
            "-y",                          # overwrite output
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-i", audio_path,
            "-c:v", "libx264",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-s", f"{width}x{height}",
            "-r", str(fps),
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            output_path,
        ]

        logger.debug("Running FFmpeg concat: %s", " ".join(cmd))
        _run_ffmpeg(cmd)

    finally:
        # Clean up temp concat file
        if concat_file and os.path.isfile(concat_file):
            try:
                os.unlink(concat_file)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Xfade renderer (crossfade transitions)
# ---------------------------------------------------------------------------


def _render_xfade_video(
    ffmpeg_path: str,
    image_paths: list[str],
    audio_path: str,
    output_path: str,
    width: int,
    height: int,
    fps: int,
    per_slide_duration: float,
    transition_type: str = "fade",
) -> None:
    """Render video with crossfade transitions between slides.

    Each image is fed as a separate input via ``-loop 1 -t DUR``.
    The filter_complex chain:

    1. Scales each input to *width* × *height* (letterboxed).
    2. Chains ``xfade`` filters between adjacent scaled streams.
    3. Outputs to ``yuv420p`` pixel format.

    The transition duration is derived from *per_slide_duration* (min 0.5 s,
    max half the slide duration).

    Parameters
    ----------
    transition_type : str
        ``xfade`` transition name (e.g. ``"fade"``, ``"fadeblack"``,
        ``"fadewhite"``, ``"slideleft"``, ``"slideright"``).
        Falls back to ``"fade"`` for unknown values.
    """
    # Map friendly names to FFmpeg xfade transition names
    _XFADE_TRANSITIONS: dict[str, str] = {
        "fade": "fade",
        "fadeblack": "fadeblack",
        "fadewhite": "fadewhite",
        "slideleft": "slideleft",
        "slideright": "slideright",
        "slideup": "slideup",
        "slidedown": "slidedown",
        "circlecrop": "circlecrop",
        "rectcrop": "rectcrop",
        "distance": "distance",
        "wipeleft": "wipeleft",
        "wiperight": "wiperight",
        "wipeup": "wipeup",
        "wipedown": "wipedown",
        "dissolve": "dissolve",
        "pixelize": "pixelize",
    }
    xfade_name = _XFADE_TRANSITIONS.get(transition_type, "fade")

    # Transition duration: 1 second or 1/3 of slide duration, whichever is
    # smaller, but at least 0.5 seconds.
    transition_dur = max(0.5, min(1.0, per_slide_duration / 3))

    num_images = len(image_paths)

    # Build ffmpeg command
    cmd: list[str] = [ffmpeg_path, "-y"]

    # --- Inputs -----------------------------------------------------------
    # Each image as a separate input looped for per_slide_duration seconds
    for img in image_paths:
        cmd += [
            "-loop", "1",
            "-t", f"{per_slide_duration:.3f}",
            "-i", img,
        ]
    # Audio input
    cmd += ["-i", audio_path]

    # --- Filter complex ---------------------------------------------------
    filter_parts: list[str] = []

    # Step 1: Scale & pad each image input
    for i in range(num_images):
        filter_parts.append(
            f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1[v{i}]"
        )

    # Step 2: Chain xfade transitions
    current_input = "[v0]"
    for i in range(1, num_images):
        offset = i * per_slide_duration - i * transition_dur
        if offset < 0:
            offset = 0.0
        label = f"f{i - 1}"
        filter_parts.append(
            f"{current_input}[v{i}]xfade=transition={xfade_name}:"
            f"duration={transition_dur:.3f}:offset={offset:.3f},"
            f"format=yuv420p[{label}]"
        )
        current_input = f"[{label}]"

    filter_complex = ";\n".join(filter_parts)

    # Final video label
    if num_images == 1:
        final_video_label = "[v0]"
    else:
        final_video_label = f"[f{num_images - 2}]"

    cmd += [
        "-filter_complex", filter_complex,
        "-map", final_video_label,
        "-map", f"{num_images}:a",
        "-c:v", "libx264",
        "-preset", "fast",
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        output_path,
    ]

    logger.debug("Running FFmpeg xfade: %s", " ".join(cmd))
    _run_ffmpeg(cmd)


# ---------------------------------------------------------------------------
# Subprocess runner
# ---------------------------------------------------------------------------


def _run_ffmpeg(cmd: list[str], timeout: float = 300) -> None:
    """Run an FFmpeg command and raise on failure.

    Parameters
    ----------
    cmd : list[str]
        FFmpeg command and arguments.
    timeout : float
        Maximum runtime in seconds (default 300).

    Raises
    ------
    RuntimeError
        If the subprocess exits with a non-zero code or times out.
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            stderr_tail = result.stderr.strip().split("\n")[-5:]
            raise RuntimeError(
                f"FFmpeg exited with code {result.returncode}:\n"
                + "\n".join(stderr_tail)
            )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"FFmpeg timed out after {timeout}s: {exc}"
        ) from exc
    except FileNotFoundError:
        raise FileNotFoundError(
            "ffmpeg executable not found at runtime"
        )


# ---------------------------------------------------------------------------
# High-level "video report" pipeline (images + audio → MP4)
# ---------------------------------------------------------------------------


def generate_report_video(
    title: str,
    sections: list[dict],
    output_path: str | None = None,
    config: VideoConfig | None = None,
    voice: str = "default",
) -> str:
    """Full pipeline: slides → narration → FFmpeg → MP4.

    Convenience wrapper that calls :func:`generate_audio_narration` and
    :func:`generate_slide_images`, then assembles the result with
    :func:`render_video`.

    Temporary artefacts (audio MP3 and slide PNGs) are written to a
    temporary directory (or next to *output_path*) and cleaned up
    after a successful render.  On failure the artefacts are left
    in place for post-mortem inspection.

    Parameters
    ----------
    title : str
        Report / video title.
    sections : list[dict]
        Section dicts with ``"heading"`` and ``"body"`` keys.
    output_path : str, optional
        Destination path for the MP4 file.  Defaults to
        ``<TMPDIR>/autoinfo_video_<timestamp>.mp4``.
    config : VideoConfig, optional
        Video render settings.
    voice : str
        TTS voice name forwarded to :func:`generate_audio_narration`.

    Returns
    -------
    str
        Absolute path to the rendered MP4 file.

    Raises
    ------
    FileNotFoundError
        If FFmpeg is not installed.
    RuntimeError
        If TTS audio generation or video assembly fails.
    """
    if config is None:
        config = VideoConfig()

    # --- Prepare working directory ----------------------------------------
    work_dir = tempfile.mkdtemp(prefix="autoinfo_video_")

    try:
        # 1. Generate audio narration
        audio_path = generate_audio_narration(
            title=title,
            sections=sections,
            output_dir=work_dir,
            voice=voice,
        )

        # 2. Generate slide images
        slide_paths = generate_slide_images(
            title=title,
            sections=sections,
            output_dir=work_dir,
            resolution=config.resolution,
        )

        # Filter to actual image files (Pillow path produces .png; placeholder
        # path produces .txt — skip those)
        real_images = [
            p for p in slide_paths
            if os.path.isfile(p) and p.lower().endswith((".png", ".jpg", ".jpeg"))
        ]
        if not real_images:
            raise RuntimeError(
                "No slide images were generated (Pillow may be missing)"
            )

        # 3. Determine output path
        if output_path is None:
            import time

            output_path = os.path.join(
                work_dir,
                f"autoinfo_video_{int(time.time())}.mp4",
            )

        # 4. Render video via FFmpeg
        render_video(
            audio_path=audio_path,
            image_paths=real_images,
            output_path=output_path,
            config=config,
        )

        # 5. Clean up temp artefacts (keep only the MP4)
        _cleanup_temp_artefacts(work_dir, output_path)

        return output_path

    except Exception:
        logger.warning(
            "Video generation failed — artefacts preserved in %s",
            work_dir,
            exc_info=True,
        )
        raise


def _cleanup_temp_artefacts(work_dir: str, output_path: str) -> None:
    """Remove temporary audio/image artefacts, keeping only the MP4."""
    keep = os.path.abspath(output_path)
    for entry in os.listdir(work_dir):
        full = os.path.join(work_dir, entry)
        if os.path.abspath(full) == keep:
            continue
        try:
            if os.path.isfile(full):
                os.unlink(full)
            elif os.path.isdir(full):
                shutil.rmtree(full, ignore_errors=True)
        except OSError:
            pass
