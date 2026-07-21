"""Embedding utilities — sqlite-vec integration + LLM embedding generation.

Provides vector storage and similarity search backed by sqlite-vec, with
graceful degradation when the extension or its dependencies are unavailable.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level availability flag
# ---------------------------------------------------------------------------

try:
    import sqlite_vec  # noqa: F401 — keep reference for load() / serialize_float32

    _sqlite_vec_available = True
except (ImportError, ModuleNotFoundError):
    _sqlite_vec_available = False

is_available: bool = _sqlite_vec_available and sqlite3.sqlite_version_info >= (3, 41)
"""``True`` if sqlite-vec is installed **and** the runtime SQLite version ≥ 3.41."""

# ---------------------------------------------------------------------------
# SearchResult
# ---------------------------------------------------------------------------


@dataclass
class SearchResult:
    """A single vector-search hit."""

    entry_id: str
    """KB entry identifier (matches ``entries.entry_id``)."""

    score: float
    """Similarity score in ``[0, 1]`` (1 = identical)."""

    method: str = "vector"
    """Search method that produced this result (``"vector"``)."""


# ---------------------------------------------------------------------------
# Extension loading
# ---------------------------------------------------------------------------


def load_vec_extension(conn: sqlite3.Connection) -> bool:
    """Load the sqlite-vec extension into *conn*.

    Enables extension loading on the connection, then calls
    ``sqlite_vec.load(conn)``.  Returns ``True`` on success.

    On failure (missing package, old SQLite, or runtime error) a warning
    is logged and ``False`` is returned.
    """
    if not _sqlite_vec_available:
        logger.warning(
            "sqlite-vec package is not installed — vector features disabled"
        )
        return False

    if sqlite3.sqlite_version_info < (3, 41):
        logger.warning(
            "SQLite version %d.%d.%d < 3.41 — sqlite-vec not supported",
            *sqlite3.sqlite_version_info,
        )
        return False

    try:
        import sqlite_vec as _sv

        conn.enable_load_extension(True)
        _sv.load(conn)
        return True
    except Exception as exc:
        logger.warning("Failed to load sqlite-vec extension: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Table management
# ---------------------------------------------------------------------------

_EMBEDDING_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS entry_embeddings (
    entry_id    TEXT PRIMARY KEY,
    embedding   BLOB NOT NULL,
    model       TEXT NOT NULL,
    created_at  TEXT DEFAULT (datetime('now'))
);
"""


def ensure_embedding_table(conn: sqlite3.Connection) -> None:
    """Create the ``entry_embeddings`` table if it does not exist."""
    conn.execute(_EMBEDDING_TABLE_DDL)


# ---------------------------------------------------------------------------
# Embedding generation
# ---------------------------------------------------------------------------

_EMBEDDING_DIM = 1536
"""Default embedding dimension returned by the fallback zero-vector."""


def generate_embedding(
    text: str,
    model_config: dict[str, Any] | None = None,
) -> list[float]:
    """Generate an embedding vector for *text* via LiteLLM.

    Parameters
    ----------
    text:
        Input text to embed.
    model_config:
        Optional configuration dict.  If present, ``model_config.get("model")``
        overrides the default model name (``text-embedding-ada-002``).

    Returns
    -------
    list[float]
        Embedding vector (dimension 1536 by convention).  Returns a zero-vector
        when the LLM embedding API is unreachable or raises an error (a warning
        is logged in that case).
    """
    if not text or not text.strip():
        logger.warning("generate_embedding called with empty text — returning zero-vector")
        return [0.0] * _EMBEDDING_DIM

    model = "text-embedding-ada-002"
    if model_config and isinstance(model_config, dict):
        model = model_config.get("model", model)

    try:
        import litellm  # noqa: PLC0415 — deferred import

        response = litellm.embedding(model=model, input=[text])  # type: ignore
        embedding: list[float] = response.data[0]["embedding"]
        return embedding
    except Exception as exc:
        logger.warning(
            "LLM embedding failed (model=%s): %s — returning zero-vector",
            model,
            exc,
        )
        return [0.0] * _EMBEDDING_DIM


