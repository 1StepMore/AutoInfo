"""Text-format tool payload metadata — T-S-09 (Todo 25).

Gap T-S-09: text-format MCP tools returned raw-text blobs under an opaque
key, so an agent had to sniff bytes to route them.  The wire contract is now
that **no tool returns an unlabelled raw-text payload**: every text-format
``data`` object carries ``format`` / ``content_type`` / ``encoding`` /
``length`` / ``bytes`` metadata beside the text (the text stays under its
domain-specific key).  ``health_check`` is the documented exception — its
``data`` is a structured object, not text (see ADR-0005 addendum).

This suite is the regression floor for that contract.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from autoinfo.mcp.server import _text_payload_metadata, call_tool

_TEXT_METADATA_KEYS = {"format", "content_type", "encoding", "length", "bytes"}


def _response_body(out: Any) -> dict[str, Any]:
    """Extract the JSON envelope from a ``call_tool`` result (both shapes)."""
    first = out[0]
    if isinstance(first, list):
        return json.loads(first[0].text)
    return json.loads(first.text)


class TestTextPayloadMetadataHelper:
    def test_metadata_is_utf8_and_lengths_agree(self) -> None:
        text = "héllo — 世界"
        meta = _text_payload_metadata(text, format="x", content_type="text/plain; charset=utf-8")
        assert meta["format"] == "x"
        assert meta["content_type"] == "text/plain; charset=utf-8"
        assert meta["encoding"] == "utf-8"
        assert meta["length"] == len(text)
        assert meta["bytes"] == len(text.encode("utf-8"))
        # Multi-byte characters make bytes > length — proves they differ.
        assert meta["bytes"] > meta["length"]


class TestPrometheusPayloadMetadata:
    @pytest.mark.asyncio
    async def test_prometheus_payload_is_self_describing(self) -> None:
        body = _response_body(await call_tool("get_prometheus_metrics", {}))
        assert body["success"] is True
        data = body["data"]
        assert isinstance(data, dict)
        assert _TEXT_METADATA_KEYS <= set(data), sorted(data)
        assert data["format"] == "prometheus"
        assert data["content_type"].startswith("text/plain")
        assert isinstance(data["metrics_text"], str)
        assert data["length"] == len(data["metrics_text"])
        assert data["bytes"] == len(data["metrics_text"].encode("utf-8"))


class TestRssPayloadMetadata:
    @pytest.mark.asyncio
    async def test_rss_payload_is_self_describing(self) -> None:
        body = _response_body(
            await call_tool(
                "get_feeds",
                {"domain": "medical-research", "format": "rss", "limit": 2},
            )
        )
        assert body["success"] is True
        data = body["data"]
        assert _TEXT_METADATA_KEYS <= set(data), sorted(data)
        assert data["format"] == "rss"
        assert data["content_type"] == "application/rss+xml; charset=utf-8"
        assert isinstance(data["content"], str)
        assert data["content"].lstrip().startswith("<?xml")
        assert data["length"] == len(data["content"])
        assert data["bytes"] == len(data["content"].encode("utf-8"))

    @pytest.mark.asyncio
    async def test_json_feed_is_structured_not_a_text_blob(self) -> None:
        body = _response_body(
            await call_tool(
                "get_feeds",
                {"domain": "medical-research", "format": "json", "limit": 2},
            )
        )
        assert body["success"] is True
        data = body["data"]
        # Structured JSON items — no opaque text payload to label.
        assert data["format"] == "json"
        assert isinstance(data["items"], list)
        assert "content" not in data


class TestHealthCheckIsStructured:
    @pytest.mark.asyncio
    async def test_health_check_data_is_structured_not_text(self) -> None:
        body = _response_body(await call_tool("health_check", {}))
        assert body["success"] is True
        data = body["data"]
        assert isinstance(data, dict)
        # Documented exception: structured object, no text metadata block.
        assert {"status", "version", "tools_count"} <= set(data)
        assert isinstance(data["status"], str)
        assert isinstance(data["tools_count"], int)
        # Documented exception: structured object, no text metadata block.
        assert not (_TEXT_METADATA_KEYS <= set(data))
