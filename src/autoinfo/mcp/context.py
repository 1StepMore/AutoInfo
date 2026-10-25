"""Shared helper tier for the AutoInfo MCP server.

Every helper that a moved handler reads lives here so ``mcp/tools/<domain>.py``
modules can reach it through ONE module object (``from autoinfo.mcp import
context as mcp_context``) without importing the server hub. That calling
convention is load-bearing: tests patch ``autoinfo.mcp.context.<name>``, so a
from-import would bind a copy and silently stop intercepting.

This module must never import ``autoinfo.mcp.server`` or ``autoinfo.mcp.tools``
(guarded by ``tests/mcp/test_tools_import_boundary.py``).

Definitions below were moved verbatim out of ``server.py`` (bodies are
byte-identical; only ``logger`` differs by design, keeping one logging target
for the whole server).
"""

from __future__ import annotations

import base64
import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, TypeVar, overload

import httpx

from autoinfo import db
from autoinfo.config import (
    SOURCE_KEY_ENV_VARS,
    VALID_SOURCE_TYPES,
    ConfigNotFoundError,
)
from autoinfo.kb import DirectorOnlyError, PromotionRejected
from autoinfo.mcp.errors import ErrorCode, error_response, success_response

logger = logging.getLogger("autoinfo.mcp.server")


def _config_path() -> Path:
    """Return the path to the project's ``.autoinfo/config.yaml``."""
    return Path.cwd() / ".autoinfo" / "config.yaml"


def _load_config() -> Any:
    """Load the AutoInfo configuration."""
    from autoinfo.config import load_config

    return load_config(_config_path())


def _save_config(config: Any) -> None:
    """Write a Config dataclass tree back to ``.autoinfo/config.yaml``."""
    from autoinfo.config import save_config as _public_save

    _public_save(config, _config_path())


def _find_domain(config: Any, name: str) -> Any | None:
    """Return the domain config object for *name*, or ``None``."""
    for d in config.domains:
        if d.name == name:
            return d
    return None


def _job_db_path() -> Path:
    """Return the path to the shared ``autoinfo.db``."""
    return Path.cwd() / "autoinfo.db"


T = TypeVar("T")


def _with_job_db(fn: Callable[[sqlite3.Connection], T]) -> T:
    """Open a connection, call *fn*, then close.

    Uses the same PRAGMA settings as :class:`~autoinfo.kb.SQLiteIndex`.
    """
    conn = db.connect(_job_db_path())
    _init_job_state_table(conn)
    try:
        return fn(conn)
    finally:
        conn.close()


def _init_job_state_table(conn: sqlite3.Connection) -> None:
    """Create the ``job_state`` table if it does not exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS job_state (
            job_id          TEXT PRIMARY KEY,
            state_type      TEXT NOT NULL,
            domain          TEXT NOT NULL DEFAULT '',
            status          TEXT NOT NULL DEFAULT 'running',
            progress_pct    REAL NOT NULL DEFAULT 0.0,
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
            metadata        TEXT NOT NULL DEFAULT '{}'
        )
    """)
    conn.commit()