# ---------------------------------------------------------------------------
# Cosine similarity
# ---------------------------------------------------------------------------


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute the cosine similarity between two vectors.

    Uses NumPy when available for performance; falls back to pure Python
    otherwise.

    Returns a float in ``[-1.0, 1.0]`` (1.0 = identical direction).
    Returns ``0.0`` for degenerate (zero-norm) or mismatched-length inputs.
    """
    if not a or not b or len(a) != len(b):
        return 0.0

    try:
        # Fast path — NumPy
        import numpy as np  # type: ignore  # noqa: PLC0415

        aa = np.array(a, dtype=np.float64)
        bb = np.array(b, dtype=np.float64)
        dot = float(np.dot(aa, bb))
        norm_a = float(np.linalg.norm(aa))
        norm_b = float(np.linalg.norm(bb))
    except ImportError:
        # Pure Python fallback
        dot = sum(x * y for x, y in zip(a, b, strict=True))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def store_embedding(
    conn: sqlite3.Connection,
    entry_id: str,
    embedding: list[float],
    model: str,
) -> None:
    """Insert or replace an embedding row in ``entry_embeddings``.

    The embedding is serialised with ``sqlite_vec.serialize_float32`` when
    the package is available; otherwise a JSON-encoded blob is stored as a
    fallback (though such entries will not be searchable via
    :func:`search_embeddings`).
    """
    if _sqlite_vec_available:
        try:
            import sqlite_vec as _sv

            blob = _sv.serialize_float32(embedding)
        except Exception:
            blob = json.dumps(embedding).encode("utf-8")
    else:
        blob = json.dumps(embedding).encode("utf-8")

    conn.execute(
        "INSERT OR REPLACE INTO entry_embeddings (entry_id, embedding, model, created_at) "
        "VALUES (?, ?, ?, datetime('now'))",
        (entry_id, blob, model),
    )


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def search_embeddings(
    conn: sqlite3.Connection,
    query_embedding: list[float],
    limit: int = 10,
) -> list[SearchResult]:
    """Search ``entry_embeddings`` by cosine distance via sqlite-vec.

    Uses the ``vec_distance_cosine`` SQL function registered by sqlite-vec
    for efficient KNN search.

    Returns
    -------
    list[SearchResult]
        Up to *limit* results ordered by similarity (closest first).  Each
        result carries a ``score`` in ``[0, 1]`` (1 = identical).

        Returns an empty list when vector search is unavailable (``is_available``
        is ``False``) or when the query fails.
    """
    if not is_available:
        logger.warning("search_embeddings: vector search unavailable (sqlite-vec not loaded)")
        return []

    try:
        import sqlite_vec as _sv

        blob = _sv.serialize_float32(query_embedding)
    except Exception as exc:
        logger.warning("search_embeddings: failed to serialise query embedding: %s", exc)
        return []

    try:
        rows = conn.execute(
            "SELECT entry_id, vec_distance_cosine(embedding, ?) AS distance "
            "FROM entry_embeddings "
            "ORDER BY distance "
            "LIMIT ?",
            (blob, limit),
        ).fetchall()
    except Exception as exc:
        logger.warning("search_embeddings: query failed: %s", exc)
        return []

    results: list[SearchResult] = []
    for row in rows:
        if isinstance(row, sqlite3.Row):
            entry_id = row["entry_id"]
            distance = row["distance"]
        else:
            entry_id = row[0]
            distance = row[1]
        # vec_distance_cosine returns NULL for degenerate (zero-norm) vectors
        if distance is None:
            continue
        score = max(0.0, 1.0 - float(distance))
        results.append(SearchResult(entry_id=entry_id, score=score, method="vector"))

    return results
