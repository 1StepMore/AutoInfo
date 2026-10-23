"""MCP tool schemas — Webhooks, gate config, product (6 tools).

Phase 1 of #581: schemas extracted from ``mcp/server.py::_full_tool_list``
verbatim.  ``build_tools()`` returns FRESH ``Tool`` objects on every call,
so ``_decorate_tools`` mutation never leaks across calls.
"""

from __future__ import annotations

from mcp.types import Tool


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
