"""Issue #849: the hermetic LLM gate blocks real network calls in non-real_api tests."""

from __future__ import annotations

import pytest

from autoinfo.llm import call_with_fallback


def test_gate_blocks_real_llm_call_in_plain_test() -> None:
    """A plain (non-real_api) test cannot reach litellm — it fails loudly.

    With a key in the environment this used to walk into the real network
    path and hang on dead endpoints (the Windows full-suite hang); the gate
    turns that into an immediate, identifiable error instead.
    """
    with pytest.raises(RuntimeError, match="hermetic gate"):
        call_with_fallback(messages=[{"role": "user", "content": "hi"}])
