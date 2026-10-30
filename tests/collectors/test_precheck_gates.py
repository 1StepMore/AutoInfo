"""Pre-request validation gates (#664/#666).

背景（2026-10-30 issue 三连）：「请求前校验缺失」一类 ——
  * #664 ``requires_key`` 死声明：generic ``type: api`` 不校验 key，
    占位符 ``YOUR_TWELVEDATA_KEY`` 被当真实 key 发出去，每晚 401。
  * #666 空 topic：semantic-scholar 在 topic 为空时仍发 ``?query=``，
    必然 400，连续失败 29 次。

修法（与 app-review 闸同构）：
  1. handler 层 ``Collector.precheck(ctx)`` 钩子 —— handler 声明自己的
     参数/凭据要求，返回 None（放行）或 skip 标记 dict；
  2. collect 分发处（``_collect_from_source``）在**发请求前**消费它，
     记 ``status="skipped"`` + 显式标记（``credential_missing`` /
     ``empty_topic``）—— 单列一类，不计 healthy 也不计 failed。

本文件覆盖两端：handler 语义 + 分发处消费。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from autoinfo import collect as collect_mod
from autoinfo.collect import _collect_from_source
from autoinfo.collectors.base import BaseHandler, CollectorContext
from autoinfo.collectors.http_api import HttpApiHandler
from autoinfo.collectors.semantic_scholar import SemanticScholarHandler
from autoinfo.config import SourceConfig
from autoinfo.dedup import DedupChecker
from autoinfo.models import Item

# ---------------------------------------------------------------------------
# 1) Collector ABC 默认 precheck —— 不声明要求就永不拦截
# ---------------------------------------------------------------------------


def test_base_handler_precheck_default_allows() -> None:
    """默认实现返回 None：没有声明的 handler 不被闸门影响。"""

    class _MinimalHandler(BaseHandler):
        def fetch_items(self, ctx: CollectorContext) -> list[Item]:
            return []

    ctx = CollectorContext()
    assert _MinimalHandler().precheck(ctx) is None


# ---------------------------------------------------------------------------
# 2) HttpApiHandler.precheck —— #664 凭据门 + #666 空 topic 门
# ---------------------------------------------------------------------------


def _api_ctx(cfg: SourceConfig, topic: str = "") -> CollectorContext:
    return CollectorContext(
        source_config=cfg,
        topic=topic,
        settings=dict(cfg.settings or {}),
    )


def test_requires_key_without_credential_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    """requires_key: true 且解析不到 key ⇒ credential_missing，不发请求。"""
    monkeypatch.delenv("AUTOINFO_HTTP_API_KEY", raising=False)
    cfg = SourceConfig(name="FRED", type="api", url="https://api.stlouisfed.org", requires_key=True)
    block = HttpApiHandler(cfg).precheck(_api_ctx(cfg))
    assert block is not None
    assert block["credential_missing"] is True
    assert "requires_key" in block["message"]


def test_placeholder_credential_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """字面占位符 key（ Twelve Data 实况：params.apikey=YOUR_* ）不算已配置。"""
    monkeypatch.delenv("AUTOINFO_HTTP_API_KEY", raising=False)
    cfg = SourceConfig(
        name="Twelve Data",
        type="api",
        url="https://api.twelvedata.com/quote",
        requires_key=True,
        settings={"params": {"apikey": "YOUR_TWELVEDATA_KEY"}},
    )
    block = HttpApiHandler(cfg).precheck(_api_ctx(cfg))
    assert block is not None
    assert block["credential_missing"] is True


@pytest.mark.parametrize("placeholder", ["YOUR_KEY", "<your key here>", "xxx", "changeme", "***"])
def test_placeholder_shapes_rejected(monkeypatch: pytest.MonkeyPatch, placeholder: str) -> None:
    monkeypatch.delenv("AUTOINFO_HTTP_API_KEY", raising=False)
    cfg = SourceConfig(
        name="X",
        type="api",
        url="https://x",
        requires_key=True,
        settings={"api_key": placeholder},
    )
    block = HttpApiHandler(cfg).precheck(_api_ctx(cfg))
    assert block is not None and block["credential_missing"] is True


@pytest.mark.parametrize("real", ["sk-live-abc123", "AUTOINFO_TEST_KEY_VALUE"])
def test_real_credential_allows(monkeypatch: pytest.MonkeyPatch, real: str) -> None:
    monkeypatch.delenv("AUTOINFO_HTTP_API_KEY", raising=False)
    cfg = SourceConfig(
        name="X",
        type="api",
        url="https://x",
        requires_key=True,
        settings={"api_key": real},
    )
    assert HttpApiHandler(cfg).precheck(_api_ctx(cfg)) is None


def test_env_key_satisfies_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """AUTOINFO_HTTP_API_KEY 是合法的凭据来源（_get_api_key 的第二落点）。"""
    monkeypatch.setenv("AUTOINFO_HTTP_API_KEY", "env-provided-key")
    cfg = SourceConfig(name="X", type="api", url="https://x", requires_key=True)
    assert HttpApiHandler(cfg).precheck(_api_ctx(cfg)) is None


def test_params_token_counts_as_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Finnhub 式 params.token（env-ref 已解析成真值）＝已配置。"""
    monkeypatch.delenv("AUTOINFO_HTTP_API_KEY", raising=False)
    cfg = SourceConfig(
        name="Finnhub",
        type="api",
        url="https://finnhub.io",
        requires_key=True,
        settings={"params": {"token": "finnhub-real-token"}},
    )
    assert HttpApiHandler(cfg).precheck(_api_ctx(cfg)) is None


