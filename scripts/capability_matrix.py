#!/usr/bin/env python3
"""Capability matrix driver (plan T15): product x format x domain evidence.

Derives the implemented ``product x format`` combinations from
``docs/dev/specs/end-user-matrix.yaml`` (never a hardcoded list), generates one
artifact per ``domain x combination`` through the REAL product-generation path,
and records an L1/L2/L3 verdict plus a keyed/unkeyed flag per row.

Layers are cumulative and monotone:

- **L1** — the artifact exists, is non-empty, and is not the
  ``is_no_data_product`` empty shell.
- **L2** — ``scripts/format_structure.check_artifact()`` passes (structural
  correctness for the artifact's own format).
- **L3** — format-specific acceptance.  For media (audio, audiobook, video) the
  L2 structural pass *is* the acceptance; for documents L3 additionally requires
  a non-empty artifact.  In practice both collapse to ``L2 and size > 0``; a
  row may never report L3 when L1 or L2 failed (``compute_layers`` is the single
  enforcement point).

Retry policy (this driver's own — the generators expose no override, and T17
owns that public-API decision): **one attempt per cell, one retry only for
transient/timeout errors, never for auth errors.**  The policy and the attempt
count are recorded in each row's ``detail``.

Exit codes: 0 = every selected cell reached L3 or was honestly recorded as an
environment block; 1 = at least one unexplained failure; 2 = usage error.
"""

from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import os
import shlex
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, cast

import yaml
from coverage_matrix import detect_llm_available

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPEC = ROOT / "docs" / "dev" / "specs" / "end-user-matrix.yaml"
DEFAULT_OUT = ROOT / "docs" / "dev" / "validation-reports" / "capability-27x3"
DEFAULT_DOMAINS = ("medical-research", "language-learning", "ai-commercial")
ARTIFACT_ROOT = ROOT / "outputs" / "capability-matrix"
CONFIG_PATH = ROOT / ".autoinfo" / "config.yaml"

TEXT_FORMATS = frozenset({"markdown", "html"})
JSON_FORMATS = frozenset({"json", "agent"})
BASE64_FORMATS = frozenset({"audio", "epub", "audiobook"})
MEDIA_FORMATS = frozenset({"audio", "audiobook", "video"})

EXT_BY_FORMAT = {
    "markdown": ".md",
    "html": ".html",
    "json": ".json",
    "agent": ".json",
    "audio": ".mp3",
    "epub": ".epub",
    "audiobook": ".zip",
    "video": ".mp4",
}

# Product-family html cells have no dedicated template (D13); they render from
# report.html.j2, so product identity for those cells is theme-level only.
D13_HTML_PRODUCTS = frozenset({"premium-briefing", "magazine-digest", "enterprise-briefing"})

RETRY_POLICY = (
    "retry_policy=single-attempt, transient-only retry, never auth (1 attempt per cell; "
    "one retry only for transient/timeout errors)"
)

HONEST_BLOCKS = frozenset(
    {
        "blocked-no-llm-key",
        "blocked-no-tts-engine",
        "blocked-no-topic",
        "blocked-no-l2-checker",
        "blocked-no-browser",
        "blocked-stale-sources",
    }
)

PENDING = "pending"


# ---------------------------------------------------------------------------
# Spec derivation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Combination:
    """One implemented ``product x format`` pair derived from the spec."""

    product: str
    format: str
    gated: bool

    @property
    def key(self) -> str:
        return f"{self.product}:{self.format}"


def load_spec(spec_path: Path) -> tuple[list[Combination], set[str], set[str]]:
    """Read *spec_path* and return (combinations, gated products, spec products).

    ``required_cells`` is a per-domain list; collapsing ``(product, format)``
    after filtering ``capability == "implemented"`` yields the distinct pairs.
    Raises ``ValueError`` when the spec lacks the keys this driver needs.
    """
    data = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"spec {spec_path} is not a mapping")
    cells = data.get("required_cells")
    if not isinstance(cells, list) or not cells:
        raise ValueError(f"spec {spec_path} has no non-empty required_cells")
    gated = {str(name) for name in (data.get("llm_gated_products") or [])}
    spec_products = {str(name) for name in (data.get("products") or [])}

    seen: dict[tuple[str, str], Combination] = {}
    for cell in cells:
        if not isinstance(cell, dict):
            continue
        if cell.get("capability") != "implemented":
            continue
        product = str(cell.get("product") or "")
        fmt = str(cell.get("format") or "")
        if not product or not fmt:
            continue
        seen.setdefault((product, fmt), Combination(product, fmt, product in gated))
    if not seen:
        raise ValueError(f"spec {spec_path} declares no implemented cells")
    return sorted(seen.values(), key=lambda c: (c.product, c.format)), gated, spec_products


