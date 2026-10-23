"""Extracted from :mod:`autoinfo.output` (#582 phase 2): audio products."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import threading
from datetime import datetime, timezone
from typing import Any, cast

import httpx

logger = logging.getLogger(__name__)

# Default TTS voice for audio output.
DEFAULT_TTS_VOICE = "alloy"

# Default local TTS engine voice (edge-tts).
DEFAULT_LOCAL_TTS_VOICE = "en-US-JennyNeural"


def _strip_markdown(text: str) -> str:
    """Convert Markdown text to plain text suitable for TTS.

    Strips links, images, headings, bold/italic markers, code fences,
    horizontal rules, blockquotes, and list markers.  Keeps the content
    readable for speech synthesis.
    """
    # Images: replace with alt text
    from autoinfo.output import (  # noqa: PLC0415
        _MD_BOLD_PATTERN,
        _MD_CODE_PATTERN,
        _MD_HEADING_PATTERN,
        _MD_HR_PATTERN,
        _MD_IMAGE_PATTERN,
        _MD_ITALIC_PATTERN,
        _MD_LINK_PATTERN,
        _MD_LIST_PATTERN,
        _MD_ORDERED_LIST_PATTERN,
        _MD_QUOTE_PATTERN,
    )

    text = _MD_IMAGE_PATTERN.sub(r"\1", text)
    # Links: keep link text, drop URL
    text = _MD_LINK_PATTERN.sub(r"\1", text)
    # Bold: keep inner text
    text = _MD_BOLD_PATTERN.sub(r"\1", text)
    # Italic: keep inner text
    text = _MD_ITALIC_PATTERN.sub(r"\1", text)
    # Inline code: keep inner text
    text = _MD_CODE_PATTERN.sub(r"\1", text)
    # Headings: remove # markers
    text = _MD_HEADING_PATTERN.sub("", text)
    # Horizontal rules: remove
    text = _MD_HR_PATTERN.sub("", text)
    # Blockquotes: remove > prefix
    text = _MD_QUOTE_PATTERN.sub("", text)
    # Unordered list markers
    text = _MD_LIST_PATTERN.sub("", text)
    # Ordered list markers
    text = _MD_ORDERED_LIST_PATTERN.sub("", text)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _render_audio(
    text: str,
    voice: str = DEFAULT_TTS_VOICE,
    timeout: float = 120.0,
    engine: str | None = None,
    local_voice: str = DEFAULT_LOCAL_TTS_VOICE,
) -> bytes:
    """Render *text* as MP3 audio using the configured TTS engine.

    Parameters
    ----------
    text:
        Plain text (or Markdown; will be stripped) to convert to speech.
        Maximum 4096 characters per request.
    voice:
        For ``engine="openai"`` and ``engine="whisper"``: one of
        OpenAI's TTS voices (``"alloy"``, ``"echo"``, ``"fable"``,
        ``"onyx"``, ``"nova"``, ``"shimmer"``).  Ignored for
        ``engine="local"``.
    timeout:
        HTTP request timeout in seconds (default 120).
    engine:
        TTS engine: ``"local"`` (edge-tts, default), ``"openai"``,
        or ``"whisper"`` (OpenAI Whisper model via TTS API).
        When *None*, reads from the ``tts.engine`` config key, falling
        back to ``"local"``.
    local_voice:
        Voice name for the local engine (edge-tts).  Defaults to
        ``"en-US-JennyNeural"``.  Ignored for ``engine="openai"``
        and ``engine="whisper"``.

    Returns
    -------
    bytes
        MP3 audio data.

    Raises
    ------
    RuntimeError
        If the API key is not configured, the API returns an error, or
        the network request fails.
    ValueError
        If *text* is empty or exceeds the character limit.
    """
    from autoinfo.output import (  # noqa: PLC0415
        _get_tts_engine_from_config,
        _render_audio_edge_tts,
        _render_audio_openai,
        _render_audio_whisper,
        _strip_markdown,
    )

    if not text or not text.strip():
        raise ValueError("Cannot render empty text as audio")

    text = text.strip()
    if len(text) > 4096:
        # Truncate at 4000 characters and append a note.
        text = text[:4000] + "... [truncated]"

    # Strip markdown for cleaner TTS output.
    text = _strip_markdown(text)

    if not text:
        raise ValueError("Text is empty after stripping markdown formatting")

    # --- Resolve engine ---
    resolved_engine = engine
    if resolved_engine is None:
        resolved_engine = _get_tts_engine_from_config()
    if resolved_engine not in ("openai", "local", "whisper"):
        logger.warning(
            "Unknown TTS engine '%s' — falling back to 'openai'.",
            resolved_engine,
        )
        resolved_engine = "openai"

    # --- Local engine (edge-tts) ---
    if resolved_engine == "local":
        try:
            return _render_audio_edge_tts(text, voice=local_voice, timeout=timeout)
        except ImportError:
            logger.warning(
                "edge-tts is not installed — falling back to OpenAI TTS. "
                "Install with: pip install 'autoinfo[tts]'"
            )
        except Exception:
            # edge-tts is configured as the engine; a synthesis failure is
            # NOT a reason to fall back to OpenAI — the user chose local
            # explicitly (e.g. no api.openai.com route), and OpenAI may be
            # unreachable (2026-08-11: WSL has no route to api.openai.com,
            # so the fallback turns a clean edge-tts error into a
            # misleading "OpenAI TTS network error" after 150s+).  Re-raise
            # so callers can retry or surface the real error.
            raise

    # --- Whisper engine (OpenAI Whisper model via TTS API) ---
    if resolved_engine == "whisper":
        try:
            return _render_audio_whisper(text, voice=voice, timeout=timeout)
        except Exception:
            logger.warning(
                "Whisper TTS failed — falling back to OpenAI TTS.",
                exc_info=True,
            )

    # --- OpenAI TTS path (explicit or fallback) ---
    return _render_audio_openai(text, voice=voice, timeout=timeout)


def _render_video_scaffold(
    context: dict[str, Any],
    title: str,
    sections: list[dict[str, str]] | None = None,
) -> str:
    """Generate a video report — audio narration + slide images → MP4 via FFmpeg.

    Calls :func:`autoinfo.output.video.generate_report_video` to run
    the full pipeline (TTS → slides → FFmpeg assembly).  Returns a JSON
    status blob with the MP4 path and render metadata.
    """
    from autoinfo.output.video import (  # noqa: PLC0415
        VideoConfig,
        generate_report_video,
    )

    if sections is None or len(sections) == 0:
        sections = [{"heading": title, "body": "No content sections available."}]

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(os.environ.get("AUTOINFO_TMPDIR", "/tmp/autoinfo/video"), timestamp)
    os.makedirs(output_dir, exist_ok=True)

    # Map context-level settings to VideoConfig
    resolution = context.get("resolution", (1920, 1080))
    if isinstance(resolution, list):
        resolution = tuple(resolution)
    vcfg = VideoConfig(
        fps=context.get("fps", 30),
        resolution=resolution,
        theme=context.get("theme", "terminal-green"),
        quality=context.get("quality", "draft"),
        tts_speed=context.get("tts_speed", 1.0),
        scene_mode=context.get("scene_mode", "auto"),
        theme_mood=context.get("theme_mood", ""),
    )

    output_path = os.path.join(output_dir, f"report_{timestamp}.mp4")

    video_path = generate_report_video(
        title=title,
        sections=sections,
        output_path=output_path,
        config=vcfg,
    )

    return json.dumps(
        {
            "status": "ok",
            "output_type": "video",
            "video_path": video_path,
            "output_dir": output_dir,
            "format": "mp4",
            "message": "Video report generated successfully.",
        },
        indent=2,
    )


def _get_tts_engine_from_config() -> str:
    """Read the ``tts.engine`` setting from the project config.

    Returns "local" (edge-tts) when the config is missing or the key
    is not set.  The OpenAI TTS endpoint is unreachable from the project's
    deployment environment (WSL has no route to api.openai.com), so the
    local engine is the sane default (#210); "tts.engine: openai" remains
    available for environments that can reach the endpoint.
    """
    from autoinfo.output import get_config_path, load_config  # noqa: PLC0415

    try:
        config_path = get_config_path()
        if config_path and config_path.is_file():
            cfg = load_config(config_path)
            engine = getattr(cfg, "tts", None)
            if engine is not None and engine.engine:
                return str(engine.engine)
    except Exception:
        pass
    return "local"


def _render_audio_openai(
    text: str,
    voice: str = DEFAULT_TTS_VOICE,
    timeout: float = 120.0,
    model: str = "tts-1",
) -> bytes:
    """Render *text* as MP3 audio using the OpenAI Text-to-Speech API."""
    # --- API key resolution ---
    from autoinfo.output import get_config_path, load_config  # noqa: PLC0415

    api_key = os.environ.get("AUTOINFO_LLM_API_KEY", "")
    if not api_key:
        # Fall back to config
        try:
            config_path = get_config_path()
            if config_path and config_path.is_file():
                cfg = load_config(config_path)
                api_key = cfg.llm.api_key or ""
        except Exception:
            pass
    if not api_key:
        # Last resort: OpenAI env var (set by LiteLLM)
        api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "AUTOINFO_LLM_API_KEY is not set.  Set the environment "
            "variable or configure `llm.api_key` in config.yaml to "
            "use OpenAI TTS."
        )

    # --- OpenAI TTS API call ---
    url = "https://api.openai.com/v1/audio/speech"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "voice": voice,
        "input": text,
        "response_format": "mp3",
    }

    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        mp3_bytes = response.content
        if not mp3_bytes:
            raise RuntimeError("OpenAI TTS API returned empty audio data")
        logger.info(
            "Generated audio: %d chars text → %d bytes MP3 (model=%s, voice=%s)",
            len(text),
            len(mp3_bytes),
            model,
            voice,
        )
        return mp3_bytes
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            detail = exc.response.json()
        except Exception:
            detail = exc.response.text
        logger.error("OpenAI TTS API error: %s %s", exc.response.status_code, detail)
        raise RuntimeError(
            f"OpenAI TTS API error (HTTP {exc.response.status_code}): {detail}"
        ) from exc
    except httpx.RequestError as exc:
        logger.error("OpenAI TTS network error: %s", exc)
        raise RuntimeError(f"OpenAI TTS network error: {exc}") from exc


def _render_audio_whisper(
    text: str,
    voice: str = DEFAULT_TTS_VOICE,
    timeout: float = 120.0,
) -> bytes:
    """Render *text* as MP3 audio using the OpenAI Whisper model via TTS API.

    Uses the same OpenAI TTS API endpoint as :func:`_render_audio_openai`
    but with ``model="whisper-1"`` instead of ``model="tts-1"``.

    Falls back to :func:`_render_audio_openai` if the Whisper model is
    unavailable or the API request fails.
    """
    from autoinfo.output import _render_audio_openai  # noqa: PLC0415

    try:
        return _render_audio_openai(text, voice=voice, timeout=timeout, model="whisper-1")
    except Exception:
        logger.warning(
            "Whisper TTS model unavailable — falling back to OpenAI TTS.",
            exc_info=True,
        )
        return _render_audio_openai(text, voice=voice, timeout=timeout, model="tts-1")


def _run_coro_in_new_thread(coro: Any) -> Any:
    """Run *coro* in a fresh thread with its own event loop.

    ``asyncio.run`` cannot be called from a running event loop, so callers
    already inside one offload the coroutine to a dedicated thread here;
    the worker's result or exception is propagated back verbatim.
    """
    result: dict[str, Any] = {"value": None, "error": None}

    def _worker() -> None:
        try:
            result["value"] = asyncio.run(coro)
        except BaseException as exc:  # noqa: BLE001
            result["error"] = exc

    thread = threading.Thread(target=_worker)
    thread.start()
    thread.join()
    if result["error"] is not None:
        raise result["error"]
    return result["value"]


def _render_audio_edge_tts(
    text: str,
    voice: str = DEFAULT_LOCAL_TTS_VOICE,
    timeout: float = 120.0,
) -> bytes:
    """Render *text* as MP3 audio using the edge-tts library (local, free).

    Auto-selects a voice matching the dominant script when the configured
    voice cannot speak it: edge-tts ``en-US-JennyNeural`` raises
    ``NoAudioReceived`` for CJK-heavy text, which surfaced as 4 failing
    digest-audiobook cells (2026-08-11).  Text containing CJK codepoints
    uses ``zh-CN-XiaoxiaoNeural``; otherwise the requested voice is used.
    When the caller is already inside a running event loop, synthesis is
    offloaded to a new thread running its own fresh loop instead of
    ``asyncio.run`` (which would raise in that context).

    Raises
    ------
    ImportError
        If ``edge_tts`` is not installed.
    RuntimeError
        If the TTS synthesis fails.
    """
    import asyncio  # noqa: PLC0415

    import edge_tts  # noqa: PLC0415

    from autoinfo.output import _run_coro_in_new_thread  # noqa: PLC0415

    # CJK detection (CJK Unified Ideographs, Hiragana/Katakana, Hangul).
    cjk_ranges = (
        (0x4E00, 0x9FFF),  # CJK Unified Ideographs
        (0x3040, 0x30FF),  # Hiragana + Katakana
        (0xAC00, 0xD7AF),  # Hangul Syllables
    )
    has_cjk = any(any(lo <= ord(ch) <= hi for lo, hi in cjk_ranges) for ch in text)
    effective_voice = "zh-CN-XiaoxiaoNeural" if has_cjk else voice

    async def _synthesize() -> bytes:
        communicate = edge_tts.Communicate(text, effective_voice)
        chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        if not chunks:
            raise RuntimeError("edge-tts returned empty audio data")
        return b"".join(chunks)

    try:
        try:
            asyncio.get_running_loop()
            running = True
        except RuntimeError:
            running = False
        if running:
            mp3_bytes = _run_coro_in_new_thread(asyncio.wait_for(_synthesize(), timeout=timeout))
        else:
            mp3_bytes = asyncio.run(asyncio.wait_for(_synthesize(), timeout=timeout))
    except asyncio.TimeoutError:
        raise RuntimeError(f"Local TTS (edge-tts) timed out after {timeout:.0f}s") from None

    logger.info(
        "Generated audio (local/edge-tts): %d chars text → %d bytes MP3 (voice=%s)",
        len(text),
        len(mp3_bytes),
        voice,
    )
    return cast(bytes, mp3_bytes)