def test_keyless_source_never_blocked() -> None:
    """没声明 requires_key 的 api 源（World Bank 式）永不拦截。"""
    cfg = SourceConfig(
        name="World Bank Data",
        type="api",
        url="https://api.worldbank.org",
        settings={"params": {"format": "json", "per_page": 10}},
    )
    assert HttpApiHandler(cfg).precheck(_api_ctx(cfg)) is None


def test_query_driven_empty_topic_blocks() -> None:
    """#666 同类：query_param 源 + 空 topic ⇒ empty_topic（collect 层可记账）。"""
    cfg = SourceConfig(
        name="X",
        type="api",
        url="https://x",
        settings={"query_param": "query"},
    )
    block = HttpApiHandler(cfg).precheck(_api_ctx(cfg, topic="  "))
    assert block is not None
    assert block["empty_topic"] is True


def test_query_driven_with_topic_allows() -> None:
    cfg = SourceConfig(
        name="X",
        type="api",
        url="https://x",
        settings={"query_param": "query"},
    )
    assert HttpApiHandler(cfg).precheck(_api_ctx(cfg, topic="IVF")) is None


def test_feed_style_source_without_query_param_not_blocked() -> None:
    """固定 URL 的 feed 式 api 源（无 query_param）不受空 topic 门约束（#182 口径）。"""
    cfg = SourceConfig(name="Mastodon", type="api", url="https://mstdn/api/v1/timelines/public")
    assert HttpApiHandler(cfg).precheck(_api_ctx(cfg)) is None


# ---------------------------------------------------------------------------
# 3) SemanticScholarHandler —— #666 根因修复
# ---------------------------------------------------------------------------


def test_semantic_scholar_empty_topic_precheck_blocks() -> None:
    cfg = SourceConfig(
        name="semantic-scholar", type="api", url="https://api.semanticscholar.org/graph/v1"
    )
    block = SemanticScholarHandler().precheck(CollectorContext(source_config=cfg, topic=""))
    assert block is not None
    assert block["empty_topic"] is True


def test_semantic_scholar_empty_topic_fetch_items_no_request() -> None:
    """空 topic ⇒ 返回 [] 且**不发网络请求**（守卫在 httpx 之前）。"""
    cfg = SourceConfig(
        name="semantic-scholar", type="api", url="https://api.semanticscholar.org/graph/v1"
    )
    items = SemanticScholarHandler().fetch_items(
        CollectorContext(source_config=cfg, topic="", limit=15)
    )
    assert items == []


def test_semantic_scholar_empty_query_fetch_raises() -> None:
    """直接调 fetch("") 也必须拒绝（SourceFailure），不再拼出 ?query=。"""
    from autoinfo.collectors.base import SourceFailure

    with pytest.raises(SourceFailure, match="empty"):
        SemanticScholarHandler().fetch("", limit=5)


