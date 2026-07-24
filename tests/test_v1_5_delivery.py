"""Tests for v1.5 delivery channel abstraction and ProductTemplate.

Covers: DeliveryChannel ABC, SMTPDeliveryChannel, WebhookDeliveryChannel,
validate_config, get_channel factory, list_channels, ProductTemplate.
"""

from __future__ import annotations

import pytest

from autoinfo.delivery import (
    DeliveryChannel,
    SMTPDeliveryChannel,
    WebhookDeliveryChannel,
    get_available_channels,
    get_channel,
    list_channels,
)
from autoinfo.models import DeliveryResult, Product, ProductType
from autoinfo.output import ProductTemplate, generate_digest, generate_report


def _make_product(
    product_id: str = "test-1",
    domain: str = "test-domain",
) -> Product:
    """Helper to create a minimal Product for tests."""
    return Product(
        id=product_id,
        domain=domain,
        type=ProductType.PROCESSED,
        name="test-product",
    )


# ===================================================================
# DeliveryChannel ABC
# ===================================================================


class TestDeliveryChannelABC:
    def test_cannot_instantiate_abc(self) -> None:
        """DeliveryChannel ABC should raise TypeError when instantiated."""
        with pytest.raises(TypeError):
            DeliveryChannel()  # type: ignore[abstract]

    def test_subclass_must_implement_abstract_methods(self) -> None:
        """Subclass missing abstract methods should raise TypeError."""

        class Incomplete(DeliveryChannel):
            pass

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]


# ===================================================================
# SMTPDeliveryChannel
# ===================================================================


class TestSMTPDeliveryChannel:
    def test_name(self) -> None:
        channel = SMTPDeliveryChannel()
        assert channel.name == "smtp"

    def test_validate_config_valid(self) -> None:
        channel = SMTPDeliveryChannel()
        assert (
            channel.validate_config(
                {
                    "smtp_host": "smtp.example.com",
                    "smtp_port": 587,
                    "from_addr": "bot@example.com",
                }
            )
            is True
        )

    def test_validate_config_missing_host(self) -> None:
        channel = SMTPDeliveryChannel()
        assert (
            channel.validate_config({"smtp_port": 587, "from_addr": "bot@example.com"})
            is False
        )

    def test_validate_config_missing_port(self) -> None:
        channel = SMTPDeliveryChannel()
        assert (
            channel.validate_config(
                {"smtp_host": "smtp.example.com", "from_addr": "bot@example.com"}
            )
            is False
        )

    def test_validate_config_missing_from(self) -> None:
        channel = SMTPDeliveryChannel()
        assert (
            channel.validate_config({"smtp_host": "smtp.example.com", "smtp_port": 587})
            is False
        )

    def test_validate_config_empty_host(self) -> None:
        channel = SMTPDeliveryChannel()
        assert (
            channel.validate_config(
                {
                    "smtp_host": "",
                    "smtp_port": 587,
                    "from_addr": "bot@example.com",
                }
            )
            is False
        )

    def test_validate_config_empty_dict(self) -> None:
        channel = SMTPDeliveryChannel()
        assert channel.validate_config({}) is False

    def test_send_returns_delivery_result(self) -> None:
        """Even when sending fails, we should get a DeliveryResult, not an exception."""
        channel = SMTPDeliveryChannel()
        product = _make_product()
        result = channel.send(
            product=product,
            payload={"domain": "test", "period": "weekly"},
            recipients=["test@example.com"],
        )
        assert isinstance(result, DeliveryResult)
        assert result.channel == "smtp"
        assert result.status in ("success", "failed")  # will fail without real SMTP
        assert result.product_id == "test-1"


# ===================================================================
# WebhookDeliveryChannel
# ===================================================================


class TestWebhookDeliveryChannel:
    def test_name(self) -> None:
        channel = WebhookDeliveryChannel()
        assert channel.name == "webhook"

    def test_validate_config_valid_http(self) -> None:
        channel = WebhookDeliveryChannel()
        assert channel.validate_config({"url": "http://example.com/hook"}) is True

    def test_validate_config_valid_https(self) -> None:
        channel = WebhookDeliveryChannel()
        assert channel.validate_config({"url": "https://hooks.example.com/xyz"}) is True

    def test_validate_config_invalid_scheme_ftp(self) -> None:
        channel = WebhookDeliveryChannel()
        assert channel.validate_config({"url": "ftp://example.com/hook"}) is False

    def test_validate_config_empty_url(self) -> None:
        channel = WebhookDeliveryChannel()
        assert channel.validate_config({"url": ""}) is False

    def test_validate_config_missing_url_key(self) -> None:
        channel = WebhookDeliveryChannel()
        assert channel.validate_config({"host": "example.com"}) is False

    def test_validate_config_non_string_url(self) -> None:
        channel = WebhookDeliveryChannel()
        assert channel.validate_config({"url": 42}) is False

    def test_validate_config_empty_dict(self) -> None:
        channel = WebhookDeliveryChannel()
        assert channel.validate_config({}) is False

    def test_send_returns_delivery_result(self) -> None:
        """Sending to unreachable URL should return failed DeliveryResult."""
        channel = WebhookDeliveryChannel()
        product = _make_product()
        result = channel.send(
            product=product,
            payload={"key": "value"},
            recipients=["http://localhost:1/nonexistent"],
        )
        assert isinstance(result, DeliveryResult)
        assert result.channel == "webhook"
        assert result.status in ("failed", "partial")
        assert result.product_id == "test-1"