def derive_combinations(spec_path: Path) -> list[Combination]:
    """The distinct implemented ``product x format`` pairs, sorted."""
    return load_spec(spec_path)[0]


# ---------------------------------------------------------------------------
# Routing table — product name -> callable factory
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RouteContext:
    domain: str
    format: str
    product: str
    topic: str = ""
    template: Any = None
    max_synthesis_attempts: int | None = None
    retry_backoff_seconds: float | None = None


@dataclass(frozen=True)
class GenerationCall:
    """A resolved generator call: the real generator plus its exact kwargs."""

    generator: Callable[..., Any]
    kwargs: dict[str, Any]
    uses_product_template: bool


class Route:
    """Callable route descriptor (``ROUTES[product](ctx) -> GenerationCall``)."""

    def __init__(self, factory: Callable[[RouteContext], GenerationCall], *, needs_template: bool):
        self._factory = factory
        self.needs_template = needs_template

    def __call__(self, ctx: RouteContext) -> GenerationCall:
        return self._factory(ctx)


def _require_template(ctx: RouteContext) -> Any:
    if ctx.template is None:
        raise ValueError(f"product {ctx.product!r} requires a ProductTemplate")
    return ctx.template


def _digest_route(needs_template: bool) -> Route:
    def factory(ctx: RouteContext) -> GenerationCall:
        from autoinfo.output import generate_digest

        kwargs: dict[str, Any] = {
            "domain": ctx.domain,
            "period": "weekly",
            "format": ctx.format,
        }
        if needs_template:
            kwargs["product_template"] = _require_template(ctx)
        if ctx.max_synthesis_attempts is not None:
            kwargs["max_synthesis_attempts"] = ctx.max_synthesis_attempts
        if ctx.retry_backoff_seconds is not None:
            kwargs["retry_backoff_seconds"] = ctx.retry_backoff_seconds
        return GenerationCall(generate_digest, kwargs, needs_template)

    return Route(factory, needs_template=needs_template)


def _report_route(needs_template: bool) -> Route:
    def factory(ctx: RouteContext) -> GenerationCall:
        from autoinfo.output import generate_report

        kwargs: dict[str, Any] = {
            "domain": ctx.domain,
            "format": ctx.format,
            "period": "weekly",
        }
        if needs_template:
            kwargs["product_template"] = _require_template(ctx)
        if ctx.max_synthesis_attempts is not None:
            kwargs["max_synthesis_attempts"] = ctx.max_synthesis_attempts
        if ctx.retry_backoff_seconds is not None:
            kwargs["retry_backoff_seconds"] = ctx.retry_backoff_seconds
        return GenerationCall(generate_report, kwargs, needs_template)

    return Route(factory, needs_template=needs_template)


def _tutorial_factory(ctx: RouteContext) -> GenerationCall:
    from autoinfo.output import generate_tutorial

    # generate_tutorial has no topic parameter.
    kwargs: dict[str, Any] = {
        "domain": ctx.domain,
        "format": ctx.format,
        "target_audience": "student",
    }
    return GenerationCall(generate_tutorial, kwargs, False)


def _presentation_factory(ctx: RouteContext) -> GenerationCall:
    from autoinfo.output import generate_presentation

    if not ctx.topic:
        raise ValueError("presentation route requires a topic")
    kwargs: dict[str, Any] = {
        "domain": ctx.domain,
        "topic": ctx.topic,
        "format": ctx.format,
        "slide_count": 8,
    }
    return GenerationCall(generate_presentation, kwargs, False)


#: ONE routing table.  Adding a product is a data edit here, not an if-chain.
ROUTES: dict[str, Route] = {
    "digest": _digest_route(False),
    "report": _report_route(False),
    "tutorial": Route(_tutorial_factory, needs_template=False),
    "presentation": Route(_presentation_factory, needs_template=False),
    "premium-briefing": _digest_route(True),
    "column": _report_route(True),
    "magazine-digest": _digest_route(True),
    "enterprise-briefing": _report_route(True),
}


def validate_routes(combinations: list[Combination], spec_products: set[str]) -> None:
    """Every derived product must have a route; no route may exceed the spec."""
    derived = {c.product for c in combinations}
    missing = derived - set(ROUTES)
    if missing:
        raise ValueError(f"no generation route for products: {', '.join(sorted(missing))}")
    extra = set(ROUTES) - spec_products
    if extra:
        joined = ", ".join(sorted(extra))
        raise ValueError(f"routes exist for products absent from the spec: {joined}")


