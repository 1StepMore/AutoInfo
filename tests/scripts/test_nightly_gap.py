"""Tests for scripts/nightly_gap.py — 差距计算器。

Issue #455: ``_log_run`` 对 ``status="skipped"`` 也追加运行记录，于是被策略跳过
（应用审核闸 #450、robots 门 #452、handler 构造失败）的源在差距矩阵里被算成
「已跑」——被闸挡住的源伪装成覆盖。本文件锁死新的三态口径：

* skipped 不计「已跑/覆盖」，也不计「源损坏」，而是带原因的单独一类；
* ``sources_healthy`` 自洽：跳过的源既不算 healthy 也不算 unhealthy；
* 无 skip 的域输出与改动前**逐字一致**（防回归）；
* 边界语义（既有成功又有跳过）按「最近一次」判定，并锁死。

全部离线：读 ``tmp_path`` 夹具（``collections/<domain>/<source>/_runs.json``），
不起子进程、不联网、不调 LLM。``main()`` 里的 ``autoinfo status`` 调用被
monkeypatch 成夹具。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pytest

# scripts/ is not a package — load it via sys.path like the script itself does.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

import nightly_gap as ng  # noqa: E402  (sys.path insert above)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _write_runs(collections: Path, domain: str, source: str, runs: list[dict[str, Any]]) -> None:
    d = collections / domain / source
    d.mkdir(parents=True, exist_ok=True)
    (d / "_runs.json").write_text(json.dumps(runs, ensure_ascii=False, indent=2), encoding="utf-8")


def _run(
    status: str,
    items: int = 0,
    ts: str = "2026-08-10T00:00:00+00:00",
    errors: list[dict] | None = None,
) -> dict[str, Any]:
    return {
        "collection_id": f"c-{ts}",
        "timestamp": ts,
        "status": status,
        "items_found": items,
        "items_new": items,
        "items_filtered": 0,
        "errors": errors or [],
        "duration_ms": 1.0,
    }


APP_REVIEW_MSG = (
    "source 'bilibili-popular' requires platform app/interface review "
    "but no acknowledgement is recorded — skipped (fail-closed)"
)
ROBOTS_MSG = "robots.txt disallows /popular (HTTP 200 body: Disallow: /popular)"


def _health(name: str, total_runs: int, status: str = "healthy") -> dict[str, Any]:
    """`autoinfo --json status` 里 source_health 的一个条目形状。"""
    return {
        "name": name,
        "status": status,
        "last_run": "2026-08-10T00:00:00+00:00",
        "total_runs": total_runs,
    }


def _domains_dir(tmp_path: Path, *domains: str) -> Path:
    d = tmp_path / "domains"
    for dom in domains:
        (d / dom).mkdir(parents=True, exist_ok=True)
        (d / dom / "sources.yaml").write_text("sources: []\n", encoding="utf-8")
    return d


def _outputs_dir(tmp_path: Path, *domains: str) -> Path:
    d = tmp_path / "outputs"
    for dom in domains:
        (d / dom).mkdir(parents=True, exist_ok=True)
        (d / dom / "digest.md").write_text("# digest\n", encoding="utf-8")
    return d


def _run_main(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: dict[str, dict], domains: list[str]
) -> tuple[int, dict, str]:
    """跑 main() 一次（status 用夹具替身），返回 (退出码, gap.json, gap.md)。"""
    monkeypatch.setattr(ng, "status_by_domain", lambda python, collections=None: status)
    jp, mp = tmp_path / "gap.json", tmp_path / "gap.md"
    rc = ng.main(
        [
            "--domains-dir",
            str(_domains_dir(tmp_path, *domains)),
            "--outputs",
            str(_outputs_dir(tmp_path, *domains)),
            "--collections",
            str(tmp_path / "collections"),
            "--skip-assertions",
            "--json-out",
            str(jp),
            "--md-out",
            str(mp),
        ]
    )
    return rc, json.loads(jp.read_text(encoding="utf-8")), mp.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# source_run_state — 三态分类
# ---------------------------------------------------------------------------


def test_success_with_items_is_produced() -> None:
    st = ng.source_run_state([_run("success", items=7)])
    assert st["state"] == ng.STATE_PRODUCED
    assert st["skipped"] is False
    assert st["runs_productive"] == 1


def test_success_without_items_is_ran_empty() -> None:
    st = ng.source_run_state([_run("success", items=0), _run("success", items=0)])
    assert st["state"] == ng.STATE_RAN_EMPTY
    assert st["skipped"] is False
    assert (st["runs_productive"], st["runs_empty"]) == (0, 2)


def test_skipped_only_is_skipped_not_ran() -> None:
    """核心 bug：只有一条 skipped 记录的源，旧口径（total_runs>0）算「已跑」。"""
    st = ng.source_run_state(
        [
            _run("skipped", errors=[{"message": APP_REVIEW_MSG, "app_review_required": True}]),
        ]
    )
    assert st["state"] == ng.STATE_SKIPPED
    assert st["skipped"] is True
    assert st["skip_reason"] == ng.SKIP_REASON_APP_REVIEW
    assert st["runs_productive"] == 0


def test_error_only_source_stays_failed_and_keeps_legacy_ran_semantics() -> None:
    """error-only 的源历史上就算「已跑」；#455 不动这条口径（只动 skipped）。"""
    st = ng.source_run_state([_run("error", errors=[{"message": "boom", "reason": "boom"}])])
    assert st["state"] == ng.STATE_FAILED
    assert st["skipped"] is False


