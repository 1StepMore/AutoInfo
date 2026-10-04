"""robots.txt 共享门 —— 正负样本回归测试。

背景（2026-10-02 独立交叉审查后）：
    审查意见说「32 个采集器里只有 2 个做 robots 检查」。**核实后这是范畴错误**：
    robots.txt 管的是**批量网页爬虫**，不管「按官方 API 条款调用接口」，也不管
    「用户指定的单个网页抓取」。全仓真正的批量爬虫只有 ``edx_sitemap`` 一个，
    而它**已经有** robots 检查。

    真正的缺口不是「覆盖数」，是「**没有共享的落点**」——``robots_allows`` 原本是
    ``edx_sitemap.py`` 的模块私有函数，所以只有定义它的那个采集器能遵守。
    本模块把它抽成共享实现；这些测试锁住行为。

问题单 #452 返工后锁定的行为：
    1. UA 组选择按 RFC 9309 §2.2.1/§2.2.2：精确匹配组优先且取并集，
       真实 UA 匹配不到时**回退到 ``*`` 组**（本文件的回归用例）。
    2. ``check_url_allowed`` 按 origin（scheme+netloc）缓存 robots.txt，
       同一 origin 二次检查不再发请求。
    3. 三个抓页采集器（web / web_playwright / pdf）在请求目标 URL 前过门，
       被拒时抛 ``RobotsDisallowed`` 而不是静默返回空列表。
"""

from __future__ import annotations

import httpx
import pytest

from autoinfo.collectors.robots import (
    RobotsDisallowed,
    _clear_robots_cache,
    check_url_allowed,
    parse_robots_rules,
    robots_allows,
    robots_url_for,
)


@pytest.fixture(autouse=True)
def _fresh_robots_cache():
    """每个用例都从干净的按-origin缓存开始（缓存是进程级 dict）。"""
    _clear_robots_cache()
    yield
    _clear_robots_cache()


# ---------------------------------------------------------------------------
# 规则解析（正样本）
# ---------------------------------------------------------------------------


def test_parse_matches_wildcard_group() -> None:
    txt = "User-agent: *\nDisallow: /private/\n"
    assert parse_robots_rules(txt, "*") == [("disallow", "/private/")]


def test_parse_ignores_non_matching_group() -> None:
    """负样本：别的 agent 的组不得影响 `*`。"""
    txt = "User-agent: BadBot\nDisallow: /\n\nUser-agent: *\nDisallow: /private/\n"
    assert parse_robots_rules(txt, "*") == [("disallow", "/private/")]


def test_parse_ignores_comments_and_blank_lines() -> None:
    txt = "# comment\n\nUser-agent: *\n# another\nDisallow: /x/\n"
    assert parse_robots_rules(txt, "*") == [("disallow", "/x/")]


# ---------------------------------------------------------------------------
# #452①②③：UA 组选择（RFC 9309 §2.2.1/§2.2.2）
# ---------------------------------------------------------------------------


def test_exact_group_wins_over_wildcard() -> None:
    """① 精确匹配组优先：命中自身组时忽略 `*` 组，且多个精确组取并集。"""
    txt = (
        "User-agent: MyBot\n"
        "Disallow: /bot-only/\n"
        "\n"
        "User-agent: mybot\n"  # 大小写不敏感的第二个精确组 → 并集
        "Disallow: /bot-only-2/\n"
        "\n"
        "User-agent: *\n"
        "Disallow: /private/\n"
    )
    expected = [("disallow", "/bot-only/"), ("disallow", "/bot-only-2/")]
    assert parse_robots_rules(txt, "MYBOT") == expected

    assert robots_allows(txt, "/bot-only/x", user_agent="MyBot") is False
    assert robots_allows(txt, "/bot-only-2/x", user_agent="MyBot") is False
    # 精确组命中 → `*` 组的规则不生效
    assert robots_allows(txt, "/private/x", user_agent="MyBot") is True


def test_real_user_agent_falls_back_to_wildcard_group() -> None:
    """② 回归（#452 实测缺陷）：真实 UA 匹配不到组 → 用 `*` 组的规则。

    改前 ``parse_robots_rules`` 只做相等比较，``User-agent: *`` 组永不参与，
    于是这条返回 ``True``（错），应为 ``False``。
    """
    txt = "User-agent: *\nDisallow: /private"
    assert parse_robots_rules(txt, "AutoInfoBot") == [("disallow", "/private")]
    assert robots_allows(txt, "/private/x", user_agent="AutoInfoBot") is False
    # `*` 组之外没有规则可命中时仍放行
    assert robots_allows(txt, "/public/x", user_agent="AutoInfoBot") is True