def test_semantic_scholar_with_topic_precheck_allows() -> None:
    cfg = SourceConfig(
        name="semantic-scholar", type="api", url="https://api.semanticscholar.org/graph/v1"
    )
    handler = SemanticScholarHandler()
    assert handler.precheck(CollectorContext(source_config=cfg, topic="CRISPR")) is None


# ---------------------------------------------------------------------------
# 4) collect 分发处消费 precheck —— skipped + 标记，不计 healthy/failed
# ---------------------------------------------------------------------------


class _BlockHandler(BaseHandler):
    """Test double: precheck blocks with a marker; fetch would explode."""

    source_name = "blocked-src"

    def __init__(self, block: dict[str, Any] | None) -> None:
        self._block = block

    def precheck(self, ctx: CollectorContext) -> dict[str, Any] | None:
        return self._block

    def fetch_items(self, ctx: CollectorContext) -> list[Item]:  # pragma: no cover
        raise AssertionError("fetch must not run when precheck blocks")


class _ExplodingPrecheckHandler(BaseHandler):
    """Test double: precheck raises — dispatch must fail OPEN."""

    source_name = "exploding-src"

    def precheck(self, ctx: CollectorContext) -> dict[str, Any] | None:
        raise RuntimeError("broken guard")

    def fetch_items(self, ctx: CollectorContext) -> list[Item]:
        return []  # never reached in the block test; reached in fail-open test


def _run_source(
    cfg: SourceConfig,
    handler: BaseHandler,
    dry_run: bool = False,
    monkeypatch: pytest.MonkeyPatch | None = None,
) -> Any:
    if monkeypatch is not None:
        monkeypatch.setattr(collect_mod, "_build_handler", lambda _cfg: handler)
    return _collect_from_source(
        source_config=cfg,
        domain="test-domain",
        topic="topic",
        limit=5,
        dry_run=dry_run,
        existing_entries=[],
        collection_id="col-precheck-test",
        checker=DedupChecker(),
        new_items_collector=None,
        force_full=True,  # skip dedup — irrelevant here
        keywords=None,
    )


def test_precheck_block_recorded_as_skipped_with_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """precheck 阻断 ⇒ status=skipped + errors 带标记；_runs.json 同步记账。"""
    monkeypatch.setattr(collect_mod, "COLLECTIONS_DIR", str(tmp_path))
    cfg = SourceConfig(name="blocked-src", type="rss", url="https://example.org/feed")
    result = _run_source(
        cfg,
        _BlockHandler({"message": "no key", "credential_missing": True}),
        monkeypatch=monkeypatch,
    )
    assert result.status == "skipped"
    assert result.errors[0]["credential_missing"] is True

    runs = json.loads(
        (tmp_path / "test-domain" / "blocked-src" / "_runs.json").read_text(encoding="utf-8")
    )
    assert runs[-1]["status"] == "skipped"
    assert runs[-1]["errors"][0]["credential_missing"] is True


def test_precheck_dry_run_skips_without_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(collect_mod, "COLLECTIONS_DIR", str(tmp_path))
    cfg = SourceConfig(name="blocked-src", type="rss", url="https://example.org/feed")
    result = _run_source(
        cfg,
        _BlockHandler({"message": "no query", "empty_topic": True}),
        dry_run=True,
        monkeypatch=monkeypatch,
    )
    assert result.status == "skipped"
    assert result.errors[0]["empty_topic"] is True
    assert not (tmp_path / "test-domain" / "blocked-src" / "_runs.json").exists()


def test_broken_precheck_fails_open(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """precheck 抛异常 ⇒ 放行（fail-open），闸门故障不得静默禁源。"""
    monkeypatch.setattr(collect_mod, "COLLECTIONS_DIR", str(tmp_path))
    cfg = SourceConfig(name="exploding-src", type="rss", url="https://example.org/feed")

    def _fake_fetch(
        handler: Any, source_config: Any, topic: Any, limit: Any, keywords: Any = None
    ) -> list[Item]:
        return []

    monkeypatch.setattr(collect_mod, "_fetch_items", _fake_fetch)
    result = _run_source(cfg, _ExplodingPrecheckHandler(), monkeypatch=monkeypatch)
    assert result.status == "success"  # 放行到 fetch，fetch 返回空 ⇒ success
