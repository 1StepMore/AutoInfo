"""canonical_url() — dedup-grade URL canonicalization (goal doc 2026-11-06 #1).

Every dedup comparison site (DedupChecker, G2Dedup, the F50 version-bump
lookup, the cross-date cache dedup) must compare URLs in this canonical
form, so the same article re-surfacing with tracking parameters, case or
trailing-slash variants cannot re-enter the KB as "new".
"""

from __future__ import annotations

import pytest

from autoinfo.urlnorm import canonical_url, is_tracking_param


class TestIsTrackingParam:
    def test_utm_prefix_variants(self):
        for name in ("utm_source", "UTM_Campaign", "utm_content"):
            assert is_tracking_param(name) is True

    def test_known_exact_names(self):
        for name in ("fbclid", "gclid", "igshid", "mc_cid", "_hsenc"):
            assert is_tracking_param(name) is True

    def test_semantic_params_are_kept(self):
        for name in ("id", "page", "lang", "q", "p", "category"):
            assert is_tracking_param(name) is False


class TestCanonicalUrl:
    def test_strips_tracking_params_keeps_semantic_ones(self):
        assert (
            canonical_url("https://example.com/a?utm_source=rss&id=7&fbclid=x")
            == "https://example.com/a?id=7"
        )

    def test_blank_tracking_only_query_is_dropped(self):
        assert canonical_url("https://example.com/a?utm_source=rss") == "https://example.com/a"

    def test_case_insensitive_scheme_and_host(self):
        assert canonical_url("HTTP://Example.COM/Article") == "http://example.com/Article"

    def test_trailing_slash_normalized(self):
        assert canonical_url("https://example.com/a/") == canonical_url("https://example.com/a")

    def test_root_path_keeps_its_slash(self):
        assert canonical_url("https://example.com/") == "https://example.com/"

    def test_default_ports_dropped(self):
        assert canonical_url("http://example.com:80/a") == "http://example.com/a"
        assert canonical_url("https://example.com:443/a") == "https://example.com/a"

    def test_non_default_port_kept(self):
        assert canonical_url("http://example.com:8080/a") == "http://example.com:8080/a"

    def test_fragment_dropped(self):
        assert canonical_url("https://example.com/a#section") == "https://example.com/a"

    def test_query_parameter_order_normalized(self):
        assert canonical_url("https://example.com/a?b=2&a=1") == canonical_url(
            "https://example.com/a?a=1&b=2"
        )

    def test_variant_family_collapses_to_one_form(self):
        base = "https://example.com/article/123"
        variants = [
            base,
            base + "/",
            base + "?utm_source=rss",
            base + "/?fbclid=AbCd&UTM_medium=cpc",
            "HTTPS://EXAMPLE.COM/article/123#top",
        ]
        canonical = {canonical_url(v) for v in variants}
        assert canonical == {base}

    def test_distinct_articles_stay_distinct(self):
        assert canonical_url("https://example.com/a/123") != canonical_url(
            "https://example.com/a/124"
        )

    def test_semantic_query_distinguishes_pages(self):
        assert canonical_url("https://example.com/list?page=1") != canonical_url(
            "https://example.com/list?page=2"
        )

    @pytest.mark.parametrize("raw", ["mailto:a@b.c", "ftp://host/file", "not a url", "", "   "])
    def test_non_http_and_degenerate_input_pass_through(self, raw):
        assert canonical_url(raw) == raw.strip()

    def test_whitespace_stripped(self):
        assert canonical_url("  https://example.com/a?utm_source=x  ") == "https://example.com/a"