def test_consecutive_user_agent_lines_share_one_group() -> None:
    """③ 连续的 User-agent 行共享其后的规则；规则行之后的 UA 才开新组。"""
    txt = (
        "User-agent: BotA\n"
        "User-agent: BotB\n"
        "Disallow: /shared/\n"
        "\n"
        "User-agent: *\n"
        "Disallow: /other/\n"
    )
    assert parse_robots_rules(txt, "BotB") == [("disallow", "/shared/")]
    assert parse_robots_rules(txt, "bota") == [("disallow", "/shared/")]
    assert parse_robots_rules(txt, "*") == [("disallow", "/other/")]
    # 共享组里没有 `*`，未知 UA 回退到 `*` 组
    assert parse_robots_rules(txt, "UnknownBot") == [("disallow", "/other/")]

    # 规则行之后再出现 User-agent → 新组，规则不串组
    txt2 = "User-agent: A\nDisallow: /a/\nUser-agent: B\nDisallow: /b/\n"
    assert parse_robots_rules(txt2, "A") == [("disallow", "/a/")]
    assert parse_robots_rules(txt2, "B") == [("disallow", "/b/")]
    assert robots_allows(txt2, "/b/x", user_agent="A") is True


# ---------------------------------------------------------------------------
# 判定（正负样本）
# ---------------------------------------------------------------------------


def test_allows_when_no_rule_matches() -> None:
    assert robots_allows("User-agent: *\nDisallow: /private/\n", "/public/a") is True


def test_disallows_matching_path() -> None:
    assert robots_allows("User-agent: *\nDisallow: /private/\n", "/private/a") is False


def test_longest_match_wins() -> None:
    txt = "User-agent: *\nDisallow: /a/\nAllow: /a/b/\n"
    assert robots_allows(txt, "/a/b/c") is True
    assert robots_allows(txt, "/a/x") is False


def test_equal_length_prefers_allow() -> None:
    txt = "User-agent: *\nDisallow: /x\nAllow: /x\n"
    assert robots_allows(txt, "/x") is True


def test_empty_disallow_is_noop() -> None:
    """空 Disallow 表示「全部允许」，不得被当成命中。"""
    assert robots_allows("User-agent: *\nDisallow:\n", "/anything") is True


def test_empty_robots_allows_everything() -> None:
    assert robots_allows("", "/anything") is True


def test_default_user_agent_is_wildcard_only() -> None:
    """默认 `user_agent="*"` 只用通配组（向后兼容）。"""
    txt = "User-agent: MyBot\nDisallow: /bot/\n\nUser-agent: *\nDisallow: /private/\n"
    assert robots_allows(txt, "/bot/x") is True
    assert robots_allows(txt, "/private/x") is False


# ---------------------------------------------------------------------------
# robots.txt URL 推导
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://example.com/a/b?c=1", "https://example.com/robots.txt"),
        ("http://sub.example.org:8080/x", "http://sub.example.org:8080/robots.txt"),
    ],
)
def test_robots_url_for(url: str, expected: str) -> None:
    assert robots_url_for(url) == expected


@pytest.mark.parametrize("bad", ["not-a-url", "/relative/path", ""])
def test_robots_url_for_rejects_unusable(bad: str) -> None:
    assert robots_url_for(bad) is None


# ---------------------------------------------------------------------------
# check_url_allowed —— 用 MockTransport，不碰网络
# ---------------------------------------------------------------------------


def _transport(robots_text: str, status: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text=robots_text, request=request)

    return httpx.MockTransport(handler)


def test_check_allows_when_robots_permits() -> None:
    ok, detail = check_url_allowed(
        "https://example.com/article", transport=_transport("User-agent: *\nDisallow: /private/\n")
    )
    assert ok is True
    assert "allowed" in detail


def test_check_blocks_when_robots_disallows() -> None:
    """正样本：robots 禁止 → 必须拦。"""
    ok, detail = check_url_allowed(
        "https://example.com/private/x",
        transport=_transport("User-agent: *\nDisallow: /private/\n"),
    )
    assert ok is False
    assert "disallowed" in detail


def test_check_includes_query_in_path() -> None:
    ok, _ = check_url_allowed(
        "https://example.com/s?q=1", transport=_transport("User-agent: *\nDisallow: /s?q=1\n")
    )
    assert ok is False


def test_check_fails_open_when_robots_unreachable() -> None:
    """RFC 9309 §2.3.1：robots.txt 取不到 ⇒ 视为无规则（放行），但要能挂日志。"""

    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("nope", request=request)

    ok, detail = check_url_allowed("https://example.com/a", transport=httpx.MockTransport(boom))
    assert ok is True
    assert "unreachable" in detail


def test_check_fails_open_on_robots_server_error_status() -> None:
    ok, detail = check_url_allowed("https://example.com/a", transport=_transport("", status=500))
    assert ok is True
    assert "unreachable" in detail


def test_check_skips_gate_for_unusable_url() -> None:
    ok, detail = check_url_allowed(
        "/relative", transport=_transport("User-agent: *\nDisallow: /\n")
    )
    assert ok is True
    assert "skipped" in detail


# ---------------------------------------------------------------------------
# #452④：按 origin 缓存
# ---------------------------------------------------------------------------


