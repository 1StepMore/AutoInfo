"""Auto-disable gate (#665): 连续失败自动降级 + force-enable 逃生阀.

背景（#665）：5 个外源 endpoint 失效（uspto/ProductHunt/arXiv/oyez/retailwire）
每晚照跑照失败，连续 26-29 次 —— 「源已失效」没有任何机制能识别，只能靠人改
yaml。修法：

1. 某源连续 N 次（=7）``status="error"`` ⇒ 采集分发处跳过该源，记
   ``status="disabled_auto"``，不发请求、不建 handler。
2. 降级发生时产出 ``source_permanently_failing`` agent-callback 事件
   （**只在转换那一刻发一次**，之后每晚只追加 disabled_auto 记录，静默）。
3. 逃生阀：``run_collection(force_enable=[...])`` / CLI ``--force-enable`` /
   MCP ``force_enable`` —— 强制跑一次；一次成功自然清零连败计数（streak
   是 _runs.json 的 trailing errors），源自动恢复。

不做自动删源 —— 删源是不可逆的数据决策，归人；自动降级只影响采集尝试，
不碰配置。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from autoinfo import collect as collect_mod
from autoinfo.collect import (
    AUTO_DISABLE_FAILURE_THRESHOLD,
    _auto_disable_skip,
    _collect_from_source,
    _consecutive_source_failures,
)
from autoinfo.config import SourceConfig
from autoinfo.dedup import DedupChecker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_runs(tmp_path: Path, domain: str, source: str, statuses: list[str]) -> Path:
    runs_path = tmp_path / domain / source / "_runs.json"
    runs_path.parent.mkdir(parents=True, exist_ok=True)
    runs = [
        {
            "collection_id": f"col-{i}",
            "timestamp": f"2026-10-{10 + (i % 20):02d}T00:00:00+00:00",
            "status": status,
            "items_found": 0,
            "items_new": 0,
            "items_filtered": 0,
            "items_duplicate": 0,
            "errors": [{"message": "404 Not Found"}] if status == "error" else [],
            "duration_ms": 1.0,
        }
        for i, status in enumerate(statuses)
    ]
    runs_path.write_text(json.dumps(runs), encoding="utf-8")
    return runs_path


def _read_last_status(tmp_path: Path, domain: str, source: str) -> str:
    runs_path = tmp_path / domain / source / "_runs.json"
    runs = json.loads(runs_path.read_text(encoding="utf-8"))
    return str(runs[-1]["status"])


# ---------------------------------------------------------------------------
# 1) streak 计算 —— trailing errors，disabled_auto 透明，success 清零
# ---------------------------------------------------------------------------


def test_streak_counts_trailing_errors() -> None:
    runs = [{"status": "success"}, {"status": "error"}, {"status": "error"}]
    assert _consecutive_source_failures(runs) == 2


def test_streak_sees_through_disabled_auto_markers() -> None:
    """disabled_auto 记录的是降级态，不是恢复 —— streak 穿透它继续数。"""
    runs = [{"status": "error"}, {"status": "disabled_auto"}, {"status": "error"}]
    assert _consecutive_source_failures(runs) == 2


def test_streak_resets_on_success() -> None:
    runs = [{"status": "error"}, {"status": "error"}, {"status": "success"}, {"status": "error"}]
    assert _consecutive_source_failures(runs) == 1


def test_streak_skipped_breaks_streak() -> None:
    """策略跳过（app_review/robots）不是失败 —— 中断连败。"""
    runs = [{"status": "error"} for _ in range(5)] + [{"status": "skipped"}]
    assert _consecutive_source_failures(runs) == 0


def test_streak_legacy_missing_status_breaks_streak() -> None:
    """历史条目缺 status 按 success 读（与 nightly_gap._run_status 同口径）——
    最新一条是 legacy 条目 ⇒ 不是失败，streak 中断。"""
    runs = [{"status": "error"}, {"items_found": 3}]
    assert _consecutive_source_failures(runs) == 0


def test_streak_legacy_older_than_errors_does_not_block() -> None:
    """legacy 条目在 error 之后（更旧）⇒ 不影响 trailing error 计数。"""
    runs = [{"items_found": 3}, {"status": "error"}, {"status": "error"}]
    assert _consecutive_source_failures(runs) == 2


def test_streak_empty_history() -> None:
    assert _consecutive_source_failures([]) == 0


# ---------------------------------------------------------------------------
# 2) 降级门 —— 7 连败后跳过、记账、发事件（仅一次）
# ---------------------------------------------------------------------------


def test_below_threshold_not_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(collect_mod, "COLLECTIONS_DIR", str(tmp_path))
    result = _auto_disable_skip(
        domain="d",
        source_name="s",
        source_type="rss",
        collection_id="c1",
        dry_run=False,
        force_enable=None,
        duration_s=0.0,
    )
    assert result is None


def test_at_threshold_disabled_and_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(collect_mod, "COLLECTIONS_DIR", str(tmp_path))
    _write_runs(tmp_path, "d", "s", ["error"] * AUTO_DISABLE_FAILURE_THRESHOLD)
    # 隔离：不往真实 outbox 写行（不启动真实 drain worker）。
    monkeypatch.setattr("autoinfo.agent_callback.notify_source_permanently_failing", lambda **kw: 1)
    result = _auto_disable_skip(
        domain="d",
        source_name="s",
        source_type="rss",
        collection_id="c1",
        dry_run=False,
        force_enable=None,
        duration_s=0.5,
    )
    assert result is not None
    assert result.status == "disabled_auto"
    assert result.errors[0]["disabled_auto"] is True
    assert str(AUTO_DISABLE_FAILURE_THRESHOLD) in result.errors[0]["message"]
    assert _read_last_status(tmp_path, "d", "s") == "disabled_auto"


def test_transition_fires_callback_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """source_permanently_failing 只在转换那刻发一次；后续降级运行静默。"""
    monkeypatch.setattr(collect_mod, "COLLECTIONS_DIR", str(tmp_path))
    fired: list[dict[str, object]] = []

    def _fake_notify(**kwargs: object) -> int:
        fired.append(kwargs)
        return 1

    monkeypatch.setattr("autoinfo.agent_callback.notify_source_permanently_failing", _fake_notify)
    _write_runs(tmp_path, "d", "s", ["error"] * AUTO_DISABLE_FAILURE_THRESHOLD)

    # 第一次：转换 —— 发事件
    r1 = _auto_disable_skip(
        domain="d",
        source_name="s",
        source_type="uspto",
        collection_id="c1",
        dry_run=False,
        force_enable=None,
        duration_s=0.0,
    )
    assert r1 is not None and r1.status == "disabled_auto"
    assert len(fired) == 1
    assert fired[0]["source"] == "s"
    assert fired[0]["source_type"] == "uspto"
    assert fired[0]["domain"] == "d"
    assert fired[0]["consecutive_failures"] == AUTO_DISABLE_FAILURE_THRESHOLD

    # 第二次：已降级 —— 只追加记录，不重复发事件
    r2 = _auto_disable_skip(
        domain="d",
        source_name="s",
        source_type="uspto",
        collection_id="c2",
        dry_run=False,
        force_enable=None,
        duration_s=0.0,
    )
    assert r2 is not None and r2.status == "disabled_auto"
    assert len(fired) == 1
    assert _read_last_status(tmp_path, "d", "s") == "disabled_auto"


def test_dry_run_reports_skip_without_ledger_or_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(collect_mod, "COLLECTIONS_DIR", str(tmp_path))
    fired: list[dict[str, object]] = []

    monkeypatch.setattr(
        "autoinfo.agent_callback.notify_source_permanently_failing",
        lambda **kw: fired.append(kw) or 1,
    )
    _write_runs(tmp_path, "d", "s", ["error"] * AUTO_DISABLE_FAILURE_THRESHOLD)
    before = (tmp_path / "d" / "s" / "_runs.json").read_text(encoding="utf-8")

    result = _auto_disable_skip(
        domain="d",
        source_name="s",
        source_type="rss",
        collection_id="c1",
        dry_run=True,
        force_enable=None,
        duration_s=0.0,
    )
    assert result is not None and result.status == "disabled_auto"
    assert (tmp_path / "d" / "s" / "_runs.json").read_text(encoding="utf-8") == before
    assert fired == []


def test_force_enable_bypasses_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """逃生阀：force_enable 列表内的源照常采集（不跳过、不写 disabled_auto）。"""
    monkeypatch.setattr(collect_mod, "COLLECTIONS_DIR", str(tmp_path))
    _write_runs(tmp_path, "d", "s", ["error"] * AUTO_DISABLE_FAILURE_THRESHOLD)
    result = _auto_disable_skip(
        domain="d",
        source_name="s",
        source_type="rss",
        collection_id="c1",
        dry_run=False,
        force_enable=["s"],
        duration_s=0.0,
    )
    assert result is None
    assert _read_last_status(tmp_path, "d", "s") == "error"  # 没追加降级记录


def test_success_in_history_not_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """历史上有成功（哪怕最近连续失败 < 7）→ 不降级。"""
    monkeypatch.setattr(collect_mod, "COLLECTIONS_DIR", str(tmp_path))
    _write_runs(tmp_path, "d", "s", ["success"] + ["error"] * (AUTO_DISABLE_FAILURE_THRESHOLD - 1))
    result = _auto_disable_skip(
        domain="d",
        source_name="s",
        source_type="rss",
        collection_id="c1",
        dry_run=False,
        force_enable=None,
        duration_s=0.0,
    )
    assert result is None


def test_fresh_source_not_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """无 _runs.json 的新源永不降级。"""
    monkeypatch.setattr(collect_mod, "COLLECTIONS_DIR", str(tmp_path))
    result = _auto_disable_skip(
        domain="d",
        source_name="never-ran",
        source_type="rss",
        collection_id="c1",
        dry_run=False,
        force_enable=None,
        duration_s=0.0,
    )
    assert result is None


# ---------------------------------------------------------------------------
# 3) 分发处集成 —— 降级源在 _collect_from_source 里被拦截（无 handler 构建）
# ---------------------------------------------------------------------------


def test_collect_from_source_respects_auto_disable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(collect_mod, "COLLECTIONS_DIR", str(tmp_path))
    _write_runs(tmp_path, "test-domain", "dead-src", ["error"] * AUTO_DISABLE_FAILURE_THRESHOLD)
    built: list[str] = []

    def _fake_build_handler(cfg: SourceConfig) -> object:
        built.append(cfg.name)
        raise AssertionError("handler must not be built for an auto-disabled source")

    monkeypatch.setattr(collect_mod, "_build_handler", _fake_build_handler)
    # 隔离：不往真实 outbox 写行、不启动 drain worker（#378 的 worker 线程
    # 是模块级长驻的，会泄漏到后续测试的 tmp-DB 断言里）。
    monkeypatch.setattr("autoinfo.agent_callback.notify_source_permanently_failing", lambda **kw: 1)
    cfg = SourceConfig(name="dead-src", type="rss", url="https://example.org/feed")
    result = _collect_from_source(
        source_config=cfg,
        domain="test-domain",
        topic="t",
        limit=5,
        dry_run=False,
        existing_entries=[],
        collection_id="col-auto-disable-test",
        checker=DedupChecker(),
        new_items_collector=None,
        force_full=True,
        keywords=None,
    )
    assert result.status == "disabled_auto"
    assert built == []  # handler 根本没被构建 —— 零成本跳过
