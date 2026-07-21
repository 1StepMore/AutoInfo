"""Tests for PDF document extractor (PDFHandler).

Uses mocked PyMuPDF (fitz) and httpx to test extraction logic
without requiring actual PDF files or network access.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from autoinfo.collectors.pdf import PDFHandler
from autoinfo.models import Item


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_mock_doc(
    page_count: int = 5,
    metadata: dict | None = None,
    pages_text: list[str] | None = None,
) -> MagicMock:
    """Build a mock fitz Document with the given properties.

    Parameters
    ----------
    page_count : int
        Number of pages in the mock document.
    metadata : dict | None
        PDF metadata dict (title, author, subject, keywords).
    pages_text : list[str] | None
        Text content for each page.  If shorter than *page_count*,
        remaining pages default to ``"Page N content"``.

    Returns
    -------
    MagicMock
        A mock Document with ``metadata``, ``page_count``,
        ``load_page`` (mapped by index), and ``close``.
    """
    md = metadata or {}
    pages_text = pages_text or []

    pages = []
    for i in range(page_count):
        page_mock = MagicMock()
        text = pages_text[i] if i < len(pages_text) else f"Page {i + 1} content"
        page_mock.get_text.return_value = text
        pages.append(page_mock)

    doc = MagicMock()
    doc.metadata = md
    doc.page_count = page_count
    doc.load_page.side_effect = lambda i: pages[i]
    doc.close = MagicMock()
    return doc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def handler() -> PDFHandler:
    """Return a default PDFHandler instance."""
    return PDFHandler()


# ---------------------------------------------------------------------------
# Text extraction from file
# ---------------------------------------------------------------------------


class TestExtractFromFile:
    """Test text extraction from a local PDF file via ``extract()``."""

    def test_extract_returns_items(
        self, handler: PDFHandler, tmp_path: Path
    ) -> None:
        """Extracting a valid PDF should return Item instances."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_text("")  # Create file so exists() passes

        mock_doc = _build_mock_doc(page_count=3)
        with patch("autoinfo.collectors.pdf.fitz.open", return_value=mock_doc):
            items = handler.extract(pdf_path)

        assert len(items) == 1
        assert isinstance(items[0], Item)

    def test_small_pdf_single_item(
        self, handler: PDFHandler, tmp_path: Path
    ) -> None:
        """PDF with ≤10 pages produces a single Item."""
        pdf_path = tmp_path / "small.pdf"
        pdf_path.write_text("")

        mock_doc = _build_mock_doc(page_count=10)
        with patch("autoinfo.collectors.pdf.fitz.open", return_value=mock_doc):
            items = handler.extract(pdf_path)

        assert len(items) == 1

    def test_large_pdf_multiple_chunks(
        self, handler: PDFHandler, tmp_path: Path
    ) -> None:
        """PDF with >10 pages produces multiple items (10 pages per chunk)."""
        pdf_path = tmp_path / "large.pdf"
        pdf_path.write_text("")

        mock_doc = _build_mock_doc(page_count=25)
        with patch("autoinfo.collectors.pdf.fitz.open", return_value=mock_doc):
            items = handler.extract(pdf_path)

        # 25 pages → 3 chunks (10 + 10 + 5)
        assert len(items) == 3

        # Each chunk title should include the page range
        assert "(pages 1-10)" in items[0].title
        assert "(pages 11-20)" in items[1].title
        assert "(pages 21-25)" in items[2].title

    def test_content_from_all_pages(
        self, handler: PDFHandler, tmp_path: Path
    ) -> None:
        """Item content should join text from all pages."""
        pdf_path = tmp_path / "content.pdf"
        pdf_path.write_text("")

        page_texts = ["Alpha ", "Beta ", "Gamma "]
        mock_doc = _build_mock_doc(page_count=3, pages_text=page_texts)
        with patch("autoinfo.collectors.pdf.fitz.open", return_value=mock_doc):
            items = handler.extract(pdf_path)

        assert len(items) == 1
        assert "Alpha" in items[0].content
        assert "Beta" in items[0].content
        assert "Gamma" in items[0].content

    def test_source_name_propagates(
        self, handler: PDFHandler, tmp_path: Path
    ) -> None:
        """Item.source_name should reflect the handler's source_name."""
        pdf_path = tmp_path / "custom.pdf"
        pdf_path.write_text("")

        custom_handler = PDFHandler(source_name="my-pdf-source")
        mock_doc = _build_mock_doc(page_count=1)
        with patch("autoinfo.collectors.pdf.fitz.open", return_value=mock_doc):
            items = custom_handler.extract(pdf_path)

        assert len(items) == 1
        assert items[0].source_name == "my-pdf-source"

    def test_file_not_found(self, handler: PDFHandler) -> None:
        """Non-existent file path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            handler.extract("/nonexistent/path/to.pdf")

    def test_import_error_when_fitz_missing(
        self, handler: PDFHandler, tmp_path: Path
    ) -> None:
        """When PyMuPDF is not installed, extract() raises ImportError."""
        pdf_path = tmp_path / "nofitz.pdf"
        pdf_path.write_text("")

        with patch(
            "autoinfo.collectors.pdf.fitz",
            None,
        ), patch.object(PDFHandler, "_check_deps", side_effect=ImportError(
            "PyMuPDF is required for PDF extraction. "
            "Install it with: pip install autoinfo[pdf]"
        )):
            with pytest.raises(ImportError, match="PyMuPDF is required"):
                handler.extract(pdf_path)


# ---------------------------------------------------------------------------
# Metadata parsing
# ---------------------------------------------------------------------------


class TestMetadataParsing:
    """Test PDF metadata is correctly mapped to Item fields."""

    def test_title_from_metadata(
        self, handler: PDFHandler, tmp_path: Path
    ) -> None:
        """Item.title comes from PDF metadata title."""
        pdf_path = tmp_path / "report.pdf"
        pdf_path.write_text("")

        metadata = {
            "title": "Annual Report 2026",
            "author": "Finance Team",
            "subject": "Financial Results",
            "keywords": "finance, annual, 2026",
        }
        mock_doc = _build_mock_doc(page_count=3, metadata=metadata)
        with patch("autoinfo.collectors.pdf.fitz.open", return_value=mock_doc):
            items = handler.extract(pdf_path)

        assert len(items) == 1
        assert items[0].title == "Annual Report 2026"

    def test_title_fallback_to_filename(
        self, handler: PDFHandler, tmp_path: Path
    ) -> None:
        """When PDF has no title metadata, use the filename (without suffix)."""
        pdf_path = tmp_path / "quarterly_report.pdf"
        pdf_path.write_text("")

        mock_doc = _build_mock_doc(page_count=1, metadata={})
        with patch("autoinfo.collectors.pdf.fitz.open", return_value=mock_doc):
            items = handler.extract(pdf_path)

        assert len(items) == 1
        assert items[0].title == "quarterly_report"

    def test_author_and_subject_in_raw_data(
        self, handler: PDFHandler, tmp_path: Path
    ) -> None:
        """Author, subject, and keywords should be in Item.raw_data."""
        pdf_path = tmp_path / "paper.pdf"
        pdf_path.write_text("")

        metadata = {
            "title": "Research Paper",
            "author": "Dr. Smith",
            "subject": "Machine Learning",
            "keywords": "ML, AI",
        }
        mock_doc = _build_mock_doc(page_count=2, metadata=metadata)
        with patch("autoinfo.collectors.pdf.fitz.open", return_value=mock_doc):
            items = handler.extract(pdf_path)

        assert len(items) == 1
        assert items[0].raw_data["author"] == "Dr. Smith"
        assert items[0].raw_data["subject"] == "Machine Learning"
        assert items[0].raw_data["keywords"] == "ML, AI"

    def test_raw_data_has_page_info(
        self, handler: PDFHandler, tmp_path: Path
    ) -> None:
        """Item.raw_data should include page count and chunk boundaries."""
        pdf_path = tmp_path / "multi.pdf"
        pdf_path.write_text("")

        mock_doc = _build_mock_doc(page_count=22)
        with patch("autoinfo.collectors.pdf.fitz.open", return_value=mock_doc):
            items = handler.extract(pdf_path)

        assert len(items) == 3
        assert items[0].raw_data["total_pages"] == 22
        assert items[0].raw_data["num_chunks"] == 3
        assert items[0].raw_data["page_start"] == 1
        assert items[0].raw_data["page_end"] == 10
        assert items[1].raw_data["page_start"] == 11
        assert items[1].raw_data["page_end"] == 20
        assert items[2].raw_data["page_start"] == 21
        assert items[2].raw_data["page_end"] == 22


# ---------------------------------------------------------------------------
# URL download + extract
# ---------------------------------------------------------------------------


class TestUrlDownloadAndParse:
    """Test URL download + extraction flow via ``extract()`` and ``fetch()``."""

    PDF_URL = "https://example.com/doc.pdf"

    def test_url_download_and_extract(
        self, handler: PDFHandler
    ) -> None:
        """PDF URL is downloaded, saved to temp file, then extracted."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.content = b"%PDF-1.4 mock pdf content"
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.raise_for_status = MagicMock()

        mock_doc = _build_mock_doc(
            page_count=1,
            metadata={"title": "Downloaded PDF"},
        )

        with (
            patch("httpx.get", return_value=mock_response),
            patch("autoinfo.collectors.pdf.fitz.open", return_value=mock_doc) as mock_fitz_open,
        ):
            items = handler.extract(self.PDF_URL)

        assert len(items) == 1
        assert items[0].title == "Downloaded PDF"
        assert items[0].source_url == self.PDF_URL
        assert items[0].source_type == "pdf"

        # fitz.open was called with a temp file path
        call_arg = mock_fitz_open.call_args[0][0]
        assert isinstance(call_arg, Path)
        assert call_arg.suffix == ".pdf"

    def test_fetch_method(
        self, handler: PDFHandler
    ) -> None:
        """``fetch()`` delegates to extract and returns items."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.content = b"%PDF-1.4 mock"
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.raise_for_status = MagicMock()

        mock_doc = _build_mock_doc(page_count=2, metadata={"title": "Fetched"})

        with (
            patch("httpx.get", return_value=mock_response),
            patch("autoinfo.collectors.pdf.fitz.open", return_value=mock_doc),
        ):
            items = handler.fetch(self.PDF_URL)

        assert len(items) == 1
        assert items[0].title == "Fetched"

    def test_fetch_returns_empty_on_error(
        self, handler: PDFHandler
    ) -> None:
        """When downloading fails, fetch() returns [] instead of raising."""
        with patch(
            "httpx.get",
            side_effect=httpx.TimeoutException("Timeout", request=None),
        ):
            items = handler.fetch(self.PDF_URL)

        assert items == []

    def test_download_size_limit(
        self, handler: PDFHandler
    ) -> None:
        """PDF exceeding 50MB raises RuntimeError."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.content = b"x" * (51 * 1024 * 1024)  # 51 MB
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.raise_for_status = MagicMock()

        with (
            patch("httpx.get", return_value=mock_response),
            pytest.raises(RuntimeError, match="exceeds maximum download size"),
        ):
            handler.extract(self.PDF_URL)
