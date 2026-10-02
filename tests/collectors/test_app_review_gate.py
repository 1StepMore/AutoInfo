"""App-review 门 —— 「不做违法采集」的机器强制点回归测试。

背景（2026-10-02 独立交叉审查发现）：
    `requires_app_review` 只有 Bilibili handler 上一个 staticmethod + `sources.yaml`
    里一个键 —— **零消费者**。更糟：`SourceConfig` 没有这个字段，yaml 那个键会掉进
    `settings` 无人读，等于**死声明**。

本文件覆盖两端：
  1. 声明真的被解析成一等字段（别再掉进 settings）
  2. 采集分发处真的消费它（fail-closed + 两条显式放行通道）
"""

from __future__ import annotations

import dataclasses

import pytest

from autoinfo.collect import _app_review_block_reason
from autoinfo.collectors.base import BaseHandler
from autoinfo.config import SourceConfig


# ---------------------------------------------------------------------------
# 1) 声明被解析成一等字段
# ---------------------------------------------------------------------------


def test_source_config_has_app_review_fields() -> None:
    """字段必须存在——否则 yaml 键会掉进 settings 无人读（原缺陷）。"""
    names = {f.name for f in dataclasses.fields(SourceConfig)}
    assert "requires_app_review" in names
    assert "app_review_ack" in names


def test_app_review_fields_default_false() -> None:
    cfg = SourceConfig(name="x", type="rss", url="http://e")
    assert cfg.requires_app_review is False
    assert cfg.app_review_ack is False


@pytest.mark.parametrize("raw", ["true", "True", "1", "yes", "on"])
def test_app_review_bool_coercion_truthy(raw: str) -> None:
    cfg = SourceConfig(name="x", requires_app_review=raw, app_review_ack=raw)  # type: ignore[arg-type]
    assert cfg.requires_app_review is True
    assert cfg.app_review_ack is True


@pytest.mark.parametrize("raw", ["false", "False", "0", "no", ""])
def test_app_review_bool_coercion_falsy(raw: str) -> None:
    """YAML 的 "false" 不得读成 truthy —— 否则会静默打开闸门。"""
    cfg = SourceConfig(name="x", requires_app_review=raw, app_review_ack=raw)  # type: ignore[arg-type]
    assert cfg.requires_app_review is False
    assert cfg.app_review_ack is False


# ---------------------------------------------------------------------------
# 2) 分发处消费它（fail-closed）
# ---------------------------------------------------------------------------


class _Plain:
    """A handler that does not claim to need app review."""

    def requires_app_review(self) -> bool:
        return False


class _NeedsReview:
    def requires_app_review(self) -> bool:
        return True


def test_not_declared_allows() -> None:
    """负样本：没声明 → 不得误拦。"""
    assert _app_review_block_reason(SourceConfig(name="open-src"), _Plain()) is None


def test_declared_in_config_without_ack_blocks() -> None:
    """正样本：配置声明了 + 没有确认 → 拦。"""
    cfg = SourceConfig(name="bili", requires_app_review=True)
    reason = _app_review_block_reason(cfg, _Plain())
    assert reason is not None
    assert "bili" in reason


def test_declared_on_handler_alone_blocks() -> None:
    """正样本：只有 handler 声明（配置没写）→ 仍要拦。"""
    assert _app_review_block_reason(SourceConfig(name="bili"), _NeedsReview()) is not None


def test_per_source_ack_allows() -> None:
    """放行通道 ①：源级 app_review_ack。"""
    cfg = SourceConfig(name="bili", requires_app_review=True, app_review_ack=True)
    assert _app_review_block_reason(cfg, _NeedsReview()) is None


def test_env_ack_allows(monkeypatch: pytest.MonkeyPatch) -> None:
    """放行通道 ②：环境变量（全局显式）。"""
    monkeypatch.setenv("AUTOINFO_APP_REVIEW_ACK", "1")
    cfg = SourceConfig(name="bili", requires_app_review=True)
    assert _app_review_block_reason(cfg, _NeedsReview()) is None


def test_env_ack_falsy_value_does_not_allow(monkeypatch: pytest.MonkeyPatch) -> None:
    """负样本：AUTOINFO_APP_REVIEW_ACK=false 不得放行。"""
    monkeypatch.setenv("AUTOINFO_APP_REVIEW_ACK", "false")
    cfg = SourceConfig(name="bili", requires_app_review=True)
    assert _app_review_block_reason(cfg, _NeedsReview()) is not None


def test_broken_handler_does_not_open_gate_by_crash() -> None:
    """handler 的声明方法炸了 → 不能因此当成「已声明」而拦住无辜的源。"""

    class _Broken:
        def requires_app_review(self) -> bool:
            raise RuntimeError("boom")

    assert _app_review_block_reason(SourceConfig(name="x"), _Broken()) is None


def test_base_handler_declares_false_by_default() -> None:
    """所有 handler 都该能统一被问 —— 基类默认 False。"""

    class _H(BaseHandler):
        def fetch(self, *a: object, **k: object) -> list:  # type: ignore[override]
            return []

    assert _H().requires_app_review() is False
    assert _H.REQUIRES_APP_REVIEW is False


def test_bilibili_declares_true_both_ways() -> None:
    """Bilibili：类属性与方法都要 True（方法保留给旧调用方）。"""
    from autoinfo.collectors.bilibili import BilibiliHandler

    assert BilibiliHandler.REQUIRES_APP_REVIEW is True
    assert BilibiliHandler.requires_app_review() is True


def test_real_sources_yaml_parses_the_declaration() -> None:
    """端到端：真实的 sources.yaml 里那句 `requires_app_review: true`
    必须落到一等字段上（以前掉进 settings，无人读）。"""
    import yaml
    from pathlib import Path

    p = (
        Path(__file__).resolve().parents[2]
        / "src/autoinfo/data/domains/tech-ai-developer/sources.yaml"
    )
    if not p.exists():  # pragma: no cover - repo layout guard
        pytest.skip(f"sources.yaml not found at {p}")
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    # 域模板用的是顶层 ``sources:``；用户项目配置里才是 ``domains[].sources``。
    srcs = raw.get("sources") or [
        s for d in raw.get("domains", []) for s in d.get("sources", [])
    ]
    bili = [s for s in srcs if s.get("type") == "bilibili"]
    assert bili, "expected a bilibili source in sources.yaml"
    assert bili[0].get("requires_app_review") is True


# ---------------------------------------------------------------------------
# 3) 落盘往返：声明与确认必须活过 save/load
#    （原缺陷：`config_to_dict` 用显式键列表，新字段一转手就丢）
# ---------------------------------------------------------------------------


def test_app_review_fields_survive_save_load_round_trip(tmp_path) -> None:
    from autoinfo.config import Config, DomainConfig, load_config, save_config

    src = SourceConfig(
        name="bili",
        type="bilibili",
        url="https://api.bilibili.com/x/web-interface/search/all/v2",
        quality_tier=3,
        requires_app_review=True,
        app_review_ack=True,
    )
    cfg = Config(domains=[DomainConfig(name="d1", sources=[src])])
    p = tmp_path / "config.yaml"
    save_config(cfg, p)

    text = p.read_text(encoding="utf-8")
    assert "requires_app_review" in text, "声明在存盘时被丢掉了"
    assert "app_review_ack" in text, "显式确认在存盘时被丢掉了"

    back = load_config(p)
    s2 = back.domains[0].sources[0]
    assert s2.requires_app_review is True
    assert s2.app_review_ack is True
    # 不得同时漏进 settings（会被当成未知键重复承载）
    assert not [k for k in s2.settings if "app_review" in k]
