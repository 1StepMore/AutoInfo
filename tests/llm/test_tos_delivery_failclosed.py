"""ToS 交付门 —— 失败关闭（fail-closed）回归测试。

背景（2026-10-02 独立交叉审查发现）：
    原实现中「受限/敏感来源 + PROCESSED」被判 passed=True、只附一句 compliance
    notice。提示不拦人 → 受限源内容经大模型加工成 digest/report 即可通过交付门，
    与「不做违法采集」这条硬约束直接冲突。

本文件是**正负样本自验证**：
    - 负样本：受限/敏感来源的 RAW 与 PROCESSED 都必须被拦（默认）
    - 正样本：公开来源不得被误杀；显式 override 后必须能放行
"""

from __future__ import annotations

from autoinfo.quality import D2FormatIntegrity


def _product(product_type: str, tiers: list[int], tos: list[str] | None = None):
    entries = []
    for i, t in enumerate(tiers):
        e = {"entry_id": f"e{i}", "title": f"t{i}", "quality_tier": t}
        if tos:
            e["tos_classification"] = tos[i]
        entries.append(e)
    return {"product_type": product_type, "entries": entries}


# ───────────────────────── 负样本：必须被拦 ─────────────────────────


def test_processed_restricted_blocked_by_default():
    """PROCESSED + tier3(restricted) → 默认拦截。"""
    gate = D2FormatIntegrity()
    r = gate.tos_delivery_check(_product("PROCESSED", [3]))
    assert r.passed is False, "受限来源的 PROCESSED 产物默认必须被拦"
    assert r.details["tos_blocked"] is True
    assert r.details["action"] == "block"
    assert "restricted" in r.details["error"]


def test_processed_sensitive_blocked_by_default():
    """PROCESSED + tier4(sensitive) → 默认拦截。"""
    gate = D2FormatIntegrity()
    r = gate.tos_delivery_check(_product("PROCESSED", [4]))
    assert r.passed is False
    assert r.details["tos_blocked"] is True
    assert "sensitive" in r.details["error"]


def test_raw_restricted_still_blocked():
    """RAW + restricted → 仍然拦截（原有行为不得回退）。"""
    gate = D2FormatIntegrity()
    r = gate.tos_delivery_check(_product("RAW", [3]))
    assert r.passed is False
    assert r.details["tos_blocked"] is True


def test_explicit_tos_classification_also_blocks():
    """显式 tos_classification 字段（而非 tier 推导）同样拦截。"""
    gate = D2FormatIntegrity()
    r = gate.tos_delivery_check(_product("PROCESSED", [1], tos=["restricted"]))
    assert r.passed is False
    assert r.details["tos_blocked"] is True


# ───────────────────────── 正样本：不得误杀 / override 可放行 ─────────────────────────


def test_processed_open_sources_pass():
    """公开来源的 PROCESSED 产物不得被误杀。"""
    gate = D2FormatIntegrity()
    r = gate.tos_delivery_check(_product("PROCESSED", [1, 1]))
    assert r.passed is True
    assert r.details["tos_blocked"] is False


def test_unclassified_entries_default_to_open():
    """未标 tier / tos 的条目按 open 处理，不拦。"""
    gate = D2FormatIntegrity()
    r = gate.tos_delivery_check({"product_type": "PROCESSED", "entries": [{"entry_id": "x"}]})
    assert r.passed is True


def test_override_allows_with_notice():
    """显式 allow_processed_from_restricted=True → 放行，且必须带合规提示与 override 标记。"""
    gate = D2FormatIntegrity(allow_processed_from_restricted=True)
    r = gate.tos_delivery_check(_product("PROCESSED", [3]))
    assert r.passed is True
    assert r.details["tos_compliance_notice"] is True
    assert r.details["override_applied"] == "allow_processed_from_restricted=True"


def test_override_does_not_allow_raw():
    """★ 关键：override 只对 PROCESSED 生效——RAW 永远拦（防止把开关当成万能钥匙）。"""
    gate = D2FormatIntegrity(allow_processed_from_restricted=True)
    r = gate.tos_delivery_check(_product("RAW", [3]))
    assert r.passed is False, "RAW 不得被 allow_processed_from_restricted 放行"
    assert r.details["tos_blocked"] is True
