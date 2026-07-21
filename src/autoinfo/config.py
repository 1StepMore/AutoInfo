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
    project_name: str = ""
    created_at: str = ""


@dataclass
class LLMConfig:
    provider: str = ""
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    fallback: list[LLMConfig] = field(default_factory=list)
    tasks: dict[str, LLMTaskConfig] = field(default_factory=dict)


@dataclass
class LLMTaskConfig:
    """Per-task LLM model override.

    Attributes match :class:`LLMConfig` fields that make sense to
    override per-task (model, provider, max_tokens).  An empty string
    means "inherit from the base LLMConfig".
    """

    model: str = ""
    provider: str = ""
    max_tokens: int = 0


@dataclass
class SourceConfig:
    name: str = ""
    type: str = "api"
    url: str = ""
    quality_tier: int = 1
    settings: dict[str, Any] = field(default_factory=dict)


@dataclass
class TopicConfig:
    name: str = ""
    keywords: list[str] = field(default_factory=list)
    group: str = ""
    relevance_threshold: int = 30


@dataclass
class DomainConfig:
    name: str = ""
    active: bool = True
    sources: list[SourceConfig] = field(default_factory=list)
    topics: list[TopicConfig] = field(default_factory=list)
    extract_fields: list[str] = field(default_factory=list)
    search_mode: str = "keyword"  # keyword | hybrid


@dataclass
class CEFRConfig:
    """CEFR (Common European Framework of Reference) classification settings."""
    enabled: bool = False
    languages: list[str] = field(default_factory=lambda: ["en", "zh", "ja"])
    model: str = ""


@dataclass
class EmailConfig:
    """Email notification / collection settings."""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    from_addr: str = ""
    to_addrs: list[str] = field(default_factory=list)
    enabled: bool = False


@dataclass
class RestAPIConfig:
    """REST API server settings."""
    enabled: bool = True
    port: int = 8741
    host: str = "127.0.0.1"


@dataclass
class VectorSearchConfig:
    """Vector / hybrid search settings (FTS5 + embeddings)."""
    enabled: bool = False
    model: str = ""
    hybrid_weight_fts5: float = 0.7
    hybrid_weight_vector: float = 0.3


@dataclass
class CronConfig:
    """Scheduled task (cron) settings."""
    auto_install: bool = False
    install_path: str = ""


@dataclass
class MultiUserConfig:
    """Multi-user / multi-tenant settings."""
    enabled: bool = False
    default_user_id: str = "default"


