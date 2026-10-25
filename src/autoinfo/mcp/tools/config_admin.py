"""MCP tool schemas — Webhooks, gate config, product (6 tools).

Phase 1 of #581: schemas extracted from ``mcp/server.py::_full_tool_list``
verbatim.  ``build_tools()`` returns FRESH ``Tool`` objects on every call,
so ``_decorate_tools`` mutation never leaks across calls.
"""

from __future__ import annotations

from typing import Any

from mcp.types import Tool

from autoinfo.mcp import context as mcp_context
from autoinfo.mcp.errors import ErrorCode, error_response


def build_tools() -> list[Tool]:
    """Return the 6 schemas for this module, in registration order."""
    return [
        # -- Webhooks (2) ----------------------------------------------------
        Tool(
            name="set_domain_webhooks",
            description=(
                "Set webhook URLs for a domain. All newly collected items "
                "will be POSTed to these URLs as JSON. Replaces any existing "
                "URLs. Fire-and-forget with retry (3 attempts)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "webhook_urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "List of webhook URLs (must start with http:// or https://)"
                        ),
                    },
                },
                "required": ["domain", "webhook_urls"],
            },
        ),
        Tool(
            name="get_domain_webhooks",
            description="Return the configured webhook URLs for a domain. Webhooks fire per collected item; use this to verify the endpoint set before relying on push delivery. Returns the raw list plus any per-source overrides.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                },
                "required": ["domain"],
            },
        ),
        # -- Gate Config (2) -------------------------------------------------
        Tool(
            name="get_gate_config",
            description="Return gate configuration (quality or delivery) for a domain — checks domain-level config, falls back to global defaults",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "gate": {
                        "type": "string",
                        "description": "Gate name (e.g. G0, G1, D1, D2, CurationGate)",
                    },
                },
                "required": ["domain", "gate"],
            },
        ),
        Tool(
            name="set_gate_config",
            description="Update gate configuration for a domain. Provide gate-specific fields (action, threshold, retries for quality gates; enabled, action_on_failure for delivery gates)",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "gate": {
                        "type": "string",
                        "description": "Gate name (e.g. G0, G1, D1, D2, CurationGate)",
                    },
                    "config": {
                        "type": "object",
                        "description": 'Gate configuration dict (e.g. {"action": "block", "retries": 3, "retry_models": [...]} for quality gates; {"enabled": true, "action_on_failure": "flag"} for delivery gates)',
                        "properties": {
                            "action": {
                                "type": "string",
                                "description": (
                                    "Action on failure: block, retry, flag, "
                                    "skip, archive (quality gates)"
                                ),
                                "enum": [
                                    "block",
                                    "retry",
                                    "flag",
                                    "skip",
                                    "archive",
                                ],
                            },
                            "retries": {
                                "type": "integer",
                                "description": "Number of retry attempts (quality gates)",
                            },
                            "retry_models": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Fallback model chain (quality gates)",
                            },
                            "threshold": {
                                "type": "number",
                                "description": "Score threshold 0-100 (quality gates)",
                            },
                            "enabled": {
                                "type": "boolean",
                                "description": "Whether enabled (delivery gates; CurationGate G4)",
                            },
                            "action_on_failure": {
                                "type": "string",
                                "description": (
                                    "Action on failure: block, fallback, flag (delivery gates)"
                                ),
                                "enum": ["block", "fallback", "flag"],
                            },
                        },
                    },
                },
                "required": ["domain", "gate", "config"],
            },
        ),
        # -- Product (2) -----------------------------------------------------
        Tool(
            name="get_product",
            description=(
                "Return configuration of a single product (RAW or PROCESSED) "
                "for a domain by product type — channels, formats, and "
                "platform limits derived from domain config. Inspect a "
                "specific product before generating or delivering."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "product_type": {
                        "type": "string",
                        "description": "Product type: RAW or PROCESSED",
                        "enum": ["RAW", "PROCESSED"],
                    },
                },
                "required": ["domain", "product_type"],
            },
        ),
        Tool(
            name="list_products",
            description=(
                "Enumerate all products (RAW and PROCESSED) configured for a "
                "domain with their product id, channels, and formats. Use "
                "for an overview before choosing one to generate."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                },
                "required": ["domain"],
            },
        ),
    ]