def test_no_runs_is_never_ran() -> None:
    st = ng.source_run_state([])
    assert st["state"] == ng.STATE_NEVER_RAN
    assert st["skipped"] is False


def test_legacy_entry_without_status_counts_as_success() -> None:
    """缺 status 的历史条目按 success 读（与 autoinfo.status.get_source_health 一致）。"""
    legacy = {"timestamp": "2026-07-01T00:00:00+00:00", "items_found": 3, "items_new": 3}
    assert ng.source_run_state([legacy])["state"] == ng.STATE_PRODUCED


# ---------------------------------------------------------------------------
# 边界语义：既有成功又有跳过 → 按「最近一次」（#455）
# ---------------------------------------------------------------------------


def test_boundary_success_then_skip_is_skipped() -> None:
    """所选语义：**最近一次运行决定 skipped**（而不是「历史上有过任一次成功」）。

    锁定理由（与 source_run_state 的注释一致）：矩阵是当前差距报表，策略跳过是当下
    待解开的阻断；「任一成功」口径会让曾经能采、现在被闸挡住的源继续显示为已覆盖，
    正是 #455 报的伪装。
    """
    st = ng.source_run_state(
        [
            _run("success", items=5, ts="2026-08-01T00:00:00+00:00"),
            _run(
                "skipped",
                ts="2026-08-10T00:00:00+00:00",
                errors=[{"message": APP_REVIEW_MSG, "app_review_required": True}],
            ),
        ]
    )
    assert st["state"] == ng.STATE_SKIPPED
    assert st["skipped"] is True
    assert st["skip_reason"] == ng.SKIP_REASON_APP_REVIEW
    # 历史信息不丢：产出与跳过次数都记着，供判断「这是可回收的覆盖」
    assert st["runs_productive"] == 1
    assert st["runs_skipped"] == 1
    assert st["runs_total"] == 2


def test_boundary_skip_then_success_is_ran_again() -> None:
    """反向：最近一次跑成功了 → 覆盖恢复（历史跳过不株伤当下口径）。"""
    st = ng.source_run_state(
        [
            _run(
                "skipped",
                ts="2026-08-01T00:00:00+00:00",
                errors=[{"message": ROBOTS_MSG, "robots_disallowed": True}],
            ),
            _run("success", items=4, ts="2026-08-10T00:00:00+00:00"),
        ]
    )
    assert st["state"] == ng.STATE_PRODUCED
    assert st["skipped"] is False
    assert st["runs_skipped"] == 1  # 历史跳过仍可见


# ---------------------------------------------------------------------------
# classify_skip_reason — 原因归纳
# ---------------------------------------------------------------------------


def test_skip_reason_from_explicit_app_review_marker() -> None:
    runs = [_run("skipped", errors=[{"message": APP_REVIEW_MSG, "app_review_required": True}])]
    assert ng.classify_skip_reason(runs) == (ng.SKIP_REASON_APP_REVIEW, APP_REVIEW_MSG)


