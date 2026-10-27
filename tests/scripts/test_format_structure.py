"""Tests for the per-format L2 structural checker (scripts/format_structure.py).

Positive cases run against the real rendered artifacts under ``outputs/``
(gitignored, so they skip when a checkout has not produced them); negative
cases synthesise deliberately broken artifacts in ``tmp_path`` so the suite
never commits binary fixtures and still proves each checker rejects the defect
it is meant to catch.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import wave
import zipfile
from pathlib import Path
from typing import Any

import pytest

# scripts/ is not a package — load it via sys.path like the script itself does.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

import format_structure as fs  # noqa: E402  (sys.path insert above)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_AI_DEMO = _REPO_ROOT / "outputs" / "ai-demo"
_MEDICAL = _REPO_ROOT / "outputs" / "medical-research"

_POSITIVE_CASES = [
    ("markdown", [_AI_DEMO / "report-markdown-20260916.md"]),
    ("html", [_AI_DEMO / "report-html-20260916.html"]),
    ("json", [_AI_DEMO / "report-json-20260916.json"]),
    ("agent", [_AI_DEMO / "report-agent-20260916.json"]),
    ("audio", [_AI_DEMO / "digest-audio-20260916.mp3"]),
    (
        "audiobook",
        [
            _AI_DEMO / "digest-audiobook-20260916.zip",
            _AI_DEMO / "report-audiobook-20260916.zip",
            _MEDICAL / "digest-audiobook-20260916.zip",
            _MEDICAL / "report-audiobook-20260916.zip",
        ],
    ),
    ("epub", [_AI_DEMO / "report-epub-20260916.epub"]),
    ("video", [_AI_DEMO / "report-video-20260916.mp4"]),
]

# One silent MPEG-1 Layer III frame (128 kbps, 44.1 kHz, stereo).
_MP3_FRAME = b"\xff\xfb\x90\x00" + b"\x00" * 413
_EMPTY_ID3 = b"ID3\x03\x00\x00\x00\x00\x00\x00"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _details(result: dict[str, Any]) -> str:
    return " ".join(check["detail"] for check in result["checks"].values())


def _run_json(capsys: pytest.CaptureFixture[str], path: Path) -> tuple[int, dict[str, Any]]:
    exit_code = fs.main(["--json", str(path)])
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1
    return exit_code, json.loads(lines[0])


def _mp3_seconds(seconds: float) -> bytes:
    frames = int(seconds / (1152 / 44100)) + 1
    return _MP3_FRAME * frames


def _id3_with_title(title: str) -> bytes:
    payload = b"\x00" + title.encode("latin-1", errors="replace")
    frame = b"TIT2" + len(payload).to_bytes(4, "big") + b"\x00\x00" + payload
    size = len(frame)
    syncsafe = bytes([(size >> 21) & 0x7F, (size >> 14) & 0x7F, (size >> 7) & 0x7F, size & 0x7F])
    return b"ID3\x03\x00\x00" + syncsafe + frame


def _write_wav(path: Path, seconds: float) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b"\x00\x00" * int(8000 * seconds))


def _write_epub_without_toc(path: Path) -> None:
    container = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">'
        "<rootfiles><rootfile media-type=\"application/oebps-package+xml\" "
        'full-path="EPUB/content.opf"/></rootfiles></container>'
    )
    opf = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
        "<manifest><item id=\"chapter_0\" href=\"chapter_0.xhtml\" "
        'media-type="application/xhtml+xml"/></manifest>'
        '<spine><itemref idref="chapter_0"/></spine></package>'
    )
    chapter = (
        '<html xmlns="http://www.w3.org/1999/xhtml"><body><p>'
        + "content words without any navigation document " * 8
        + "</p></body></html>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        mimetype = zipfile.ZipInfo("mimetype")
        mimetype.compress_type = zipfile.ZIP_STORED
        archive.writestr(mimetype, "application/epub+zip")
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("EPUB/content.opf", opf)
        archive.writestr("EPUB/chapter_0.xhtml", chapter)


# ---------------------------------------------------------------------------
# Positive cases — real artifacts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fmt", "candidates"),
    _POSITIVE_CASES,
    ids=[case[0] for case in _POSITIVE_CASES],
)
def test_positive_real_artifact(fmt: str, candidates: list[Path]) -> None:
    present = [path for path in candidates if path.is_file()]
    if not present:
        pytest.skip(f"no {fmt} artifact under outputs/ (run the generator first)")
    if fmt == "video" and shutil.which("ffprobe") is None:
        pytest.skip("ffprobe not installed")
    if fmt in {"audio", "audiobook"} and fs.mutagen is None:
        pytest.skip("mutagen not installed")

    for path in present:
        result = fs.check_artifact(path)
        assert result["format"] == fmt
        assert result["passed"] is True, result


# ---------------------------------------------------------------------------
# Negative cases — synthesized broken artifacts
# ---------------------------------------------------------------------------


def test_negative_truncated_epub(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "truncated.epub"
    path.write_bytes(b"PK\x03\x04" + b"\x00" * 196)
    exit_code, result = _run_json(capsys, path)
    assert exit_code == 1
    assert result["passed"] is False
    assert "not a valid ZIP archive" in _details(result)


def test_negative_ten_byte_mp4(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    if shutil.which("ffprobe") is None:
        pytest.skip("ffprobe not installed")
    path = tmp_path / "tiny.mp4"
    path.write_bytes(b"\x00" * 10)
    exit_code, result = _run_json(capsys, path)
    assert exit_code == 1
    assert result["passed"] is False
    assert "ffprobe exited" in _details(result)


def test_negative_non_chaptered_zip_audiobook(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "book.zip"
    path.write_bytes(_EMPTY_ID3 + _mp3_seconds(30.0))
    exit_code, result = _run_json(capsys, path)
    assert exit_code == 1
    assert result["passed"] is False
    assert "CHAP" in _details(result)


def test_negative_markdown_todo(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "draft.md"
    path.write_text("# Draft\n\nTODO finish the report\nhttps://example.com\n", encoding="utf-8")
    exit_code, result = _run_json(capsys, path)
    assert exit_code == 1
    assert result["passed"] is False
    assert "TODO" in _details(result)


def test_negative_html_empty_body(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "empty.html"
    path.write_text(
        "<html><head><title>Empty</title></head><body></body></html>", encoding="utf-8"
    )
    exit_code, result = _run_json(capsys, path)
    assert exit_code == 1
    assert result["passed"] is False
    assert "body text chars=0" in _details(result)


def test_negative_json_trailing_garbage(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "broken.json"
    path.write_text('{"a": 1, "b": 2, "c": 3} trailing', encoding="utf-8")
    exit_code, result = _run_json(capsys, path)
    assert exit_code == 1
    assert result["passed"] is False
    assert "json.loads failed" in _details(result)


def test_negative_agent_without_type(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "report-agent.json"
    path.write_text('{"a": 1, "b": 2, "c": 3}', encoding="utf-8")
    exit_code, result = _run_json(capsys, path)
    assert exit_code == 1
    assert result["passed"] is False
    assert "@type" in _details(result)


def test_framesync_mp3_without_id3_is_accepted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The plan accepts an MPEG frame sync in place of an ID3 header (bullet 7).

    The audio pipeline's own output starts with a frame sync when it has no
    metadata to write, so requiring an ID3 tag unconditionally would fail the
    real artifact while the format itself is perfectly valid.
    """
    if fs.mutagen is None:
        pytest.skip("mutagen not installed")
    if shutil.which("ffprobe") is None:
        pytest.skip("ffprobe not installed")
    path = tmp_path / "framesync.mp3"
    path.write_bytes(_mp3_seconds(6.0))
    exit_code, result = _run_json(capsys, path)
    assert exit_code == 0, _details(result)
    assert result["passed"] is True
    assert result["checks"]["magic"]["passed"] is True
    assert "id3_tag" not in result["checks"]