def _handle_set_domain_webhooks(
    domain: str,
    webhook_urls: list[str],
) -> dict[str, Any]:
    """Set webhook URLs for a domain. Replaces any existing URLs."""
    # -- Validate URLs ----------------------------------------------------
    invalid: list[str] = []
    for url in webhook_urls:
        if not url.startswith(("http://", "https://")):
            invalid.append(url)
    if invalid:
        return error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message=f"Invalid webhook URLs (must start with http:// or https://): {invalid}",
            actionable=True,
        )

    try:
        config = mcp_context._load_config()
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = mcp_context._find_domain(config, domain)
    if domain_cfg is None:
        return error_response(
            code=ErrorCode.DOMAIN_NOT_FOUND,
            message=f"Domain '{domain}' is not configured. Use add_domain(name='{domain}') to create it.",
            actionable=True,
        )

    domain_cfg.webhook_urls = list(webhook_urls)
    mcp_context._save_config(config)

    return {
        "domain": domain,
        "webhook_urls": domain_cfg.webhook_urls,
        "updated": True,
    }


def _handle_get_domain_webhooks(domain: str) -> dict[str, Any]:
    """Return the configured webhook URLs for a domain."""
    try:
        config = mcp_context._load_config()
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = mcp_context._find_domain(config, domain)
    if domain_cfg is None:
        return error_response(
            code=ErrorCode.DOMAIN_NOT_FOUND,
            message=f"Domain '{domain}' is not configured. Use add_domain(name='{domain}') to create it.",
            actionable=True,
        )

    return {
        "domain": domain,
        "webhook_urls": list(getattr(domain_cfg, "webhook_urls", [])),
    }


def _handle_get_gate_config(domain: str, gate: str) -> dict[str, Any]:
    """Return gate configuration for a domain.

    Checks both quality gates (G0-G5 etc.) and delivery gates (D1-D3 etc.),
    falling back to global defaults when the gate is not set at the domain level.
    """
    try:
        config = mcp_context._load_config()
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = mcp_context._find_domain(config, domain)
    if domain_cfg is None:
        return error_response(
            code=ErrorCode.DOMAIN_NOT_FOUND,
            message=f"Domain '{domain}' is not configured. Use add_domain(name='{domain}') to create it.",
            actionable=True,
        )

    from dataclasses import asdict as _asdict

    # Normalise the queried gate name to its canonical long form — config
    # keys are stored as e.g. "G3-RelevanceScoring" (short "G3" accepted).
    from autoinfo.config import _GATE_CONFIG_KEY_MAP

    gate_key = _GATE_CONFIG_KEY_MAP.get(gate, gate)

    # Check quality gates first, then delivery gates, then global defaults
    gate_config: dict[str, Any] | None = None
    gate_type: str = ""

    if gate_key in domain_cfg.quality_gates:
        gate_config = _asdict(domain_cfg.quality_gates[gate_key])
        gate_type = "quality"
    elif gate_key in domain_cfg.delivery_gates:
        gate_config = _asdict(domain_cfg.delivery_gates[gate_key])
        gate_type = "delivery"
    elif gate_key in config.quality_gates:
        gate_config = _asdict(config.quality_gates[gate_key])
        gate_type = "quality"
    elif gate_key in config.delivery_gates:
        gate_config = _asdict(config.delivery_gates[gate_key])
        gate_type = "delivery"

    if gate_config is None:
        return error_response(
            code=ErrorCode.GATE_NOT_FOUND,
            message=f"Gate '{gate}' is not configured for domain '{domain}'",
            actionable=True,
        )

    # Remove internal fields from serialization
    gate_config.pop("name", None)

    return {
        "domain": domain,
        "gate": gate,
        "gate_type": gate_type,
        "config": gate_config,
    }