def test_cache_serves_second_check_without_new_request() -> None:
    """④ 同一 origin（scheme+netloc）只抓一次 robots.txt。

    第二次检查用**不同 path**，证明缓存键是 origin 而不是整个 URL；
    判定仍按各自 path 计算（允许 + 拦截）。
    """
    calls = 0

    def counting(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, text="User-agent: *\nDisallow: /private/\n", request=request)

    transport = httpx.MockTransport(counting)
    ok1, _ = check_url_allowed("https://cache.example.com/public", transport=transport)
    ok2, _ = check_url_allowed("https://cache.example.com/private/x", transport=transport)
    ok3, _ = check_url_allowed("https://other.example.com/public", transport=transport)

    assert ok1 is True
    assert ok2 is False  # 缓存的 robots.txt 仍按新 path 判定
    assert ok3 is True  # 不同 origin → 一次新请求
    assert calls == 2  # cache.example.com 只抓了 1 次

    _clear_robots_cache()
    ok4, _ = check_url_allowed("https://cache.example.com/public", transport=transport)
    assert ok4 is True
    assert calls == 3  # 清空缓存后重新抓


def test_cache_bypass_opt_out() -> None:
    """``use_cache=False`` / ``_clear_robots_cache()`` 是测试的绕过手段。"""
    calls = 0

    def counting(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, text="User-agent: *\nDisallow: /\n", request=request)

    transport = httpx.MockTransport(counting)
    ok1, _ = check_url_allowed("https://bypass.example.com/a", transport=transport)
    ok2, _ = check_url_allowed("https://bypass.example.com/a", transport=transport, use_cache=False)
    assert ok1 is False
    assert ok2 is False
    assert calls == 2


# ---------------------------------------------------------------------------
# #452⑤：采集器接入 —— Disallow → 抛 RobotsDisallowed，页面请求 0 次
# ---------------------------------------------------------------------------


def test_robots_disallowed_is_a_runtime_error() -> None:
    exc = RobotsDisallowed("https://x.example/a", "disallowed by test")
    assert isinstance(exc, RuntimeError)
    assert "https://x.example/a" in str(exc)
    assert exc.reason == "disallowed by test"


def test_web_fetch_raises_robots_disallowed_without_page_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⑤ web：robots 拒绝 → 抛异常，且目标页面请求为 0 次。"""
    monkeypatch.setattr(
        "autoinfo.collectors.web.check_url_allowed",
        lambda url, **kwargs: (False, "disallowed by test robots"),
    )
    page_calls = 0

    def page_get(*args: object, **kwargs: object) -> httpx.Response:
        nonlocal page_calls
        page_calls += 1
        return httpx.Response(
            200,
            text="<html><body><p>should never be fetched</p></body></html>",
            headers={"content-type": "text/html"},
        )

    monkeypatch.setattr("httpx.get", page_get)

    from autoinfo.collectors.web import WebHandler

    with pytest.raises(RobotsDisallowed) as excinfo:
        WebHandler().fetch("https://blocked.example/private/x")

    assert page_calls == 0, "robots 拒绝后不得发出任何页面请求"
    assert "https://blocked.example/private/x" in str(excinfo.value)


def test_playwright_fetch_raises_robots_disallowed_before_quick_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⑤ web_playwright：门在 quick path 之前，内部 web handler 不被调用。"""
    monkeypatch.setattr(
        "autoinfo.collectors.web_playwright.check_url_allowed",
        lambda url, **kwargs: (False, "disallowed by test robots"),
    )
    from autoinfo.collectors.web_playwright import PlaywrightWebHandler

    handler = PlaywrightWebHandler()
    web_fetch_calls = 0

    def forbidden_fetch(url: str) -> list[object]:
        nonlocal web_fetch_calls
        web_fetch_calls += 1
        return []

    monkeypatch.setattr(handler._web_handler, "fetch", forbidden_fetch)

    with pytest.raises(RobotsDisallowed):
        handler.fetch("https://blocked.example/spa")

    assert web_fetch_calls == 0, "robots 拒绝后 quick path 不得执行"


def test_pdf_fetch_raises_robots_disallowed_without_download(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⑤ pdf：robots 拒绝 → 抛异常（fetch 不吞），下载请求 0 次。"""
    monkeypatch.setattr(
        "autoinfo.collectors.pdf.check_url_allowed",
        lambda url, **kwargs: (False, "disallowed by test robots"),
    )
    download_calls = 0

    def download_get(*args: object, **kwargs: object) -> httpx.Response:
        nonlocal download_calls
        download_calls += 1
        return httpx.Response(200, content=b"%PDF-1.4", headers={"content-type": "application/pdf"})

    monkeypatch.setattr("httpx.get", download_get)

    from autoinfo.collectors.pdf import PDFHandler

    with pytest.raises(RobotsDisallowed):
        PDFHandler().fetch("https://blocked.example/doc.pdf")

    assert download_calls == 0, "robots 拒绝后不得下载 PDF"
