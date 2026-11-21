"""Speech cleaning before TTS — bare URLs must never be read aloud (issue #900)."""

from __future__ import annotations

import pytest

from autoinfo.output.audio import (
    SPOKEN_SOURCE_REPLACEMENT,
    _render_audio,
    _strip_for_speech,
    _strip_markdown,
    audit_speech_text,
)


def _clean(text: str) -> str:
    """Run the production order: markdown first, then speech cleaning."""
    return _strip_for_speech(_strip_markdown(text))


def test_bare_url_is_replaced_and_not_spoken() -> None:
    text = "Investment players source: https://techcrunch.com/2026/11/12/five-waze-x"
    out = _clean(text)
    assert "https" not in out.lower()
    assert ".com" not in out.lower()
    assert "techcrunch" not in out.lower()
    assert SPOKEN_SOURCE_REPLACEMENT in out
    assert audit_speech_text(out)["spoken_url_tokens"] == 0


def test_query_string_does_not_survive_cleaning() -> None:
    text = (
        "数据库检索 source https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        "?db=pubmed&id=43031895&retmode=xml"
    )
    out = _clean(text)
    assert "fcgi" not in out
    assert "pubmed" not in out
    assert "retmode" not in out
    assert audit_speech_text(out)["spoken_url_tokens"] == 0


def test_markdown_link_keeps_its_text_only() -> None:
    assert _strip_for_speech("See [the report](https://example.com/a/b) for details.") == (
        "See the report for details."
    )


def test_plain_chinese_text_is_untouched() -> None:
    text = "这是一段完全正常的中文正文，没有任何链接。"
    out = _clean(text)
    assert out == text
    assert audit_speech_text(out)["spoken_url_tokens"] == 0


def test_mixed_chinese_and_english_keeps_words_but_drops_address() -> None:
    text = "研究显示一定有效，详见 https://pubmed.ncbi.nlm.nih.gov/43031895/ 。"
    out = _clean(text)
    assert "研究显示一定有效" in out
    assert "pubmed" not in out
    assert "一定" in out  # ordinary words are never touched
    assert audit_speech_text(out)["spoken_url_tokens"] == 0


def test_multiple_urls_are_each_replaced() -> None:
    text = (
        "First https://a.example.com/x then www.b.org/y and finally "
        "https://c.gov/z?q=1&k=2"
    )
    out = _clean(text)
    assert out.count(SPOKEN_SOURCE_REPLACEMENT) == 3
    assert audit_speech_text(out)["spoken_url_tokens"] == 0


def test_domain_without_scheme_is_replaced() -> None:
    out = _clean("TechCrunch.com reported the launch.")
    assert "TechCrunch" not in out
    assert ".com" not in out.lower()
    assert out.startswith(SPOKEN_SOURCE_REPLACEMENT)


def test_whitespace_and_punctuation_are_tidied_after_removal() -> None:
    out = _clean("来源 A 、 、，B。。C")
    assert out == "来源 A、B。C"
    assert "  " not in out


def test_audit_shape_and_sample_head() -> None:
    audit = audit_speech_text("hello world")
    assert audit == {
        "spoken_url_tokens": 0,
        "text_chars": 11,
        "sample_head": "hello world",
    }
    assert len(audit_speech_text("x" * 500)["sample_head"]) == 200


def test_render_audio_fills_the_audit_sink(monkeypatch: pytest.MonkeyPatch) -> None:
    """The spoken text recorded by the audit is the text handed to the engine."""
    captured: dict[str, str] = {}

    def fake_edge_tts(text: str, voice: str = "", timeout: float = 120.0) -> bytes:
        captured["text"] = text
        return b"ID3" + b"\x00" * 16

    monkeypatch.setattr("autoinfo.output.audio._render_audio_edge_tts", fake_edge_tts)
    sink: dict[str, object] = {}

    mp3 = _render_audio(
        "Read https://example.com/a/b now", engine="local", audit_out=sink
    )

    assert mp3.startswith(b"ID3")
    assert "example.com" not in captured["text"]
    assert sink["spoken_url_tokens"] == 0
    assert sink["sample_head"] == captured["text"][:200]
