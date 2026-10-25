"""Jinja environment, product templates, and product-type resolution.

Extracted from ``output/__init__.py`` (#582 phase 3). ``_TEMPLATES_DIR`` stays
hub-resident because tests patch it through ``autoinfo.output``; every reader
resolves it with a function-local hub import.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, TemplateNotFound

from autoinfo.output.entries import (
    _domain_display_name,
    _entry_source_cell,
    _is_empty_summary,
    _platform_name,
    _user_source_label,
)

logger = logging.getLogger("autoinfo.output")


def _templates_dir() -> Path:
    """Read the hub's ``_TEMPLATES_DIR`` at call time (tests patch it there)."""
    from autoinfo.output import _TEMPLATES_DIR

    return _TEMPLATES_DIR


_jinja_env: Environment | None = None


def _html_autoescape(template_name: str | None) -> bool:
    """Enable Jinja2 autoescaping for HTML templates only.

    Markdown templates (``*.md.j2``) keep autoescaping OFF so they can
    emit raw Markdown freely.  HTML templates (``*.html.j2``) turn
    autoescaping ON so user-supplied text is safely escaped; pre-rendered
    HTML content is marked ``|safe`` in the template where needed.
    """
    if template_name is None:
        return False
    return template_name.endswith(".html.j2")