def test_skip_reason_from_explicit_robots_marker() -> None:
    runs = [_run("skipped", errors=[{"message": ROBOTS_MSG, "robots_disallowed": True}])]
    assert ng.classify_skip_reason(runs)[0] == ng.SKIP_REASON_ROBOTS


def test_skip_reason_from_message_sniff_when_no_marker() -> None:
    """handler 构造失败只写 message（collect.py 的 ValueError 分支）。"""
    runs = [_run("skipped", errors=[{"message": "Unknown source type: bilibili"}])]
    assert ng.classify_skip_reason(runs) == (ng.SKIP_REASON_OTHER, "Unknown source type: bilibili")


def test_skip_reason_falls_back_to_other() -> None:
    assert (
        ng.classify_skip_reason([_run("skipped", errors=[{"message": "???"}])])[0]
        == ng.SKIP_REASON_OTHER
    )
    assert ng.classify_skip_reason([_run("skipped")])[0] == ng.SKIP_REASON_OTHER


def test_explicit_marker_beats_message_sniff() -> None:
    """显式标记优先于文本嗅探；两个显式标记同时存在时 app_review 优先（可操作的闸）。"""
    runs = [
        _run(
            "skipped",
            errors=[
                {"message": "robots disallowed", "robots_disallowed": True},
                {"message": APP_REVIEW_MSG, "app_review_required": True},
            ],
        )
    ]
    assert ng.classify_skip_reason(runs)[0] == ng.SKIP_REASON_APP_REVIEW


def test_skip_reason_ignores_non_skipped_runs() -> None:
    """error 条目里的同名字样不能把一次真错误误判成 skip 原因。"""
    runs = [_run("error", errors=[{"message": "app review required"}])]
    assert ng.classify_skip_reason(runs) == (ng.SKIP_REASON_OTHER, "")


# ---------------------------------------------------------------------------
# summarize_sources — 域级聚合
# ---------------------------------------------------------------------------


def test_skipped_source_not_counted_as_ran(tmp_path: Path) -> None:
    col = tmp_path / "collections"
    _write_runs(col, "online-video", "pubmed-like", [_run("success", items=9)])
    _write_runs(
        col,
        "online-video",
        "bili-popular",
        [_run("skipped", errors=[{"message": APP_REVIEW_MSG, "app_review_required": True}])],
    )
    _write_runs(col, "online-video", "untouched", [])
    health = [_health("pubmed-like", 3), _health("bili-popular", 1), _health("untouched", 0)]

    agg = ng.summarize_sources(health, col, "online-video")

    assert agg["sources_total"] == 3
    # 旧口径会给 2（bili-popular 有 total_runs=1 → 算已跑）；现在只有 pubmed-like
    assert agg["sources_ran"] == 1
    assert agg["sources_skipped"] == 1
    assert agg["sources_productive"] == 1
    assert agg["skipped_sources"] == [
        {
            "source": "bili-popular",
            "reason": ng.SKIP_REASON_APP_REVIEW,
            "detail": APP_REVIEW_MSG,
            "runs_total": 1,
            "runs_skipped": 1,
            "runs_productive": 0,
        }
    ]


def test_skipped_source_is_neither_healthy_nor_unhealthy(tmp_path: Path) -> None:
    col = tmp_path / "collections"
    _write_runs(col, "d", "ok", [_run("success", items=2)])
    _write_runs(
        col,
        "d",
        "gated",
        [_run("skipped", errors=[{"message": ROBOTS_MSG, "robots_disallowed": True}])],
    )
    _write_runs(col, "d", "broken", [_run("error", errors=[{"message": "boom"}])])
    health = [
        _health("ok", 2, "healthy"),
        # status.py 只看时间新鲜度 → 被跳过的源在 status 里也是 healthy
        _health("gated", 1, "healthy"),
        _health("broken", 1, "stale"),
    ]

    agg = ng.summarize_sources(health, col, "d")

    assert agg["sources_healthy"] == 1  # ok（gated 被踢出 healthy）
    assert agg["sources_skipped"] == 1
    assert agg["sources_unhealthy"] == 1  # 只有 broken；gated 两边都不算
    # 恒等式：三类互斥且合起来 = 总数
    assert (agg["sources_healthy"] + agg["sources_unhealthy"] + agg["sources_skipped"]) == agg[
        "sources_total"
    ]