# ---------------------------------------------------------------------------
# Layer verdict (single monotone enforcement point)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LayerVerdict:
    l1: bool
    l2: bool
    l3: bool
    reached: str


def compute_layers(
    *,
    l1_pass: bool,
    l2_passed: bool,
    artifact_bytes: int,
    l1_block: str = "blocked-empty-artifact",
) -> LayerVerdict:
    """Compute cumulative L1/L2/L3; a later layer can never outrun an earlier one."""
    l1 = bool(l1_pass) and artifact_bytes > 0
    l2 = l1 and bool(l2_passed)
    l3 = l2 and artifact_bytes > 0
    if l3:
        reached = "L3"
    elif l2:
        reached = "L2"
    elif l1:
        reached = "L1"
    else:
        reached = l1_block
    return LayerVerdict(l1=l1, l2=l2, l3=l3, reached=reached)


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------


def keyed_state() -> str:
    """``"keyed"`` when an LLM key is resolvable, else ``"unkeyed"``."""
    from autoinfo.output import _llm_key_available

    return "keyed" if _llm_key_available(None) else "unkeyed"


def load_topics(config_path: Path = CONFIG_PATH) -> dict[str, str]:
    """Map domain -> its first configured topic name (``""`` when absent)."""
    if not config_path.is_file():
        return {}
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    topics: dict[str, str] = {}
    for entry in data.get("domains") or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "")
        names = [
            str(topic.get("name"))
            for topic in (entry.get("topics") or [])
            if isinstance(topic, dict) and topic.get("name")
        ]
        if name:
            topics[name] = names[0] if names else ""
    return topics


def resolve_product_template(product: str) -> Any:
    """Resolve *product* through the registry (same lookup as the CLI)."""
    from autoinfo.output import PRODUCT_TEMPLATES

    for row in PRODUCT_TEMPLATES:
        if row["name"] == product:
            return cast(Any, row["template"])
    valid = ", ".join(str(row["name"]) for row in PRODUCT_TEMPLATES)
    raise ValueError(f"unknown product template {product!r}; valid: {valid}")


def _edge_tts_available() -> bool:
    return importlib.util.find_spec("edge_tts") is not None


def _is_auth_error(exc: BaseException) -> bool:
    if isinstance(exc, PermissionError):
        return True
    try:
        import litellm.exceptions as litellm_exceptions

        if isinstance(exc, litellm_exceptions.AuthenticationError):
            return True
        if isinstance(exc, litellm_exceptions.PermissionDeniedError):
            return True
    except ImportError:
        pass
    text = str(exc).lower()
    return "401" in text or "unauthorized" in text or "authentication" in text


def _is_missing_browser_error(exc: BaseException) -> bool:
    """True when the video renderer failed because no browser is installed.

    HyperFrames renders through a headless Chrome; on a host without one the
    failure is an absent environment prerequisite, exactly like a missing TTS
    engine, not a product defect.  Keep the raw error in the row detail — the
    classification only decides whether the row counts as an honest block.
    """
    text = str(exc).lower()
    return any(
        marker in text
        for marker in (
            "chrome cannot launch",
            "could not find chrome",
            "no executable browser",
            "browser was not found",
        )
    )


def _is_stale_source_error(exc: BaseException) -> bool:
    """True when the generator refused because every candidate is stale.

    This is the freshness gate doing its job (#525's sibling): the product
    refuses to emit an empty shell rather than shipping old content.  The KB
    stays stale because processing new raw items is itself blocked, so the row
    is an honest block, and the cause chain belongs in the evidence pack.
    """
    if type(exc).__name__ == "StaleSourceError":
        return True
    return "are stale" in str(exc).lower()