def _get_jinja_env() -> Environment:
    """Return a cached Jinja2 environment for the ``data/templates/`` directory.

    The environment loads any template file in ``data/templates/`` —
    including both ``.md.j2`` (Markdown) and ``.html.j2`` (HTML)
    templates.  Autoescaping is enabled selectively for ``.html.j2``
    files via :func:`_html_autoescape`.

    Registers a ``product_summary`` filter that returns ``""`` for
    empty/placeholder summaries (defense-in-depth for issue #294).
    """
    global _jinja_env
    if _jinja_env is None:
        _jinja_env = Environment(
            loader=FileSystemLoader(str(_templates_dir())),
            autoescape=_html_autoescape,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        _jinja_env.filters["product_summary"] = lambda v: "" if _is_empty_summary(str(v)) else v
        _jinja_env.filters["platform_name"] = _platform_name
        _jinja_env.globals["user_source_label"] = _user_source_label
        _jinja_env.globals["domain_display_name"] = _domain_display_name
        _jinja_env.globals["entry_source_cell"] = _entry_source_cell
    return _jinja_env


FORMAT_TO_VARIANT: dict[str, str] = {
    "markdown": "md",
    "html": "html",
    "json": "json",
    "pdf": "pdf",
}


class ProductTemplate:
    """Wraps Jinja2 rendering with product metadata and template selection.

    Template selection strategy (first match wins):

    1. ``.autoinfo/templates/<domain>/<type>/<variant>.j2`` — domain-specific
       override (e.g. ``.autoinfo/templates/medical-research/digest/weekly.j2``)
    2. ``data/templates/<type>/<variant>.j2`` — built-in base template
       (e.g. ``data/templates/digest/weekly.j2``)
    3. ``data/templates/<type>/default.j2`` — default variant for that type
    4. ``data/templates/<type>.<variant>.j2`` — legacy flat naming (backward
       compatible with the existing ``digest.md.j2`` convention)

    The *access_level* controls freemium gating (G15):

    - ``"free"`` (default) — available to all users
    - ``"premium"`` — requires active paid subscription
    - ``"enterprise"`` — requires enterprise-tier subscription

    Usage::

        pt = ProductTemplate(domain="medical-research", access_level="premium")
        output = pt.render("digest", "md", context_dict)
    """

    def __init__(
        self,
        domain: str,
        access_level: Literal["free", "premium", "enterprise"] = "free",
    ):
        self.domain = domain
        self.access_level: Literal["free", "premium", "enterprise"] = access_level
        self._domain_dir = Path.cwd() / ".autoinfo" / "templates" / domain

    @property
    def _base_dir(self) -> Path:
        return _templates_dir()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(
        self,
        product_type: str,
        variant: str,
        data: dict[str, Any],
    ) -> str:
        """Render a template for *product_type* and *variant* with *data*.

        Parameters
        ----------
        product_type:
            Template category (e.g. ``"digest"``, ``"report"``,
            ``"tutorial"``, ``"presentation"``).
        variant:
            Template variant (e.g. ``"md"``, ``"html"``, ``"weekly"``).
        data:
            Template context variables.

        Returns
        -------
        str
            Rendered template output.

        Raises
        ------
        FileNotFoundError
            If no matching template is found in any search path.
        """
        env = self._get_env()

        candidates = [
            f"{product_type}/{variant}.j2",
            f"{product_type}/default.j2",
            f"{product_type}.{variant}.j2",  # legacy flat naming
            f"{product_type}.default.j2",  # legacy default
        ]

        for name in candidates:
            try:
                template = env.get_template(name)
                return template.render(**data)
            except TemplateNotFound:
                continue

        raise FileNotFoundError(
            f"No template found for domain={self.domain}, type={product_type}, variant={variant}"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_env(self) -> Environment:
        """Create a Jinja2 environment that checks domain overrides first.

        Uses :class:`ChoiceLoader` so that domain-specific templates (in
        ``.autoinfo/templates/<domain>/``) are preferred over built-in
        base templates (in ``data/templates/``).
        """
        loaders: list[FileSystemLoader] = []
        if self._domain_dir.is_dir():
            loaders.append(FileSystemLoader(str(self._domain_dir)))
        loaders.append(FileSystemLoader(str(self._base_dir)))

        if len(loaders) == 1:
            # Only base dir exists — no ChoiceLoader needed
            env = Environment(
                loader=loaders[0],
                autoescape=_html_autoescape,
                trim_blocks=True,
                lstrip_blocks=True,
            )
        else:
            env = Environment(
                loader=ChoiceLoader(loaders),
                autoescape=_html_autoescape,
                trim_blocks=True,
                lstrip_blocks=True,
            )
        # Defense-in-depth for issue #294: normalize empty/placeholder summaries
        env.filters["product_summary"] = lambda v: "" if _is_empty_summary(str(v)) else v
        # Defense-in-depth for issue #302: map internal platform ids to display names
        env.filters["platform_name"] = _platform_name
        # Issue #91: never leak raw internal platform ids in References
        env.globals["user_source_label"] = _user_source_label
        # Issue #138: expose user-facing domain display names in footers
        env.globals["domain_display_name"] = _domain_display_name
        # Issue #167: source cell for product-table rows
        env.globals["entry_source_cell"] = _entry_source_cell
        return env


PRODUCT_TEMPLATES: list[dict[str, Any]] = [
    {
        "name": "digest",
        "description": "Scheduled knowledge digests",
        "access_level": "free",
        "template": ProductTemplate(domain="*", access_level="free"),
    },
    {
        "name": "report",
        "description": "Thematic structured reports",
        "access_level": "free",
        "template": ProductTemplate(domain="*", access_level="free"),
    },
    {
        "name": "tutorial",
        "description": "Learning path tutorials",
        "access_level": "free",
        "template": ProductTemplate(domain="*", access_level="free"),
    },
    {
        "name": "presentation",
        "description": "Slide-based presentations",
        "access_level": "free",
        "template": ProductTemplate(domain="*", access_level="free"),
    },
    {
        "name": "premium-briefing",
        "description": "Premium briefings with deep analysis and actionable insights",
        "access_level": "premium",
        "template": ProductTemplate(domain="*", access_level="premium"),
    },
    {
        "name": "column",
        "description": "Paid deep-dive column",
        "access_level": "premium",
        "template": ProductTemplate(domain="*", access_level="premium"),
    },
    {
        "name": "magazine-digest",
        "description": "Magazine-styled digest of per-title RSS",
        "access_level": "free",
        "template": ProductTemplate(domain="*", access_level="free"),
    },
    {
        "name": "enterprise-briefing",
        "description": "Enterprise briefings with custom data, white-labeling, and priority support",  # noqa: E501
        "access_level": "enterprise",
        "template": ProductTemplate(domain="*", access_level="enterprise"),
    },
]


_PRODUCT_H1_WORDS: dict[str, str] = {
    "digest": "Digest",
    "report": "Report",
    "tutorial": "Tutorial",
    "presentation": "Presentation",
    "premium-briefing": "Premium Briefing",
    "column": "Column",
    "magazine-digest": "Magazine Digest",
    "enterprise-briefing": "Enterprise Briefing",
}


def _product_h1_word(family: str, default: str = "Digest") -> str:
    """Return the H1 product word for a resolved product *family* (issue #318).

    *family* is the template family name produced by
    :func:`_resolve_digest_product_type` / :func:`_resolve_report_product_type`
    (e.g. ``"premium-briefing"``).  Unknown families fall back to *default*
    so the non-product paths keep their historical titles.
    """
    return _PRODUCT_H1_WORDS.get(family, default)


def _resolve_digest_product_type(template: ProductTemplate, variant: str) -> str:
    """Map a ProductTemplate instance back to its digest template family.

    ``generate_digest``'s *product_template* parameter is expected to be a
    row's ``template`` from :data:`PRODUCT_TEMPLATES`. Rows whose name has
    a flat template file of its own (e.g. ``magazine-digest`` →
    ``magazine-digest.md.j2``) render through their own family; every other
    row — and any non-registry template — keeps the default ``digest``
    family, so the base ``digest`` row (and report-family rows, should one
    ever be passed) still render ``digest.md.j2`` unchanged.

    This mirrors how ``generate_report`` derives ``product_type`` for the
    ``column`` template (T40): the render site selects the family, and the
    identity lookup is guarded by an on-disk existence check so a registry
    name can never point at a template that does not exist (FileNotFoundError
    trap from the T40 premium-briefing/enterprise-briefing rows).
    """
    for row in PRODUCT_TEMPLATES:
        if row["template"] is template:
            name = str(row["name"])
            if (_templates_dir() / f"{name}.{variant}.j2").is_file():
                return name
            return "digest"
    return "digest"


def _resolve_report_product_type(template: ProductTemplate, variant: str, report_type: str) -> str:
    """Map a ProductTemplate instance back to its report template family.

    ``generate_report``'s *product_template* parameter is expected to be a
    row's ``template`` from :data:`PRODUCT_TEMPLATES`. Rows whose name has
    a flat template file of its own (e.g. ``premium-briefing`` →
    ``premium-briefing.md.j2``, ``enterprise-briefing`` →
    ``enterprise-briefing.md.j2``, ``column`` → ``column.md.j2``) render
    through their own family; every other row — and any non-registry
    template — keeps the default ``report`` family, so the base ``report``
    row still renders ``report.md.j2`` unchanged. The ``column`` report
    type keeps its own family even for non-registry templates (T40
    backward compatibility).

    This mirrors the ``column`` selection previously hardcoded at the
    render site and the guard-first identity lookup of
    :func:`_resolve_digest_product_type`: the on-disk existence check
    ensures a registry name can never point at a template that does not
    exist (FileNotFoundError trap from the T40
    premium-briefing/enterprise-briefing rows).
    """
    for row in PRODUCT_TEMPLATES:
        if row["template"] is template:
            name: str = row["name"]
            if (_templates_dir() / f"{name}.{variant}.j2").is_file():
                return name
            return "column" if report_type == "column" else "report"
    return "column" if report_type == "column" else "report"


def list_output_templates(domain: str = "") -> dict[str, Any]:
    """List available output templates for a domain.

    Parameters
    ----------
    domain:
        Domain name filter (optional; empty string = all domains).

    Returns
    -------
    dict with keys: ``domain``, ``templates``, ``count``.
    """
    templates = [
        {"name": t["name"], "description": t["description"], "access_level": t["access_level"]}
        for t in PRODUCT_TEMPLATES
    ]
    return {"domain": domain, "templates": templates, "count": len(templates)}


TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "data" / "templates" / "report.md.j2"
