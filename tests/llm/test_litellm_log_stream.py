"""Regression lock for the closed LiteLLM log-stream guard (``llm.py``)."""

from __future__ import annotations

import logging
import tempfile

import pytest

from autoinfo.llm import LLMExtractor


def test_get_litellm_survives_closed_log_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    """``_get_litellm`` rebuilds a live handler when a bound stream is closed.

    Before the fix, ``StreamHandler.setStream(sys.stderr)`` flushed the OLD
    (already closed) stream first and raised ``ValueError: I/O operation on
    closed file``, which propagated out of ``_get_litellm`` and aborted every
    LLM call.  The fix drops the dead handler and installs a live one.

    The closed stream is a real closed file, mirroring pytest's closed capture
    stream from the original traceback: on Python 3.14 a closed ``StringIO``
    flushes as a no-op, so it cannot reproduce the ``ValueError``.
    """
    monkeypatch.setenv("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    litellm_logger = logging.getLogger("LiteLLM")
    original_handlers = list(litellm_logger.handlers)
    original_propagate = litellm_logger.propagate

    closed_stream = tempfile.TemporaryFile("w+")
    dead_handler = logging.StreamHandler(closed_stream)
    closed_stream.close()
    litellm_logger.addHandler(dead_handler)
    try:
        module = LLMExtractor._get_litellm()

        assert module is not None
        assert dead_handler not in litellm_logger.handlers
        assert any(
            isinstance(handler, logging.StreamHandler)
            and not getattr(handler.stream, "closed", False)
            for handler in litellm_logger.handlers
        )
    finally:
        for handler in list(litellm_logger.handlers):
            if handler not in original_handlers:
                litellm_logger.removeHandler(handler)
                handler.close()
        for handler in original_handlers:
            if handler not in litellm_logger.handlers:
                litellm_logger.addHandler(handler)
        litellm_logger.propagate = original_propagate