# ===================================================================
# get_channel factory
# ===================================================================


class TestGetChannel:
    def test_get_channel_smtp(self) -> None:
        channel = get_channel("smtp")
        assert isinstance(channel, SMTPDeliveryChannel)

    def test_get_channel_webhook(self) -> None:
        channel = get_channel("webhook")
        assert isinstance(channel, WebhookDeliveryChannel)

    def test_get_channel_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown delivery channel 'slack'"):
            get_channel("slack")

    def test_get_channel_unknown_empty_string(self) -> None:
        with pytest.raises(ValueError):
            get_channel("")

    def test_get_channel_returns_new_instance(self) -> None:
        """Each call to get_channel should return a fresh instance."""
        a = get_channel("smtp")
        b = get_channel("smtp")
        assert a is not b


# ===================================================================
# list_channels
# ===================================================================


class TestListChannels:
    def test_list_channels(self) -> None:
        channels = list_channels()
        assert "smtp" in channels
        assert "webhook" in channels

    def test_list_channels_sorted(self) -> None:
        channels = list_channels()
        assert channels == sorted(channels)


# ===================================================================
# get_available_channels
# ===================================================================


class TestGetAvailableChannels:
    def test_get_available_channels_contains_smtp_and_webhook(self) -> None:
        channels = get_available_channels()
        assert "smtp" in channels
        assert "webhook" in channels

    def test_get_available_channels_returns_sorted(self) -> None:
        channels = get_available_channels()
        assert channels == sorted(channels)

    def test_get_available_channels_matches_list_channels(self) -> None:
        assert get_available_channels() == list_channels()


# ===================================================================
# ProductTemplate
# ===================================================================


class TestProductTemplate:
    """Tests for ProductTemplate rendering and integration."""

    def test_renders_digest_with_correct_template(self) -> None:
        """ProductTemplate renders digest using the legacy flat template name."""
        pt = ProductTemplate(domain="test")
        data: dict[str, object] = {
            "title": "Digest Title",
            "domain": "test",
            "period_label": "Daily",
            "date_from": "2024-01-01",
            "date_to": "2024-01-07",
            "generated_at": "2024-01-07T00:00:00Z",
            "entries": [],
            "llm_synthesis": {},
        }
        result = pt.render("digest", "md", data)
        assert isinstance(result, str)
        assert "# Digest Title" in result
        assert len(result) > 0

    def test_domain_override(self, tmp_path: pytest.TempPathFactory) -> None:
        """Domain-specific template overrides the base template."""
        domain = "test-domain"
        domain_dir = (
            tmp_path / ".autoinfo" / "templates" / domain / "digest"
        )
        domain_dir.mkdir(parents=True)
        domain_dir.joinpath("custom.j2").write_text(
            "CUSTOM OVERRIDE: {{ title }}"
        )

        pt = ProductTemplate(domain=domain)
        pt._domain_dir = domain_dir.parent.parent / domain  # type: ignore[attr-defined]

        data: dict[str, object] = {"title": "Hello"}
        result = pt.render("digest", "custom", data)
        assert "CUSTOM OVERRIDE: Hello" in result

    def test_unknown_variant_falls_back_to_default(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        """Unknown variant falls back to the default template for the type."""
        domain = "test-domain"
        domain_dir = (
            tmp_path / ".autoinfo" / "templates" / domain / "digest"
        )
        domain_dir.mkdir(parents=True)
        domain_dir.joinpath("default.j2").write_text(
            "DEFAULT FALLBACK: {{ title }}"
        )

        pt = ProductTemplate(domain=domain)
        pt._domain_dir = domain_dir.parent.parent / domain  # type: ignore[attr-defined]

        data: dict[str, object] = {"title": "Works"}
        result = pt.render("digest", "nonexistent_variant", data)
        assert "DEFAULT FALLBACK: Works" in result

    def test_render_returns_non_empty_string(self) -> None:
        """render() always returns a non-empty string for known templates."""
        pt = ProductTemplate(domain="test")
        data: dict[str, object] = {
            "title": "Test",
            "domain": "test",
            "period_label": "Daily",
            "date_from": "2024-01-01",
            "date_to": "2024-01-07",
            "generated_at": "2024-01-07T00:00:00Z",
            "entries": [],
            "llm_synthesis": {},
        }
        result = pt.render("digest", "md", data)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_backward_compatible_digest(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """generate_digest still works without the product_template parameter."""
        # Mock KBStore so we don't need a real knowledge base
        class _MockStore:
            def list_entries(self, **kwargs: object) -> list[dict[str, object]]:
                return [
                    {
                        "title": "Entry 1",
                        "summary": "A test entry",
                        "tags": "[]",
                        "source_platform": "web",
                        "source_type": "article",
                        "collected_at": "2024-01-01",
                        "relevance_score": 85,
                        "source_url": "http://example.com",
                    }
                ]

        monkeypatch.setattr("autoinfo.kb.KBStore", lambda: _MockStore())
        # Prevent actual LLM calls during testing
        monkeypatch.setattr(
            "autoinfo.output._call_llm_for_digest",
            lambda prompt=None, config=None: {},
        )

        result = generate_digest(
            domain="test",
            period="daily",
            format="markdown",
        )
        assert isinstance(result, str)
        assert len(result) > 0
        # Verify the result uses the old rendering path (no ProductTemplate)
        assert "Entry 1" in result
