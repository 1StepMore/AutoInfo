#!/usr/bin/env python3
"""Per-format structural checks (L2) over generated product artifacts.

The capability matrix proves a product was *produced* (L1) and that the system
is healthy (L3), but neither layer proves the produced bytes are structurally
what the format claims.  A 0-byte ``.epub`` or a truncated ``.mp4`` can pass a
"file exists" check while being unusable by the end user; this checker closes
that gap by parsing each artifact with its own format's rules.

Exit codes mirror ``scripts/quality_gate.py``: 0 = every artifact passed,
1 = at least one failed, 2 = usage error (missing file / no arguments).
``--json`` emits one JSON object per artifact for machine consumers (the
``scripts/capability_matrix.py`` driver consumes the same ``check_artifact()``
function directly).

Format detection is by extension, with one deliberate exception: audiobook
artifacts in this repo are chaptered MP3s that carry a ``.zip`` extension
(issue D12), so a ``.zip`` is classified by its magic bytes rather than its
name.  A genuine ZIP is still supported for any future ``zip_b64`` writer.
"""

from __future__ import annotations

import argparse
import html
import io
import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

try:
    import mutagen
except ImportError:  # pragma: no cover - mutagen ships in the ebook extra
    mutagen = None

ROOT = Path(__file__).resolve().parents[1]

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a"}
VIDEO_EXTENSIONS = {".mp4", ".webm"}
_EXTENSION_FORMATS = {
    ".mp3": "audio",
    ".wav": "audio",
    ".m4a": "audio",
    ".mp4": "video",
    ".webm": "video",
    ".epub": "epub",
    ".mobi": "mobi",
    ".azw3": "mobi",
    ".html": "html",
    ".htm": "html",
    ".md": "markdown",
    ".markdown": "markdown",
}

_MARKDOWN_PLACEHOLDERS = re.compile(r"TODO|TBD|PLACEHOLDER|\{\{|\}\}")
_MARKDOWN_LINK = re.compile(r"!?\[[^\]\n]+\]\([^)\n]+\)|https?://\S+")
_MARKDOWN_H1 = re.compile(r"^# ", re.MULTILINE)
_MARKDOWN_H2 = re.compile(r"^## ", re.MULTILINE)
_HTML_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")
_WORD = re.compile(r"\b\w+\b")

MIN_AUDIO_DURATION = 1.0
MIN_AUDIOBOOK_DURATION = 5.0
MIN_AV_DURATION = 3.0
MIN_AV_SIZE = 50 * 1024
MIN_EPUB_TEXT = 200
MIN_HTML_TEXT = 500
MIN_MARKDOWN_WORDS = 200
MIN_HTML_HEADINGS = 3
FFPROBE_TIMEOUT = 60
ALLOWED_PIX_FMTS = {"yuv420p", "yuvj420p"}


# ---------------------------------------------------------------------------
# Check helpers
# ---------------------------------------------------------------------------


def _check(passed: bool, detail: str) -> dict[str, Any]:
    return {"passed": bool(passed), "detail": detail}


def _result(path: Path, fmt: str, checks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "path": str(path),
        "format": fmt,
        "passed": all(c["passed"] for c in checks.values()),
        "checks": checks,
    }


