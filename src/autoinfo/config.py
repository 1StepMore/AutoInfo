"""YAML-based configuration loading, validation, and command guard.

Provides dataclasses for project/LLM/domain configuration, YAML parsing
with env var resolution, validation, and the ``ensure_config_exists``
guard used by CLI commands.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ProjectConfig:
    name: str = ""
    created_at: str = ""


@dataclass
class LLMConfig:
    provider: str = ""
    model: str = ""
    api_key: str = ""


@dataclass
class SourceConfig:
    name: str = ""
    type: str = "api"
    url: str = ""
    quality_tier: int = 1


@dataclass
class TopicConfig:
    name: str = ""
    keywords: list[str] = field(default_factory=list)


@dataclass
class DomainConfig:
    name: str = ""
    active: bool = True
    sources: list[SourceConfig] = field(default_factory=list)
    topics: list[TopicConfig] = field(default_factory=list)


@dataclass
class Config:
    project: ProjectConfig = field(default_factory=ProjectConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    domains: list[DomainConfig] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Env var resolution
# ---------------------------------------------------------------------------

_ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _resolve_env_vars(value: str) -> str:
    """Replace ``${VAR_NAME}`` placeholders with environment variable values."""
    def _replace(match: re.Match[str]) -> str:
        return os.environ.get(match.group(1), "")
    return _ENV_VAR_PATTERN.sub(_replace, value)


def _resolve_env_vars_recursively(obj: Any) -> Any:
    """Walk an object tree and resolve env vars in all string fields."""
    if isinstance(obj, str):
        return _resolve_env_vars(obj)
    if isinstance(obj, dict):
        return {k: _resolve_env_vars_recursively(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_env_vars_recursively(item) for item in obj]
    return obj


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_config(path: Path | str) -> Config:
    """Parse *path* as YAML and return a :class:`Config` instance.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    yaml.YAMLError
        If the YAML is malformed.  The error message includes the file path
        and line number.
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    raw: dict[str, Any]
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        line = f" (line {mark.line + 1})" if mark is not None else ""
        raise yaml.YAMLError(f"Invalid YAML in {path}{line}: {exc}") from exc

    raw = _resolve_env_vars_recursively(raw)
    return _dict_to_config(raw)


def _dict_to_config(raw: dict[str, Any]) -> Config:
    """Convert a nested dict (from YAML) into a :class:`Config` tree."""
    project_raw: dict[str, Any] = raw.get("project", {}) or {}
    llm_raw: dict[str, Any] = raw.get("llm", {}) or {}

    domains_raw: list[dict[str, Any]] = raw.get("domains", []) or []

    domains = []
    for d in domains_raw:
        sources_raw: list[dict[str, Any]] = d.get("sources", []) or []
        sources = [
            SourceConfig(
                name=s.get("name", ""),
                type=s.get("type", "api"),
                url=s.get("url", ""),
                quality_tier=s.get("quality_tier", 1),
            )
            for s in sources_raw
        ]
        topics_raw: list[dict[str, Any]] = d.get("topics", []) or []
        topics = [
            TopicConfig(
                name=t.get("name", ""),
                keywords=t.get("keywords", []),
            )
            for t in topics_raw
        ]
        domains.append(
            DomainConfig(
                name=d.get("name", ""),
                active=bool(d.get("active", True)),
                sources=sources,
                topics=topics,
            )
        )

    return Config(
        project=ProjectConfig(
            name=str(project_raw.get("name", "")),
            created_at=str(project_raw.get("created_at", "")),
        ),
        llm=LLMConfig(
            provider=str(llm_raw.get("provider", "")),
            model=str(llm_raw.get("model", "")),
            api_key=str(llm_raw.get("api_key", "")),
        ),
        domains=domains,
    )


# ---------------------------------------------------------------------------
# Config path discovery
# ---------------------------------------------------------------------------


def get_config_path() -> Path | None:
    """Locate the configuration file.

    Checks (in order):
    1. ``$PWD/.autoinfo/config.yaml``
    2. ``~/.autoinfo/config.yaml``

    Returns ``None`` when neither file exists.
    """
    candidates = [
        Path.cwd() / ".autoinfo" / "config.yaml",
        Path.home() / ".autoinfo" / "config.yaml",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_config(config: Config) -> list[str]:
    """Validate *config* and return a list of error messages.

    Returns an empty list when the configuration is valid.
    """
    errors: list[str] = []

    if not config.project.name:
        errors.append("project.name is required")

    if not config.llm.provider:
        errors.append("llm.provider is required")
    if not config.llm.model:
        errors.append("llm.model is required")

    active_domains = [d for d in config.domains if d.active]
    if not active_domains:
        errors.append("at least one domain must be active")

    for domain in active_domains:
        if not domain.name:
            errors.append("active domain missing name")
        if not domain.sources:
            errors.append(f"active domain '{domain.name or '(unnamed)'}' must have at least one source")

    return errors


# ---------------------------------------------------------------------------
# Default config generator
# ---------------------------------------------------------------------------


def create_default_config(domain: str) -> dict[str, Any]:
    """Generate a minimal default configuration for *domain*.

    The returned dict is suitable for writing to ``.autoinfo/config.yaml``.
    """
    return {
        "project": {
            "name": f"autoinfo-{domain}",
            "created_at": "",
        },
        "llm": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "api_key": "${AUTOINFO_LLM_API_KEY}",
        },
        "domains": [
            {
                "name": domain,
                "active": True,
                "sources": [],
                "topics": [],
            }
        ],
    }


# ---------------------------------------------------------------------------
# Command guard
# ---------------------------------------------------------------------------


def ensure_config_exists() -> None:
    """Exit with an error message when no configuration file is found."""
    if get_config_path() is None:
        print("Run 'autoinfo init' first", file=sys.stderr)
        sys.exit(1)