def test_negative_audio_under_one_second(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    if fs.mutagen is None:
        pytest.skip("mutagen not installed")
    path = tmp_path / "short.wav"
    _write_wav(path, 0.5)
    exit_code, result = _run_json(capsys, path)
    assert exit_code == 1
    assert result["passed"] is False
    assert "need >= 1.0s" in _details(result)


def test_negative_markdown_without_h1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "no-h1.md"
    path.write_text(
        "Intro paragraph https://example.com\n\n## Section\n\n" + "word " * 220,
        encoding="utf-8",
    )
    exit_code, result = _run_json(capsys, path)
    assert exit_code == 1
    assert result["passed"] is False
    assert "H1 count=0" in _details(result)


def test_negative_markdown_short_body(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "short.md"
    path.write_text(
        "# Title\n\n## Section\n\nToo short. https://example.com\n", encoding="utf-8"
    )
    exit_code, result = _run_json(capsys, path)
    assert exit_code == 1
    assert result["passed"] is False
    assert "body words=" in _details(result)


def test_negative_html_two_headings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "two-headings.html"
    path.write_text(
        "<html><head><title>Two</title></head><body>"
        "<h1>One</h1><h2>Two</h2><p>" + "body text " * 80 + "</p></body></html>",
        encoding="utf-8",
    )
    exit_code, result = _run_json(capsys, path)
    assert exit_code == 1
    assert result["passed"] is False
    assert "heading count=2" in _details(result)


def test_negative_html_literal_braces(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "braces.html"
    path.write_text(
        "<html><head><title>Braces</title></head><body>"
        "<h1>One</h1><h2>Two</h2><h3>Three</h3><p>"
        + "body text " * 80
        + "{{ template }}</p></body></html>",
        encoding="utf-8",
    )
    exit_code, result = _run_json(capsys, path)
    assert exit_code == 1
    assert result["passed"] is False
    assert "literal braces" in _details(result)


def test_negative_audio_smaller_than_size_floor(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    if fs.mutagen is None:
        pytest.skip("mutagen not installed")
    path = tmp_path / "small.mp3"
    path.write_bytes(_EMPTY_ID3 + _mp3_seconds(1.0))
    exit_code, result = _run_json(capsys, path)
    assert exit_code == 1
    assert result["passed"] is False
    assert "need > 51200" in _details(result)


def test_negative_video_shorter_than_three_seconds(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("ffmpeg/ffprobe not installed; cannot synthesize a short video")
    path = tmp_path / "short.mp4"
    completed = subprocess.run(
        [
            shutil.which("ffmpeg") or "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=64x64:r=10",
            "-t",
            "2",
            "-c:v",
            "mpeg4",
            "-pix_fmt",
            "yuv420p",
            "-y",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if completed.returncode != 0:
        pytest.skip(f"ffmpeg could not synthesize a short video: {completed.stderr[-200:]}")
    exit_code, result = _run_json(capsys, path)
    assert exit_code == 1
    assert result["passed"] is False
    assert "need > 3.0s" in _details(result)


def test_negative_epub_without_ncx_or_nav(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "no-toc.epub"
    _write_epub_without_toc(path)
    exit_code, result = _run_json(capsys, path)
    assert exit_code == 1
    assert result["passed"] is False
    assert "no NCX navMap navPoint" in _details(result)


# ---------------------------------------------------------------------------
# Contract details
# ---------------------------------------------------------------------------


def test_mobi_reports_explicit_skip_not_silent_pass(tmp_path: Path) -> None:
    if shutil.which("ebook-meta") is not None:
        pytest.skip("ebook-meta present; the skip path is only reachable without it")
    path = tmp_path / "book.mobi"
    path.write_bytes(b"\x00" * 2048)
    result = fs.check_artifact(path)
    assert result["format"] == "mobi"
    assert result["passed"] is True
    assert "mobi structurally unverified (no tool)" in _details(result)


def test_empty_mobi_still_fails(tmp_path: Path) -> None:
    path = tmp_path / "empty.mobi"
    path.write_bytes(b"")
    result = fs.check_artifact(path)
    assert result["passed"] is False


def test_unknown_extension_fails_without_crashing(tmp_path: Path) -> None:
    path = tmp_path / "artifact.xyz"
    path.write_text("data", encoding="utf-8")
    result = fs.check_artifact(path)
    assert result["format"] == "unknown"
    assert result["passed"] is False
    assert "unrecognised extension" in _details(result)


def test_missing_file_is_usage_error(tmp_path: Path) -> None:
    assert fs.main([str(tmp_path / "absent.md")]) == 2


def test_real_zip_audiobook_member_is_parsed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "container.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("audio/chapter.mp3", _id3_with_title("Chapter 1") + _mp3_seconds(6.0))
    exit_code, result = _run_json(capsys, path)
    assert exit_code == 0
    assert result["passed"] is True, result
    assert any(name.startswith("member_") for name in result["checks"])