def _save_job_state(
    job_id: str,
    state_type: str,
    domain: str,
    status: str,
    progress_pct: float,
    metadata: dict[str, Any],
) -> None:
    """Insert-or-update a row in ``job_state``."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    meta_json = json.dumps(metadata)

    def _write(conn: sqlite3.Connection) -> None:
        existing = conn.execute(
            "SELECT job_id FROM job_state WHERE job_id = ?", (job_id,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE job_state
                   SET state_type = ?, domain = ?, status = ?,
                       progress_pct = ?, updated_at = ?,
                       metadata = ?
                   WHERE job_id = ?""",
                (state_type, domain, status, progress_pct, now, meta_json, job_id),
            )
        else:
            conn.execute(
                """INSERT INTO job_state
                   (job_id, state_type, domain, status, progress_pct,
                    created_at, updated_at, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (job_id, state_type, domain, status, progress_pct, now, now, meta_json),
            )
        conn.commit()

    _with_job_db(_write)


def _load_job_state(job_id: str) -> dict[str, Any] | None:
    """Return the full job state row as a dict, or ``None``."""

    def _read(conn: sqlite3.Connection) -> dict[str, Any] | None:
        row = conn.execute("SELECT * FROM job_state WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        meta = _safe_json_load(row["metadata"])
        return {
            "job_id": row["job_id"],
            "state_type": row["state_type"],
            "domain": row["domain"],
            "status": row["status"],
            "progress_pct": row["progress_pct"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            **meta,
        }

    return _with_job_db(_read)


def _load_latest_domain_state(domain: str, state_type: str) -> dict[str, Any] | None:
    """Return the most recent job state for *domain*+*state_type*, or ``None``."""

    def _read(conn: sqlite3.Connection) -> dict[str, Any] | None:
        row = conn.execute(
            """SELECT * FROM job_state
               WHERE domain = ? AND state_type = ?
               ORDER BY created_at DESC LIMIT 1""",
            (domain, state_type),
        ).fetchone()
        if row is None:
            return None
        meta = _safe_json_load(row["metadata"])
        return {
            "job_id": row["job_id"],
            "state_type": row["state_type"],
            "domain": row["domain"],
            "status": row["status"],
            "progress_pct": row["progress_pct"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            **meta,
        }

    return _with_job_db(_read)


def _safe_json_load(raw: str) -> dict[str, Any]:
    """Parse JSON string, returning ``{}`` on failure."""
    try:
        val = json.loads(raw)
        return val if isinstance(val, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _detect_phase(
    result: dict[str, Any],
    config_path: Any,
    collections_dir: Path,
    knowledge_dir: Path,
) -> str:
    """Determine system operational phase from diagnostic results.

    Returns one of: uninitialized, llm_unconfigured, no_sources,
    ready_to_collect, operational.
    """
    if not config_path or "config_error" in result:
        return "uninitialized"
    if not result["llm"].get("key_configured", False):
        return "llm_unconfigured"
    if result["sources"]["count"] == 0:
        return "no_sources"

    has_collected = False
    try:
        if collections_dir.is_dir():
            has_collected = any(collections_dir.iterdir())
    except OSError:
        pass
    if not has_collected:
        try:
            raw_dir = knowledge_dir / "01-Raw"
            if raw_dir.is_dir():
                has_collected = any(raw_dir.iterdir())
        except OSError:
            pass
    if not has_collected:
        return "ready_to_collect"

    return "operational"


def _detect_kb_status() -> str:
    """Detect knowledge base initialisation status.

    Returns:
        ``"uninitialized"`` — ``knowledge/`` directory does not exist.
        ``"empty"`` — ``knowledge/`` directory exists but has no content
            (no tier subdirectories with files inside).
        ``"operational"`` — ``knowledge/`` directory exists and has
            content in at least one tier subdirectory.
    """
    knowledge_dir = Path("knowledge")

    if not knowledge_dir.is_dir():
        return "uninitialized"

    # Check if any tier subdirectory (01-Raw, 02-Draft, 03-Wiki) has files
    has_content = False
    try:
        for entry in knowledge_dir.iterdir():
            if entry.is_dir() and any(entry.iterdir()):
                has_content = True
                break
    except OSError:
        pass

    if not has_content:
        return "empty"

    return "operational"


_PLATFORM_INFO: dict[str, dict[str, Any]] = {
    "rss": {
        "name": "RSS/Atom Feed",
        "description": "Fetch content from RSS or Atom feeds",
        "output_formats": ["xml", "json"],
    },
    "api": {
        "name": "REST API",
        "description": "Call REST API endpoints that return JSON data (PubMed via name match, or generic HTTP API)",
        "output_formats": ["json"],
    },
    "web": {
        "name": "Web Page",
        "description": "Extract content from web pages using trafilatura/readability",
        "output_formats": ["html", "markdown"],
    },
    "webhook": {
        "name": "Webhook Receiver",
        "description": "Receive pushed content via HTTP POST webhooks",
        "output_formats": ["json"],
    },
    "email": {
        "name": "Email (IMAP)",
        "description": "Collect content from email inboxes via IMAP",
        "output_formats": ["html", "text"],
    },
    "email_imap": {
        "name": "Email (IMAP)",
        "description": "Collect content from email inboxes via IMAP",
        "output_formats": ["html", "text"],
    },
    "pdf": {
        "name": "PDF Document",
        "description": "Extract text content from PDF documents",
        "output_formats": ["text", "markdown"],
    },
    "apple_podcasts": {
        "name": "Apple Podcasts (iTunes Search)",
        "description": "Search Apple Podcasts via free iTunes Search API (shows only, no episodes)",
        "output_formats": ["json"],
    },
    "dblp": {
        "name": "DBLP",
        "description": "Computer science bibliography via the DBLP API",
        "output_formats": ["json"],
    },
    "nyt": {
        "name": "NYT",
        "description": "New York Times article search API",
        "output_formats": ["json"],
    },
    "openalex": {
        "name": "OpenAlex",
        "description": "Open scholarly metadata via the OpenAlex API",
        "output_formats": ["json"],
    },
    "ap_api": {
        "name": "AP API",
        "description": "Associated Press content API (paid)",
        "output_formats": ["json"],
    },
    "reuters_mcp": {
        "name": "Reuters MCP",
        "description": "Reuters content via the Reuters MCP server",
        "output_formats": ["json"],
    },
    "reddit": {
        "name": "Reddit",
        "description": "Reddit submissions and comments via the JSON API",
        "output_formats": ["json"],
    },
    "spotify": {
        "name": "Spotify",
        "description": "Spotify shows and episodes via the Spotify API",
        "output_formats": ["json"],
    },
    "youtube": {
        "name": "YouTube",
        "description": "YouTube videos and playlists via the YouTube Data API",
        "output_formats": ["json"],
    },
    "bilibili": {
        "name": "Bilibili",
        "description": "Bilibili video content via the public API",
        "output_formats": ["json"],
    },
    "yahoo_finance": {
        "name": "Yahoo Finance",
        "description": "Yahoo Finance market data quotes",
        "output_formats": ["json"],
    },
    "quandl": {
        "name": "Quandl (Nasdaq Data Link)",
        "description": "Financial and economic datasets via Quandl",
        "output_formats": ["json"],
    },
    "ssrn": {
        "name": "SSRN",
        "description": "SSRN preprint repository (working papers)",
        "output_formats": ["json"],
    },
    "gdelt": {
        "name": "GDELT",
        "description": "GDELT global news event database",
        "output_formats": ["json"],
    },
    "huggingface": {
        "name": "Hugging Face",
        "description": "Hugging Face hub datasets and content",
        "output_formats": ["json"],
    },
    "kaggle": {
        "name": "Kaggle",
        "description": "Kaggle datasets and competitions",
        "output_formats": ["json"],
    },
    "unpaywall": {
        "name": "Unpaywall",
        "description": "Open-access scholarly full text via Unpaywall",
        "output_formats": ["json"],
    },
    "core": {
        "name": "CORE",
        "description": "CORE aggregator of open-access research papers",
        "output_formats": ["json"],
    },
    "akshare": {
        "name": "AKShare",
        "description": "Chinese A-share market data via AKShare",
        "output_formats": ["json"],
    },
    "sec_edgar": {
        "name": "SEC EDGAR",
        "description": "SEC EDGAR company filings (ticker → CIK → submissions)",
        "output_formats": ["json"],
    },
    "edx_sitemap": {
        "name": "edX Sitemap",
        "description": "edX course catalog via sitemap index",
        "output_formats": ["xml", "json"],
    },
}


def _default_platform_info(source_type: str) -> dict[str, Any]:
    """Fallback metadata for source types without a curated entry."""
    return {
        "name": source_type.replace("_", " ").title(),
        "description": f"{source_type} source platform",
        "output_formats": ["json"],
    }


PLATFORMS: list[dict[str, Any]] = [
    {"type": source_type, **_PLATFORM_INFO.get(source_type, _default_platform_info(source_type))}
    for source_type in sorted(VALID_SOURCE_TYPES)
]


_SOURCE_SETTINGS_KEY_KEYS: frozenset[str] = frozenset(
    {"api_key", "client_id", "client_secret", "token", "password", "secret"}
)


_REQUIRED_KEYS_DOCS_REF = "docs/dev/required-api-keys.md"


def _source_key_status(source_type: str) -> dict[str, Any]:
    """Report whether *source_type* needs an API key and whether it is configured.

    Returns ``{"key_required", "key_configured", "env_vars", "missing_env_vars"}``.
    Types without a known key contract report ``key_required: False``.
    """
    env_vars = list(SOURCE_KEY_ENV_VARS.get(source_type, ()))
    if not env_vars:
        return {"key_required": False, "key_configured": True, "env_vars": []}
    missing = [v for v in env_vars if not os.environ.get(v)]
    return {
        "key_required": True,
        "key_configured": not missing,
        "env_vars": env_vars,
        "missing_env_vars": missing,
    }


def _demo_sources_defs(domain: str) -> list[dict[str, Any]]:
    """Load a demo domain's source definitions as plain dicts (pre-init).

    Returns ``[{"name", "type", "requires_key", "settings"}]``.  Used by
    ``_detect_missing_source_keys`` when no project config exists yet (the
    ``init_project`` flow) so onboarding can still see key requirements.
    """
    from autoinfo.cli.init import _DEMO_DOMAINS_DIR

    try:
        import yaml as _yaml

        demo_yaml = _DEMO_DOMAINS_DIR / domain / "sources.yaml"
        raw = _yaml.safe_load(demo_yaml.read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    defs: list[dict[str, Any]] = []
    for s in raw.get("sources", []) or []:
        if not isinstance(s, dict):
            continue
        settings_raw = s.get("settings")
        defs.append(
            {
                "name": str(s.get("name", "")),
                "type": str(s.get("type", "api")),
                "requires_key": bool(s.get("requires_key", False)),
                "settings": dict(settings_raw) if isinstance(settings_raw, dict) else {},
            }
        )
    return defs


def _detect_missing_source_keys(
    domain: str,
    sources_yaml: Path | None = None,
) -> list[dict[str, Any]]:
    """Detect sources in *domain* whose required API keys are unconfigured.

    A source is flagged when at least one of its canonical env vars (see
    ``SOURCE_KEY_ENV_VARS``) is absent from the environment, or when the
    source declares ``requires_key: true`` in YAML with no known env var to
    point at.  A credential delivered in the source ``settings`` block
    satisfies the requirement.  Returns ``[{"name", "type", "env_vars"}]``
    where ``env_vars`` may be empty for YAML-declared requirements without a
    canonical env var.
    """
    if sources_yaml is not None:
        try:
            import yaml as _yaml

            raw = _yaml.safe_load(sources_yaml.read_text(encoding="utf-8")) or {}
        except Exception:
            raw = {}
        source_defs: list[dict[str, Any]] = []
        for s in raw.get("sources", []) or []:
            if not isinstance(s, dict):
                continue
            settings_raw = s.get("settings")
            source_defs.append(
                {
                    "name": str(s.get("name", "")),
                    "type": str(s.get("type", "api")),
                    "requires_key": bool(s.get("requires_key", False)),
                    "settings": dict(settings_raw) if isinstance(settings_raw, dict) else {},
                }
            )
    else:
        source_defs = []
        try:
            config = _load_config()
            domain_cfg = _find_domain(config, domain)
            if domain_cfg is not None:
                source_defs = [
                    {
                        "name": s.name,
                        "type": s.type,
                        "requires_key": bool(s.requires_key),
                        "settings": dict(s.settings or {}),
                    }
                    for s in domain_cfg.sources
                ]
        except Exception:
            source_defs = []
        if not source_defs:
            source_defs = _demo_sources_defs(domain)

    missing: list[dict[str, Any]] = []
    for sdef in source_defs:
        name = str(sdef.get("name", ""))
        stype = str(sdef.get("type", "api"))
        settings_raw = sdef.get("settings")
        settings = settings_raw if isinstance(settings_raw, dict) else {}
        if any(k in settings for k in _SOURCE_SETTINGS_KEY_KEYS):
            continue
        env_vars = list(SOURCE_KEY_ENV_VARS.get(stype, ()))
        if env_vars:
            unconfigured = [v for v in env_vars if not os.environ.get(v)]
            if unconfigured:
                missing.append({"name": name, "type": stype, "env_vars": unconfigured})
        elif sdef.get("requires_key"):
            missing.append({"name": name, "type": stype, "env_vars": []})
    return missing


_VALID_SOURCE_TYPES = VALID_SOURCE_TYPES


def _validate_url(
    url: str,
    source_type: str | None = None,
) -> str | None:
    """Return an error message if *url* is invalid, or ``None``.

    Accepts different URL schemes depending on *source_type*:
    - email: imap://, imaps://
    - pdf: file://, http://, https://
    - other types: http://, https://
    """
    if not url or not isinstance(url, str):
        return "URL is required"
    url = url.strip()
    if not url:
        return "URL is required"

    _valid_schemes: tuple[str, ...]
    if source_type == "email":
        _valid_schemes = ("imap://", "imaps://")
    elif source_type == "pdf":
        _valid_schemes = ("file://", "http://", "https://")
    else:
        _valid_schemes = ("http://", "https://")

    if not url.startswith(_valid_schemes):
        schemes_str = ", ".join(s.rstrip("/") + "://" for s in _valid_schemes)
        return f"URL must start with {schemes_str} for source type '{source_type or 'default'}'"
    parts = url.split("://", 1)
    if len(parts) != 2 or not parts[1]:
        return "URL must have a valid host"
    return None


def _validate_source_type(type_: str) -> str | None:
    """Return an error message if *type_* is invalid, or ``None``."""
    if not type_ or not isinstance(type_, str):
        return "Source type is required"
    if type_ not in _VALID_SOURCE_TYPES:
        return (
            f"Invalid source type '{type_}'. "
            f"Must be one of: {', '.join(sorted(_VALID_SOURCE_TYPES))}"
        )
    return None


def _suggest_extract_fields(source_type: str) -> list[str]:
    """Return recommended extract fields for a given source type."""
    suggestions: dict[str, list[str]] = {
        "pubmed": ["pmid", "doi", "authors", "journal"],
        "api": ["pmid", "doi", "authors", "journal"],
        "rss": ["title", "pub_date", "description"],
        "web": ["description", "author", "published_date"],
    }
    return suggestions.get(source_type, ["title", "description"])


def _chain_contains_timeout(exc: BaseException) -> bool:
    """Walk the exception cause/context chain looking for a timeout.

    ``call_with_fallback`` raises ``RuntimeError`` with the last provider
    error as ``__cause__``; a timeout can sit anywhere in that chain (e.g.
    a wrapped ``httpx.TimeoutException``).
    """
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, httpx.TimeoutException):
            return True
        current = current.__cause__ or current.__context__
    return False


def _infer_format(content_type: str, content_preview: str) -> str:
    """Infer content format from content-type header and body preview."""
    if "xml" in content_type:
        return "xml"
    if "json" in content_type:
        return "json"
    if "html" in content_type or "xhtml" in content_type:
        return "html"
    if content_preview.strip().startswith(("<rss", "<feed", "<?xml")):
        return "rss"
    if content_preview.strip().startswith("{"):
        return "json"
    return "unknown"


OUTPUTS_DIR = Path("outputs")


_PERSIST_EXT_BY_FORMAT: dict[str, str] = {
    "json": ".json",
    "agent": ".json",
    "markdown": ".md",
    "html": ".html",
    "audio": ".mp3",
    "video": ".mp4",
    "epub": ".epub",
    "audiobook": ".zip",
}


def _persist_output(
    domain: str,
    product: str,
    format: str,
    content: Any,
) -> str:
    """Write *content* under ``OUTPUTS_DIR/<domain>``; return the relative path.

    Filename: ``<product>-<format>-<YYYYmmdd-HHMMSS>.<ext>`` where the
    extension is derived from *format* (json/agent → ``.json``, markdown →
    ``.md``, html → ``.html``, audio → ``.mp3``, epub → ``.epub``,
    audiobook → ``.zip``).

    Content handling:

    - json/agent: pretty-printed JSON (``ensure_ascii=False, indent=2``).
      *content* may be a dict (re-dumped for pretty JSON) or a str that is
      parsed first; unparseable strings are written raw.
    - audio/epub/audiobook: *content* is a base64 string in the envelope —
      decoded and written as bytes.
    - everything else (markdown/html): written as text as-is.
    """
    _stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    _ext = _PERSIST_EXT_BY_FORMAT.get(format, ".txt")
    _dir = OUTPUTS_DIR / domain
    os.makedirs(_dir, exist_ok=True)
    _path = _dir / f"{product}-{format}-{_stamp}{_ext}"
    if format in ("json", "agent"):
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except (ValueError, TypeError):
                pass
        if isinstance(content, (dict, list)):
            _path.write_text(
                json.dumps(content, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        else:
            _path.write_text(str(content), encoding="utf-8")
    elif format in ("audio", "epub", "audiobook"):
        _path.write_bytes(base64.b64decode(content))
    elif format == "video":
        # Two accepted shapes: (1) _render_video_scaffold's JSON blob
        # {"video_path": ...} — copy the referenced MP4 (#254);
        # (2) base64-encoded MP4 bytes (audio-compatible test contract).
        blob: Any = None
        if isinstance(content, str):
            try:
                blob = json.loads(content)
            except (ValueError, TypeError):
                blob = None
        video_path = blob.get("video_path") if isinstance(blob, dict) else None
        if isinstance(video_path, str) and os.path.isfile(video_path):
            import shutil

            shutil.copy2(video_path, _path)
        elif isinstance(blob, dict):
            _path.write_text(
                json.dumps(blob, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        else:
            _path.write_bytes(base64.b64decode(content))
    else:
        _path.write_text(str(content), encoding="utf-8")
    return str(OUTPUTS_DIR / domain / _path.name)


def _output_text(result: str | Any) -> str:
    """Unwrap a generate_* result to its plain text.

    ``generate_digest``/``generate_report`` return ``str | DeliveryOutput``;
    the MCP handlers never pass *delivery_gate_configs*, so a
    ``DeliveryOutput`` can only appear if the contract changes.  Normalise to
    ``str`` so callers can safely ``json.loads`` / persist the text.
    """
    from autoinfo.output import DeliveryOutput

    return result.output if isinstance(result, DeliveryOutput) else result


def _maybe_persist_output(
    payload: dict[str, Any],
    persist: bool,
    domain: str,
    product: str,
    format: str,
    content: Any,
) -> dict[str, Any]:
    """Build the canonical success envelope for a generated output.

    *payload* carries the output fields (callers may include a ``success``
    key from the pre-unification shape; it is dropped).  With *persist* true
    a ``persisted_path`` key is added to the envelope's ``data``.
    """
    data = {k: v for k, v in payload.items() if k != "success"}
    if persist:
        data["persisted_path"] = _persist_output(domain, product, format, content)
    return success_response(data)


def _validate_llm_pool_params(
    llm_fallback: list[dict[str, Any]] | None,
    llm_tasks: dict[str, Any] | None,
) -> str | None:
    """Validate ``llm_fallback`` / ``llm_tasks`` before any disk write.

    Returns a human-readable error message when invalid, ``None`` when
    valid.  Runs BEFORE the YAML write so a failed validation leaves the
    config file untouched (mtime unchanged).
    """
    if llm_fallback is not None:
        if not isinstance(llm_fallback, list):
            return "llm_fallback must be a list of fallback entries"
        for i, entry in enumerate(llm_fallback):
            if not isinstance(entry, dict):
                return f"llm_fallback[{i}] must be an object with at least a 'model' field"
            model = entry.get("model")
            if not isinstance(model, str) or not model.strip():
                return f"llm_fallback[{i}] is missing the required 'model' field"
    if llm_tasks is not None:
        if not isinstance(llm_tasks, dict):
            return "llm_tasks must be an object mapping task names to configs"
        allowed = {"model", "provider", "max_tokens"}
        for task_name, task_cfg in llm_tasks.items():
            if not isinstance(task_cfg, dict):
                return (
                    f"llm_tasks[{task_name}] must be an object with "
                    "model/provider/max_tokens fields"
                )
            unknown = set(task_cfg) - allowed
            if unknown:
                return f"llm_tasks[{task_name}] has unknown fields: {', '.join(sorted(unknown))}"
            for field, value in task_cfg.items():
                if field in ("model", "provider") and not isinstance(value, str):
                    return f"llm_tasks[{task_name}].{field} must be a string"
                if field == "max_tokens" and not isinstance(value, int):
                    return f"llm_tasks[{task_name}].max_tokens must be an integer"
    return None


def _merge_fallback_entries(
    existing: list[dict[str, Any]],
    new_entries: list[dict[str, Any]],
    primary_provider: str,
    primary_model: str,
) -> list[dict[str, Any]]:
    """Merge new fallback entries into the existing list.

    Entries are keyed on the FULL ``(provider or primary_provider, model)``
    identity (after inheritance) — same key updates fields in place,
    different key appends.  Empty-model entries are completed with the
    inherited primary model BEFORE writing so ``call_with_fallback``
    (llm.py:714-727) can never confuse a backup entry with the primary.
    """
    result = list(existing)
    for entry in new_entries:
        provider = entry.get("provider") or primary_provider
        model = entry.get("model") or primary_model
        key = (provider, model)
        replaced = False
        for i, ex in enumerate(result):
            ex_provider = ex.get("provider") or primary_provider
            ex_model = ex.get("model") or primary_model
            if (ex_provider, ex_model) == key:
                merged = dict(ex)
                merged.update(entry)
                if not merged.get("model"):
                    merged["model"] = primary_model
                result[i] = merged
                replaced = True
                break
        if not replaced:
            completed = dict(entry)
            if not completed.get("model"):
                completed["model"] = primary_model
            result.append(completed)
    return result


def _parse_tags(raw: dict[str, Any]) -> list[str]:
    """Deserialise the ``tags`` column from a raw entry dict."""
    import json as _json

    tags_raw = raw.get("tags") or []
    if isinstance(tags_raw, str):
        try:
            return list(_json.loads(tags_raw))
        except (_json.JSONDecodeError, TypeError):
            return [tags_raw] if tags_raw else []
    return list(tags_raw) if tags_raw else []


def _gate_to_dict(gate_obj: Any) -> dict[str, Any]:
    """Serialize a QualityGateConfig or DeliveryGateConfig to a plain dict."""
    from dataclasses import asdict as _asdict

    d = _asdict(gate_obj)
    d.pop("name", None)
    return d


def _classify_exception(exc: Exception) -> ErrorCode:
    """Map *exc* to a semantic :class:`ErrorCode`.

    Issue #364: expected failures (missing config, unknown domain, invalid
    input, network timeouts, auth errors) must not be flattened into
    ``INTERNAL_ERROR``.  Resolution is by exception type, checked from the
    most specific to the least specific:

    - :class:`~autoinfo.kb.DirectorOnlyError` → ``DIRECTOR_ONLY``
    - :class:`~autoinfo.kb.PromotionRejected` → ``VALIDATION_ERROR``
    - :class:`~autoinfo.config.ConfigNotFoundError` → ``CONFIG_NOT_FOUND``
    - :class:`FileNotFoundError` → ``NOT_FOUND``
    - :class:`ValueError` / :class:`KeyError` → ``VALIDATION_ERROR``
    - :class:`ConnectionError` → ``TIMEOUT``
    - ``httpx.ConnectError`` → ``TIMEOUT``
    - ``litellm.exceptions.AuthenticationError`` → ``LLM_NOT_CONFIGURED``
    - anything else → ``INTERNAL_ERROR``

    ``INTERNAL_ERROR`` is therefore reserved for genuinely unexpected
    server-internal failures.  A promotion admission rejection is a *designed*
    outcome — the draft stays in 02-Draft with a ``_failed/`` marker — not an
    internal fault, so it classifies as ``VALIDATION_ERROR``: the caller passed
    a draft that did not meet the gate criteria and can act on that.
    """
    if isinstance(exc, DirectorOnlyError):
        return ErrorCode.DIRECTOR_ONLY
    if isinstance(exc, PromotionRejected):
        return ErrorCode.VALIDATION_ERROR
    if isinstance(exc, ConfigNotFoundError):
        return ErrorCode.CONFIG_NOT_FOUND
    if isinstance(exc, FileNotFoundError):
        return ErrorCode.NOT_FOUND
    if isinstance(exc, (ValueError, KeyError)):
        return ErrorCode.VALIDATION_ERROR
    if isinstance(exc, ConnectionError):
        return ErrorCode.TIMEOUT
    try:
        if isinstance(exc, httpx.ConnectError):
            return ErrorCode.TIMEOUT
    except Exception:
        pass
    try:
        import litellm.exceptions

        if isinstance(exc, litellm.exceptions.AuthenticationError):
            return ErrorCode.LLM_NOT_CONFIGURED
    except ImportError:
        pass
    return ErrorCode.INTERNAL_ERROR


def _error_from_exc(
    exc: Exception,
    context: str,
    code: ErrorCode | str | None = None,
) -> dict[str, Any]:
    """Build an actionable error dict from an unexpected exception.

    Replaces the old ``_error_dict(exc)`` which leaked the raw exception
    string as the agent-facing message (D-工-4: no raw-exception leakage).
    The message now carries a human-readable operation context plus the
    exception detail and a concrete next step.

    ``code`` preserves the semantic :class:`ErrorCode` a call site used to
    pass to ``error_response`` (e.g. ``COLLECTION_FAILED``,
    ``DIRECTOR_ONLY``).  When ``code`` is omitted **or** is the generic
    ``INTERNAL_ERROR``, the code is resolved from the exception type via
    :func:`_classify_exception` (issue #364: classify first; use
    ``INTERNAL_ERROR`` only for genuinely unknown exceptions).

    Returns the canonical error envelope
    ``{success: False, error: {code, message, actionable}}`` so callers can
    return it directly and the standard ``call_tool`` wrapping passes it
    through unchanged (idempotent).
    """
    if code is None or code is ErrorCode.INTERNAL_ERROR:
        code_str = _classify_exception(exc).value
    elif isinstance(code, ErrorCode):
        code_str = code.value
    else:
        code_str = str(code)
    message_str = (
        f"{context}: {exc}. Check the request parameters and retry, "
        "or consult the docs for supported inputs."
    )
    return error_response(
        code=code_str,
        message=message_str,
        actionable=True,
    )


def _text_payload_metadata(
    text: str,
    *,
    format: str,
    content_type: str,
) -> dict[str, Any]:
    """Build machine-readable metadata for a raw-text tool payload.

    T-S-09: no tool may return an unlabelled text blob.  Every text-format
    payload carries the text under a domain-specific key (``metrics_text``
    for Prometheus exposition text, ``content`` for RSS XML) **plus** this
    metadata block so an agent can parse/route it without sniffing bytes:

    - ``format`` — payload family (``"prometheus"`` / ``"rss"``)
    - ``content_type`` — IANA media type + parameters (RFC 7231)
    - ``encoding`` — text encoding of ``bytes`` (always UTF-8 here)
    - ``length`` — character count (``len(text)``)
    - ``bytes`` — encoded size in UTF-8 octets

    The metadata is merged into the handler's result dict; the caller keeps
    its own keys (``domain``, ``pagination``, ...).  This is a pure payload
    annotation — it changes no business behavior.
    """
    return {
        "format": format,
        "content_type": content_type,
        "encoding": "utf-8",
        "length": len(text),
        "bytes": len(text.encode("utf-8")),
    }


@overload
def _canonicalize(result: dict[str, Any]) -> dict[str, Any]: ...


@overload
def _canonicalize(result: list[dict[str, Any]]) -> list[dict[str, Any]]: ...


@overload
def _canonicalize(result: T) -> T: ...


def _canonicalize(result: Any) -> Any:
    """Normalize a forwarded helper result into the canonical envelope.

    Some handlers forward the result of a lower-level helper (e.g.
    ``status.get_source_health``, ``user_store.update_preferences``) that
    still speaks the legacy flat shape (``error_code`` / bare ``success``).
    This boundary helper converts those into the canonical envelope and
    passes already-canonical or plain-data results through unchanged.

    The overloads state what the body already guarantees, so the ``Any``
    return does not erase the argument type at every call site: a ``dict``
    argument always comes back a ``dict`` (rewritten into an envelope or
    passed through), a ``list[dict[str, Any]]`` comes back unchanged, and
    anything else is an identity pass-through.
    """
    if not isinstance(result, dict):
        return result
    if "error_code" in result:
        return error_response(
            code=result["error_code"],
            message=result.get("message", ""),
            actionable=result.get("actionable", True),
        )
    if "success" in result and not {"data", "error"} & set(result):
        return success_response({k: v for k, v in result.items() if k != "success"})
    return result


def _error_response(exc: Exception) -> dict[str, Any]:
    """Build a standardised error envelope from an exception.

    Maps well-known exception types to appropriate ``ErrorCodes``.
    Falls back to ``INTERNAL_ERROR`` for unrecognised exceptions.

    Returns the uniform ``{success: False, error: {...}}`` dict; the caller
    packs it into the MCP content/structured-content tuple.
    """
    code = _classify_exception(exc)
    return {
        "success": False,
        "error": {
            "code": code.value,
            "message": str(exc),
            "actionable": True,
        },
    }
