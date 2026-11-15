#!/usr/bin/env python3
"""Dependency & capability probe for the local machine (detection only).

Answers one question before any work starts: **what can this machine do?**
It checks interpreter/venv, whether the repo's declared Python dependencies
are installed, which external binaries are on PATH, and whether required
env vars / config files exist — then emits a capability verdict:

    TEXT    text line      — a usable interpreter
    AUDIO   speech line    — ffmpeg + ffprobe + any TTS/ASR channel
                             (edge-tts / whisper / cloud key)
    VIDEO   video line     — AUDIO all satisfied + a renderer
                             (hyperframes(bun) / remotion(node) / ffmpeg chain)
    BROWSER browser line   — chrome / chromium / playwright, at least one

Design constraints (hard):
- stdlib only; runs on Windows and POSIX; ``--json`` for machine readers;
- never touches the network; never mutates any state (files, env, installs);
- env vars are reported as ``set``/``unset`` only — values are never printed;
- a missing *external binary* is reported with an install hint but the probe
  NEVER installs anything (installing is an Owner decision, not ours).

Usage::

    python scripts/check_deps.py            # human-readable report
    python scripts/check_deps.py --json     # machine-readable
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

# Dist names as declared in pyproject [project.optional-dependencies] that
# carry capability weight (checked in addition to core dependencies).
CAPABILITY_EXTRAS = ("web", "tts", "video", "pdf", "ebook")

# External binaries relevant to AutoInfo's output lines.
BINARIES = ("ffmpeg", "ffprobe", "node", "npm", "bun", "whisper")

# Cloud TTS/ASR env vars (presence-only, part of the AUDIO TTS-channel test).
CLOUD_TTS_ENV_VARS = ("AZURE_SPEECH_KEY", "OPENAI_API_KEY")

# Required runtime env vars (harness-run-facts.md: only the LLM key is hard).
REQUIRED_ENV_VARS = ("AUTOINFO_LLM_API_KEY",)

# Runtime config files that must exist for a configured domain (gitignored).
CONFIG_FILES = (".autoinfo/config.yaml",)


def _check_interpeter() -> dict[str, Any]:
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    return {
        "platform": sys.platform,
        "python": platform.python_version(),
        "executable": sys.executable,
        "in_venv": in_venv,
        "venv_path": sys.prefix if in_venv else None,
    }


def _declared_dependencies() -> dict[str, list[str]]:
    """Read dependency names from pyproject.toml (stdlib tomllib, 3.11+)."""
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover - py<3.11 fallback
        import tomli as tomllib  # type: ignore[no-redef]

    pyproject = REPO_ROOT / "pyproject.toml"
    if not pyproject.exists():
        return {"dependencies": [], "extras": {}}
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    project = data.get("project", {})
    deps = []
    for raw in project.get("dependencies", []):
        deps.append(_dist_name(raw))
    extras: dict[str, list[str]] = {}
    for extra, entries in (project.get("optional-dependencies") or {}).items():
        extras[extra] = [_dist_name(raw) for raw in entries]
    return {"dependencies": deps, "extras": extras}


def _dist_name(requirement: str) -> str:
    """``edge-tts>=6.1 ; python_version<'3.13'`` → ``edge-tts``."""
    name = requirement.split(";")[0].split("[")[0]
    for op in (">=", "<=", "==", ">", "<", "~=", "!="):
        if op in name:
            name = name.split(op)[0]
            break
    return name.strip()


def _installed(dist: str) -> str | None:
    """Installed version of *dist*, or None. Never imports the package."""
    try:
        return metadata.version(dist)
    except metadata.PackageNotFoundError:
        return None


def _check_python_deps() -> dict[str, Any]:
    declared = _declared_dependencies()
    core = {d: _installed(d) for d in declared["dependencies"]}
    extras = {
        extra: {d: _installed(d) for d in dists}
        for extra, dists in declared["extras"].items()
        if extra in CAPABILITY_EXTRAS
    }
    core_missing = sorted(d for d, v in core.items() if v is None)
    return {
        "core_declared": len(core),
        "core_missing": core_missing,
        "extras": {
            name: {
                "missing": sorted(d for d, v in dists.items() if v is None),
                "installed": sorted(d for d, v in dists.items() if v is not None),
            }
            for name, dists in extras.items()
        },
    }


def _playwright_chrome() -> list[Path]:
    """Locate chrome/chromium binaries inside playwright browser caches."""
    candidates: list[Path] = []
    local = os.environ.get("LOCALAPPDATA")
    cache_roots = [
        Path(local) / "ms-playwright" if local else None,
        Path.home() / ".cache" / "ms-playwright",
        Path.home() / ".cache" / "puppeteer",
        Path.home() / ".cache" / "hyperframes" / "chrome",
    ]
    for root in cache_roots:
        if root is None or not root.is_dir():
            continue
        for pattern in ("chromium-*/chrome-win*/chrome.exe", "chromium-*/chrome-linux*/chrome"):
            candidates.extend(root.glob(pattern))
        for pattern in (
            "chrome-*/chrome-win*/chrome.exe",
            "chrome-headless-shell-*/**/chrome-headless-shell",
            "chrome-headless-shell-*/**/chrome-headless-shell.exe",
        ):
            candidates.extend(root.glob(pattern))
    return sorted(set(p for p in candidates if p.exists()))


def _check_binaries() -> dict[str, Any]:
    on_path = {b: shutil.which(b) for b in BINARIES}
    chrome_which = shutil.which("chrome") or shutil.which("chromium")
    chrome_cached = _playwright_chrome()
    return {
        "on_path": {b: p for b, p in on_path.items()},
        "chrome_which": chrome_which,
        "chrome_cached": [str(p) for p in chrome_cached],
        "browser_available": bool(chrome_which or chrome_cached),
    }


def _check_env_and_config() -> dict[str, Any]:
    def _presence(names: tuple[str, ...]) -> dict[str, str]:
        return {name: "set" if os.environ.get(name) else "unset" for name in names}

    return {
        "required_env": _presence(REQUIRED_ENV_VARS),
        "cloud_tts_env": _presence(CLOUD_TTS_ENV_VARS),
        "config_files": {p: (REPO_ROOT / p).exists() for p in CONFIG_FILES},
    }


def _tts_channel_available(deps: dict[str, Any], envcfg: dict[str, Any]) -> bool:
    edge_tts_installed = (
        "edge-tts" not in deps["extras"].get("tts", {}).get("missing", [])
        and _installed("edge-tts") is not None
    )
    whisper_installed = _installed("openai-whisper") is not None or bool(shutil.which("whisper"))
    cloud_key = any(v == "set" for v in envcfg["cloud_tts_env"].values())
    return edge_tts_installed or whisper_installed or cloud_key


def capability_verdict(
    deps: dict[str, Any], binaries: dict[str, Any], envcfg: dict[str, Any]
) -> dict[str, bool]:
    """The four-line verdict this probe exists to produce."""
    text = True  # a usable interpreter is running this probe
    ffmpeg_ok = bool(binaries["on_path"].get("ffmpeg"))
    ffprobe_ok = bool(binaries["on_path"].get("ffprobe"))
    audio = ffmpeg_ok and ffprobe_ok and _tts_channel_available(deps, envcfg)
    renderer = (
        bool(binaries["on_path"].get("bun"))
        or bool(binaries["on_path"].get("node"))
        or (ffmpeg_ok and ffprobe_ok)  # ffmpeg synthesis chain
    )
    video = audio and renderer
    browser = bool(binaries["browser_available"])
    return {"TEXT": text, "AUDIO": audio, "VIDEO": video, "BROWSER": browser}


def collect() -> dict[str, Any]:
    env = _check_interpeter()
    deps = _check_python_deps()
    binaries = _check_binaries()
    envcfg = _check_env_and_config()
    verdict = capability_verdict(deps, binaries, envcfg)
    missing: list[str] = []
    missing.extend(f"python-dep:{d}" for d in deps["core_missing"])
    for name, entry in binaries["on_path"].items():
        if name in ("ffmpeg", "ffprobe", "bun", "node") and not entry:
            missing.append(f"binary:{name}")
    if not binaries["browser_available"]:
        missing.append("browser:chrome/chromium/playwright")
    missing.extend(f"env:{k}" for k, v in envcfg["required_env"].items() if v == "unset")
    return {
        "environment": env,
        "python_deps": deps,
        "binaries": binaries,
        "env_config": envcfg,
        "capability": verdict,
        "missing": missing,
    }


_INSTALL_HINTS = {
    "ffmpeg": (
        "winget install Gyan.FFmpeg  (Windows)  |  apt install ffmpeg / brew install ffmpeg"
        "  — 外部二进制，装不装由 Owner 决定"
    ),
    "ffprobe": "随 ffmpeg 一起安装（同一发行包） — 外部二进制，装不装由 Owner 决定",
    "bun": (
        'powershell -c "irm bun.sh/install.ps1|iex"  (Windows)'
        "  |  curl -fsSL bun.sh/install | bash  — 外部二进制，装不装由 Owner 决定"
    ),
    "node": (
        "winget install OpenJS.NodeJS.LTS  (Windows)  |  apt install nodejs npm"
        "  — 外部二进制，装不装由 Owner 决定"
    ),
    "AUTOINFO_LLM_API_KEY": (
        "在系统级环境变量设置（BYOK）；项目文件里只写 ${AUTOINFO_LLM_API_KEY} 引用"
    ),
    "edge-tts": 'pip install -e ".[tts]"  — 仓库声明的 Python 依赖，允许安装',
}


def _hint_for(item: str) -> str:
    key = item.split(":", 1)[-1]
    return _INSTALL_HINTS.get(key, "")


def render(report: dict[str, Any]) -> str:
    env = report["environment"]
    deps = report["python_deps"]
    bins = report["binaries"]
    envcfg = report["env_config"]
    cap = report["capability"]
    lines: list[str] = []
    lines.append("== 环境 ==")
    venv_note = f"是 {env['venv_path']}" if env["in_venv"] else "否（系统解释器）"
    lines.append(f"平台 {env['platform']} · Python {env['python']} · venv={venv_note}")
    lines.append("")
    lines.append("== Python 依赖 ==")
    core_missing = deps["core_missing"]
    core_line = f"核心依赖：声明 {deps['core_declared']} 项，缺 {len(core_missing)} 项"
    core_line += f"：{', '.join(core_missing)}" if core_missing else "（全部可装）"
    lines.append(core_line)
    for extra, entry in deps["extras"].items():
        if entry["missing"]:
            lines.append(f"  extra[{extra}] 缺：{', '.join(entry['missing'])}")
    lines.append("")
    lines.append("== 外部二进制 ==")
    for name in ("ffmpeg", "ffprobe", "bun", "node", "whisper"):
        found = bins["on_path"].get(name)
        lines.append(f"  {name:9s} {'✓ ' + found if found else '✗ 不在 PATH'}")
    chrome = bins["chrome_which"] or (bins["chrome_cached"][0] if bins["chrome_cached"] else None)
    n_cached = len(bins["chrome_cached"])
    chrome_state = f"✓ {chrome}" if chrome else "✗ 未找到"
    chrome_note = f"（playwright/缓存里另有 {n_cached} 个）" if n_cached else ""
    lines.append(f"  chrome    {chrome_state}{chrome_note}")
    lines.append("")
    lines.append("== 环境变量与配置 ==")
    for name, state in {**envcfg["required_env"], **envcfg["cloud_tts_env"]}.items():
        lines.append(f"  {name} = {state}")
    for path, exists in envcfg["config_files"].items():
        lines.append(f"  {path} {'存在' if exists else '不存在'}")
    lines.append("")
    lines.append("== 能力判定 ==")
    lines.append(f"  TEXT    {'✓' if cap['TEXT'] else '✗'}  文本：可用解释器")
    lines.append(f"  AUDIO   {'✓' if cap['AUDIO'] else '✗'}  语音：ffmpeg + ffprobe + TTS/ASR 通道")
    lines.append(
        f"  VIDEO   {'✓' if cap['VIDEO'] else '✗'}  视频：AUDIO 全满足 + 渲染器"
        "（hyperframes/remotion/ffmpeg 链）"
    )
    lines.append(
        f"  BROWSER {'✓' if cap['BROWSER'] else '✗'}  浏览器：chrome/chromium/playwright 至少一个"
    )
    lines.append("")
    lines.append("== 结论 ==")
    if report["missing"]:
        lines.append(f"缺：{', '.join(report['missing'])}")
        for item in report["missing"]:
            hint = _hint_for(item)
            if hint:
                lines.append(f"  {item} → 最小装法（仅提示，不执行）：{hint}")
        blocked = [c for c in ("AUDIO", "VIDEO") if not cap[c]]
        if blocked:
            lines.append(
                f"判定为缺失的能力线（{', '.join(blocked)}）上的活一律标 ENV-MISSING 交回，"
                "不安装、不找替代、不绕路。"
            )
    else:
        lines.append("可跑：无缺件。")
    return "\n".join(lines)


def main() -> int:
    # Windows consoles default to a legacy codepage (gbk/cp936) that cannot
    # encode the ✓/✗ glyphs this report uses — reconfigure before printing.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="machine-readable JSON output")
    args = parser.parse_args()
    report = collect()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render(report))
    return 0  # detection + report only; consumers read the verdict, exit code stays neutral


if __name__ == "__main__":
    sys.exit(main())