def _handle_set_gate_config(
    domain: str,
    gate: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Update gate configuration for a domain.

    *config* should contain gate-specific fields (e.g. ``action``, ``threshold``
    for quality gates; ``enabled``, ``action_on_failure`` for delivery gates).
    """
    try:
        cfg = mcp_context._load_config()
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = mcp_context._find_domain(cfg, domain)
    if domain_cfg is None:
        return error_response(
            code=ErrorCode.DOMAIN_NOT_FOUND,
            message=f"Domain '{domain}' is not configured. Use add_domain(name='{domain}') to create it.",
            actionable=True,
        )

    from autoinfo.config import DeliveryGateConfig, QualityGateConfig

    # Determine if this is a quality or delivery gate. CurationGate is
    # always a quality gate: its dict carries ``enabled`` (the G4 switch),
    # which the generic heuristic below would otherwise misread as delivery.
    is_delivery = (
        gate in domain_cfg.delivery_gates
        or ("action_on_failure" in config)
        or (gate != "CurationGate" and "enabled" in config and "category" not in config)
    )
    is_quality = (gate in domain_cfg.quality_gates) or not is_delivery

    new_gc: QualityGateConfig | None = None
    new_dc: DeliveryGateConfig | None = None

    if is_quality:
        new_gc = QualityGateConfig(
            name=gate,
            category=str(config.get("category", "soft")),
            retries=int(config.get("retries", 0)),
            retry_models=list(config.get("retry_models", [])),
            action=str(config.get("action", "flag")),
            threshold=config.get("threshold", None),
            enabled=bool(config.get("enabled", True)),
        )
        domain_cfg.quality_gates[gate] = new_gc
    else:
        new_dc = DeliveryGateConfig(
            name=gate,
            enabled=bool(config.get("enabled", True)),
            action_on_failure=str(config.get("action_on_failure", "block")),
        )
        domain_cfg.delivery_gates[gate] = new_dc

    mcp_context._save_config(cfg)

    # Both branches of is_quality/is_delivery set one of new_gc/new_dc
    if is_quality and new_gc is not None:
        from dataclasses import asdict as _asdict

        config_dict = _asdict(new_gc)
    elif new_dc is not None:
        from dataclasses import asdict as _asdict

        config_dict = _asdict(new_dc)
    else:
        config_dict = {}

    return {
        "domain": domain,
        "gate": gate,
        "updated": True,
        "config": config_dict,
    }


def _handle_get_product(domain: str, product_type: str) -> dict[str, Any]:
    """Return product configuration for a domain and product type.

    *product_type* is ``"RAW"`` or ``"PROCESSED"``.  Products are derived
    from the domain's configuration (sources, quality gates, delivery
    channels, etc.).
    """
    try:
        cfg = mcp_context._load_config()
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = mcp_context._find_domain(cfg, domain)
    if domain_cfg is None:
        return error_response(
            code=ErrorCode.DOMAIN_NOT_FOUND,
            message=f"Domain '{domain}' is not configured. Use add_domain(name='{domain}') to create it.",
            actionable=True,
        )

    product_type_upper = product_type.upper()
    if product_type_upper not in ("RAW", "PROCESSED"):
        return error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message=f"Invalid product_type '{product_type}'. Must be 'RAW' or 'PROCESSED'.",
            actionable=True,
        )

    if product_type_upper == "RAW":
        product = {
            "id": f"{domain}-raw",
            "domain": domain,
            "type": "raw",
            "name": f"{domain} RAW Feed",
            "config": {
                "sources": [
                    {"name": s.name, "type": s.type, "url": s.url} for s in domain_cfg.sources
                ],
                "extract_fields": list(getattr(domain_cfg, "extract_fields", [])),
            },
            "templates": [],
            "delivery_channels": ["api"],
            "quality_gates": list(domain_cfg.quality_gates.keys()),
            "variants": ["api_feed", "webhook", "bulk_export"],
        }
    else:
        product = {
            "id": f"{domain}-processed",
            "domain": domain,
            "type": "processed",
            "name": f"{domain} PROCESSED Output",
            "config": {
                "delivery_gates": {
                    dg: mcp_context._gate_to_dict(gc)
                    for dg, gc in domain_cfg.delivery_gates.items()
                },
                "webhook_urls": list(getattr(domain_cfg, "webhook_urls", [])),
                "search_mode": getattr(domain_cfg, "search_mode", "keyword"),
            },
            "templates": ["digest", "report", "tutorial", "presentation"],
            "delivery_channels": ["webhook", "smtp", "api", "export"],
            "quality_gates": list(domain_cfg.quality_gates.keys()),
        }

    return {"product": product}


def _handle_list_products(domain: str) -> dict[str, Any]:
    """List all configured products for a domain.

    Returns both RAW and PROCESSED product types derived from the
    domain's configuration.
    """
    try:
        cfg = mcp_context._load_config()
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Failed to load the project configuration")

    domain_cfg = mcp_context._find_domain(cfg, domain)
    if domain_cfg is None:
        return error_response(
            code=ErrorCode.DOMAIN_NOT_FOUND,
            message=f"Domain '{domain}' is not configured. Use add_domain(name='{domain}') to create it.",
            actionable=True,
        )

    raw_product = {
        "id": f"{domain}-raw",
        "domain": domain,
        "type": "raw",
        "name": f"{domain} RAW Feed",
        "source_count": len(domain_cfg.sources),
        "extract_fields": list(getattr(domain_cfg, "extract_fields", [])),
        "quality_gate_count": len(domain_cfg.quality_gates),
        "variants": ["api_feed", "webhook", "bulk_export"],
    }

    processed_product = {
        "id": f"{domain}-processed",
        "domain": domain,
        "type": "processed",
        "name": f"{domain} PROCESSED Output",
        "delivery_channel_count": len(
            list(getattr(domain_cfg, "webhook_urls", [])) + ["smtp", "api", "export"]
        ),
        "delivery_gate_count": len(domain_cfg.delivery_gates),
        "templates": ["digest", "report", "tutorial", "presentation"],
    }

    return {
        "domain": domain,
        "products": [raw_product, processed_product],
        "count": 2,
    }
