"""Tests for B-005 remediation: B3 requirement awareness for missing credentials.

Covers the two escalation surfaces added for missing platform/source
credentials (user-lifecycle-definition.md §4.1: "source API key expired"
is a B3 intervention case):

1. The ``source_credential_missing`` alert rule kind: registered (with
   kind persisted), triggered when a configured source requires a key that
   is absent from the operator environment, and dispatched through the
   existing delivery channel abstraction.
2. The ``source_requires_key`` agent callback event: registered,
   enqueued, and delivered through the durable outbox with the canonical
   envelope; the payload carries the source name and the env var NAME
   (key_ref) only — never the key value.

Backward compatibility: legacy rules (no kind in YAML) load as
``kind="content"``, and the existing content-matching flow is untouched.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import pytest
import yaml

from autoinfo.alerts import (
    add_alert_rule,
    check_source_alerts,
    check_source_credentials,
    load_alerts,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_config(
    tmp_path: Path,
    *,
    sources_yaml: str = "",
    webhook_urls: list[str] | None = None,
) -> Path:
    """Write a minimal config.yaml into tmp_path/.autoinfo and return its path."""
    config_dir = tmp_path / ".autoinfo"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    urls_yaml = (
        f"    webhook_urls: {json.dumps(webhook_urls)}" if webhook_urls else ""
    )
    config_path.write_text(
        "project:\n  name: Test\n"
        "llm:\n  provider: openai\n  model: gpt-4\n  api_key: key\n"
        "domains:\n"
        "  - name: medical-research\n"
        "    active: true\n"
        f"{urls_yaml}\n"
        "    sources:\n"
        f"{sources_yaml}"
    )
    return config_path


_NYT_SOURCE_YAML = (
    "      - name: NYT\n"
    "        type: nyt\n"
    "        url: https://api.nytimes.com/svc\n"
)


def _patch_alerts_path(tmp_path: Path):
    """Patch the alerts YAML path resolver to tmp_path (test isolation)."""
    alerts_path = tmp_path / ".autoinfo" / "alerts.yaml"
    alerts_path.parent.mkdir(parents=True, exist_ok=True)
    return patch("autoinfo.alerts._alerts_path", return_value=alerts_path)


# ===================================================================
# 1. Alert rule kind: registration and persistence
# ===================================================================


class TestSourceCredentialRuleRegistration:
    """The source_credential_missing kind registers and persists."""

    def test_add_rule_with_kind_persists(self, tmp_path: Path) -> None:
        """add_alert_rule(kind=...) round-trips through YAML."""
        with _patch_alerts_path(tmp_path):
            rule = add_alert_rule(
                domain="medical-research",
                kind="source_credential_missing",
                channel="webhook",
            )
            assert rule.kind == "source_credential_missing"

            reloaded = load_alerts()[rule.id]
            assert reloaded.kind == "source_credential_missing"

            with open(tmp_path / ".autoinfo" / "alerts.yaml", "r") as fh:
                raw = yaml.safe_load(fh)
            assert raw["alerts"][rule.id]["kind"] == "source_credential_missing"

    def test_default_kind_is_content(self, tmp_path: Path) -> None:
        """Existing callers without kind keep the legacy behavior."""
        with _patch_alerts_path(tmp_path):
            rule = add_alert_rule(domain="medical-research", topic_keywords=["IVF"])
            assert rule.kind == "content"

    def test_legacy_yaml_without_kind_loads_as_content(self, tmp_path: Path) -> None:
        """Rules persisted before this change (no kind key) load as content."""
        alerts_path = tmp_path / ".autoinfo" / "alerts.yaml"
        alerts_path.parent.mkdir(parents=True, exist_ok=True)
        alerts_path.write_text(
            "alerts:\n"
            "  alert-legacy:\n"
            "    domain: medical-research\n"
            "    topic_keywords: [IVF]\n"
            "    relevance_threshold: 50.0\n"
            "    channel: email\n"
            "    enabled: true\n"
        )
        with patch("autoinfo.alerts._alerts_path", return_value=alerts_path):
            rule = load_alerts()["alert-legacy"]
            assert rule.kind == "content"

    def test_invalid_kind_rejected(self, tmp_path: Path) -> None:
        """Unknown kinds raise ValueError."""
        with _patch_alerts_path(tmp_path):
            with pytest.raises(ValueError):
                add_alert_rule(domain="medical-research", kind="not-a-kind")


# ===================================================================
# 2. Detection: check_source_credentials
# ===================================================================


class TestCheckSourceCredentials:
    """Triggers when a source requires a key that is not configured."""

    def test_missing_env_key_reported(self, tmp_path: Path, monkeypatch) -> None:
        """NYT source with AUTOINFO_NYT_API_KEY unset is reported missing."""
        monkeypatch.delenv("AUTOINFO_NYT_API_KEY", raising=False)
        config_path = _write_config(tmp_path, sources_yaml=_NYT_SOURCE_YAML)
        with patch("autoinfo.alerts.get_config_path", return_value=config_path):
            missing = check_source_credentials("medical-research")

        assert len(missing) == 1
        assert missing[0]["source"] == "NYT"
        assert missing[0]["source_type"] == "nyt"
        assert missing[0]["key_ref"] == "AUTOINFO_NYT_API_KEY"
        assert "key" not in missing[0]  # never a value field

    def test_env_key_set_not_reported(self, tmp_path: Path, monkeypatch) -> None:
        """The same source is NOT reported when the env var holds a value."""
        monkeypatch.setenv("AUTOINFO_NYT_API_KEY", "sk-test-12345")
        config_path = _write_config(tmp_path, sources_yaml=_NYT_SOURCE_YAML)
        try:
            with patch("autoinfo.alerts.get_config_path", return_value=config_path):
                missing = check_source_credentials("medical-research")
        finally:
            monkeypatch.delenv("AUTOINFO_NYT_API_KEY", raising=False)
        assert missing == []

    def test_env_ref_setting_unset_reported(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """A ${ENV_VAR} api_key setting with the var unset is reported."""
        monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
        config_path = _write_config(
            tmp_path,
            sources_yaml=(
                "      - name: Finnhub\n"
                "        type: api\n"
                "        url: https://finnhub.io/api/v1\n"
                "        settings:\n"
                "          api_key: ${FINNHUB_API_KEY}\n"
            ),
        )
        with patch("autoinfo.alerts.get_config_path", return_value=config_path):
            missing = check_source_credentials("medical-research")

        assert len(missing) == 1
        assert missing[0]["source"] == "Finnhub"
        assert missing[0]["key_ref"] == "FINNHUB_API_KEY"

    def test_env_ref_setting_set_not_reported(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """The env-ref source is not reported when the variable is set."""
        monkeypatch.setenv("FINNHUB_API_KEY", "secret-value")
        config_path = _write_config(
            tmp_path,
            sources_yaml=(
                "      - name: Finnhub\n"
                "        type: api\n"
                "        url: https://finnhub.io/api/v1\n"
                "        settings:\n"
                "          api_key: ${FINNHUB_API_KEY}\n"
            ),
        )
        try:
            with patch("autoinfo.alerts.get_config_path", return_value=config_path):
                missing = check_source_credentials("medical-research")
        finally:
            monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
        assert missing == []

    def test_literal_key_configured_not_reported(self, tmp_path: Path) -> None:
        """A source with a literal key in settings is never reported."""
        config_path = _write_config(
            tmp_path,
            sources_yaml=(
                "      - name: NYT\n"
                "        type: nyt\n"
                "        url: https://api.nytimes.com/svc\n"
                "        settings:\n"
                "          api_key: abc123literal\n"
            ),
        )
        with patch("autoinfo.alerts.get_config_path", return_value=config_path):
            missing = check_source_credentials("medical-research")
        assert missing == []

    def test_no_config_returns_empty(self, tmp_path: Path) -> None:
        """Missing config file yields an empty list (never raises)."""
        with patch("autoinfo.alerts.get_config_path", return_value=None):
            assert check_source_credentials("medical-research") == []

    def test_unknown_domain_returns_empty(self, tmp_path: Path) -> None:
        """A domain not present in config yields an empty list."""
        config_path = _write_config(tmp_path, sources_yaml=_NYT_SOURCE_YAML)
        with patch("autoinfo.alerts.get_config_path", return_value=config_path):
            assert check_source_credentials("no-such-domain") == []

    def test_unpaywall_missing_key_reported(self, tmp_path: Path, monkeypatch) -> None:
        """Unpaywall (requires_key collector, D4 gap) with the email env unset is flagged."""
        monkeypatch.delenv("AUTOINFO_UNPAYWALL_EMAIL", raising=False)
        config_path = _write_config(
            tmp_path,
            sources_yaml=(
                "      - name: Unpaywall\n"
                "        type: unpaywall\n"
                "        url: https://api.unpaywall.org/v2\n"
            ),
        )
        with patch("autoinfo.alerts.get_config_path", return_value=config_path):
            missing = check_source_credentials("medical-research")

        assert len(missing) == 1
        assert missing[0]["source"] == "Unpaywall"
        assert missing[0]["source_type"] == "unpaywall"
        assert missing[0]["key_ref"] == "AUTOINFO_UNPAYWALL_EMAIL"

    def test_unpaywall_key_set_not_reported(self, tmp_path: Path, monkeypatch) -> None:
        """Unpaywall is NOT reported when AUTOINFO_UNPAYWALL_EMAIL holds a value."""
        monkeypatch.setenv("AUTOINFO_UNPAYWALL_EMAIL", "researcher@example.com")
        config_path = _write_config(
            tmp_path,
            sources_yaml=(
                "      - name: Unpaywall\n"
                "        type: unpaywall\n"
                "        url: https://api.unpaywall.org/v2\n"
            ),
        )
        try:
            with patch("autoinfo.alerts.get_config_path", return_value=config_path):
                missing = check_source_credentials("medical-research")
        finally:
            monkeypatch.delenv("AUTOINFO_UNPAYWALL_EMAIL", raising=False)
        assert missing == []

    def test_requires_key_flag_generic_api_reported(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """A generic api source with requires_key: true and no canonical env var is flagged."""
        monkeypatch.delenv("ALPHA_VANTAGE_API_KEY", raising=False)
        config_path = _write_config(
            tmp_path,
            sources_yaml=(
                "      - name: Alpha Vantage\n"
                "        type: api\n"
                "        url: https://www.alphavantage.co/query\n"
                "        requires_key: true\n"
            ),
        )
        with patch("autoinfo.alerts.get_config_path", return_value=config_path):
            missing = check_source_credentials("medical-research")

        assert len(missing) == 1
        assert missing[0]["source"] == "Alpha Vantage"
        assert missing[0]["source_type"] == "api"

    def test_requires_key_flag_with_env_ref_reported(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """requires_key: true falls back to any unset ${ENV_VAR} ref in settings."""
        monkeypatch.delenv("WANFANG_APP_KEY", raising=False)
        config_path = _write_config(
            tmp_path,
            sources_yaml=(
                "      - name: wanfang\n"
                "        type: api\n"
                "        url: https://api.wanfangdata.com.cn/openwanfang/getQuery\n"
                "        requires_key: true\n"
                "        settings:\n"
                "          headers:\n"
                "            X-Ca-AppKey: ${WANFANG_APP_KEY}\n"
            ),
        )
        with patch("autoinfo.alerts.get_config_path", return_value=config_path):
            missing = check_source_credentials("medical-research")

        assert len(missing) == 1
        assert missing[0]["key_ref"] == "WANFANG_APP_KEY"

    def test_requires_key_flag_with_literal_credential_not_reported(
        self, tmp_path: Path
    ) -> None:
        """requires_key: true with a literal credential in settings is never flagged."""
        config_path = _write_config(
            tmp_path,
            sources_yaml=(
                "      - name: Alpha Vantage\n"
                "        type: api\n"
                "        url: https://www.alphavantage.co/query\n"
                "        requires_key: true\n"
                "        settings:\n"
                "          api_key: abc123literal\n"
            ),
        )
        with patch("autoinfo.alerts.get_config_path", return_value=config_path):
            missing = check_source_credentials("medical-research")
        assert missing == []


# ===================================================================
# 3. Map consolidation: alerts + mcp.server share ONE source of truth
# ===================================================================


class TestSourceKeyMapConsolidation:
    """The D4 key map lives in config.py and both consumers use the same object."""

    def test_both_consumers_import_the_same_map(self) -> None:
        """alerts and mcp.server must reference the identical constant (no drift)."""
        from autoinfo import alerts
        from autoinfo.config import SOURCE_KEY_ENV_VARS
        from autoinfo.mcp import server as mcp_server

        assert alerts.SOURCE_KEY_ENV_VARS is SOURCE_KEY_ENV_VARS
        assert mcp_server.SOURCE_KEY_ENV_VARS is SOURCE_KEY_ENV_VARS
        assert len(SOURCE_KEY_ENV_VARS) == 11

    def test_map_covers_all_requires_key_collectors(self) -> None:
        """Every collector with requires_key()==True is present (unpaywall closed)."""
        from autoinfo.config import SOURCE_KEY_ENV_VARS

        for stype in ("ap_api", "reuters_mcp", "unpaywall", "youtube"):
            assert stype in SOURCE_KEY_ENV_VARS
        # collect-time guards retained
        for stype in ("email", "email_imap", "nyt", "spotify", "quandl", "kaggle", "core"):
            assert stype in SOURCE_KEY_ENV_VARS

    def test_old_map_names_removed(self) -> None:
        """Neither consumer still defines its own private key map."""
        from autoinfo import alerts
        from autoinfo.mcp import server as mcp_server

        assert not hasattr(alerts, "_SOURCE_KEY_ENV")
        assert not hasattr(mcp_server, "_SOURCE_KEY_REQUIREMENTS")


# ===================================================================
# 4. Dispatch: check_source_alerts through the channel abstraction
# ===================================================================


class TestCheckSourceAlertsDispatch:
    """source_credential_missing rules dispatch via delivery channels."""

    def test_webhook_dispatch_succeeds(self, tmp_path: Path, monkeypatch) -> None:
        """A webhook rule dispatches through the real webhook channel."""
        monkeypatch.delenv("AUTOINFO_NYT_API_KEY", raising=False)
        config_path = _write_config(
            tmp_path,
            sources_yaml=_NYT_SOURCE_YAML,
            webhook_urls=["https://hooks.example.com/alert"],
        )

        with _patch_alerts_path(tmp_path):
            rule = add_alert_rule(
                domain="medical-research",
                kind="source_credential_missing",
                channel="webhook",
            )

            posted: list[tuple[str, dict[str, Any]]] = []

            def _fake_post(
                url: str,
                payload: dict[str, Any],
                retries: int = 3,
                hmac_secret: str | None = None,
            ) -> None:
                posted.append((url, payload))

            from autoinfo.delivery import WebhookDeliveryChannel

            with patch(
                "autoinfo.alerts.get_config_path", return_value=config_path
            ), patch.object(
                WebhookDeliveryChannel, "_post_webhook", staticmethod(_fake_post)
            ):
                results = check_source_alerts("medical-research")

        assert len(results) == 1
        assert results[0]["status"] == "success"
        assert results[0]["channel"] == "webhook"
        assert results[0]["rule_id"] == rule.id

        assert len(posted) == 1
        url, payload = posted[0]
        assert url == "https://hooks.example.com/alert"
        assert payload["kind"] == "source_credential_missing"
        assert payload["source"] == "NYT"
        assert payload["source_type"] == "nyt"
        assert payload["key_ref"] == "AUTOINFO_NYT_API_KEY"
        assert payload["severity"] == "critical"

    def test_content_rules_not_triggered_for_missing_credentials(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Legacy content rules ignore credential state (backward compat)."""
        monkeypatch.delenv("AUTOINFO_NYT_API_KEY", raising=False)
        config_path = _write_config(tmp_path, sources_yaml=_NYT_SOURCE_YAML)

        with _patch_alerts_path(tmp_path):
            _ = add_alert_rule(
                domain="medical-research",
                topic_keywords=["IVF"],
                channel="email",
            )
            with patch("autoinfo.alerts.get_config_path", return_value=config_path):
                results = check_source_alerts("medical-research")
        assert results == []

    def test_wrong_domain_rule_not_triggered(self, tmp_path: Path, monkeypatch) -> None:
        """A rule for another domain does not fire."""
        monkeypatch.delenv("AUTOINFO_NYT_API_KEY", raising=False)
        config_path = _write_config(tmp_path, sources_yaml=_NYT_SOURCE_YAML)

        with _patch_alerts_path(tmp_path):
            _ = add_alert_rule(
                domain="ai-commercial",
                kind="source_credential_missing",
                channel="webhook",
            )
            with patch("autoinfo.alerts.get_config_path", return_value=config_path):
                results = check_source_alerts("medical-research")
        assert results == []

    def test_no_missing_credentials_no_dispatch(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """With the env var set, nothing is dispatched."""
        monkeypatch.setenv("AUTOINFO_NYT_API_KEY", "sk-test-12345")
        config_path = _write_config(
            tmp_path,
            sources_yaml=_NYT_SOURCE_YAML,
            webhook_urls=["https://hooks.example.com/alert"],
        )
        try:
            with _patch_alerts_path(tmp_path):
                _ = add_alert_rule(
                    domain="medical-research",
                    kind="source_credential_missing",
                    channel="webhook",
                )
                with patch(
                    "autoinfo.alerts.get_config_path", return_value=config_path
                ):
                    results = check_source_alerts("medical-research")
        finally:
            monkeypatch.delenv("AUTOINFO_NYT_API_KEY", raising=False)
        assert results == []

    def test_precomputed_missing_list_used(self, tmp_path: Path, monkeypatch) -> None:
        """check_source_alerts accepts a precomputed missing list."""
        config_path = _write_config(
            tmp_path,
            webhook_urls=["https://hooks.example.com/alert"],
        )
        missing = [
            {
                "source": "Reuters",
                "source_type": "reuters_mcp",
                "key_ref": "AUTOINFO_REUTERS_API_KEY",
            }
        ]
        posted: list[tuple[str, dict[str, Any]]] = []

        def _fake_post(
            url: str,
            payload: dict[str, Any],
            retries: int = 3,
            hmac_secret: str | None = None,
        ) -> None:
            posted.append((url, payload))

        from autoinfo.delivery import WebhookDeliveryChannel

        with _patch_alerts_path(tmp_path):
            rule = add_alert_rule(
                domain="medical-research",
                kind="source_credential_missing",
                channel="webhook",
            )
            with patch(
                "autoinfo.alerts.get_config_path", return_value=config_path
            ), patch.object(
                WebhookDeliveryChannel, "_post_webhook", staticmethod(_fake_post)
            ):
                results = check_source_alerts("medical-research", missing=missing)
        assert len(results) == 1
        assert results[0]["status"] == "success"
        assert results[0]["rule_id"] == rule.id
        assert posted[0][1]["source"] == "Reuters"
        assert posted[0][1]["key_ref"] == "AUTOINFO_REUTERS_API_KEY"


# ===================================================================
# 4. Agent callback event: source_requires_key
# ===================================================================


@pytest.fixture
def ac_module(monkeypatch, tmp_path):
    """Hermetic agent_callback module: per-test tmp SQLite DB."""
    import autoinfo.agent_callback as ac

    db_path = tmp_path / "autoinfo.db"
    monkeypatch.setattr(ac, "_default_db_path", lambda: db_path)
    return ac


_REAL_HTTPX_CLIENT = httpx.Client


def _patch_client(monkeypatch, transport: httpx.MockTransport) -> None:
    """Make the drain worker's httpx.Client use *transport*."""

    def _client_factory(*args: Any, **kwargs: Any) -> httpx.Client:
        return _REAL_HTTPX_CLIENT(transport=transport, *args, **kwargs)

    import autoinfo.agent_callback as ac

    monkeypatch.setattr(ac.httpx, "Client", _client_factory)


def _wait_outbox(ac_module, row_id: int, timeout: float = 5.0) -> dict[str, Any]:
    """Wait until the outbox row leaves ``pending``."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for row in ac_module.list_outbox(limit=500):
            if row["id"] == row_id:
                if row["status"] != "pending":
                    return row
        time.sleep(0.02)
    raise AssertionError(f"outbox row {row_id} never left 'pending'")


class TestSourceRequiresKeyCallbackEvent:
    """The source_requires_key event registers and delivers via the outbox."""

    def test_event_registers_and_validates(self, ac_module) -> None:
        """The event name is accepted at registration; unknown ones are not."""
        cid = ac_module.register_agent_callback(
            "https://agent.example.com/hook", ["source_requires_key"]
        )
        listed = ac_module.list_agent_callbacks()
        assert listed[0]["callback_id"] == cid
        assert listed[0]["events"] == ["source_requires_key"]

        with pytest.raises(ValueError):
            ac_module.register_agent_callback(
                "https://agent.example.com/hook", ["source_not_a_real_event"]
            )

    def test_old_events_still_register(self, ac_module) -> None:
        """Legacy events are unchanged (backward compat)."""
        cid = ac_module.register_agent_callback(
            "https://agent.example.com/hook", ["new_digest", "new_report"]
        )
        listed = ac_module.list_agent_callbacks()
        assert listed[0]["callback_id"] == cid
        assert listed[0]["events"] == ["new_digest", "new_report"]

    def test_notify_delivers_canonical_envelope_no_key_value(
        self, ac_module, monkeypatch
    ) -> None:
        """Delivery: canonical 5-key envelope; payload carries key_ref only."""
        captured: dict[str, list[httpx.Request]] = {}
        _patch_client(monkeypatch, _make_capture_transport(captured))

        url = "https://agent.example.com/hook"
        ac_module.register_agent_callback(url, ["source_requires_key"])

        row_id = ac_module.notify_source_requires_key(
            source="NYT",
            source_type="nyt",
            key_ref="AUTOINFO_NYT_API_KEY",
            domain="medical-research",
        )
        assert row_id > 0

        row = _wait_outbox(ac_module, row_id)
        assert row["status"] == "delivered"

        (request,) = captured[url]
        body = json.loads(request.content)
        assert set(body) == {
            "event",
            "payload",
            "schema_version",
            "trace_id",
            "product_id",
        }
        assert body["event"] == "source_requires_key"
        assert body["schema_version"] == 1
        assert body["trace_id"], "trace_id must be generated"

        payload = body["payload"]
        assert payload["source"] == "NYT"
        assert payload["source_type"] == "nyt"
        assert payload["key_ref"] == "AUTOINFO_NYT_API_KEY"
        assert payload["domain"] == "medical-research"
        assert payload["severity"] == "critical"

        raw_body = request.content.decode()
        assert "sk-test" not in raw_body
        assert "secret" not in raw_body

    def test_notify_with_explicit_trace_id(self, ac_module, monkeypatch) -> None:
        """An explicit trace_id is honored end to end."""
        captured: dict[str, list[httpx.Request]] = {}
        _patch_client(monkeypatch, _make_capture_transport(captured))

        url = "https://agent.example.com/hook"
        ac_module.register_agent_callback(url, ["source_requires_key"])

        row_id = ac_module.notify_source_requires_key(
            source="Reuters",
            source_type="reuters_mcp",
            key_ref="AUTOINFO_REUTERS_API_KEY",
            domain="financial-intelligence",
            trace_id="trace-b005-xyz",
        )
        assert row_id > 0
        assert _wait_outbox(ac_module, row_id)["status"] == "delivered"

        (request,) = captured[url]
        body = json.loads(request.content)
        assert body["trace_id"] == "trace-b005-xyz"


def _make_capture_transport(requests_by_url: dict[str, list[httpx.Request]]):
    """MockTransport recording every request, per callback URL."""

    def _handler(request: httpx.Request) -> httpx.Response:
        requests_by_url.setdefault(str(request.url), []).append(request)
        return httpx.Response(200, json={"ok": True})

    return httpx.MockTransport(_handler)