@dataclass
class Config:
    project: ProjectConfig = field(default_factory=ProjectConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    domains: list[DomainConfig] = field(default_factory=list)
    cefr: CEFRConfig = field(default_factory=CEFRConfig)
    email: EmailConfig = field(default_factory=EmailConfig)
    rest_api: RestAPIConfig = field(default_factory=RestAPIConfig)
    vector_search: VectorSearchConfig = field(default_factory=VectorSearchConfig)
    cron: CronConfig = field(default_factory=CronConfig)
    multi_user: MultiUserConfig = field(default_factory=MultiUserConfig)


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

    # --- Parse llm.fallback (list of LLMConfig) ---
    fallback_raw: list[dict[str, Any]] = llm_raw.get("fallback", []) or []
    fallback = [
        LLMConfig(
            provider=str(f.get("provider", "")),
            model=str(f.get("model", "")),
            api_key=str(f.get("api_key", "")),
            base_url=str(f.get("base_url", "")),
        )
        for f in fallback_raw
    ]

    # --- Parse llm.tasks (dict of LLMTaskConfig) ---
    tasks_raw: dict[str, Any] = llm_raw.get("tasks", {}) or {}
    tasks: dict[str, LLMTaskConfig] = {}
    for task_name, task_cfg_raw in tasks_raw.items():
        tc = task_cfg_raw or {}
        tasks[str(task_name)] = LLMTaskConfig(
            model=str(tc.get("model", "")),
            provider=str(tc.get("provider", "")),
            max_tokens=int(tc.get("max_tokens", 0)),
        )

    domains_raw: list[dict[str, Any]] = raw.get("domains", []) or []

    domains = []
    for d in domains_raw:
        sources_raw: list[dict[str, Any]] = d.get("sources", []) or []
        _SOURCE_CORE_KEYS = frozenset({"name", "type", "url", "quality_tier"})
        sources = [
            SourceConfig(
                name=s.get("name", ""),
                type=s.get("type", "api"),
                url=s.get("url", ""),
                quality_tier=s.get("quality_tier", 1),
                settings={k: v for k, v in s.items() if k not in _SOURCE_CORE_KEYS},
            )
            for s in sources_raw
        ]
        topics_raw: list[dict[str, Any]] = d.get("topics", []) or []
        topics = [
            TopicConfig(
                name=t.get("name", ""),
                keywords=t.get("keywords", []),
                group=t.get("group", ""),
                relevance_threshold=int(t.get("relevance_threshold", 30)),
            )
            for t in topics_raw
        ]
        domains.append(
            DomainConfig(
                name=d.get("name", ""),
                active=bool(d.get("active", True)),
                sources=sources,
                topics=topics,
                extract_fields=d.get("extract_fields", []),
                search_mode=str(d.get("search_mode", "keyword")),
            )
        )

    # --- Parse new v1.2 sections ---
    def _dict_or_empty(key: str) -> dict[str, Any]:
        return raw.get(key, {}) or {}

    cefr_raw = _dict_or_empty("cefr")
    email_raw = _dict_or_empty("email")
    rest_api_raw = _dict_or_empty("rest_api")
    vector_search_raw = _dict_or_empty("vector_search")
    cron_raw = _dict_or_empty("cron")
    multi_user_raw = _dict_or_empty("multi_user")

    return Config(
        project=ProjectConfig(
            name=str(project_raw.get("name", "")),
            project_name=str(project_raw.get("project_name", "")),
            created_at=str(project_raw.get("created_at", "")),
        ),
        llm=LLMConfig(
            provider=str(llm_raw.get("provider", "")),
            model=str(llm_raw.get("model", "")),
            api_key=str(llm_raw.get("api_key", "")),
            base_url=str(llm_raw.get("base_url", "")),
            fallback=fallback,
            tasks=tasks,
        ),
        domains=domains,
        cefr=CEFRConfig(
            enabled=bool(cefr_raw.get("enabled", False)),
            languages=list(cefr_raw.get("languages", ["en", "zh", "ja"])),
            model=str(cefr_raw.get("model", "")),
        ),
        email=EmailConfig(
            smtp_host=str(email_raw.get("smtp_host", "")),
            smtp_port=int(email_raw.get("smtp_port", 587)),
            smtp_user=str(email_raw.get("smtp_user", "")),
            smtp_pass=str(email_raw.get("smtp_pass", "")),
            from_addr=str(email_raw.get("from_addr", "")),
            to_addrs=list(email_raw.get("to_addrs", [])),
            enabled=bool(email_raw.get("enabled", False)),
        ),
        rest_api=RestAPIConfig(
            enabled=bool(rest_api_raw.get("enabled", True)),
            port=int(rest_api_raw.get("port", 8741)),
            host=str(rest_api_raw.get("host", "127.0.0.1")),
        ),
        vector_search=VectorSearchConfig(
            enabled=bool(vector_search_raw.get("enabled", False)),
            model=str(vector_search_raw.get("model", "")),
            hybrid_weight_fts5=float(vector_search_raw.get("hybrid_weight_fts5", 0.7)),
            hybrid_weight_vector=float(vector_search_raw.get("hybrid_weight_vector", 0.3)),
        ),
        cron=CronConfig(
            auto_install=bool(cron_raw.get("auto_install", False)),
            install_path=str(cron_raw.get("install_path", "")),
        ),
        multi_user=MultiUserConfig(
            enabled=bool(multi_user_raw.get("enabled", False)),
            default_user_id=str(multi_user_raw.get("default_user_id", "default")),
        ),
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
        if domain.search_mode not in ("keyword", "hybrid"):
            errors.append(
                f"domain '{domain.name}'.search_mode must be 'keyword' or 'hybrid', "
                f"got '{domain.search_mode}'"
            )

    return errors


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
# Configuration write-back
# ---------------------------------------------------------------------------


def config_to_dict(config: Config) -> dict[str, Any]:
    """Serialize a ``Config`` dataclass tree to a plain nested dict.

    The returned dict is suitable for writing back to a YAML file via
    ``yaml.dump``.  Domain ``search_mode`` and ``extract_fields`` are
    omitted when they carry default / empty values so that the YAML
    stays clean.
    """
    raw: dict[str, Any] = {
        "project": {
            "name": config.project.name,
            "created_at": config.project.created_at,
        },
        "llm": {
            "provider": config.llm.provider,
            "model": config.llm.model,
            "api_key": config.llm.api_key,
        },
        "domains": [],
    }
    # Only include project_name when non-empty (backward compat)
    if config.project.project_name:
        raw["project"]["project_name"] = config.project.project_name
    # Serialize llm.fallback
    if config.llm.fallback:
        raw["llm"]["fallback"] = [
            {"provider": fb.provider, "model": fb.model} for fb in config.llm.fallback
        ]
    # Serialize llm.tasks
    if config.llm.tasks:
        raw["llm"]["tasks"] = {}
        for task_name, tc in config.llm.tasks.items():
            raw["llm"]["tasks"][task_name] = {
                k: v for k, v in {
                    "model": tc.model,
                    "provider": tc.provider,
                    "max_tokens": tc.max_tokens,
                }.items() if v
            }

    # Serialize v1.2 config sections
    raw["cefr"] = {
        "enabled": config.cefr.enabled,
        "languages": config.cefr.languages,
        "model": config.cefr.model,
    }
    raw["email"] = {
        "smtp_host": config.email.smtp_host,
        "smtp_port": config.email.smtp_port,
        "smtp_user": config.email.smtp_user,
        "smtp_pass": config.email.smtp_pass,
        "from_addr": config.email.from_addr,
        "to_addrs": config.email.to_addrs,
        "enabled": config.email.enabled,
    }
    raw["rest_api"] = {
        "enabled": config.rest_api.enabled,
        "port": config.rest_api.port,
        "host": config.rest_api.host,
    }
    raw["vector_search"] = {
        "enabled": config.vector_search.enabled,
        "model": config.vector_search.model,
        "hybrid_weight_fts5": config.vector_search.hybrid_weight_fts5,
        "hybrid_weight_vector": config.vector_search.hybrid_weight_vector,
    }
    raw["cron"] = {
        "auto_install": config.cron.auto_install,
        "install_path": config.cron.install_path,
    }
    raw["multi_user"] = {
        "enabled": config.multi_user.enabled,
        "default_user_id": config.multi_user.default_user_id,
    }

    for domain in config.domains:
        domain_dict: dict[str, Any] = {
            "name": domain.name,
            "active": domain.active,
            "sources": [
                {
                    "name": s.name,
                    "type": s.type,
                    "url": s.url,
                    "quality_tier": s.quality_tier,
                    **s.settings,
                }
                for s in domain.sources
            ],
            "topics": [
                {
                    "name": t.name,
                    "keywords": t.keywords,
                    **({"group": t.group} if t.group else {}),
                    **({"relevance_threshold": t.relevance_threshold} if t.relevance_threshold != 30 else {}),
                }
                for t in domain.topics
            ],
        }
        if domain.extract_fields:
            domain_dict["extract_fields"] = domain.extract_fields
        if domain.search_mode != "keyword":
            domain_dict["search_mode"] = domain.search_mode
        raw["domains"].append(domain_dict)
    return raw


def save_config(config: Config, path: Path | str) -> None:
    """Write *config* to a YAML file at *path*.

    The parent directory is created if it does not exist.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = config_to_dict(config)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.dump(raw, fh, default_flow_style=False, sort_keys=False, allow_unicode=True)


# ---------------------------------------------------------------------------
# Effective LLM config resolution
# ---------------------------------------------------------------------------


def _resolve_task_llm_config(config: Config, task_name: str = "") -> LLMConfig:
    """Resolve effective :class:`LLMConfig` for *task_name* from an in-memory config.

    Priority (highest to lowest):
    1. Task-specific overrides from ``llm.tasks[task_name]``
    2. Base ``llm`` configuration

    Returns a new ``LLMConfig`` with task-level fields merged on top of
    the base config.  Falls back to the base ``LLMConfig`` when
    *task_name* is empty or unknown.
    """
    base = config.llm
    if not task_name or task_name not in base.tasks:
        return base

    task_cfg = base.tasks[task_name]
    return LLMConfig(
        provider=task_cfg.provider if task_cfg.provider else base.provider,
        model=task_cfg.model if task_cfg.model else base.model,
        api_key=base.api_key,
        fallback=base.fallback,
        tasks=base.tasks,
    )


def get_effective_llm_config(task: str | None = None) -> dict[str, Any]:
    """Resolve the effective LLM configuration for a given *task*.

    When *task* is provided and matches a key in ``llm.tasks``, task-level
    fields (model, provider, max_tokens) override the base LLM config.
    Falls back to the base config otherwise.

    Parameters
    ----------
    task:
        Optional task name (e.g. ``"extraction"``, ``"summarization"``).

    Returns
    -------
    dict
        Keys: ``task``, ``provider``, ``model``, ``max_tokens``,
        ``api_key_configured``, ``fallback_chain``.

    Raises
    ------
    RuntimeError
        When no config file is found.
    """
    config_path = get_config_path()
    if config_path is None:
        raise RuntimeError("No configuration file found. Run 'autoinfo init' first.")

    config = load_config(config_path)
    base = config.llm

    if task and task in base.tasks:
        tc = base.tasks[task]
        provider = tc.provider if tc.provider else base.provider
        model = tc.model if tc.model else base.model
        max_tokens = tc.max_tokens
    else:
        provider = base.provider
        model = base.model
        max_tokens = 0

    fallback_chain = [
        {"provider": fb.provider, "model": fb.model}
        for fb in base.fallback
    ]

    return {
        "task": task or "default",
        "provider": provider,
        "model": model,
        "max_tokens": max_tokens,
        "api_key_configured": str(bool(base.api_key or os.environ.get("AUTOINFO_LLM_API_KEY"))),
        "fallback_chain": fallback_chain,
    }


def ensure_config_exists() -> None:
    """Exit with an error message when no configuration file is found."""
    if get_config_path() is None:
        print("Run 'autoinfo init' first", file=sys.stderr)
        sys.exit(1)
