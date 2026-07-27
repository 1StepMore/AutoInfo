"""Tests for Stripe integration (billing module).

All stripe library calls are mocked via ``unittest.mock.patch`` — no
network calls, no stripe-mock, no Docker required.

Test coverage:
- Webhook event signature verification (valid + invalid)
- ``handle_webhook()`` event dispatch for each supported event type
- ``get_user_stripe_id()`` / ``set_user_stripe_id()`` with persisted store
- ``_sync_user_stripe_id()`` success + failure paths
- ``create_checkout_session()`` with existing and new customers
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from autoinfo.api.server import app
from autoinfo.billing import (
    _user_stripe_map,
    create_checkout_session,
    get_user_stripe_id,
    handle_webhook,
    set_user_stripe_id,
)

# Module reference for checking mutable global state
import autoinfo.billing as _billing_mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(event_type: str, **kwargs: object) -> dict:
    """Build a minimal Stripe webhook event dict.

    Extra keyword arguments are merged into ``data.object`` for
    convenience (e.g. ``customer="cus_xxx"``).
    """
    event: dict = {
        "id": "evt_test",
        "type": event_type,
        "data": {
            "object": {
                "id": "sub_test456",
                "customer": "cus_test123",
            }
        },
    }
    event["data"]["object"].update(kwargs)
    return event


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_global_state() -> None:
    """Clear billing global state between each test.

    This includes the in-memory ``_user_stripe_map`` and the
    ``_stripe_sync_failures`` counter so tests do not leak state.
    """
    _user_stripe_map.clear()
    _billing_mod._stripe_sync_failures = 0
    yield


@pytest.fixture
def checkout_completed_event() -> dict:
    """A realistic ``checkout.session.completed`` Stripe event."""
    return {
        "id": "evt_cs_123",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_session",
                "customer": "cus_test123",
                "subscription": "sub_test456",
                "metadata": {"end_user_id": "user_abc"},
                "mode": "subscription",
                "status": "complete",
            }
        },
    }


@pytest.fixture
def sub_updated_event() -> dict:
    """A realistic ``customer.subscription.updated`` event."""
    return {
        "id": "evt_sub_upd",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_test456",
                "customer": "cus_test123",
                "status": "past_due",
            }
        },
    }


@pytest.fixture
def sub_deleted_event() -> dict:
    """A realistic ``customer.subscription.deleted`` event."""
    return {
        "id": "evt_sub_del",
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_test456",
                "customer": "cus_test123",
            }
        },
    }


# ===================================================================
# 1. Webhook event signature verification (FastAPI endpoint)
# ===================================================================


class TestWebhookSignatureVerification:
    """Test the ``/api/v1/webhook/stripe`` endpoint signature verification.

    The endpoint verifies the ``Stripe-Signature`` header via
    ``stripe.Webhook.construct_event`` when ``STRIPE_WEBHOOK_SECRET``
    is set, otherwise falls back to raw JSON parsing (dev mode).
    """

    # ------------------------------------------------------------------
    # Valid signature
    # ------------------------------------------------------------------

    @patch("autoinfo.api.server.os.environ.get")
    def test_valid_signature_returns_200(self, mock_env_get: MagicMock) -> None:
        """Valid signature -> 200 with processed webhook result."""
        mock_env_get.return_value = "whsec_test_secret"
        payload = json.dumps({
            "type": "checkout.session.completed",
            "data": {"object": {"metadata": {}}},
        })

        client = TestClient(app)
        with patch("stripe.Webhook.construct_event") as mock_construct:
            mock_construct.return_value = {
                "type": "checkout.session.completed",
                "data": {"object": {"metadata": {}}},
            }
            resp = client.post(
                "/api/v1/webhook/stripe",
                content=payload,
                headers={"Stripe-Signature": "t=123,v1=valid_sig"},
            )

        assert resp.status_code == 200
        mock_construct.assert_called_once_with(
            payload.encode(), "t=123,v1=valid_sig", "whsec_test_secret",
        )

    # ------------------------------------------------------------------
    # Invalid signature
    # ------------------------------------------------------------------

    @patch("autoinfo.api.server.os.environ.get")
    def test_invalid_signature_returns_400(self, mock_env_get: MagicMock) -> None:
        """Invalid Stripe-Signature -> 400 with ``invalid_signature`` error."""
        mock_env_get.return_value = "whsec_test_secret"
        payload = json.dumps({"type": "checkout.session.completed"})

        import stripe as _stripe

        client = TestClient(app)
        with patch("stripe.Webhook.construct_event") as mock_construct:
            mock_construct.side_effect = _stripe.error.SignatureVerificationError(
                "Signature does not match", "t=123,v1=bad",
            )
            resp = client.post(
                "/api/v1/webhook/stripe",
                content=payload,
                headers={"Stripe-Signature": "t=123,v1=bad"},
            )

        assert resp.status_code == 400
        data = resp.json()
        assert data["error"] == "invalid_signature"
        assert "Signature does not match" in data["detail"]

    # ------------------------------------------------------------------
    # Dev mode (no secret configured)
    # ------------------------------------------------------------------

    @patch("autoinfo.api.server.os.environ.get")
    def test_dev_mode_no_secret_skips_verification(
        self, mock_env_get: MagicMock,
    ) -> None:
        """No ``STRIPE_WEBHOOK_SECRET`` -> raw JSON parsed directly (dev mode).

        The endpoint should still return 200 because ``handle_webhook``
        handles the missing ``end_user_id`` gracefully.
        """
        mock_env_get.return_value = ""  # no secret
        payload = json.dumps({
            "type": "checkout.session.completed",
            "data": {"object": {"metadata": {}}},
        })

        client = TestClient(app)
        resp = client.post(
            "/api/v1/webhook/stripe",
            content=payload,
            headers={"Stripe-Signature": "t=123,v1=whatever"},
        )

        # Endpoint returns 200; webhook reports missing end_user_id
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"
        assert resp.json()["action"] == "missing_end_user_id"

    # ------------------------------------------------------------------
    # Invalid JSON payload (dev mode only)
    # ------------------------------------------------------------------

    @patch("autoinfo.api.server.os.environ.get")
    def test_invalid_json_payload_returns_400(
        self, mock_env_get: MagicMock,
    ) -> None:
        """Invalid JSON body in dev mode -> 400."""
        mock_env_get.return_value = ""  # dev mode
        client = TestClient(app)
        resp = client.post(
            "/api/v1/webhook/stripe",
            content=b"not valid json {{{",
            headers={"Stripe-Signature": "t=123,v1=whatever"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_payload"


# ===================================================================
# 2. handle_webhook() event dispatch
# ===================================================================


class TestHandleWebhookDispatch:
    """Test ``handle_webhook()`` routes each event type to the correct handler."""

    # ------------------------------------------------------------------
    # checkout.session.completed
    # ------------------------------------------------------------------

    def test_checkout_completed_activates_subscription(
        self, checkout_completed_event: dict,
    ) -> None:
        """``checkout.session.completed`` -> subscription activated and customer stored."""
        _user_stripe_map["user_abc"] = "cus_test123"

        with (
            patch("autoinfo.user_store.update_profile") as mock_update,
            patch("autoinfo.user_store.get_stripe_customer_id") as mock_get,
        ):
            mock_get.return_value = "cus_test123"
            result = handle_webhook(checkout_completed_event)

        assert result["status"] == "processed"
        assert result["action"] == "activated_subscription"
        assert result["end_user_id"] == "user_abc"
        assert result["subscription_id"] == "sub_test456"

        # ``update_profile`` is called:
        # 1. from ``set_stripe_customer_id`` inside ``_sync_user_stripe_id``,
        # 2. then from ``_handle_checkout_completed`` itself.
        mock_update.assert_any_call(
            user_id="user_abc",
            stripe_customer_id="cus_test123",
        )
        mock_update.assert_any_call(
            user_id="user_abc",
            stripe_subscription_id="sub_test456",
            status="active",
        )
        assert mock_update.call_count == 2

    def test_checkout_completed_missing_end_user_id(
        self, checkout_completed_event: dict,
    ) -> None:
        """Missing ``end_user_id`` metadata -> error response."""
        checkout_completed_event["data"]["object"]["metadata"] = {}
        result = handle_webhook(checkout_completed_event)
        assert result["status"] == "error"
        assert result["action"] == "missing_end_user_id"

    # ------------------------------------------------------------------
    # customer.subscription.updated
    # ------------------------------------------------------------------

    def test_subscription_updated_maps_status(
        self, sub_updated_event: dict,
    ) -> None:
        """``customer.subscription.updated`` -> status mapped (past_due -> suspended)."""
        _user_stripe_map["user_abc"] = "cus_test123"

        with patch("autoinfo.user_store.update_profile") as mock_update:
            result = handle_webhook(sub_updated_event)

        assert result["status"] == "processed"
        assert result["action"] == "updated_status"
        assert result["new_status"] == "suspended"  # past_due -> suspended
        mock_update.assert_called_once_with(
            user_id="user_abc",
            status="suspended",
        )

    def test_subscription_updated_no_end_user_match(
        self, sub_updated_event: dict,
    ) -> None:
        """Unknown customer (no end_user_id match) -> ignored."""
        _user_stripe_map.clear()
        result = handle_webhook(sub_updated_event)
        assert result["status"] == "ignored"
        assert result["action"] == "no_end_user_match"

    # ------------------------------------------------------------------
    # customer.subscription.deleted
    # ------------------------------------------------------------------

    def test_subscription_deleted_cancels(
        self, sub_deleted_event: dict,
    ) -> None:
        """``customer.subscription.deleted`` -> subscription cancelled."""
        _user_stripe_map["user_abc"] = "cus_test123"

        with patch("autoinfo.user_store.update_profile") as mock_update:
            result = handle_webhook(sub_deleted_event)

        assert result["status"] == "processed"
        assert result["action"] == "cancelled_subscription"
        mock_update.assert_called_once_with(
            user_id="user_abc",
            status="cancelled",
        )

    def test_subscription_deleted_no_end_user_match(
        self, sub_deleted_event: dict,
    ) -> None:
        """Unknown customer in delete event -> ignored."""
        _user_stripe_map.clear()
        result = handle_webhook(sub_deleted_event)
        assert result["status"] == "ignored"
        assert result["action"] == "no_end_user_match"

    # ------------------------------------------------------------------
    # Unknown event type
    # ------------------------------------------------------------------

    def test_unknown_event_type_is_ignored(self) -> None:
        """Event type with no registered handler -> ignored."""
        event = _make_event("charge.succeeded")
        result = handle_webhook(event)
        assert result["status"] == "ignored"
        assert result["action"] == "no_handler"


# ===================================================================
# 3. get_user_stripe_id() / set_user_stripe_id()
# ===================================================================


class TestStripeIdMapping:
    """Test the Stripe customer ID <-> end_user_id mapping layer.

    The mapping uses an in-memory dict (``_user_stripe_map``) as cache
    with the DB as authoritative backing store.  Mutations always update
    the cache and best-effort persist to the DB.
    """

    # ------------------------------------------------------------------
    # get_user_stripe_id
    # ------------------------------------------------------------------

    def test_get_returns_cached_value(self) -> None:
        """Value in cache -> returned immediately, no DB call."""
        _user_stripe_map["user_abc"] = "cus_cached"
        assert get_user_stripe_id("user_abc") == "cus_cached"

    def test_get_falls_back_to_db_on_cache_miss(self) -> None:
        """Cache miss -> DB lookup, result cached for next call."""
        with patch("autoinfo.user_store.get_stripe_customer_id") as mock_get:
            mock_get.return_value = "cus_from_db"
            result = get_user_stripe_id("user_xyz")

        assert result == "cus_from_db"
        assert _user_stripe_map["user_xyz"] == "cus_from_db"

    def test_get_returns_none_when_not_found(self) -> None:
        """Neither cache nor DB -> None."""
        with patch("autoinfo.user_store.get_stripe_customer_id") as mock_get:
            mock_get.return_value = None
            result = get_user_stripe_id("user_none")
        assert result is None

    # ------------------------------------------------------------------
    # set_user_stripe_id
    # ------------------------------------------------------------------

    def test_set_updates_cache_and_persists(self) -> None:
        """Cache updated, DB write attempted."""
        with patch("autoinfo.user_store.set_stripe_customer_id") as mock_set:
            set_user_stripe_id("user_abc", "cus_new")

        assert _user_stripe_map["user_abc"] == "cus_new"
        mock_set.assert_called_once_with("user_abc", "cus_new")

    def test_set_cache_only_on_value_error(self) -> None:
        """ValueError (no profile) -> cache updated, counter unchanged."""
        with patch(
            "autoinfo.user_store.set_stripe_customer_id",
            side_effect=ValueError("user not found"),
        ):
            set_user_stripe_id("user_new", "cus_new")

        assert _user_stripe_map["user_new"] == "cus_new"
        # ValueError does NOT increment the failure counter
        assert _billing_mod._stripe_sync_failures == 0

    def test_set_increments_failure_on_connection_error(self) -> None:
        """ConnectionError -> cache updated, failure counter incremented."""
        with patch(
            "autoinfo.user_store.set_stripe_customer_id",
            side_effect=ConnectionError("DB connection refused"),
        ):
            set_user_stripe_id("user_fail", "cus_fail")

        assert _user_stripe_map["user_fail"] == "cus_fail"
        assert _billing_mod._stripe_sync_failures == 1

    def test_set_increments_failure_on_stripe_error(self) -> None:
        """StripeError -> cache updated, failure counter incremented."""
        import stripe as _stripe

        with patch(
            "autoinfo.user_store.set_stripe_customer_id",
            side_effect=_stripe.error.StripeError("Stripe API error"),
        ):
            set_user_stripe_id("user_fail2", "cus_fail2")

        assert _user_stripe_map["user_fail2"] == "cus_fail2"
        assert _billing_mod._stripe_sync_failures == 1

    def test_set_increments_failure_on_generic_exception(self) -> None:
        """Any other Exception -> cache updated, failure counter incremented."""
        with patch(
            "autoinfo.user_store.set_stripe_customer_id",
            side_effect=RuntimeError("unexpected"),
        ):
            set_user_stripe_id("user_gen", "cus_gen")

        assert _user_stripe_map["user_gen"] == "cus_gen"
        assert _billing_mod._stripe_sync_failures == 1


# ===================================================================
# 4. _sync_user_stripe_id() -- success + failure paths
# ===================================================================


class TestSyncUserStripeId:
    """Test ``_sync_user_stripe_id()`` which persists the stripe customer ID
    and verifies the result."""

    def test_sync_success(self) -> None:
        """Persist and verify succeed -> returns True."""
        from autoinfo.billing import _sync_user_stripe_id

        with (
            patch("autoinfo.user_store.set_stripe_customer_id"),
            patch("autoinfo.user_store.get_stripe_customer_id") as mock_get,
        ):
            mock_get.return_value = "cus_expected"
            result = _sync_user_stripe_id("user_abc", "cus_expected")

        assert result is True
        assert _user_stripe_map["user_abc"] == "cus_expected"

    def test_sync_failure_mismatch(self) -> None:
        """Persisted value differs from expected -> returns False, counter incremented."""
        from autoinfo.billing import _sync_user_stripe_id

        with (
            patch("autoinfo.user_store.set_stripe_customer_id"),
            patch("autoinfo.user_store.get_stripe_customer_id") as mock_get,
        ):
            mock_get.return_value = "cus_different"
            result = _sync_user_stripe_id("user_abc", "cus_expected")

        assert result is False
        assert _billing_mod._stripe_sync_failures == 1

    def test_sync_failure_connection_error(self) -> None:
        """ConnectionError during verify -> returns False, counter incremented."""
        from autoinfo.billing import _sync_user_stripe_id

        with (
            patch("autoinfo.user_store.set_stripe_customer_id"),
            patch(
                "autoinfo.user_store.get_stripe_customer_id",
                side_effect=ConnectionError("DB is down"),
            ),
        ):
            result = _sync_user_stripe_id("user_abc", "cus_expected")

        assert result is False
        assert _billing_mod._stripe_sync_failures == 1

    def test_sync_failure_value_error(self) -> None:
        """ValueError during verify -> returns False, counter incremented."""
        from autoinfo.billing import _sync_user_stripe_id

        with (
            patch("autoinfo.user_store.set_stripe_customer_id"),
            patch(
                "autoinfo.user_store.get_stripe_customer_id",
                side_effect=ValueError("bad value"),
            ),
        ):
            result = _sync_user_stripe_id("user_abc", "cus_expected")

        assert result is False
        assert _billing_mod._stripe_sync_failures == 1


# ===================================================================
# 5. create_checkout_session()
# ===================================================================


class TestCreateCheckoutSession:
    """Test ``create_checkout_session()`` -- the checkout session creation flow."""

    def test_create_with_existing_customer(self) -> None:
        """Existing customer ID in cache -> reused, no ``Customer.create`` call."""
        _user_stripe_map["user_existing"] = "cus_existing"

        with (
            patch("stripe.checkout.Session.create") as mock_session,
            patch("stripe.Customer.create") as mock_customer,
        ):
            mock_session.return_value = {
                "id": "cs_test_123",
                "url": "https://checkout.stripe.com/cs_test_123",
            }
            result = create_checkout_session("price_monthly", "user_existing")

        assert result["session_id"] == "cs_test_123"
        assert result["customer_id"] == "cus_existing"
        assert result["end_user_id"] == "user_existing"
        assert result["mode"] == "subscription"
        # Customer.create should NOT be called since the ID was cached
        mock_customer.assert_not_called()
        mock_session.assert_called_once()

    def test_create_new_customer_and_session(self) -> None:
        """No cached customer -> creates Stripe customer + checkout session."""
        with (
            patch("stripe.Customer.create") as mock_customer,
            patch("stripe.checkout.Session.create") as mock_session,
        ):
            mock_customer.return_value = {"id": "cus_brand_new"}
            mock_session.return_value = {
                "id": "cs_new",
                "url": "https://checkout.stripe.com/cs_new",
            }
            result = create_checkout_session("price_enterprise", "user_newbie")

        assert result["session_id"] == "cs_new"
        assert result["customer_id"] == "cus_brand_new"
        assert result["end_user_id"] == "user_newbie"
        mock_customer.assert_called_once()
        mock_session.assert_called_once()

    def test_create_failure_returns_error_dict(self) -> None:
        """Exception during creation -> error dict returned (never raises)."""
        with patch("stripe.Customer.create") as mock_customer:
            mock_customer.side_effect = ValueError("Stripe API down")
            result = create_checkout_session("price_fail", "user_fail")

        assert "error" in result
        assert result["end_user_id"] == "user_fail"
