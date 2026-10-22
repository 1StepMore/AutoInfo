"""Single source of truth for runtime defaults (issue #587).

The same knob used to carry different values in different modules (model,
TTL, minimum content length, timeouts, runtime directories).  Every module
imports the value from here; ``tests/test_defaults_single_source.py`` keeps
the documented and runtime values aligned.
"""

from __future__ import annotations

DEFAULT_PROVIDER = "openrouter"
DEFAULT_MODEL = "deepseek/deepseek-chat"
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_LLM_TIMEOUT = DEFAULT_TIMEOUT_SECONDS
DEFAULT_TTL_DAYS = 90
MIN_KB_CONTENT_CHARS = 50
DEFAULT_EMBEDDING_MODEL = "text-embedding-ada-002"
COLLECTIONS_DIR = "collections"
