"""Tests for the end-user storefront (``/storefront``).

All tests mock the MCP backend product handlers and ``user_store`` so no
real SQLite database or config file is required.  The FastAPI
``TestClient`` is used to exercise both the Jinja2-rendered HTML routes
and the JSON API endpoints.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from autoinfo.models import Subscription


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_products() -> list[dict[str, Any]]:
    """Return two synthetic products (one raw/free, one processed/premium)."""
    return [
        {
            "id": "medical-research-raw",
            "domain": "medical-research",
            "type": "raw",
            "name": "medical-research RAW Feed",
            "source_count": 7,
            "extract_fields": ["tldr", "key_points"],
            "quality_gate_count": 6,
            "access_level": "free",
            "price_monthly": 0.0,
            "currency": "USD",
            "tier": "free",
        },
        {
            "id": "medical-research-processed",
            "domain": "medical-research",
            "type": "processed",
            "name": "medical-research PROCESSED Output",
            "delivery_channel_count": 4,
            "delivery_gate_count": 3,
            "templates": ["digest", "report", "tutorial", "presentation"],
            "access_level": "premium",
            "price_monthly": 29.0,
            "currency": "USD",
            "tier": "premium",
        },
    ]


@pytest.fixture
def sample_product_detail() -> dict[str, Any]:
    """Return a detailed product dict (PROCESSED, premium)."""
    return {
        "id": "medical-research-processed",
        "domain": "medical-research",
        "type": "processed",
        "name": "medical-research PROCESSED Output",
        "config": {
            "delivery_gates": {},
            "webhook_urls": [],
            "search_mode": "keyword",
        },
        "templates": ["digest", "report", "tutorial", "presentation"],
        "delivery_channels": ["webhook", "smtp", "api", "export"],
        "quality_gates": ["G0", "G1", "G2", "G3", "G4", "G5"],
        "access_level": "premium",
        "price_monthly": 29.0,
        "currency": "USD",
        "tier": "premium",
    }


@pytest.fixture
def sample_raw_product_detail() -> dict[str, Any]:
    """Return a detailed product dict (RAW, free)."""
    return {
        "id": "medical-research-raw",
        "domain": "medical-research",
        "type": "raw",
        "name": "medical-research RAW Feed",
        "config": {
            "sources": [],
            "extract_fields": ["tldr", "key_points"],
        },
        "templates": [],
        "delivery_channels": ["api"],
        "quality_gates": ["G0", "G1", "G2", "G3", "G4", "G5"],
        "access_level": "free",
        "price_monthly": 0.0,
        "currency": "USD",
        "tier": "free",
    }


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    """Return a TestClient with isolated config."""
    from autoinfo.api.server import app
    import autoinfo.api.routes as routes

    config_dir = tmp_path / ".autoinfo"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(
        "rest_api:\n  port: 8741\n  host: 127.0.0.1\n"
        "llm:\n  provider: openai\n  model: gpt-4\n"
    )

    with patch("autoinfo.config.get_config_path", return_value=config_path):
        yield TestClient(app)

    routes._store = None


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _mock_list_all_products(products: list[dict[str, Any]]):
    """Patch the storefront's product aggregator."""
    return patch(
        "autoinfo.api.storefront._list_all_products", return_value=products
    )


def _mock_get_product(product: dict[str, Any] | None):
    """Patch the storefront's single-product lookup."""
    return patch(
        "autoinfo.api.storefront._get_product", return_value=product
    )


def _mock_check_access(result: dict[str, Any]):
    """Patch billing.check_access."""
    return patch("autoinfo.billing.check_access", return_value=result)


def _mock_create_subscription(sub: Subscription):
    """Patch user_store.create_subscription."""
    return patch("autoinfo.user_store.create_subscription", return_value=sub)


# ---------------------------------------------------------------------------
# Catalog route
# ---------------------------------------------------------------------------