def detect_format(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix == ".zip":
        # Audiobooks are ID3-headed MP3s named .zip; a real ZIP is accepted too.
        return "audiobook"
    if suffix == ".json":
        return "agent" if "agent" in path.stem.lower() else "json"
    return _EXTENSION_FORMATS.get(suffix)


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------


def _run_ffprobe(path: Path) -> tuple[dict[str, Any] | None, str]:
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        return None, "ffprobe not found"
    command = [
        ffprobe,
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-print_format",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=FFPROBE_TIMEOUT, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"ffprobe could not inspect the file: {exc}"
    if completed.returncode != 0:
        stderr = completed.stderr.strip().splitlines()
        reason = stderr[-1] if stderr else "no stderr"
        return None, f"ffprobe exited {completed.returncode}: {reason[:200]}"
    try:
        return json.loads(completed.stdout), ""
    except json.JSONDecodeError as exc:
        return None, f"ffprobe emitted invalid JSON: {exc}"


def _audio_checks(audio: Any, *, require_id3: bool) -> dict[str, dict[str, Any]]:
    checks: dict[str, dict[str, Any]] = {}
    if audio is None:
        return {"parse": _check(False, "mutagen could not identify an audio stream")}

    info = getattr(audio, "info", None)
    checks["parse"] = _check(True, f"mutagen parsed {type(audio).__name__}")
    duration = float(getattr(info, "length", 0.0) or 0.0)
    checks["duration"] = _check(
        duration >= MIN_AUDIO_DURATION,
        f"duration={duration:.3f}s (need >= {MIN_AUDIO_DURATION}s)",
    )

    bitrate = float(getattr(info, "bitrate", 0) or 0)
    bits = int(getattr(info, "bits_per_sample", 0) or 0)
    sample_rate = int(getattr(info, "sample_rate", 0) or 0)
    checks["bitrate"] = _check(
        bitrate > 0 or (bits > 0 and sample_rate > 0),
        f"bitrate={bitrate:.0f} bits_per_sample={bits} sample_rate={sample_rate}",
    )

    if require_id3:
        tags = getattr(audio, "tags", None)
        checks["id3_tag"] = _check(
            tags is not None and len(tags) > 0,
            f"ID3 frames={len(tags) if tags is not None else 0}",
        )
    return checks


def check_audio(path: Path) -> dict[str, dict[str, Any]]:
    checks: dict[str, dict[str, Any]] = {}
    size = path.stat().st_size
    checks["size"] = _check(
        size > MIN_AV_SIZE, f"size={size} bytes (need > {MIN_AV_SIZE})"
    )
    try:
        with path.open("rb") as handle:
            magic = handle.read(3)
    except OSError as exc:
        checks["magic"] = _check(False, str(exc))
    else:
        is_frame_sync = len(magic) >= 2 and magic[0] == 0xFF and magic[1] & 0xE0 == 0xE0
        checks["magic"] = _check(
            magic.startswith(b"ID3") or is_frame_sync,
            f"first bytes={magic.hex()} (need ID3 or MPEG frame sync)",
        )

    if mutagen is None:
        checks["mutagen"] = _check(False, "mutagen not installed; cannot parse audio")
    else:
        try:
            audio = mutagen.File(str(path))
        except (OSError, ValueError) as exc:
            checks["parse"] = _check(False, f"mutagen rejected the file: {exc}")
        else:
            checks.update(_audio_checks(audio, require_id3=path.suffix.lower() == ".mp3"))

    probe, error = _run_ffprobe(path)
    if probe is None:
        checks["ffprobe_duration"] = _check(False, error)
    else:
        duration = float((probe.get("format") or {}).get("duration") or 0)
        checks["ffprobe_duration"] = _check(
            duration > MIN_AUDIOBOOK_DURATION,
            f"format.duration={duration:.3f}s (need > {MIN_AUDIOBOOK_DURATION}s)",
        )
    return checks


# ---------------------------------------------------------------------------
# Audiobook
# ---------------------------------------------------------------------------


def check_audiobook_magic(path: Path, magic: bytes) -> dict[str, dict[str, Any]]:
    checks: dict[str, dict[str, Any]] = {}
    checks["id3_header"] = _check(magic.startswith(b"ID3"), f"first bytes={magic.hex()}")

    sidecar = [
        candidate.name
        for candidate in (path.with_suffix(".chapters.txt"), path.with_suffix(".chapters.json"))
        if candidate.is_file()
    ]
    if mutagen is None:
        checks["mutagen"] = _check(False, "mutagen not installed; cannot parse audio")
        return checks
    try:
        audio = mutagen.File(str(path))
    except (OSError, ValueError) as exc:
        checks["parse"] = _check(False, f"mutagen rejected the file: {exc}")
        return checks
    checks.update(_audio_checks(audio, require_id3=True))

    tags = getattr(audio, "tags", None)
    duration = float(getattr(getattr(audio, "info", None), "length", 0.0) or 0.0)
    checks["chapter_duration"] = _check(
        duration >= MIN_AUDIOBOOK_DURATION,
        f"duration={duration:.3f}s (need >= {MIN_AUDIOBOOK_DURATION}s)",
    )
    chap = sum(1 for key in tags if key.startswith("CHAP")) if tags is not None else 0
    ctoc = sum(1 for key in tags if key.startswith("CTOC")) if tags is not None else 0
    checks["chap_frames"] = _check(chap >= 1, f"CHAP frames={chap}")
    ctoc_detail = f"CTOC frames={ctoc}"
    if sidecar:
        ctoc_detail += f"; sidecars present={sidecar} (not a substitute for ID3 frames)"
    checks["ctoc_frames"] = _check(ctoc >= 1, ctoc_detail)

    probe, error = _run_ffprobe(path)
    if probe is None:
        checks["ffprobe_audio"] = _check(False, error)
    else:
        streams = probe.get("streams") or []
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
        checks["ffprobe_audio"] = _check(
            bool(audio_streams), f"audio streams={len(audio_streams)}"
        )
    return checks


def check_audiobook_zip(path: Path) -> dict[str, dict[str, Any]]:
    checks: dict[str, dict[str, Any]] = {}
    try:
        with zipfile.ZipFile(path) as archive:
            members = [n for n in archive.namelist() if n.lower().endswith(".mp3")]
            checks["zip"] = _check(True, f"{len(archive.namelist())} entries, {len(members)} mp3")
            checks["mp3_members"] = _check(
                bool(members), f"mp3 members={members[:5]}"
            )
            if mutagen is None:
                checks["mutagen"] = _check(False, "mutagen not installed; cannot parse audio")
                return checks
            for index, name in enumerate(members):
                try:
                    payload = archive.read(name)
                    member_audio = mutagen.File(io.BytesIO(payload))
                except (OSError, ValueError, zipfile.BadZipFile) as exc:
                    checks[f"member_{index}"] = _check(False, f"{name}: {exc}")
                    continue
                member_checks = _audio_checks(member_audio, require_id3=True)
                failed = [key for key, value in member_checks.items() if not value["passed"]]
                detail = f"{name}: " + (
                    "all audio checks passed"
                    if not failed
                    else "; ".join(f"{key}: {member_checks[key]['detail']}" for key in failed)
                )
                checks[f"member_{index}"] = _check(not failed, detail)
    except zipfile.BadZipFile as exc:
        checks["zip"] = _check(False, f"not a valid ZIP archive: {exc}")
    return checks


def check_audiobook(path: Path) -> dict[str, dict[str, Any]]:
    try:
        with path.open("rb") as handle:
            magic = handle.read(4)
    except OSError as exc:
        return {"read": _check(False, str(exc))}

    checks: dict[str, dict[str, Any]] = {"magic": _check(False, magic.hex())}
    is_frame_sync = len(magic) >= 2 and magic[0] == 0xFF and magic[1] & 0xE0 == 0xE0
    if magic.startswith(b"ID3") or is_frame_sync:
        checks["magic"] = _check(True, f"chaptered-MP3 magic={magic.hex()}")
        checks.update(check_audiobook_magic(path, magic))
    elif magic.startswith(b"PK\x03\x04"):
        checks["magic"] = _check(True, "ZIP container magic=504b0304")
        checks.update(check_audiobook_zip(path))
    else:
        checks["magic"] = _check(
            False, f"unexpected magic={magic.hex()}; expected ID3, MPEG frame sync, or PK"
        )
    return checks


# ---------------------------------------------------------------------------
# Video
# ---------------------------------------------------------------------------


def _fps(value: Any) -> float:
    text = str(value or "0/0")
    if "/" in text:
        numerator, _, denominator = text.partition("/")
        try:
            den = float(denominator)
            return float(numerator) / den if den else 0.0
        except ValueError:
            return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def check_video(path: Path) -> dict[str, dict[str, Any]]:
    checks: dict[str, dict[str, Any]] = {}
    size = path.stat().st_size
    checks["size"] = _check(
        size > MIN_AV_SIZE, f"size={size} bytes (need > {MIN_AV_SIZE})"
    )

    probe, error = _run_ffprobe(path)
    if probe is None:
        checks["ffprobe"] = _check(False, error)
        return checks

    streams = probe.get("streams") or []
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    checks["ffprobe"] = _check(True, f"{len(video_streams)} video stream(s)")
    checks["video_stream"] = _check(bool(video_streams), f"video streams={len(video_streams)}")
    if not video_streams:
        return checks
    stream = video_streams[0]

    duration = float(stream.get("duration") or (probe.get("format") or {}).get("duration") or 0)
    checks["duration"] = _check(
        duration > MIN_AV_DURATION, f"duration={duration:.3f}s (need > {MIN_AV_DURATION}s)"
    )

    frames_raw = stream.get("nb_frames")
    if frames_raw in (None, "N/A"):
        estimated = duration * _fps(stream.get("avg_frame_rate"))
        checks["nb_frames"] = _check(
            estimated > 0, f"nb_frames=N/A; duration*avg_frame_rate={estimated:.1f}"
        )
    else:
        try:
            frames = int(frames_raw)
        except (TypeError, ValueError):
            frames = 0
        checks["nb_frames"] = _check(frames > 0, f"nb_frames={frames_raw}")

    pix_fmt = str(stream.get("pix_fmt") or "")
    checks["pix_fmt"] = _check(
        pix_fmt in ALLOWED_PIX_FMTS, f"pix_fmt={pix_fmt!r} (allowed {sorted(ALLOWED_PIX_FMTS)})"
    )
    return checks


# ---------------------------------------------------------------------------
# EPUB
# ---------------------------------------------------------------------------


def _container_opf(archive: zipfile.ZipFile) -> str | None:
    try:
        payload = archive.read("META-INF/container.xml")
    except KeyError:
        return None
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return None
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] == "rootfile":
            full_path = element.get("full-path")
            if full_path:
                return full_path
    return None


def _strip_text(payload: bytes) -> str:
    return html.unescape(_HTML_TAG.sub(" ", payload.decode("utf-8", errors="replace")))


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _ncx_navpoints(payload: bytes) -> int:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return 0
    for element in root.iter():
        if _local_name(element.tag) == "navMap":
            return sum(1 for child in element.iter() if _local_name(child.tag) == "navPoint")
    return 0


def _nav_links(payload: bytes) -> int:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        text = payload.decode("utf-8", errors="replace")
        if not re.search(r"<nav[\s>]", text, re.IGNORECASE):
            return 0
        return len(re.findall(r"<a\s+[^>]*href=", text, re.IGNORECASE))
    for element in root.iter():
        if _local_name(element.tag) == "nav":
            return sum(1 for child in element.iter() if _local_name(child.tag) in {"a", "link"})
    return 0


def check_epub(path: Path) -> dict[str, dict[str, Any]]:
    checks: dict[str, dict[str, Any]] = {}
    try:
        archive = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        return {"zip": _check(False, f"not a valid ZIP archive: {exc}")}
    with archive:
        infos = archive.infolist()
        first = infos[0] if infos else None
        checks["mimetype_first"] = _check(
            first is not None and first.filename == "mimetype",
            f"first entry={first.filename if first else None}",
        )
        checks["mimetype_stored"] = _check(
            first is not None and first.compress_type == zipfile.ZIP_STORED,
            f"compress_type={first.compress_type if first else None} (ZIP_STORED=0)",
        )
        mimetype = archive.read("mimetype") if first and first.filename == "mimetype" else b""
        checks["mimetype_content"] = _check(
            mimetype == b"application/epub+zip", f"content={mimetype!r}"
        )

        opf_path = _container_opf(archive)
        checks["container"] = _check(
            bool(opf_path) and opf_path.endswith(".opf"),
            f"container.xml rootfile={opf_path!r}",
        )
        if not opf_path:
            return checks
        try:
            opf_root = ET.fromstring(archive.read(opf_path))
        except ET.ParseError as exc:
            checks["opf"] = _check(False, f"OPF does not parse: {exc}")
            return checks

        manifest: dict[str, str] = {}
        spine: list[str] = []
        for element in opf_root.iter():
            tag = element.tag.rsplit("}", 1)[-1]
            if tag == "item" and element.get("id") and element.get("href"):
                manifest[element.get("id", "")] = element.get("href", "")
            elif tag == "itemref" and element.get("idref"):
                spine.append(element.get("idref", ""))

        checks["spine"] = _check(bool(spine), f"spine items={len(spine)}")
        base = opf_path.rsplit("/", 1)[0] + "/" if "/" in opf_path else ""
        names = set(archive.namelist())
        missing = [
            ref
            for ref in spine
            if ref not in manifest or (base + manifest[ref]) not in names
        ]
        checks["spine_manifest"] = _check(
            bool(spine) and not missing,
            f"missing spine targets={missing}" if missing else "all spine targets present",
        )

        text_parts: list[str] = []
        for ref in spine:
            href = manifest.get(ref)
            if not href:
                continue
            member = base + href
            if member in names:
                text_parts.append(_strip_text(archive.read(member)))
        text = _WHITESPACE.sub(" ", " ".join(text_parts)).strip()
        checks["body_text"] = _check(
            len(text) >= MIN_EPUB_TEXT, f"body text chars={len(text)} (need >= {MIN_EPUB_TEXT})"
        )

        toc_detail = "no NCX navMap navPoint and no nav document link"
        toc_ok = False
        for name in (member for member in names if member.lower().endswith(".ncx")):
            count = _ncx_navpoints(archive.read(name))
            if count:
                toc_ok = True
                toc_detail = f"{name} navMap navPoints={count}"
                break
        if not toc_ok:
            for name in (
                member
                for member in names
                if member.lower().endswith((".xhtml", ".html", ".htm"))
            ):
                count = _nav_links(archive.read(name))
                if count:
                    toc_ok = True
                    toc_detail = f"{name} nav links={count}"
                    break
        checks["toc"] = _check(toc_ok, toc_detail)
    return checks


# ---------------------------------------------------------------------------
# MOBI
# ---------------------------------------------------------------------------


def check_mobi(path: Path) -> dict[str, dict[str, Any]]:
    size = path.stat().st_size
    inspector = shutil.which("ebook-meta")
    if inspector is None:
        tool = _check(
            True, "skip: mobi structurally unverified (no tool); ebook-meta not found"
        )
    else:
        try:
            completed = subprocess.run(
                [inspector, str(path)],
                capture_output=True,
                text=True,
                timeout=FFPROBE_TIMEOUT,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            tool = _check(False, f"ebook-meta could not inspect the file: {exc}")
        else:
            tool = _check(
                completed.returncode == 0 and bool(completed.stdout.strip()),
                f"ebook-meta exited {completed.returncode}",
            )
    return {"size": _check(size > 0, f"size={size} bytes"), "tool": tool}


# ---------------------------------------------------------------------------
# HTML / Markdown / JSON
# ---------------------------------------------------------------------------


class _HtmlText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.headings: list[str] = []
        self._in_title = False
        self._in_head = 0
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "head":
            self._in_head += 1
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.headings.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip:
            self._skip -= 1
        elif tag == "title":
            self._in_title = False
        elif tag == "head":
            self._in_head = max(0, self._in_head - 1)

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        elif self._skip == 0 and self._in_head == 0:
            self.text_parts.append(data)


def check_html(path: Path) -> dict[str, dict[str, Any]]:
    parser = _HtmlText()
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
        parser.feed(raw)
        parser.close()
    except OSError as exc:
        return {"read": _check(False, str(exc))}
    title = _WHITESPACE.sub(" ", " ".join(parser.title_parts)).strip()
    body = _WHITESPACE.sub(" ", " ".join(parser.text_parts)).strip()
    braces = sorted({token for token in ("{{", "}}") if token in raw})
    return {
        "title": _check(bool(title), f"title={title!r}"),
        "headings": _check(
            len(parser.headings) >= MIN_HTML_HEADINGS,
            f"heading count={len(parser.headings)} (need >= {MIN_HTML_HEADINGS})",
        ),
        "literal_braces": _check(not braces, f"literal braces={braces}"),
        "body_text": _check(
            len(body) >= MIN_HTML_TEXT, f"body text chars={len(body)} (need >= {MIN_HTML_TEXT})"
        ),
    }


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            return parts[2]
    return text


def check_markdown(path: Path) -> dict[str, dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"read": _check(False, str(exc))}
    placeholders = _MARKDOWN_PLACEHOLDERS.findall(text)
    h1_count = len(_MARKDOWN_H1.findall(text))
    section_count = len(_MARKDOWN_H2.findall(text))
    words = _WORD.findall(_strip_frontmatter(text))
    return {
        "placeholders": _check(
            not placeholders, f"placeholder markers={placeholders[:5]}"
        ),
        "h1": _check(h1_count >= 1, f"H1 count={h1_count} (need >= 1)"),
        "body_words": _check(
            len(words) >= MIN_MARKDOWN_WORDS,
            f"body words={len(words)} (need >= {MIN_MARKDOWN_WORDS})",
        ),
        "section": _check(
            section_count >= 1, f"H2 section count={section_count} (need >= 1)"
        ),
        "links": _check(bool(_MARKDOWN_LINK.search(text)), "inline link or URL present"),
    }


def _find_type(payload: Any) -> str | None:
    if isinstance(payload, dict):
        if isinstance(payload.get("@type"), str) and payload["@type"]:
            return payload["@type"]
        graph = payload.get("@graph")
        if isinstance(graph, list):
            for node in graph:
                if isinstance(node, dict) and isinstance(node.get("@type"), str):
                    return node["@type"]
    return None


def check_json(path: Path, *, agent: bool) -> dict[str, dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"read": _check(False, str(exc))}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return {"parse": _check(False, f"json.loads failed: {exc}")}

    checks: dict[str, dict[str, Any]] = {"parse": _check(True, f"parsed {type(payload).__name__}")}
    keys = list(payload) if isinstance(payload, dict) else []
    checks["object"] = _check(
        len(keys) >= 3, f"top-level keys={len(keys)} (need >= 3)"
    )
    if agent:
        json_type = _find_type(payload)
        checks["jsonld_type"] = _check(bool(json_type), f"@type={json_type!r}")
    return checks


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def check_artifact(path: str | Path) -> dict[str, Any]:
    """Structurally validate one artifact; pure inspection, no writes."""
    artifact = Path(path)
    fmt = detect_format(artifact)
    if fmt is None:
        return _result(
            artifact,
            "unknown",
            {"format": _check(False, f"unrecognised extension {artifact.suffix!r}")},
        )
    if not artifact.is_file():
        return _result(artifact, fmt, {"path": _check(False, "file not found")})

    if fmt == "audio":
        checks = check_audio(artifact)
    elif fmt == "audiobook":
        checks = check_audiobook(artifact)
    elif fmt == "video":
        checks = check_video(artifact)
    elif fmt == "epub":
        checks = check_epub(artifact)
    elif fmt == "mobi":
        checks = check_mobi(artifact)
    elif fmt == "html":
        checks = check_html(artifact)
    elif fmt == "markdown":
        checks = check_markdown(artifact)
    elif fmt == "json":
        checks = check_json(artifact, agent=False)
    else:
        checks = check_json(artifact, agent=True)
    return _result(artifact, fmt, checks)


def _render_human(result: dict[str, Any]) -> list[str]:
    status = "PASS" if result["passed"] else "FAIL"
    lines = [f"{status} {result['format']} {result['path']}"]
    for name, outcome in result["checks"].items():
        if not outcome["passed"]:
            lines.append(f"    {name}: {outcome['detail']}")
    return lines


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the structure of generated product artifacts (audio, "
            "audiobook, video, epub, mobi, html, markdown, json/agent)."
        )
    )
    parser.add_argument("paths", nargs="+", help="artifact paths to check")
    parser.add_argument("--json", action="store_true", help="emit one JSON object per artifact")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    missing = [p for p in args.paths if not Path(p).is_file()]
    if missing:
        for path in missing:
            print(f"error: file not found: {path}", file=sys.stderr)
        return 2

    results = [check_artifact(path) for path in args.paths]
    if args.json:
        for result in results:
            print(json.dumps(result))
    else:
        for result in results:
            for line in _render_human(result):
                print(line)
    return 0 if all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
