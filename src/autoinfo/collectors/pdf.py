"""PDF document content extractor using PyMuPDF (fitz).

Extracts text content from PDF files (local paths) and PDF URLs.
Supports chunking for large documents (>10 pages) and metadata extraction.

Usage::

    handler = PDFHandler()
    items = handler.extract("/path/to/document.pdf")
    for item in items:
        print(item.title, item.content[:100])
"""

from __future__ import annotations

import hashlib
import logging
import tempfile
from pathlib import Path
from typing import Any

import httpx

from autoinfo.models import Item

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy import for PyMuPDF (optional dependency)
# ---------------------------------------------------------------------------

try:
    import fitz  # type: ignore[import-untyped]
except ImportError:
    fitz = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TIMEOUT = 30  # seconds
MAX_DOWNLOAD_SIZE = 50 * 1024 * 1024  # 50 MB
CHUNK_PAGE_SIZE = 10

# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


class PDFHandler:
    """Extract text content from PDF files and URLs.

    Parameters
    ----------
    source_name : str
        Identifier used for :attr:`Item.source_name` (default ``"pdf"``).
    """

    source_name: str

    def __init__(self, source_name: str = "pdf") -> None:
        self.source_name = source_name

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(self, url: str) -> list[Item]:
        """Download a PDF from *url* and extract its content.

        This method exists for compatibility with the ``collect.py``
        dispatch mechanism.  It delegates to :meth:`extract`.

        Parameters
        ----------
        url : str
            The PDF URL to download and extract.

        Returns
        -------
        list[Item]
            Extracted items (chunked if the PDF exceeds 10 pages).
            Returns an empty list on fetch errors.
        """
        try:
            return self.extract(url)
        except Exception as exc:
            logger.error("Failed to fetch PDF from %s: %s", url, exc)
            return []

    def extract(
        self,
        source: str | Path,
        config: dict[str, Any] | None = None,
    ) -> list[Item]:
        """Extract text content from a PDF file or URL.

        Parameters
        ----------
        source : str | Path
            Path to a PDF file, or a URL starting with ``http://``
            or ``https://``.
        config : dict | None
            Optional configuration (reserved for future extension).

        Returns
        -------
        list[Item]
            One or more :class:`Item` instances.  PDFs longer than 10
            pages are split into multiple items (one chunk per 10 pages).

        Raises
        ------
        ImportError
            If PyMuPDF is not installed.
        FileNotFoundError
            If *source* is a file path that does not exist.
        RuntimeError
            If the PDF download exceeds the maximum size limit.
        httpx.HTTPStatusError
            If the PDF URL returns an error status.
        httpx.TimeoutException
            If the PDF download times out.
        """
        self._check_deps()

        source_str = str(source)

        # -- Resolve source to a local file path ----------------------------
        if source_str.startswith(("http://", "https://")):
            local_path = self._download(source_str)
            should_cleanup = True
        else:
            local_path = Path(source_str)
            if not local_path.exists():
                raise FileNotFoundError(f"PDF file not found: {local_path}")
            should_cleanup = False

        try:
            return self._extract_from_path(local_path, source_str)
        finally:
            if should_cleanup:
                local_path.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _download(self, url: str) -> Path:
        """Download a PDF from *url* to a temporary file.

        Returns the path to the temporary file.

        Raises
        ------
        httpx.TimeoutException
            On network timeouts.
        httpx.HTTPStatusError
            On HTTP error responses.
        RuntimeError
            If the response exceeds :const:`MAX_DOWNLOAD_SIZE`.
        """
        response = httpx.get(
            url,
            timeout=DEFAULT_TIMEOUT,
            follow_redirects=True,
        )
        response.raise_for_status()

        # -- Content-Type check (advisory only) -------------------------
        content_type = (response.headers.get("content-type") or "").lower()
        if "pdf" not in content_type and "application/octet-stream" not in content_type:
            logger.warning(
                "URL %s does not appear to be a PDF (content-type: %s)",
                url,
                content_type,
            )

        # -- Size check -------------------------------------------------
        if len(response.content) > MAX_DOWNLOAD_SIZE:
            raise RuntimeError(
                f"PDF at {url} exceeds maximum download size "
                f"({len(response.content)} > {MAX_DOWNLOAD_SIZE} bytes)"
            )

        # -- Write to temp file -----------------------------------------
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        try:
            tmp.write(response.content)
        except Exception:
            tmp.close()
            Path(tmp.name).unlink(missing_ok=True)
            raise
        tmp.close()
        return Path(tmp.name)

    def _extract_from_path(self, path: Path, source_url: str) -> list[Item]:
        """Extract text from a local PDF file using PyMuPDF."""
        doc = fitz.open(path)

        try:
            metadata: dict[str, Any] = doc.metadata or {}
            pdf_title = (metadata.get("title") or "").strip() or path.stem
            author = (metadata.get("author") or "").strip()
            subject = (metadata.get("subject") or "").strip()
            keywords = (metadata.get("keywords") or "").strip()

            total_pages = doc.page_count
            item_id_base = _make_item_id(source_url)

            items: list[Item] = []
            num_chunks = max(1, (total_pages + CHUNK_PAGE_SIZE - 1) // CHUNK_PAGE_SIZE)

            for chunk_idx in range(num_chunks):
                start_page = chunk_idx * CHUNK_PAGE_SIZE
                end_page = min(start_page + CHUNK_PAGE_SIZE, total_pages)

                pages_text: list[str] = []
                for page_num in range(start_page, end_page):
                    page = doc.load_page(page_num)
                    text = page.get_text()
                    pages_text.append(text)

                content = "\n".join(pages_text).strip()

                if num_chunks > 1:
                    title = f"{pdf_title} (pages {start_page + 1}-{end_page})"
                    item_id = f"{item_id_base}-chunk{chunk_idx:03d}"
                else:
                    title = pdf_title
                    item_id = item_id_base

                items.append(
                    Item(
                        id=item_id,
                        source_name=self.source_name,
                        source_type="pdf",
                        source_url=source_url,
                        title=title,
                        content=content,
                        content_type="text",
                        raw_data={
                            "author": author,
                            "subject": subject,
                            "keywords": keywords,
                            "total_pages": total_pages,
                            "chunk_index": chunk_idx,
                            "num_chunks": num_chunks,
                            "page_start": start_page + 1,
                            "page_end": end_page,
                        },
                    )
                )

            return items

        finally:
            doc.close()

    # ------------------------------------------------------------------
    # Dependency check
    # ------------------------------------------------------------------

    @staticmethod
    def _check_deps() -> None:
        """Raise ``ImportError`` when PyMuPDF is not installed."""
        if fitz is None:
            raise ImportError(
                "PyMuPDF is required for PDF extraction. "
                "Install it with: pip install autoinfo[pdf]"
            )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _make_item_id(source: str) -> str:
    """Produce a stable item identifier from a source URL or path.

    Uses SHA-256 of the source string, truncated to 16 hex characters.
    """
    return hashlib.sha256(source.encode()).hexdigest()[:16]
