"""Tests for B23 ebook/audiobook output: EPUB, MOBI, and chaptered audiobook.

Covers :func:`autoinfo.output.ebook.render_epub` (EPUB3 round-trip, XML
well-formedness of chapter XHTML, empty-chapters guard),
:func:`autoinfo.output.ebook.render_audiobook` (chaptered MP3 + ZIP bundle
with a defensive tagging fallback), and :func:`autoinfo.output.ebook.render_mobi`
(clear RuntimeError when calibre is absent).
"""

from __future__ import annotations

import base64
import io
import shutil
import zipfile
from pathlib import Path

import pytest
from lxml import etree

from autoinfo.output.ebook import (
    render_audiobook,
    render_epub,
    render_mobi,
)

CJK_CHAPTER = (
    "第一章",
    "这是一段中文测试文本。\n\n- 要点一\n- 要点二\n\n**加粗** 和 <br/> 未闭合标签测试。",
)


@pytest.fixture(autouse=True)
def _tmp_autoinfo_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect /tmp/autoinfo scratch space into the pytest tmp dir."""
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))


def test_render_epub_roundtrip(tmp_path: Path) -> None:
    """render_epub produces a readable EPUB3 with spine, TOC, and language."""
    import ebooklib
    from ebooklib.epub import read_epub

    result = render_epub(
        title="测试书籍",
        author="AutoInfo",
        lang="zh",
        chapters=[
            ("Introduction", "# Hello\n\nWorld text."),
            CJK_CHAPTER,
        ],
    )
    assert result["format"] == "epub"
    assert result["chapters"] == 2
    assert result["title"] == "测试书籍"

    epub_path = tmp_path / "book.epub"
    epub_path.write_bytes(base64.b64decode(result["data_b64"]))

    book = read_epub(str(epub_path))
    assert len(book.spine) == 3  # nav + 2 chapters
    assert len(book.toc) == 2
    assert book.get_metadata("DC", "language")[0][0] == "zh"

    docs = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
    assert len(docs) >= 2


def test_epub_xhtml_wellformed() -> None:
    """Every chapter's XHTML parses under lxml (XML-well-formed)."""
    import ebooklib

    result = render_epub(
        title="Well-Formed",
        author="AutoInfo",
        lang="en",
        chapters=[
            ("One", "Text with **bold**, `code`, and a <br/> break."),
            (
                "Two",
                "| A | B |\n|---|----|\n| 1 | 2 |\n\n```python\nprint('hi')\n```",
            ),
            CJK_CHAPTER,
        ],
    )
    book = ebooklib.epub.read_epub(io.BytesIO(base64.b64decode(result["data_b64"])))
    docs = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
    assert len(docs) >= 3
    for item in docs:
        content = item.get_content()
        assert content  # non-empty
        etree.fromstring(content)  # must not raise


def test_render_epub_empty_chapters() -> None:
    """render_epub rejects an empty chapter list."""
    with pytest.raises(ValueError, match="zero chapters"):
        render_epub(title="Empty", author="AutoInfo", lang="en", chapters=[])


def test_render_epub_empty_chapter_body() -> None:
    """A chapter with an empty body still produces a valid EPUB.

    Regression: entries with no extractable content produced an empty XHTML
    document, and ebooklib crashed with ``lxml.etree.ParserError:
    Document is empty`` inside ``get_pages`` (caught by the
    kb-import-export validation scenario).  Empty bodies must render to a
    valid empty-paragraph fragment.
    """
    import ebooklib
    from ebooklib.epub import read_epub

    result = render_epub(
        title="Empty Body",
        author="AutoInfo",
        lang="en",
        chapters=[
            ("No Content", ""),
            ("Whitespace", "   \n\n  "),
            ("Real Content", "# Heading\n\nBody text."),
        ],
    )
    assert result["chapters"] == 3

    book = read_epub(io.BytesIO(base64.b64decode(result["data_b64"])))
    docs = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
    assert len(docs) >= 3
    for item in docs:
        content = item.get_content()
        assert content  # non-empty — never a zero-byte document
        etree.fromstring(content)  # must not raise


def test_render_audiobook_chapters(monkeypatch: pytest.MonkeyPatch) -> None:
    """render_audiobook returns a ZIP bundle + chaptered MP3 for N chapters."""
    import autoinfo.output.ebook as ebook_mod

    fake_mp3 = b"ID3\x04\x00\x00\x00\x00\x00\x00fake"
    monkeypatch.setattr(
        ebook_mod,
        "_render_audio",
        lambda text, voice="alloy", engine=None: fake_mp3,
    )

    result = render_audiobook(
        chapters=[("Chapter One", "First body"), ("第二章", "第二条正文")],
    )
    assert result["format"] == "audiobook"
    assert result["chapter_count"] == 2

    with zipfile.ZipFile(
        io.BytesIO(base64.b64decode(result["zip_b64"]))
    ) as zf:
        assert zf.namelist() == ["chapter_000.mp3", "chapter_001.mp3"]
        assert zf.read("chapter_000.mp3") == fake_mp3
        assert zf.read("chapter_001.mp3") == fake_mp3

    # Chaptered MP3 falls back to plain concatenation when tagging fails
    # (fake bytes are not parseable MPEG frames).
    assert base64.b64decode(result["data_b64"]) == fake_mp3 * 2


def test_render_audiobook_empty_chapters() -> None:
    """render_audiobook rejects an empty chapter list."""
    with pytest.raises(ValueError, match="zero chapters"):
        render_audiobook(chapters=[])


@pytest.mark.skipif(
    shutil.which("ebook-convert") is not None,
    reason="calibre installed; can't test the missing-binary path",
)
def test_render_mobi_no_calibre() -> None:
    """render_mobi raises RuntimeError with a calibre install hint."""
    epub_result = render_epub(
        title="Mobi Test",
        author="AutoInfo",
        lang="en",
        chapters=[("One", "Body")],
    )
    with pytest.raises(RuntimeError, match="calibre"):
        render_mobi(epub_result["data_b64"])