def test_ran_breakdown_matches_ran_total(tmp_path: Path) -> None:
    """self-consistency: ran = productive + ran_empty + failed（skipped 不在其中）。"""
    col = tmp_path / "collections"
    _write_runs(col, "d", "a", [_run("success", items=3)])
    _write_runs(col, "d", "b", [_run("success", items=0)])
    _write_runs(col, "d", "c", [_run("error", errors=[{"message": "x"}])])
    _write_runs(col, "d", "e", [_run("skipped", errors=[{"message": "y"}])])
    health = [_health(n, 1) for n in "abce"]

    agg = ng.summarize_sources(health, col, "d")

    assert agg["sources_ran"] == 3
    assert (agg["sources_productive"], agg["sources_ran_empty"], agg["sources_failed"]) == (1, 1, 1)
    assert agg["sources_ran"] == (
        agg["sources_productive"] + agg["sources_ran_empty"] + agg["sources_failed"]
    )


def test_missing_collections_dir_is_all_never_ran(tmp_path: Path) -> None:
    agg = ng.summarize_sources([_health("a", 2)], tmp_path / "nope", "d")
    assert agg["sources_skipped"] == 0
    assert agg["skipped_sources"] == []
    assert agg["sources_productive"] == 0


def test_corrupt_runs_json_does_not_crash(tmp_path: Path) -> None:
    col = tmp_path / "collections"
    d = col / "d" / "a"
    d.mkdir(parents=True)
    (d / "_runs.json").write_text("{not json", encoding="utf-8")
    assert ng._read_runs(col, "d", "a") == []
    assert ng.summarize_sources([_health("a", 2)], col, "d")["sources_skipped"] == 0


# ---------------------------------------------------------------------------
# main() 端到端（夹具替身，无子进程/无网络）
# ---------------------------------------------------------------------------