class TestProductCatalog:
    """``GET /storefront/products`` — product catalog."""

    def test_catalog_renders_html(
        self, client: TestClient, sample_products: list[dict[str, Any]]
    ):
        with _mock_list_all_products(sample_products):
            response = client.get("/storefront/products")

        assert response.status_code == 200
        html = response.text
        assert "Product Catalog" in html
        assert "medical-research-raw" in html
        assert "medical-research-processed" in html
        assert "medical-research RAW Feed" in html
        assert "medical-research PROCESSED Output" in html
        # Pricing
        assert "Free" in html
        assert "29" in html
        # Tier badges
        assert "free" in html
        assert "premium" in html
        # Product count badge
        assert "2 product" in html

    def test_catalog_returns_json(
        self, client: TestClient, sample_products: list[dict[str, Any]]
    ):
        with _mock_list_all_products(sample_products):
            response = client.get("/storefront/products?format=json")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        inner = data["data"]
        assert inner["count"] == 2
        assert len(inner["products"]) == 2
        ids = {p["id"] for p in inner["products"]}
        assert "medical-research-raw" in ids
        assert "medical-research-processed" in ids

    def test_catalog_empty_shows_empty_state(self, client: TestClient):
        with _mock_list_all_products([]):
            response = client.get("/storefront/products")

        assert response.status_code == 200
        assert "No products available" in response.text
        assert "0 product" in response.text

    def test_catalog_has_bootstrap_cdn(
        self, client: TestClient, sample_products: list[dict[str, Any]]
    ):
        with _mock_list_all_products(sample_products):
            response = client.get("/storefront/products")

        assert response.status_code == 200
        html = response.text
        assert "bootstrap@5.3.3" in html
        assert "bootstrap-icons@1.11.3" in html
        assert "bootstrap.bundle.min.js" in html

    def test_catalog_has_subscribe_cta_links(
        self, client: TestClient, sample_products: list[dict[str, Any]]
    ):
        with _mock_list_all_products(sample_products):
            response = client.get("/storefront/products")

        assert response.status_code == 200
        html = response.text
        assert "View Details" in html
        assert "/storefront/products/medical-research-raw" in html
        assert "/storefront/products/medical-research-processed" in html

    def test_storefront_root_redirects_to_catalog(self, client: TestClient):
        response = client.get("/storefront", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/storefront/products"


# ---------------------------------------------------------------------------
# Product detail route
# ---------------------------------------------------------------------------


class TestProductDetail:
    """``GET /storefront/products/{product_id}`` — product detail."""

    def test_detail_renders_html_free_product(
        self,
        client: TestClient,
        sample_raw_product_detail: dict[str, Any],
    ):
        with _mock_get_product(sample_raw_product_detail):
            response = client.get("/storefront/products/medical-research-raw")

        assert response.status_code == 200
        html = response.text
        assert "medical-research RAW Feed" in html
        assert "Free" in html
        assert "raw" in html
        # Breadcrumb
        assert "Catalog" in html
        # Subscribe form
        assert "subscribeForm" in html
        assert 'name="product_id"' in html
        assert 'value="medical-research-raw"' in html

    def test_detail_renders_html_premium_product(
        self,
        client: TestClient,
        sample_product_detail: dict[str, Any],
    ):
        with _mock_get_product(sample_product_detail):
            response = client.get(
                "/storefront/products/medical-research-processed"
            )

        assert response.status_code == 200
        html = response.text
        assert "medical-research PROCESSED Output" in html
        assert "29" in html
        assert "premium" in html
        assert "processed" in html
        # Templates listed
        assert "digest" in html
        assert "report" in html

    def test_detail_returns_json(
        self,
        client: TestClient,
        sample_product_detail: dict[str, Any],
    ):
        with _mock_get_product(sample_product_detail):
            response = client.get(
                "/storefront/products/medical-research-processed?format=json"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        inner = data["data"]
        assert inner["product"]["id"] == "medical-research-processed"
        assert inner["product"]["access_level"] == "premium"
        assert inner["access"]["allowed"] is True

    def test_detail_missing_product_returns_404_html(self, client: TestClient):
        with _mock_get_product(None):
            response = client.get("/storefront/products/nonexistent-product")

        assert response.status_code == 404
        assert "not found" in response.text.lower()
        assert "Back to Catalog" in response.text

    def test_detail_missing_product_returns_404_json(self, client: TestClient):
        with _mock_get_product(None):
            response = client.get(
                "/storefront/products/nonexistent-product?format=json"
            )

        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "NotFound"
        assert "not found" in data["error"]["message"].lower()

    def test_detail_with_user_id_grants_access_for_free(
        self,
        client: TestClient,
        sample_raw_product_detail: dict[str, Any],
    ):
        access = {
            "allowed": True,
            "reason": "Free content is available to all users.",
            "access_level": "free",
            "end_user_id": "user-001",
            "upgrade_prompt": None,
            "profile_status": "any",
            "plan": "any",
        }
        with (
            _mock_get_product(sample_raw_product_detail),
            _mock_check_access(access),
        ):
            response = client.get(
                "/storefront/products/medical-research-raw?user_id=user-001"
            )

        assert response.status_code == 200
        html = response.text
        assert "Access granted" in html or "available to all" in html
        # Pre-filled user id
        assert 'value="user-001"' in html

    def test_detail_with_user_id_blocks_access_for_premium(
        self,
        client: TestClient,
        sample_product_detail: dict[str, Any],
    ):
        access = {
            "allowed": False,
            "reason": "Premium content requires an active paid subscription.",
            "access_level": "premium",
            "end_user_id": "user-free",
            "upgrade_prompt": "Upgrade to Premium to access this product.",
            "profile_status": "trial",
            "plan": "free",
        }
        with (
            _mock_get_product(sample_product_detail),
            _mock_check_access(access),
        ):
            response = client.get(
                "/storefront/products/medical-research-processed?user_id=user-free"
            )

        assert response.status_code == 200
        html = response.text
        assert "Upgrade required" in html or "requires an active" in html
        assert "Upgrade to Premium" in html

    def test_detail_has_bootstrap_cdn(
        self,
        client: TestClient,
        sample_product_detail: dict[str, Any],
    ):
        with _mock_get_product(sample_product_detail):
            response = client.get(
                "/storefront/products/medical-research-processed"
            )

        assert response.status_code == 200
        html = response.text
        assert "bootstrap@5.3.3" in html
        assert "bootstrap-icons@1.11.3" in html
        assert "bootstrap.bundle.min.js" in html


# ---------------------------------------------------------------------------
# Subscription creation route
# ---------------------------------------------------------------------------


class TestCreateSubscription:
    """``POST /storefront/subscriptions`` — subscription creation."""

    def test_create_subscription_success(
        self,
        client: TestClient,
        sample_product_detail: dict[str, Any],
    ):
        sub = Subscription(
            subscription_id="sub_" + str(uuid4())[:12],
            user_id="user-001",
            plan="medical-research-processed",
            status="active",
            tier="premium",
            auto_renew=True,
        )
        with (
            _mock_get_product(sample_product_detail),
            _mock_create_subscription(sub),
        ):
            response = client.post(
                "/storefront/subscriptions",
                json={
                    "user_id": "user-001",
                    "product_id": "medical-research-processed",
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        inner = data["data"]
        assert inner["subscription_id"] == sub.subscription_id
        assert inner["user_id"] == "user-001"
        assert inner["product_id"] == "medical-research-processed"
        assert inner["status"] == "active"
        assert inner["tier"] == "premium"

    def test_create_subscription_raw_product_sets_raw_access(
        self,
        client: TestClient,
        sample_raw_product_detail: dict[str, Any],
    ):
        sub = Subscription(
            subscription_id="sub_" + str(uuid4())[:12],
            user_id="user-002",
            plan="medical-research-raw",
            status="active",
            tier="free",
            auto_renew=True,
        )
        with (
            _mock_get_product(sample_raw_product_detail),
            _mock_create_subscription(sub),
        ):
            response = client.post(
                "/storefront/subscriptions",
                json={
                    "user_id": "user-002",
                    "product_id": "medical-research-raw",
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["data"]["tier"] == "free"

    def test_create_subscription_missing_product_returns_404(
        self, client: TestClient
    ):
        with _mock_get_product(None):
            response = client.post(
                "/storefront/subscriptions",
                json={
                    "user_id": "user-001",
                    "product_id": "nonexistent-product",
                },
            )

        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "NotFound"
        assert "not found" in data["error"]["message"].lower()

    def test_create_subscription_missing_user_id_returns_422(
        self, client: TestClient, sample_product_detail: dict[str, Any]
    ):
        with _mock_get_product(sample_product_detail):
            response = client.post(
                "/storefront/subscriptions",
                json={"product_id": "medical-research-processed"},
            )

        assert response.status_code == 422

    def test_create_subscription_missing_product_id_returns_422(
        self, client: TestClient
    ):
        response = client.post(
            "/storefront/subscriptions",
            json={"user_id": "user-001"},
        )
        assert response.status_code == 422

    def test_create_subscription_empty_user_id_returns_422(
        self, client: TestClient, sample_product_detail: dict[str, Any]
    ):
        with _mock_get_product(sample_product_detail):
            response = client.post(
                "/storefront/subscriptions",
                json={"user_id": "", "product_id": "medical-research-processed"},
            )

        assert response.status_code == 422

    def test_create_subscription_with_explicit_tier(
        self,
        client: TestClient,
        sample_product_detail: dict[str, Any],
    ):
        sub = Subscription(
            subscription_id="sub_" + str(uuid4())[:12],
            user_id="user-001",
            plan="medical-research-processed",
            status="active",
            tier="enterprise",
            auto_renew=False,
        )
        with (
            _mock_get_product(sample_product_detail),
            _mock_create_subscription(sub),
        ):
            response = client.post(
                "/storefront/subscriptions",
                json={
                    "user_id": "user-001",
                    "product_id": "medical-research-processed",
                    "tier": "enterprise",
                    "auto_renew": False,
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["data"]["tier"] == "enterprise"
        assert data["data"]["auto_renew"] is False


# ---------------------------------------------------------------------------
# Cross-cutting: base template consistency
# ---------------------------------------------------------------------------


class TestStorefrontBaseTemplate:
    """Verify the base template is consistent across all pages."""

    @pytest.mark.parametrize(
        "path",
        [
            "/storefront/products",
            "/storefront/products/medical-research-processed",
        ],
    )
    def test_all_pages_have_bootstrap_cdn(
        self,
        client: TestClient,
        sample_products: list[dict[str, Any]],
        sample_product_detail: dict[str, Any],
        path: str,
    ):
        with (
            _mock_list_all_products(sample_products),
            _mock_get_product(sample_product_detail),
        ):
            response = client.get(path)

        assert response.status_code == 200
        html = response.text
        assert "bootstrap@5.3.3" in html
        assert "bootstrap-icons@1.11.3" in html
        assert "bootstrap.bundle.min.js" in html

    @pytest.mark.parametrize(
        "path",
        [
            "/storefront/products",
            "/storefront/products/medical-research-processed",
        ],
    )
    def test_all_pages_have_dark_mode_toggle(
        self,
        client: TestClient,
        sample_products: list[dict[str, Any]],
        sample_product_detail: dict[str, Any],
        path: str,
    ):
        with (
            _mock_list_all_products(sample_products),
            _mock_get_product(sample_product_detail),
        ):
            response = client.get(path)

        assert response.status_code == 200
        html = response.text
        assert 'data-bs-theme="auto"' in html
        assert "themeToggle" in html
        assert "autoinfo-theme" in html

    @pytest.mark.parametrize(
        "path",
        [
            "/storefront/products",
            "/storefront/products/medical-research-processed",
        ],
    )
    def test_all_pages_have_nav_link_to_catalog(
        self,
        client: TestClient,
        sample_products: list[dict[str, Any]],
        sample_product_detail: dict[str, Any],
        path: str,
    ):
        with (
            _mock_list_all_products(sample_products),
            _mock_get_product(sample_product_detail),
        ):
            response = client.get(path)

        assert response.status_code == 200
        html = response.text
        assert "AutoInfo Storefront" in html
        assert "/storefront/products" in html