def _is_transient_error(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    text = str(exc).lower()
    return any(
        marker in text
        for marker in (
            "timeout",
            "timed out",
            "connection reset",
            "temporarily unavailable",
            "429",
            "503",
        )
    )


def _is_tts_error(exc: BaseException, fmt: str) -> bool:
    if fmt not in {"audio", "audiobook"}:
        return False
    text = str(exc).lower()
    ttsish = any(marker in text for marker in ("tts", "edge-tts", "edge_tts", "audio"))
    if not ttsish:
        return False
    return isinstance(exc, ImportError) or not _edge_tts_available()


# ---------------------------------------------------------------------------
# L2 (format_structure) — lazy so ``--list`` works when the checker is missing
# ---------------------------------------------------------------------------


def _load_l2_checker() -> Any | None:
    target = ROOT / "scripts" / "format_structure.py"
    if not target.is_file():
        return None
    module_name = "_autoinfo_format_structure"
    cached = sys.modules.get(module_name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(module_name, target)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def repo_relative(path: Path) -> str:
    """Render *path* relative to the repo root when it lives inside it.

    Artifact paths are published into ``docs/`` (``matrix.json`` / ``matrix.md``),
    and the drift guard bans absolute workspace paths in tracked docs, so the
    recorded form must be portable. Paths outside the repo keep their absolute
    form rather than being silently rewritten.
    """
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def check_l2(artifact_path: Path) -> dict[str, Any] | None:
    """Run the L2 structural checker; ``None`` means the checker is unavailable."""
    module = _load_l2_checker()
    if module is None:
        return None
    result = module.check_artifact(artifact_path)
    return cast(dict[str, Any], result)


# ---------------------------------------------------------------------------
# Artifact writing
# ---------------------------------------------------------------------------


class VideoUnavailableError(RuntimeError):
    """The video generator returned no usable MP4 path."""


def _unique_path(base: Path) -> Path:
    if not base.exists():
        return base
    for index in range(2, 1000):
        candidate = base.with_name(f"{base.stem}-{index}{base.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not allocate a unique artifact path near {base}")


def _unwrap(result: Any) -> str:
    from autoinfo.output import DeliveryOutput

    return result.output if isinstance(result, DeliveryOutput) else result


def _decode_video(content: str, target: Path) -> None:
    blob: Any = None
    try:
        blob = json.loads(content)
    except (TypeError, ValueError):
        blob = None
    if isinstance(blob, dict):
        video_path = blob.get("video_path")
        if isinstance(video_path, str) and os.path.isfile(video_path):
            shutil.copy2(video_path, target)
            return
        raise VideoUnavailableError(
            f"video generator returned no usable video_path (status={blob.get('status')!r})"
        )
    target.write_bytes(base64.b64decode(content))


def write_artifact(
    *,
    artifact_root: Path,
    domain: str,
    product: str,
    fmt: str,
    content: str,
    force: bool,
) -> Path:
    """Persist the generated *content* under *artifact_root* (never silently overwrite)."""
    if fmt not in EXT_BY_FORMAT:
        raise ValueError(f"no artifact extension known for format {fmt!r}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    directory = artifact_root / domain
    directory.mkdir(parents=True, exist_ok=True)
    base = directory / f"{product}-{fmt}-{stamp}{EXT_BY_FORMAT[fmt]}"
    target = base if force else _unique_path(base)
    if target.exists() and not force:
        raise RuntimeError(f"refusing to overwrite existing artifact {target} without --force")

    if fmt in JSON_FORMATS:
        try:
            parsed = json.loads(content)
        except (TypeError, ValueError):
            target.write_text(str(content), encoding="utf-8")
        else:
            target.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
    elif fmt in BASE64_FORMATS:
        target.write_bytes(base64.b64decode(content))
    elif fmt == "video":
        _decode_video(content, target)
    else:
        target.write_text(str(content), encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# One cell
# ---------------------------------------------------------------------------


def _invoke(call: GenerationCall) -> tuple[Any, int]:
    """Call the generator once; retry exactly once for transient errors only."""
    attempts = 0
    while True:
        attempts += 1
        try:
            return call.generator(**call.kwargs), attempts
        except Exception as exc:  # noqa: BLE001 - classified below, never swallowed
            if _is_auth_error(exc) or not _is_transient_error(exc) or attempts >= 2:
                raise
            time.sleep(1.0)


def _detail_parts(messages: list[str]) -> str:
    return "; ".join(part for part in messages if part)


def _error_detail(exc: BaseException) -> str:
    text = " ".join(str(exc).split())
    if len(text) > 400:
        text = text[:397] + "..."
    return f"error={type(exc).__name__}: {text}"


def _base_row(combo: Combination, domain: str, keyed: str) -> dict[str, Any]:
    return {
        "domain": domain,
        "product": combo.product,
        "format": combo.format,
        "gated": combo.gated,
        "keyed": keyed,
        "artifact": "",
        "reached": PENDING,
        "l1": False,
        "l2": False,
        "l3": False,
        "detail": "",
        "duration_s": 0.0,
    }


def _blocked(row: dict[str, Any], reason: str, detail: str, started: float) -> dict[str, Any]:
    row["reached"] = reason
    row["l1"] = row["l2"] = row["l3"] = False
    row["detail"] = detail
    row["duration_s"] = round(time.monotonic() - started, 3)
    return row


def _d13_note(combo: Combination) -> str:
    if combo.format == "html" and combo.product in D13_HTML_PRODUCTS:
        return (
            f"renderer=report.html.j2 (no dedicated {combo.product}.html.j2; "
            "product identity is theme-level only)"
        )
    return ""


def generate_cell(
    combo: Combination,
    *,
    domain: str,
    topic: str,
    artifact_root: Path,
    force: bool,
    keyed: str,
    llm_available: bool | None = None,
    llm_attempts: int | None = None,
    llm_backoff: float | None = None,
) -> dict[str, Any]:
    """Generate one artifact through the real path and evaluate L1/L2/L3."""
    started = time.monotonic()
    row = _base_row(combo, domain, keyed)
    no_llm = (not llm_available) if llm_available is not None else keyed == "unkeyed"

    if no_llm and combo.gated:
        return _blocked(
            row,
            "blocked-no-llm-key",
            _detail_parts(
                [
                    "generation skipped: the LLM prerequisite is provably absent "
                    "(no API key configured), and this product is LLM-gated",
                    RETRY_POLICY,
                ]
            ),
            started,
        )

    if combo.product == "presentation" and not topic:
        return _blocked(
            row,
            "blocked-no-topic",
            _detail_parts(
                [
                    f"domain {domain!r} has no configured topic in {CONFIG_PATH}",
                    RETRY_POLICY,
                ]
            ),
            started,
        )

    max_synthesis_attempts = llm_attempts
    if max_synthesis_attempts is None and no_llm:
        max_synthesis_attempts = 1
    retry_backoff_seconds = llm_backoff
    if retry_backoff_seconds is None and no_llm:
        retry_backoff_seconds = 0.0

    if combo.format == "video":
        # The video pipeline writes its intermediate MP4 under AUTOINFO_TMPDIR;
        # keep that inside the gitignored artifact tree, never the system temp.
        os.environ.setdefault("AUTOINFO_TMPDIR", str(artifact_root / ".video-tmp"))

    route = ROUTES[combo.product]
    template = resolve_product_template(combo.product) if route.needs_template else None
    ctx = RouteContext(
        domain=domain,
        format=combo.format,
        product=combo.product,
        topic=topic,
        template=template,
        max_synthesis_attempts=max_synthesis_attempts,
        retry_backoff_seconds=retry_backoff_seconds,
    )
    try:
        call = route(ctx)
        result, attempts = _invoke(call)
    except Exception as exc:  # noqa: BLE001 - classified below, never swallowed
        if _is_tts_error(exc, combo.format):
            reason = "blocked-no-tts-engine"
        elif _is_missing_browser_error(exc):
            reason = "blocked-no-browser"
        elif _is_stale_source_error(exc):
            reason = "blocked-stale-sources"
        elif _is_auth_error(exc):
            reason = "blocked-no-llm-key"
        else:
            reason = "blocked-generation-error"
        retried = not _is_auth_error(exc) and _is_transient_error(exc)
        attempts = 2 if retried else 1
        return _blocked(
            row,
            reason,
            _detail_parts([_error_detail(exc), RETRY_POLICY, f"attempts={attempts}"]),
            started,
        )

    attempts_detail = f"attempts={attempts}"
    detail = _detail_parts([RETRY_POLICY, attempts_detail, _d13_note(combo)])

    try:
        content = _unwrap(result)
    except Exception as exc:  # noqa: BLE001 - contract violation surfaced, not swallowed
        return _blocked(
            row,
            "blocked-generation-error",
            _detail_parts([_error_detail(exc), detail]),
            started,
        )

    from autoinfo.output import is_no_data_product

    if is_no_data_product(content, combo.format):
        return _blocked(
            row,
            "blocked-empty-artifact",
            _detail_parts(["empty-state product (is_no_data_product=True); not a pass", detail]),
            started,
        )

    try:
        artifact = write_artifact(
            artifact_root=artifact_root,
            domain=domain,
            product=combo.product,
            fmt=combo.format,
            content=content,
            force=force,
        )
    except VideoUnavailableError as exc:
        return _blocked(
            row,
            "blocked-video-unavailable",
            _detail_parts([_error_detail(exc), detail]),
            started,
        )
    except Exception as exc:  # noqa: BLE001 - write/decode failure is evidence, not a crash
        return _blocked(
            row,
            "blocked-artifact-write",
            _detail_parts([_error_detail(exc), detail]),
            started,
        )

    size = artifact.stat().st_size
    l2_result = check_l2(artifact)
    if l2_result is None:
        return _blocked(
            row,
            "blocked-no-l2-checker",
            _detail_parts(
                [
                    f"artifact={repo_relative(artifact)}; bytes={size}",
                    "format_structure module unavailable",
                    detail,
                ]
            ),
            started,
        )

    l2_passed = bool(l2_result.get("passed"))
    failing = [
        name
        for name, outcome in (l2_result.get("checks") or {}).items()
        if isinstance(outcome, dict) and not outcome.get("passed")
    ]
    verdict = compute_layers(l1_pass=True, l2_passed=l2_passed, artifact_bytes=size)
    l2_detail = "l2=pass" if l2_passed else f"l2=fail({', '.join(failing) or 'unknown'})"
    row.update(
        {
            "artifact": repo_relative(artifact),
            "reached": verdict.reached,
            "l1": verdict.l1,
            "l2": verdict.l2,
            "l3": verdict.l3,
            "detail": _detail_parts([f"bytes={size}", l2_detail, detail]),
            "duration_s": round(time.monotonic() - started, 3),
        }
    )
    return row


def reevaluate_cell(row: dict[str, Any], *, keyed: str) -> dict[str, Any]:
    """Re-run L1/L2/L3 over an already-recorded artifact (no generation)."""
    started = time.monotonic()
    updated = dict(row)
    updated["keyed"] = keyed
    artifact_value = str(row.get("artifact") or "")
    previous = str(row.get("reached") or PENDING)
    prior_block = previous if previous in HONEST_BLOCKS else ""

    if not artifact_value:
        updated.update({"l1": False, "l2": False, "l3": False})
        updated["reached"] = prior_block or "blocked-empty-artifact"
        updated["detail"] = _detail_parts([f"assert_only; no artifact recorded; prior={previous}"])
        updated["duration_s"] = round(time.monotonic() - started, 3)
        return updated

    artifact = Path(artifact_value)
    if not artifact.is_absolute():
        artifact = ROOT / artifact
    updated["artifact"] = repo_relative(artifact)
    exists = artifact.is_file()
    size = artifact.stat().st_size if exists else 0

    l1_pass = exists and size > 0
    l1_detail = f"assert_only; artifact={repo_relative(artifact)}; bytes={size}"
    if l1_pass and updated.get("format") in TEXT_FORMATS:
        from autoinfo.output import is_no_data_product

        try:
            text = artifact.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            text = ""
        if is_no_data_product(text, str(updated.get("format"))):
            l1_pass = False
            l1_detail = _detail_parts([l1_detail, "empty-state product (is_no_data_product=True)"])

    if not l1_pass:
        updated.update(
            {
                "l1": False,
                "l2": False,
                "l3": False,
                "reached": prior_block or "blocked-empty-artifact",
                "detail": _detail_parts([l1_detail, f"prior={previous}"]),
                "duration_s": round(time.monotonic() - started, 3),
            }
        )
        return updated

    l2_result = check_l2(artifact)
    if l2_result is None:
        updated.update(
            {
                "l1": True,
                "l2": False,
                "l3": False,
                "reached": "blocked-no-l2-checker",
                "detail": _detail_parts([l1_detail, "format_structure module unavailable"]),
                "duration_s": round(time.monotonic() - started, 3),
            }
        )
        return updated

    l2_passed = bool(l2_result.get("passed"))
    verdict = compute_layers(l1_pass=l1_pass, l2_passed=l2_passed, artifact_bytes=size)
    failing = [
        name
        for name, outcome in (l2_result.get("checks") or {}).items()
        if isinstance(outcome, dict) and not outcome.get("passed")
    ]
    l2_detail = "l2=pass" if l2_passed else f"l2=fail({', '.join(failing) or 'unknown'})"
    updated.update(
        {
            "l1": verdict.l1,
            "l2": verdict.l2,
            "l3": verdict.l3,
            "reached": verdict.reached,
            "detail": _detail_parts([l1_detail, l2_detail, f"prior={previous}"]),
            "duration_s": round(time.monotonic() - started, 3),
        }
    )
    return updated


# ---------------------------------------------------------------------------
# Matrix persistence
# ---------------------------------------------------------------------------


def _row_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (str(row.get("domain")), str(row.get("product")), str(row.get("format")))


def load_matrix(path: Path) -> list[dict[str, Any]]:
    """Load rows from a previous matrix file (``[]`` when absent)."""
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        rows = data.get("rows")
    else:
        rows = data
    if not isinstance(rows, list):
        raise ValueError(f"matrix file {path} has no rows list")
    return [row for row in rows if isinstance(row, dict)]


def _write_matrix_json(path: Path, meta: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    payload = dict(meta)
    payload["rows"] = sorted(rows, key=_row_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _md_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_markdown(meta: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    keyed = sum(1 for row in rows if row.get("keyed") == "keyed")
    unkeyed = sum(1 for row in rows if row.get("keyed") == "unkeyed")
    gated = sum(1 for row in rows if row.get("gated"))
    lines = [
        "# Capability matrix (product x format x domain)",
        "",
        f"- Generated: {meta['generated_at']}",
        f"- Domains: {', '.join(meta['domains'])}",
        f"- Spec: {meta['spec']}",
        f"- Keyed/unkeyed split: keyed={keyed}, unkeyed={unkeyed} (run key state: {meta['keyed']})",
        f"- Gated/non-gated split: gated={gated}, non-gated={len(rows) - gated}",
        f"- Command: `{meta['command']}`",
        "",
        "Layers are cumulative and monotone: L2 implies L1, L3 implies L2.",
        "A cell never reports L3 when L1 or L2 failed.",
        "",
        "| Domain | Cell | Gated | Keyed | Reached | L1 | L2 | L3 "
        "| Duration (s) | Artifact | Detail |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in sorted(rows, key=_row_key):
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(row.get("domain", "")),
                    _md_cell(f"{row.get('product')}:{row.get('format')}"),
                    "yes" if row.get("gated") else "no",
                    _md_cell(row.get("keyed", "")),
                    _md_cell(row.get("reached", "")),
                    "pass" if row.get("l1") else "fail",
                    "pass" if row.get("l2") else "fail",
                    "pass" if row.get("l3") else "fail",
                    _md_cell(row.get("duration_s", "")),
                    _md_cell(row.get("artifact", "")),
                    _md_cell(row.get("detail", "")),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="capability_matrix.py",
        description=(
            "Generate one artifact per implemented product x format x domain and record "
            "L1/L2/L3 verdicts. Retry policy: one attempt per cell; one retry only for "
            "transient/timeout errors, never for auth errors."
        ),
    )
    parser.add_argument("--list", action="store_true", help="print the derived pairs and exit")
    parser.add_argument(
        "--domains",
        default=",".join(DEFAULT_DOMAINS),
        help=f"comma-separated domains (default: {','.join(DEFAULT_DOMAINS)})",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="PRODUCT:FORMAT",
        help="restrict cells (repeatable), e.g. --only digest:markdown",
    )
    parser.add_argument(
        "--only-assert",
        action="store_true",
        dest="only_assert",
        help="do not generate; re-run L1/L2/L3 over artifacts recorded in the matrix",
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="output directory for matrix files")
    parser.add_argument(
        "--checkpoint",
        default=None,
        help=(
            "resume file (default: <out>/matrix.json); rows with a "
            "non-pending verdict are skipped"
        ),
    )
    parser.add_argument("--spec", default=str(DEFAULT_SPEC), help="end-user-matrix spec path")
    parser.add_argument("--json", action="store_true", help="emit rows as JSONL on stdout")
    parser.add_argument("--force", action="store_true", help="re-run cells already recorded")
    parser.add_argument(
        "--llm-attempts",
        type=int,
        default=None,
        metavar="INT",
        help=(
            "override synthesis attempts per digest/report call (default: 1 when no "
            "LLM key is configured, else the generator's shipped default)"
        ),
    )
    parser.add_argument(
        "--llm-backoff",
        type=float,
        default=None,
        metavar="FLOAT",
        help=(
            "override synthesis retry backoff seconds (default: 0.0 when no LLM key "
            "is configured, else the generator's shipped default)"
        ),
    )
    return parser.parse_args(argv)


def _usage_error(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 2


def _log(message: str, json_mode: bool) -> None:
    stream = sys.stderr if json_mode else sys.stdout
    print(message, file=stream)


def _emit_rows(rows: list[dict[str, Any]], json_mode: bool) -> None:
    if json_mode:
        for row in rows:
            print(json.dumps(row, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    raw_argv = argv if argv is not None else sys.argv[1:]
    command = shlex.join([sys.executable, str(Path(__file__).resolve()), *raw_argv])
    # The command and spec are republished into docs/, where absolute workspace
    # paths are banned; strip the checkout prefix so the record stays portable.
    command = command.replace(str(ROOT.resolve()) + "/", "").replace(str(ROOT) + "/", "")

    spec_path = Path(args.spec)
    try:
        combinations, _gated, spec_products = load_spec(spec_path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return _usage_error(f"cannot read spec {spec_path}: {exc}")

    try:
        validate_routes(combinations, spec_products)
    except ValueError as exc:
        return _usage_error(str(exc))

    known = {combo.key for combo in combinations}
    only = list(args.only)
    unknown = [key for key in only if key not in known]
    if unknown:
        return _usage_error(f"unknown --only cell(s): {', '.join(unknown)}; use --list")

    domains = [item.strip() for item in str(args.domains).split(",") if item.strip()]
    if not domains:
        return _usage_error("--domains is empty")

    if args.llm_attempts is not None and args.llm_attempts < 1:
        return _usage_error("--llm-attempts must be >= 1")
    if args.llm_backoff is not None and args.llm_backoff < 0:
        return _usage_error("--llm-backoff must be >= 0")

    selected = [combo for combo in combinations if not only or combo.key in only]

    if args.list:
        for combo in selected:
            marker = "gated" if combo.gated else "non-gated"
            if args.json:
                payload = {"product": combo.product, "format": combo.format, "gated": combo.gated}
                print(json.dumps(payload))
            else:
                print(f"{combo.key}\t{marker}")
        return 0

    out_dir = Path(args.out)
    canonical = out_dir / "matrix.json"
    checkpoint = Path(args.checkpoint) if args.checkpoint else canonical
    try:
        existing_rows = load_matrix(checkpoint)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _usage_error(f"cannot read checkpoint {checkpoint}: {exc}")

    keyed = keyed_state()
    llm_available = detect_llm_available(CONFIG_PATH)
    if not llm_available:
        # A no-key run cannot reach a provider, so skip LiteLLM's remote
        # model-cost-map fetch (tens of seconds on a blocked network).
        os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    topics = load_topics()
    existing = {_row_key(row): row for row in existing_rows}
    final: dict[tuple[str, str, str], dict[str, Any]] = dict(existing)
    run_rows: list[dict[str, Any]] = []

    if args.only_assert:
        missing = [
            f"{domain}/{combo.key}"
            for domain in domains
            for combo in selected
            if (domain, combo.product, combo.format) not in existing
        ]
        if missing:
            print(
                "error: --only-assert found no recorded row for: " + ", ".join(missing),
                file=sys.stderr,
            )
            return 1
        for domain in domains:
            for combo in selected:
                row = existing[(domain, combo.product, combo.format)]
                updated = reevaluate_cell(row, keyed=keyed)
                final[_row_key(updated)] = updated
                run_rows.append(updated)
                _log(f"[assert] {domain}/{combo.key} -> {updated['reached']}", args.json)
    else:
        total = len(domains) * len(selected)
        index = 0
        for domain in domains:
            for combo in selected:
                index += 1
                existing_row = existing.get((domain, combo.product, combo.format))
                recorded = existing_row is not None and existing_row.get("reached") != PENDING
                if existing_row is not None and not args.force and recorded:
                    final[_row_key(existing_row)] = existing_row
                    run_rows.append(existing_row)
                    _log(
                        f"[{index}/{total}] {domain}/{combo.key} -> skipped "
                        f"(recorded {existing_row.get('reached')}; use --force to re-run)",
                        args.json,
                    )
                    continue
                row = generate_cell(
                    combo,
                    domain=domain,
                    topic=topics.get(domain, ""),
                    artifact_root=ARTIFACT_ROOT,
                    force=args.force,
                    keyed=keyed,
                    llm_available=llm_available,
                    llm_attempts=args.llm_attempts,
                    llm_backoff=args.llm_backoff,
                )
                final[_row_key(row)] = row
                run_rows.append(row)
                artifact = row.get("artifact") or "(no artifact)"
                _log(
                    f"[{index}/{total}] {domain}/{combo.key} -> {row['reached']} {artifact}",
                    args.json,
                )

    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "command": command,
        "spec": repo_relative(spec_path),
        "domains": domains,
        "keyed": keyed,
        "only": only,
        "only_assert": bool(args.only_assert),
    }
    matrix_rows = list(final.values())
    _write_matrix_json(canonical, meta, matrix_rows)
    if checkpoint != canonical:
        _write_matrix_json(checkpoint, meta, matrix_rows)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "matrix.md").write_text(render_markdown(meta, matrix_rows), encoding="utf-8")

    _emit_rows(run_rows, args.json)
    failures = [row for row in run_rows if row.get("reached") not in {"L3"} | HONEST_BLOCKS]
    if not args.json:
        print(f"Matrix written to {canonical} and {out_dir / 'matrix.md'}")
        print(f"Rows: {len(run_rows)}; unexplained failures: {len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