def test_gap_md_marks_skipped_count(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    col = tmp_path / "collections"
    _write_runs(col, "online-video", "pubmed-like", [_run("success", items=9)])
    _write_runs(
        col,
        "online-video",
        "bili-popular",
        [_run("skipped", errors=[{"message": APP_REVIEW_MSG, "app_review_required": True}])],
    )
    status = {
        "online-video": {
            "entries": 30,
            **ng.summarize_sources(
                [_health("pubmed-like", 3), _health("bili-popular", 1)], col, "online-video"
            ),
        }
    }

    rc, payload, md = _run_main(tmp_path, monkeypatch, status, ["online-video"])

    assert rc == 0  # 跳过不是差距，也不是源损坏
    assert "| online-video | 30 | 1/2（含 1 策略跳过） | 1 | 0 | ✅ 达标 |" in md
    unit = payload["units"][0]
    assert unit["sources_skipped"] == 1
    assert unit["skipped_sources"][0]["source"] == "bili-popular"
    assert unit["skipped_sources"][0]["reason"] == ng.SKIP_REASON_APP_REVIEW
    assert payload["skip_summary"] == {
        "sources_skipped": 1,
        "by_reason": {ng.SKIP_REASON_APP_REVIEW: 1},
    }
    assert "## 策略跳过的源（不计覆盖，也不计源损坏，#455）" in md
    assert "`app_review_required`" in md


def test_domain_with_only_skipped_sources_reports_skip_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """全部源被闸挡住 → ① 不达标，且措辞说清是被跳过，不是「从未跑过」。"""
    col = tmp_path / "collections"
    _write_runs(
        col,
        "online-video",
        "bili",
        [_run("skipped", errors=[{"message": ROBOTS_MSG, "robots_disallowed": True}])],
    )
    status = {
        "online-video": {
            "entries": 0,
            **ng.summarize_sources([_health("bili", 1)], col, "online-video"),
        }
    }

    rc, payload, md = _run_main(tmp_path, monkeypatch, status, ["online-video"])

    assert rc == 1
    unit = payload["units"][0]
    assert unit["passing"] is False
    assert unit["missing"] == ["真语料（该域没有任何源跑过：1 个源被策略跳过）"]
    assert "1/0" not in md  # 分母是配置源数，不是 0
    assert "| online-video | 0 | 0/1（含 1 策略跳过） |" in md
    assert "robots_disallowed" in md


def test_no_skip_domain_output_is_verbatim_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """防回归：无 skipped 的域，md 行、missing、数字全部与改动前一致。

    注意「逐字一致」的边界：gap.json 的 unit 新增了 #455 要求的字段
    （sources_skipped / skipped_sources / 三态细分），所以整份 JSON 不可能逐字相同；
    本例锁定的是**改动前就存在的每个字段** + md 表格行逐字不变。
    """
    col = tmp_path / "collections"
    _write_runs(col, "d", "a", [_run("success", items=5)])
    _write_runs(col, "d", "b", [_run("success", items=0)])
    _write_runs(col, "d", "c", [_run("error", errors=[{"message": "boom"}])])
    health = [_health("a", 4), _health("b", 1), _health("c", 2)]

    status = {"d": {"entries": 12, **ng.summarize_sources(health, col, "d")}}
    rc, payload, md = _run_main(tmp_path, monkeypatch, status, ["d"])

    # 旧口径（改动前的算法）在这里复算一遍，逐字段对比
    legacy_ran = sum(1 for s in health if int(s.get("total_runs") or 0) > 0)
    legacy_healthy = sum(1 for s in health if str(s.get("status")) == "healthy")
    unit = payload["units"][0]
    assert unit["sources_ran"] == legacy_ran == 3
    assert unit["sources_healthy"] == legacy_healthy
    assert unit["sources_total"] == len(health)
    assert unit["entries"] == 12
    assert unit["missing"] == []  # 与改动前同一份 missing 列表
    assert unit["passing"] is True
    assert unit["output_files"] == 1
    assert unit["assertion_failures"] == 0
    # md 表格行逐字不变：没有「（含 N 策略跳过）」后缀，也没有跳过小节
    assert "| d | 12 | 3/3 | 1 | 0 | ✅ 达标 |" in md
    assert "策略跳过" not in md
    # 新字段归零（不是缺失，是显式 0）
    assert unit["sources_skipped"] == 0
    assert unit["skipped_sources"] == []
    assert payload["skip_summary"] == {"sources_skipped": 0, "by_reason": {}}
    assert rc == 0


def test_no_skip_domain_low_entries_message_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """低条数域的 missing 文案也不因 #455 变化（无 skip → 原话术）。"""
    col = tmp_path / "collections"
    _write_runs(col, "d", "a", [_run("success", items=5)])
    status = {"d": {"entries": 7, **ng.summarize_sources([_health("a", 4)], col, "d")}}

    _, payload, md = _run_main(tmp_path, monkeypatch, status, ["d"])

    assert payload["units"][0]["missing"] == ["真语料（7 条 < 阈值 10）"]
    assert "| d | 7 | 1/1 | 1 | 0 | 真语料（7 条 < 阈值 10） |" in md


def test_mixed_domain_counts_only_real_coverage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """11 源 / 3 跳过 → md 显式写「8/11（含 3 策略跳过）」，json 同步字段。"""
    col = tmp_path / "collections"
    names = []
    for i in range(11):
        name = f"s{i}"
        names.append(name)
        if i < 3:
            _write_runs(
                col,
                "big",
                name,
                [_run("skipped", errors=[{"message": ROBOTS_MSG, "robots_disallowed": True}])],
            )
        else:
            _write_runs(col, "big", name, [_run("success", items=3)])
    health = [_health(n, 1) for n in names]
    status = {"big": {"entries": 40, **ng.summarize_sources(health, col, "big")}}

    rc, payload, md = _run_main(tmp_path, monkeypatch, status, ["big"])

    assert rc == 0
    assert "| big | 40 | 8/11（含 3 策略跳过） | 1 | 0 | ✅ 达标 |" in md
    unit = payload["units"][0]
    assert (unit["sources_ran"], unit["sources_total"], unit["sources_skipped"]) == (8, 11, 3)
    assert [e["source"] for e in unit["skipped_sources"]] == ["s0", "s1", "s2"]
    assert payload["skip_summary"]["by_reason"] == {ng.SKIP_REASON_ROBOTS: 3}
