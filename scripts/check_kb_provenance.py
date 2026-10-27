"""T19 check (a): every 01-Raw entry's source_url must trace to a collected item.

Reads ``autoinfo.db`` and the ``collections/`` cache; exits 1 on an unmatched
URL. Query-string variants of a collected URL are counted as drift, not as a
match, because the KB copy is what a reader is shown.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from urllib.parse import urlsplit

DOMAINS = ("medical-research", "language-learning", "ai-commercial")


def _bare(url: str) -> str:
    """Scheme+host+path of *url*, dropping query and fragment."""
    parts = urlsplit(url or "")
    return f"{parts.scheme}://{parts.netloc}{parts.path}"


def _collected_urls(root: Path) -> set[str]:
    urls: set[str] = set()
    for path in root.rglob("*.json"):
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("source_url"):
            urls.add(str(data["source_url"]).strip())
    return urls


def main() -> int:
    urls = _collected_urls(Path("collections"))
    bare = {_bare(u) for u in urls}
    conn = sqlite3.connect("autoinfo.db")
    rows = list(
        conn.execute(
            "select domain, source_url from entries where deleted=0 and tier='01-Raw'"
            f" and domain in ({','.join('?' * len(DOMAINS))})",
            DOMAINS,
        )
    )
    exact = [r for r in rows if (r[1] or "").strip() in urls]
    missing = [r for r in rows if (r[1] or "").strip() not in urls]
    drift = [r for r in missing if _bare(r[1]) in bare]
    unmatched = [r for r in missing if r not in drift]
    print(
        f"raw entries: {len(rows)}  exact: {len(exact)}"
        f"  query-string drift: {len(drift)}  unmatched: {len(unmatched)}"
    )
    for domain, url in unmatched:
        print(f"  UNMATCHED {domain} {url}")
    return 1 if unmatched else 0


if __name__ == "__main__":
    sys.exit(main())
